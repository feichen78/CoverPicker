"""
测试导入视频核心逻辑（使用临时数据库隔离，并确保连接关闭）
"""

import pytest
import os
import tempfile
from pathlib import Path
from ui.views.segment_view import SegmentView

pytestmark = pytest.mark.ui


class TestImportOperations:

    @pytest.fixture(autouse=True)
    def isolate_home(self, mock_config_home):
        """自动使用临时 HOME 目录，隔离数据库"""
        pass

    @pytest.fixture
    def temp_video_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            files = []
            for i in range(3):
                path = os.path.join(tmpdir, f"video_{i}.mp4")
                Path(path).touch()
                files.append(path)
            yield tmpdir, files

    @pytest.fixture
    def view(self, qtbot, mock_controller):
        view = SegmentView()
        view.controller = mock_controller
        view.all_videos.clear()
        view.filtered_videos.clear()
        view._refresh_video_list()
        qtbot.addWidget(view)
        yield view
        # 测试结束后关闭数据库连接，释放文件句柄
        try:
            if view.controller and hasattr(view.controller, 'db'):
                view.controller.db.close()
        except Exception:
            pass

    def test_add_videos_success(self, qtbot, view, temp_video_files):
        """测试 _add_videos 能正确添加存在的视频文件"""
        tmpdir, files = temp_video_files
        view._add_videos(files)
        from src.video_scanner import normalize_path
        norm_files = [normalize_path(f) for f in files]
        assert len(view.all_videos) == 3
        for nf in norm_files:
            assert any(nf == v for v in view.all_videos)

    def test_add_videos_skip_nonexistent(self, qtbot, view):
        """测试 _add_videos 跳过不存在的文件"""
        fake_paths = ["/nonexistent/video1.mp4", "/nonexistent/video2.mp4"]
        view._add_videos(fake_paths)
        assert len(view.all_videos) == 0

    def test_add_videos_skip_duplicates(self, qtbot, view, temp_video_files):
        """测试 _add_videos 跳过已存在的路径"""
        tmpdir, files = temp_video_files
        view._add_videos(files)
        assert len(view.all_videos) == 3
        view._add_videos(files)
        assert len(view.all_videos) == 3