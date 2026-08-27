"""
监控目录测试 - 完全隔离测试环境，禁用定时器和 watcher
"""

import pytest
import os
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from PySide6.QtCore import Qt, QTimer
from ui.views.segment_view import SegmentView
from src.config_manager import ConfigManager

pytestmark = pytest.mark.ui


@pytest.fixture(autouse=True)
def isolate_db_and_home(monkeypatch):
    """每个测试使用独立的临时目录作为 HOME，隔离数据库和配置"""
    temp_home = tempfile.mkdtemp(prefix="coverpicker_test_home_")
    def mock_home():
        return Path(temp_home)
    monkeypatch.setattr(Path, "home", mock_home)
    def mock_expanduser(path):
        if path.startswith("~"):
            return path.replace("~", temp_home)
        return path
    monkeypatch.setattr(os.path, "expanduser", mock_expanduser)
    yield temp_home
    shutil.rmtree(temp_home, ignore_errors=True)


@pytest.fixture(autouse=True)
def mock_timer_single_shot(monkeypatch):
    """阻止 QTimer.singleShot 在 teardown 阶段执行回调"""
    def patched_single_shot(msec, callback, *args, **kwargs):
        pass
    monkeypatch.setattr(QTimer, "singleShot", patched_single_shot)


@pytest.fixture(autouse=True)
def mock_ffmpeg_duration(monkeypatch):
    """模拟 get_video_duration 避免真实 FFprobe 调用"""
    import src.video_scanner as vs
    monkeypatch.setattr(vs, "get_video_duration", lambda path: 120.0)
    monkeypatch.setattr(vs, "get_video_resolution", lambda path: "1920x1080")


@pytest.fixture
def temp_video_dir():
    """创建临时目录，包含一个测试视频"""
    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, "test1.mp4")
        Path(video_path).touch()
        text_path = os.path.join(tmpdir, "readme.txt")
        Path(text_path).touch()
        yield tmpdir


@pytest.fixture
def mock_scan_videos():
    """模拟 scan_videos 函数，返回指定目录中的视频文件"""
    def _mock_scan(directory):
        video_exts = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm')
        result = []
        for root, dirs, files in os.walk(directory):
            for f in files:
                if f.lower().endswith(video_exts):
                    result.append(os.path.join(root, f))
        return result
    return _mock_scan


def disable_timers_and_watcher(view):
    """停止所有定时器并断开 watcher，防止外部事件干扰测试"""
    view.scan_timer.stop()
    view._watch_debounce_timer.stop()
    try:
        view.watcher.directoryChanged.disconnect()
    except:
        pass


def test_setup_watch_dirs(qtbot, temp_video_dir):
    """测试添加监控目录后，watcher 包含该目录"""
    config = ConfigManager()
    config.set_watch_dirs([temp_video_dir])

    view = SegmentView()
    disable_timers_and_watcher(view)
    qtbot.addWidget(view)

    assert temp_video_dir in view.watcher.directories()


def test_scan_all_watch_dirs_add(qtbot, temp_video_dir, mock_scan_videos):
    """测试扫描到新视频时，自动添加到列表"""
    config = ConfigManager()
    config.set_watch_dirs([temp_video_dir])

    with patch('ui.views.segment_view.scan_videos') as mock_scan:
        mock_scan.side_effect = mock_scan_videos

        view = SegmentView()
        disable_timers_and_watcher(view)
        qtbot.addWidget(view)

        view._scan_all_watch_dirs()
        assert len(view.all_videos) == 1
        assert any("test1.mp4" in v for v in view.all_videos)

        new_video = os.path.join(temp_video_dir, "test2.mp4")
        Path(new_video).touch()

        view._scan_all_watch_dirs()
        assert len(view.all_videos) == 2
        assert any("test2.mp4" in v for v in view.all_videos)


def test_scan_all_watch_dirs_remove(qtbot, temp_video_dir, mock_scan_videos):
    """测试删除视频时，自动从列表移除"""
    config = ConfigManager()
    config.set_watch_dirs([temp_video_dir])

    with patch('ui.views.segment_view.scan_videos') as mock_scan:
        mock_scan.side_effect = mock_scan_videos

        view = SegmentView()
        disable_timers_and_watcher(view)
        qtbot.addWidget(view)

        view._scan_all_watch_dirs()
        assert len(view.all_videos) == 1

        os.remove(os.path.join(temp_video_dir, "test1.mp4"))
        view._scan_all_watch_dirs()
        assert len(view.all_videos) == 0


@pytest.mark.asyncio
async def test_scan_add_only_with_loading(qtbot, temp_video_dir, mock_scan_videos):
    """测试有加载任务时，仅新增不删除"""
    config = ConfigManager()
    config.set_watch_dirs([temp_video_dir])

    with patch('ui.views.segment_view.scan_videos') as mock_scan:
        mock_scan.side_effect = mock_scan_videos

        view = SegmentView()
        disable_timers_and_watcher(view)
        qtbot.addWidget(view)

        view._scan_all_watch_dirs()
        assert len(view.all_videos) == 1

        async def dummy_load():
            await asyncio.sleep(0.1)
        view.controller._load_task = asyncio.create_task(dummy_load())

        os.remove(os.path.join(temp_video_dir, "test1.mp4"))
        new_video = os.path.join(temp_video_dir, "test2.mp4")
        Path(new_video).touch()

        view._scan_all_watch_dirs()

        assert len(view._pending_deletions) == 1
        assert any("test1.mp4" in p for p in view._pending_deletions)
        assert len(view.all_videos) == 2

        with patch.object(view.controller, 'remove_video', return_value=True) as mock_remove:
            await asyncio.sleep(0.2)
            view._process_pending_deletions()
            mock_remove.assert_called_once()

        assert len(view.all_videos) == 1
        assert any("test2.mp4" in v for v in view.all_videos)


def test_process_pending_deletions(qtbot, temp_video_dir, mock_scan_videos):
    """测试延迟删除执行"""
    config = ConfigManager()
    config.set_watch_dirs([temp_video_dir])

    with patch('ui.views.segment_view.scan_videos') as mock_scan:
        mock_scan.side_effect = mock_scan_videos

        view = SegmentView()
        disable_timers_and_watcher(view)
        qtbot.addWidget(view)

        view._scan_all_watch_dirs()
        assert len(view.all_videos) == 1

        deleted_file = os.path.join(temp_video_dir, "test1.mp4")
        view._pending_deletions = [deleted_file]
        view._pending_deletion_scan = True

        with patch.object(view.controller, 'remove_video', return_value=True) as mock_remove:
            view._process_pending_deletions()
            mock_remove.assert_called_once()

        assert len(view.all_videos) == 0
        assert view._pending_deletions == []
        assert view._pending_deletion_scan is False


def test_watch_debounce(qtbot, temp_video_dir):
    """测试监控目录防抖机制"""
    config = ConfigManager()
    config.set_watch_dirs([temp_video_dir])

    with patch('ui.views.segment_view.scan_videos') as mock_scan:
        mock_scan.return_value = []

        view = SegmentView()
        disable_timers_and_watcher(view)
        qtbot.addWidget(view)

        view._on_directory_changed(temp_video_dir)
        assert view._watch_debounce_timer.isActive() is True

        view._on_directory_changed(temp_video_dir)
        view._on_directory_changed(temp_video_dir)
        assert view._watch_debounce_timer.isActive() is True

        view._watch_debounce_timer.stop()
        assert view._watch_debounce_timer.isActive() is False