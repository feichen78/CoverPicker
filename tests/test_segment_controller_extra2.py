"""
继续补充 segment_controller 未覆盖分支
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from src.controllers.segment_controller import SegmentController
from src.database import Database

# 移除类级别的 asyncio mark，只在需要的测试上单独标记


class TestSegmentControllerExtra2:

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        db_path = tmp_path / "test.db"
        return str(db_path)

    @pytest.fixture
    def controller(self, temp_db_path):
        db = Database(db_path=temp_db_path)
        video_id = db.get_or_create_video(
            file_path="test.mp4",
            file_name="test.mp4",
            duration=120,
            resolution="1920x1080",
            file_size=100,
            modified_time=1234567890
        )
        controller = SegmentController()
        controller.db = db
        controller.video_id = video_id
        controller.video_path = "test.mp4"
        controller.duration = 120.0
        controller.num_segments = 3
        controller.segments = [
            ("A", 0.0, 40.0),
            ("B", 40.0, 80.0),
            ("C", 80.0, 120.0),
        ]
        controller.screenshots = {
            'A': [{'time': 10.0, 'path': '/tmp/f1.jpg', 'locked': False, 'favorite': False, 'exported': False}],
        }
        controller.loaded_segments = set()
        controller.favorites = []
        return controller

    @pytest.mark.asyncio
    async def test_load_segment_cancellation(self, controller):
        """测试加载过程中取消任务"""
        with patch('src.controllers.segment_controller.extract_frame_async') as mock_extract:
            mock_extract.side_effect = asyncio.CancelledError()
            try:
                await controller._load_segment(0, restore_locks=False, randomize=False)
            except asyncio.CancelledError:
                pass
            # 不应崩溃

    # 以下测试是同步的，移除 asyncio mark
    def test_undo_with_empty_stack(self, controller):
        """测试空撤销栈时不崩溃"""
        controller.undo_stack.clear()
        controller.undo()
        # 不应崩溃

    def test_redo_with_empty_stack(self, controller):
        """测试空重做栈时不崩溃"""
        controller.redo_stack.clear()
        controller.redo()
        # 不应崩溃

    def test_get_favorites_count_no_video(self, controller):
        """测试未加载视频时收藏数为0"""
        controller.video_path = None
        count = controller.get_favorites_count()
        assert count == 0

    def test_auto_clean_cache_default(self, controller):
        """测试自动清理缓存（当前为占位）"""
        deleted, freed = controller.auto_clean_cache()
        assert deleted == 0
        assert freed == 0.0

    @pytest.mark.asyncio
    async def test_refresh_unlocked_with_empty_items(self, controller):
        """测试空截图列表刷新"""
        controller.screenshots['A'] = []
        result = await controller.refresh_unlocked(0)
        assert result == 0

    def test_apply_custom_segments_invalid(self, controller):
        """测试应用无效自定义分区"""
        controller.apply_custom_segments([])
        # 不应崩溃

        controller.apply_custom_segments([("X", 10.0, 5.0)])
        # 不应崩溃

    def test_clear_history(self, controller):
        """测试清空历史"""
        controller.undo_stack.append(MagicMock())
        controller.redo_stack.append(MagicMock())
        controller._clear_history()
        assert len(controller.undo_stack) == 0
        assert len(controller.redo_stack) == 0