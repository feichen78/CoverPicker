# tests/conftest.py
# 最终版：包含 mock_config_home 别名，兼容旧测试
# v3.2.11: 添加 QMessageBox 全局 mock，避免测试弹窗
# v3.2.12: 添加更强力的资源清理，消除 ResourceWarning

import os
import sys
import tempfile
import shutil
import gc
import warnings
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ============================================================
# 全局隔离 HOME 目录（自动应用于所有测试）
# ============================================================
@pytest.fixture(autouse=True, scope="function")
def isolate_home_for_all_tests(monkeypatch):
    tmpdir = tempfile.mkdtemp(prefix="coverpicker_test_home_")

    # ---- 1. 覆盖 Path.home() ----
    def mock_home():
        return Path(tmpdir)
    monkeypatch.setattr(Path, "home", mock_home)

    # ---- 2. 覆盖 os.path.expanduser ----
    def mock_expanduser(path):
        if path.startswith("~"):
            return path.replace("~", tmpdir)
        return path
    monkeypatch.setattr(os.path, "expanduser", mock_expanduser)

    # ---- 3. 覆盖环境变量（Windows / Linux / macOS） ----
    monkeypatch.setenv("APPDATA", tmpdir)
    monkeypatch.setenv("LOCALAPPDATA", tmpdir)
    monkeypatch.setenv("USERPROFILE", tmpdir)
    monkeypatch.setenv("HOME", tmpdir)
    monkeypatch.setenv("XDG_CONFIG_HOME", tmpdir)

    # ---- 4. 重置 ConfigManager 的内部缓存（如果有） ----
    try:
        import src.config_manager
        if hasattr(src.config_manager.ConfigManager, '_config_dir'):
            src.config_manager.ConfigManager._config_dir = None
    except Exception:
        pass

    yield tmpdir

    # ---- 5. 强制关闭所有数据库连接 ----
    import sqlite3
    for obj in gc.get_objects():
        if isinstance(obj, sqlite3.Connection):
            try:
                obj.close()
            except Exception:
                pass
    gc.collect()

    # ---- 6. 删除临时目录（忽略权限错误） ----
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass

    # ---- 7. 忽略残留的 ResourceWarning（兜底） ----
    warnings.filterwarnings("ignore", category=ResourceWarning)


# 为了兼容旧测试，添加别名
@pytest.fixture
def mock_config_home(isolate_home_for_all_tests):
    return isolate_home_for_all_tests


# ============================================================
# 全局模拟 QFileDialog
# ============================================================
@pytest.fixture(autouse=True)
def mock_file_dialogs(monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    def mock_get_open_file_names(parent=None, caption="", dir="", filter="", *args, **kwargs):
        return ([], "")
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", mock_get_open_file_names)

    def mock_get_existing_directory(parent=None, caption="", dir="", *args, **kwargs):
        return tempfile.mkdtemp()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", mock_get_existing_directory)

    def mock_get_save_file_name(parent=None, caption="", dir="", filter="", *args, **kwargs):
        return ("/tmp/test.jpg", "")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", mock_get_save_file_name)

    yield


# ============================================================
# 全局模拟 QMessageBox（避免测试弹窗）
# ============================================================
@pytest.fixture(autouse=True)
def mock_message_boxes(monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    def mock_information(*args, **kwargs):
        pass
    monkeypatch.setattr(QMessageBox, "information", mock_information)

    def mock_warning(*args, **kwargs):
        pass
    monkeypatch.setattr(QMessageBox, "warning", mock_warning)

    def mock_critical(*args, **kwargs):
        pass
    monkeypatch.setattr(QMessageBox, "critical", mock_critical)

    def mock_question(*args, **kwargs):
        return QMessageBox.Yes
    monkeypatch.setattr(QMessageBox, "question", mock_question)

    yield


# ============================================================
# 全局禁用 QTimer.singleShot
# ============================================================
@pytest.fixture(autouse=True)
def patch_timer_single_shot(monkeypatch):
    from PySide6.QtCore import QTimer
    def patched_single_shot(msec, callback, *args, **kwargs):
        pass
    monkeypatch.setattr(QTimer, "singleShot", patched_single_shot)


# ============================================================
# 模拟 FFmpeg/FFprobe
# ============================================================
@pytest.fixture
def mock_video_scanner_functions(monkeypatch):
    import src.video_scanner as vs
    monkeypatch.setattr(vs, 'get_video_duration', lambda x: 123.45)
    monkeypatch.setattr(vs, 'get_video_resolution', lambda x: "1920x1080")
    yield


# ============================================================
# 模拟 extract_frame_async
# ============================================================
@pytest.fixture
def mock_extract_frame_async(monkeypatch):
    import src.video_scanner as vs
    async def mock_extract(video_path, time_sec, output_path, retries=1):
        return True, None
    monkeypatch.setattr(vs, 'extract_frame_async', mock_extract)
    yield


# ============================================================
# 临时数据库 fixture
# ============================================================
@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    try:
        if os.path.exists(db_path):
            os.unlink(db_path)
    except PermissionError:
        pass


@pytest.fixture
def sample_video_path():
    return "C:/test/video.mp4"


@pytest.fixture
def temp_export_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# ============================================================
# mock_controller fixture
# ============================================================
@pytest.fixture
def mock_controller():
    mock = MagicMock()
    mock.density = 9
    mock.num_segments = 3
    mock.current_seg_index = 0
    mock.get_segments.return_value = [
        ("A", 0.0, 40.0),
        ("B", 40.0, 80.0),
        ("C", 80.0, 120.0),
    ]
    mock.get_segment_items.return_value = [
        {'time': i*10.0, 'path': None, 'locked': False, 'favorite': False, 'exported': False}
        for i in range(9)
    ]
    mock.get_video_name.return_value = "test.mp4"
    mock.get_video_path.return_value = "test.mp4"
    mock.get_video_state_icon.return_value = ""
    mock.get_favorites_count.return_value = 0
    mock.can_undo.return_value = False
    mock.can_redo.return_value = False
    mock.get_cache_size_mb.return_value = 0.0
    mock.get_cache_file_count.return_value = 0
    mock.get_current_segment.return_value = ("A", 0.0, 40.0)
    mock.load_segment = AsyncMock(return_value=None)
    mock.favorite_selected = MagicMock(return_value=(1, 0))
    mock.unfavorite_selected = MagicMock(return_value=1)
    mock.lock_selected = MagicMock(return_value=1)
    mock.unlock_selected = MagicMock(return_value=1)
    mock.export_selected = MagicMock(return_value=(1, []))
    mock.remove_video = MagicMock(return_value=True)
    # 添加 db mock 以便关闭
    mock.db = MagicMock()
    mock.db.close = MagicMock()
    yield mock
    # 测试结束后关闭数据库连接
    if hasattr(mock, 'db') and hasattr(mock.db, 'close'):
        mock.db.close()


# ============================================================
# config_with_watch_dirs fixture
# ============================================================
from src.config_manager import ConfigManager

@pytest.fixture
def config_with_watch_dirs():
    config = ConfigManager()
    config.set_watch_dirs(["C:/movies", "D:/tv"])
    yield config
    config.set_watch_dirs([])