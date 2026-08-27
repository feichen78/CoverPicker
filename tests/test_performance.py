"""
性能基准测试 - 记录关键操作耗时，作为后续版本对比基线
"""

import pytest
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from ui.views.segment_view import SegmentView
from src.controllers.segment_controller import SegmentController
from src.database import Database

pytestmark = pytest.mark.slow


@pytest.fixture
def temp_video_file():
    """创建一个模拟视频文件（空文件）"""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def db_with_video_and_id(temp_video_file):
    """创建一个包含单个视频的数据库，并返回 (db, video_id)"""
    db = Database()
    video_id = db.get_or_create_video(
        file_path=temp_video_file,
        file_name=os.path.basename(temp_video_file),
        duration=120,
        resolution="1920x1080",
        file_size=1024*1024*100,
        modified_time=1234567890
    )
    yield db, video_id
    db.close()


@pytest.fixture
def temp_image_files():
    """创建 3 个临时图片文件，用于截图路径"""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = []
        for i in range(3):
            path = os.path.join(tmpdir, f"frame{i}.jpg")
            Path(path).touch()
            paths.append(path)
        yield paths


@pytest.fixture
def controller_with_mocks(db_with_video_and_id, temp_video_file, temp_image_files):
    """创建 SegmentController 并配置有效的截图路径和视频 ID"""
    db, video_id = db_with_video_and_id
    controller = SegmentController()
    controller.db = db
    controller.video_path = temp_video_file
    controller.video_id = video_id
    controller.duration = 120.0
    controller.num_segments = 3
    controller.segments = [
        ("A", 0.0, 40.0),
        ("B", 40.0, 80.0),
        ("C", 80.0, 120.0),
    ]
    controller.screenshots = {
        'A': [{'time': i*5.0, 'path': temp_image_files[i % 3], 'locked': False, 'favorite': False, 'exported': False}
              for i in range(9)],
        'B': [{'time': 40.0 + i*5.0, 'path': temp_image_files[i % 3], 'locked': False, 'favorite': False, 'exported': False}
              for i in range(9)],
        'C': [{'time': 80.0 + i*5.0, 'path': temp_image_files[i % 3], 'locked': False, 'favorite': False, 'exported': False}
              for i in range(9)],
    }
    controller.loaded_segments = {'A', 'B', 'C'}
    return controller


class TestPerformance:

    @pytest.mark.asyncio
    async def test_load_video_performance(self, temp_video_file):
        """测试加载视频的耗时（不包含 FFmpeg 提取帧）"""
        with patch('src.controllers.segment_controller.get_video_duration', return_value=120.0):
            with patch('src.controllers.segment_controller.get_video_resolution', return_value="1920x1080"):
                async def mock_extract(*args, **kwargs):
                    return True, None
                with patch('src.controllers.segment_controller.extract_frame_async', side_effect=mock_extract):
                    controller = SegmentController()
                    start = time.perf_counter()
                    result = await controller.load_video(temp_video_file)
                    elapsed = time.perf_counter() - start
                    assert elapsed < 2.0
                    assert result is True

    def test_segment_switch_performance(self, controller_with_mocks):
        """测试分区切换的耗时"""
        controller = controller_with_mocks
        controller.current_seg_index = 0

        async def mock_load(*args, **kwargs):
            return
        with patch.object(controller, 'load_segment', side_effect=mock_load):
            start = time.perf_counter()
            controller.current_seg_index = 1
            elapsed = time.perf_counter() - start
            assert elapsed < 0.02

    def test_grid_refresh_performance(self, qtbot, controller_with_mocks):
        """测试截图网格刷新的耗时"""
        view = SegmentView()
        view.controller = controller_with_mocks
        view._rebuild_seg_buttons()

        start = time.perf_counter()
        view._refresh_grid()
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1

    def test_favorite_operation_performance(self, controller_with_mocks):
        """测试收藏操作的耗时（放宽阈值适应环境波动）"""
        controller = controller_with_mocks
        with patch.object(controller.db, 'is_favorite', return_value=False):
            with patch.object(controller.db, 'add_favorite', return_value=1):
                start = time.perf_counter()
                controller.favorite_selected('A', [0, 1, 2])
                elapsed = time.perf_counter() - start
                # 放宽至 0.1s 适应环境波动
                assert elapsed < 0.1

    def test_export_operation_performance(self, controller_with_mocks):
        """测试导出操作的耗时"""
        controller = controller_with_mocks
        with tempfile.TemporaryDirectory() as tmpdir:
            start = time.perf_counter()
            exported, _ = controller.export_selected('A', [0], export_dir=tmpdir)
            elapsed = time.perf_counter() - start
            assert exported == 1
            assert elapsed < 0.05

    def test_undo_redo_performance(self, controller_with_mocks):
        """测试撤销/重做操作的耗时"""
        controller = controller_with_mocks
        with patch.object(controller.db, 'is_favorite', return_value=False):
            with patch.object(controller.db, 'add_favorite', return_value=1):
                controller.favorite_selected('A', [0])

        start = time.perf_counter()
        controller.undo()
        elapsed = time.perf_counter() - start
        assert elapsed < 0.05

        start = time.perf_counter()
        controller.redo()
        elapsed = time.perf_counter() - start
        assert elapsed < 0.05

    def test_cache_info_performance(self, controller_with_mocks):
        """测试缓存信息获取的耗时"""
        controller = controller_with_mocks
        start = time.perf_counter()
        size_mb = controller.get_cache_size_mb()
        file_count = controller.get_cache_file_count()
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0
        assert size_mb >= 0
        assert file_count >= 0