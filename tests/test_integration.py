"""
集成测试 - 模拟完整工作流
"""

import pytest
import os
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import src.database
import src.controllers.segment_controller


class TestIntegration:

    @pytest.fixture
    def temp_db_path(self):
        """临时数据库路径"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except PermissionError:
            pass

    @pytest.fixture
    def temp_video_dir(self):
        """临时视频目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建模拟视频文件
            video_path = os.path.join(tmpdir, "test_video.mp4")
            Path(video_path).touch()
            yield tmpdir

    def test_full_workflow(self, temp_db_path, temp_video_dir):
        """
        测试完整工作流：
        1. 数据库初始化
        2. 导入视频
        3. 加载视频并生成分区
        4. 收藏截图
        5. 导出截图
        """
        # 1. 初始化数据库
        db = src.database.Database(db_path=temp_db_path)
        video_path = os.path.join(temp_video_dir, "test_video.mp4")

        # 2. 导入视频
        video_id = db.get_or_create_video(
            file_path=video_path,
            file_name="test_video.mp4",
            duration=120,
            resolution="1920x1080",
            file_size=1024*1024*100,
            modified_time=1234567890
        )
        assert video_id > 0

        # 3. 创建 SegmentController 并加载视频
        controller = src.controllers.segment_controller.SegmentController()
        controller.db = db
        controller.video_id = video_id
        controller.video_path = video_path
        controller.duration = 120.0
        controller.num_segments = 3
        controller.segments = [
            ("A", 0.0, 40.0),
            ("B", 40.0, 80.0),
            ("C", 80.0, 120.0),
        ]

        # 模拟截图数据
        controller.screenshots = {
            'A': [
                {'time': 10.0, 'path': '/tmp/frame1.jpg', 'locked': False, 'favorite': False, 'exported': False},
                {'time': 20.0, 'path': '/tmp/frame2.jpg', 'locked': False, 'favorite': False, 'exported': False},
                {'time': 30.0, 'path': '/tmp/frame3.jpg', 'locked': False, 'favorite': False, 'exported': False},
            ]
        }
        controller.favorites = []

        # 4. 收藏截图
        added, _ = controller.favorite_selected('A', [0, 1])
        assert added == 2
        assert controller.screenshots['A'][0]['favorite'] is True
        assert controller.screenshots['A'][1]['favorite'] is True

        # 验证数据库中的收藏记录
        db_favs = db.get_favorites(video_id)
        assert len(db_favs) == 2

        # 5. 导出截图（使用临时导出目录）
        with tempfile.TemporaryDirectory() as export_dir:
            # 创建模拟图片文件
            for i in range(3):
                img_path = os.path.join(export_dir, f"frame{i+1}.jpg")
                Path(img_path).touch()

            # 更新截图路径
            controller.screenshots['A'][0]['path'] = os.path.join(export_dir, "frame1.jpg")
            controller.screenshots['A'][1]['path'] = os.path.join(export_dir, "frame2.jpg")

            exported, exported_list = controller.export_selected('A', [0, 1], export_dir=export_dir)
            assert exported == 2
            # 验证导出文件存在
            for _, dest_path in exported_list:
                assert os.path.exists(dest_path)

        db.close()

    # ============================================================
    # 修正点1：使用列表而非元组，与数据库返回类型一致
    # ============================================================

    def test_excluded_ranges_workflow(self, temp_db_path):
        """测试排除区间功能"""
        db = src.database.Database(db_path=temp_db_path)
        video_id = db.get_or_create_video(
            file_path="test.mp4",
            file_name="test.mp4",
            duration=120,
            resolution="1920x1080",
            file_size=100,
            modified_time=1234567890
        )

        controller = src.controllers.segment_controller.SegmentController()
        controller.db = db
        controller.video_id = video_id
        controller.video_path = "test.mp4"
        controller.duration = 120.0

        # 使用列表，与数据库返回类型一致
        ranges = [[0.0, 10.0], [110.0, 120.0]]
        controller.set_excluded_ranges(ranges, save=True)

        # 验证数据库持久化
        saved_ranges = db.get_video_excluded_ranges(video_id)
        assert saved_ranges == ranges

        # 验证排除判断
        assert controller._is_time_excluded(5.0) is True
        assert controller._is_time_excluded(30.0) is False
        assert controller._is_time_excluded(115.0) is True

        db.close()

    def test_backup_and_restore(self, temp_db_path):
        """测试备份和恢复功能"""
        db = src.database.Database(db_path=temp_db_path)

        # 插入测试数据
        video_id = db.get_or_create_video(
            file_path="test.mp4",
            file_name="test.mp4",
            duration=120,
            resolution="1920x1080",
            file_size=100,
            modified_time=1234567890
        )
        db.add_favorite(video_id, "A", 10000, "/tmp/thumb.jpg", "thumb.jpg")

        # 执行备份
        with tempfile.TemporaryDirectory() as backup_dir:
            success, backup_path = db.backup(backup_dir)
            assert success is True
            assert os.path.exists(backup_path)

            # 关闭数据库
            db.close()

            # 恢复备份（重新创建数据库实例）
            db2 = src.database.Database(db_path=temp_db_path)
            success2, msg = db2.restore(backup_path)
            assert success2 is True

            # 验证数据恢复
            restored_video = db2.get_video_by_path("test.mp4")
            assert restored_video is not None
            assert restored_video['file_name'] == "test.mp4"

            restored_favs = db2.get_favorites(restored_video['id'])
            assert len(restored_favs) == 1
            db2.close()

    # ============================================================
    # 修正点2：添加 monkeypatch 模拟 extract_frame_async，避免 FFmpeg 调用挂起
    # ============================================================

    @pytest.mark.asyncio
    async def test_segment_loading_with_exclusions(self, temp_db_path, monkeypatch):
        """测试带排除区间的分区加载"""
        # 模拟 extract_frame_async 快速返回成功，避免真实 FFmpeg 调用
        async def mock_extract(video_path, time_sec, output_path, retries=1):
            return True, None
        monkeypatch.setattr(
            src.controllers.segment_controller,
            'extract_frame_async',
            mock_extract
        )

        db = src.database.Database(db_path=temp_db_path)
        video_id = db.get_or_create_video(
            file_path="test.mp4",
            file_name="test.mp4",
            duration=120,
            resolution="1920x1080",
            file_size=100,
            modified_time=1234567890
        )

        controller = src.controllers.segment_controller.SegmentController()
        controller.db = db
        controller.video_id = video_id
        controller.video_path = "test.mp4"
        controller.duration = 120.0
        controller.density = 9
        controller.num_segments = 3

        # 设置排除区间（排除开头和结尾）
        ranges = [(0.0, 5.0), (115.0, 120.0)]
        controller.set_excluded_ranges(ranges, save=True)

        # 模拟分区计算
        controller.segments = [
            ("A", 0.0, 40.0),
            ("B", 40.0, 80.0),
            ("C", 80.0, 120.0),
        ]

        # 加载分区
        await controller.load_segment(0, restore_locks=True, randomize=False)

        # 验证截图不会出现在排除区间内
        seg_label, _, _ = controller.get_current_segment()
        items = controller.get_segment_items(seg_label)
        for item in items:
            t = item.get('time', 0)
            is_excluded = any(low <= t <= high for low, high in ranges)
            assert is_excluded is False

        db.close()