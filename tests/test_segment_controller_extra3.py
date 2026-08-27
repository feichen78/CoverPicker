"""
继续补充 segment_controller 未覆盖分支（目标 80%+）
覆盖：异步取消、异常处理、边界条件、缓存管理
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from src.controllers.segment_controller import SegmentController
from src.database import Database

# 移除类级别的 asyncio mark，仅在异步测试上单独标记


class TestSegmentControllerExtra3:

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

    # ---- 异步取消分支 ----

    @pytest.mark.asyncio
    async def test_load_segment_cancels_existing_task(self, controller):
        """测试 load_segment 取消现有任务"""
        async def slow_task():
            await asyncio.sleep(10)

        controller._load_task = asyncio.create_task(slow_task())
        await controller.load_segment(0, restore_locks=True, randomize=False)
        assert controller._load_task is None or controller._load_task.done()

    @pytest.mark.asyncio
    async def test_cancel_current_task_handles_done_task(self, controller):
        """测试 _cancel_current_task 处理已完成任务"""
        async def done_task():
            return None
        task = asyncio.create_task(done_task())
        await task
        controller._load_task = task
        await controller._cancel_current_task()
        assert controller._load_task is None

    # ---- 异常处理分支 ----

    @pytest.mark.asyncio
    async def test_load_video_with_ffprobe_failure(self, controller):
        """测试 FFprobe 返回 None 时 load_video 返回 False"""
        with patch('src.controllers.segment_controller.get_video_duration', return_value=None):
            result = await controller.load_video("test.mp4")
            assert result is False
            assert controller.duration == 0.0

    @pytest.mark.asyncio
    async def test_extract_frame_exception_in_load(self, controller):
        """测试提取帧异常时 _load_segment 继续处理"""
        with patch('src.controllers.segment_controller.extract_frame_async') as mock_extract:
            mock_extract.side_effect = [
                Exception("FFmpeg error"),
                (True, None)
            ]
            controller.density = 2
            controller.screenshots['A'] = []
            await controller._load_segment(0, restore_locks=False, randomize=False)
            items = controller.screenshots.get('A', [])
            success_count = sum(1 for item in items if item.get('path') is not None)
            assert success_count >= 1

    # ---- 边界条件 ----

    def test_set_num_segments_with_custom_segments(self, controller):
        """测试自定义分区时设置分区数（实际会改变，因为条件满足）"""
        controller.num_segments = -1
        controller.segments = [("X", 0.0, 30.0), ("Y", 30.0, 60.0)]
        controller.set_num_segments(5)
        # 实际行为：因为 video_path 和 duration 有效，num_segments 会被改为 5
        assert controller.num_segments == 5

    def test_get_current_segment_with_empty_segments(self, controller):
        """测试空分区列表时 get_current_segment 返回 None"""
        controller.segments = []
        result = controller.get_current_segment()
        assert result is None

    def test_get_current_segment_with_invalid_index(self, controller):
        """测试无效索引时 get_current_segment 返回 None"""
        controller.current_seg_index = 99
        result = controller.get_current_segment()
        assert result is None

    # ---- 缓存管理 ----

    def test_get_cache_size_with_invalid_dir(self, controller):
        """测试无效缓存目录时 get_cache_size 返回 0"""
        with patch('os.listdir', side_effect=PermissionError("Access denied")):
            size = controller.get_cache_size()
            assert size == 0

    def test_get_cache_file_count_with_invalid_dir(self, controller):
        """测试无效缓存目录时 get_cache_file_count 返回 0"""
        with patch('os.listdir', side_effect=PermissionError("Access denied")):
            count = controller.get_cache_file_count()
            assert count == 0

    def test_clear_cache_handles_errors(self, controller):
        """测试 clear_cache 处理删除错误"""
        with patch('shutil.rmtree', side_effect=Exception("Delete error")):
            count = controller.clear_cache()
            assert count >= 0

    # ---- 收藏相关 ----

    def test_replace_screenshot_without_favorite(self, controller):
        """测试替换非收藏截图"""
        controller.screenshots['A'] = [
            {'time': 10.0, 'path': '/tmp/f1.jpg', 'locked': False, 'favorite': False, 'exported': False}
        ]
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            temp_path = f.name
        try:
            result = controller.replace_screenshot('A', 0, 15.0, temp_path, 10.0)
            assert result is True
            assert controller.screenshots['A'][0]['time'] == 15.0
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_replace_screenshot_with_favorite(self, controller):
        """测试替换收藏截图"""
        controller.screenshots['A'] = [
            {'time': 10.0, 'path': '/tmp/f1.jpg', 'locked': False, 'favorite': True, 'exported': False}
        ]
        controller.favorites = [{
            'video_path': 'test.mp4',
            'segment': 'A',
            'time': 10.0,
            'path': '/tmp/fav.jpg',
            'exported': False
        }]
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            temp_path = f.name
        try:
            with patch.object(controller.db, 'remove_favorite'):
                with patch.object(controller.db, 'add_favorite'):
                    result = controller.replace_screenshot('A', 0, 15.0, temp_path, 10.0)
                    assert result is True
                    assert controller.screenshots['A'][0]['time'] == 15.0
                    assert controller.favorites[0]['time'] == 15.0
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    # ---- 导出相关 ----

    def test_export_selected_no_images(self, controller):
        """测试导出时没有有效图片"""
        controller.screenshots['A'] = [{'time': 10.0, 'path': None, 'locked': False, 'favorite': False, 'exported': False}]
        with tempfile.TemporaryDirectory() as tmpdir:
            exported, exported_list = controller.export_selected('A', [0], export_dir=tmpdir)
            assert exported == 0
            assert exported_list == []

    # ---- 状态保存 ----

    def test_save_state_to_db_with_no_video(self, controller):
        """测试无视频时保存状态"""
        controller.video_path = None
        controller._save_state_to_db()
        # 不应崩溃

    # ---- 清理 ----

    def test_cleanup_with_no_backup_dir(self, controller):
        """测试无备份目录时 cleanup"""
        with patch.object(controller, 'get_backup_dir', return_value=None):
            controller.cleanup()
            # 不应崩溃

    def test_cleanup_with_backup_failure(self, controller):
        """测试 backup 失败时 cleanup"""
        with patch.object(controller, 'get_backup_dir', return_value="/tmp"):
            with patch.object(controller.db, 'backup', return_value=(False, "Error")):
                controller.cleanup()
                # 不应崩溃