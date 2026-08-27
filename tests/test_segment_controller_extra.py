"""
补充测试 segment_controller 未覆盖分支
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from src.controllers.segment_controller import SegmentController
from src.database import Database

# 移除类级别的 asyncio mark，只在需要的测试上单独标记


class TestSegmentControllerExtra:

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
            'A': [{'time': 10.0, 'path': '/tmp/frame1.jpg', 'locked': False, 'favorite': False, 'exported': False}],
        }
        controller.loaded_segments = set()
        controller.favorites = []
        return controller

    @pytest.mark.asyncio
    async def test_load_video_failure_handling(self, controller):
        """测试 load_video 失败时的处理"""
        with patch('src.controllers.segment_controller.get_video_duration', return_value=None):
            result = await controller.load_video("nonexistent.mp4")
            assert result is False

    @pytest.mark.asyncio
    async def test_load_segment_with_excluded_ranges(self, controller):
        """测试排除区间影响分区加载"""
        controller.excluded_ranges = [(0.0, 10.0)]
        with patch('src.controllers.segment_controller.extract_frame_async') as mock_extract:
            mock_extract.return_value = (True, None)
            await controller._load_segment(0, restore_locks=False, randomize=False)
            items = controller.screenshots.get('A', [])
            for item in items:
                assert not any(low <= item['time'] <= high for low, high in controller.excluded_ranges)

    @pytest.mark.asyncio
    async def test_refresh_unlocked_with_all_locked(self, controller):
        """测试所有截图都锁定时刷新返回0"""
        controller.screenshots['A'] = [
            {'time': 10.0, 'path': '/tmp/f1.jpg', 'locked': True, 'favorite': False, 'exported': False},
            {'time': 20.0, 'path': '/tmp/f2.jpg', 'locked': True, 'favorite': False, 'exported': False},
        ]
        refreshed = await controller.refresh_unlocked(0)
        assert refreshed == 0

    @pytest.mark.asyncio
    async def test_reset_segment_invalid_index(self, controller):
        """测试 reset_segment 越界处理"""
        await controller.reset_segment(99)
        # 不应抛出异常

    # 以下测试是同步的，移除 asyncio mark
    def test_remove_video_not_found(self, controller):
        """测试 remove_video 找不到视频时返回 False"""
        result = controller.remove_video("nonexistent.mp4")
        assert result is False

    def test_remove_video_current_loaded(self, controller):
        """测试删除当前加载的视频"""
        controller.video_path = "test.mp4"
        result = controller.remove_video("test.mp4")
        assert result is True
        assert controller.video_path is None

    def test_get_video_state_icon_exported_priority(self, controller):
        """测试视频状态图标优先级"""
        with patch.object(controller.db, 'get_video_by_path') as mock_get:
            mock_get.return_value = {'is_exported': 1, 'is_starred': 1, 'is_viewed': 1}
            icon = controller.get_video_state_icon("test.mp4")
            assert icon == "✅"

    @pytest.mark.asyncio
    async def test_load_segment_with_seg_idx_out_of_range(self, controller):
        """测试 load_segment 索引越界"""
        await controller.load_segment(99, restore_locks=True, randomize=False)
        # 不应抛出异常

    def test_set_num_segments_with_no_video(self, controller):
        """测试未加载视频时设置分区数不生效（因为 video_path 为空）"""
        controller.video_path = None
        controller.num_segments = 3
        controller.set_num_segments(5)
        assert controller.num_segments == 3

    def test_get_cache_size(self, controller):
        """测试获取缓存大小"""
        size = controller.get_cache_size()
        assert size >= 0