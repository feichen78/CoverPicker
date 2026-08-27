import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
import src.controllers.segment_controller as sc


class TestSegmentController:

    # ============================================================
    # 初始化与配置测试
    # ============================================================

    def test_init(self):
        """测试 SegmentController 初始化"""
        controller = sc.SegmentController()
        assert controller.duration == 0.0
        assert controller.num_segments == 3
        assert controller.density == 9
        assert controller.skip_ratio == 0.15
        assert controller.excluded_ranges == []
        assert controller.undo_stack == []
        assert controller.redo_stack == []

    def test_set_num_segments(self):
        """测试设置分区数"""
        controller = sc.SegmentController()
        controller.video_path = "test.mp4"
        controller.duration = 120.0
        controller.num_segments = 3
        controller.segments = [("A", 0.0, 40.0), ("B", 40.0, 80.0), ("C", 80.0, 120.0)]

        controller.set_num_segments(5)
        assert controller.num_segments == 5
        # 分区数变化应清空截图和加载状态
        assert controller.screenshots == {}
        assert controller.loaded_segments == set()

    def test_set_num_segments_out_of_range(self):
        """测试设置分区数超出范围时自动修正"""
        controller = sc.SegmentController()
        # 设置有效视频路径和时长，使 set_num_segments 的条件成立
        controller.video_path = "test.mp4"
        controller.duration = 120.0
        controller.segments = [("A", 0.0, 40.0)]  # 设置初始分区
        
        controller.set_num_segments(0)
        assert controller.num_segments == 1
        controller.set_num_segments(10)
        assert controller.num_segments == 5

    # ============================================================
    # 排除区间测试
    # ============================================================

    def test_excluded_ranges_get_set(self):
        """测试排除区间的获取和设置"""
        controller = sc.SegmentController()
        ranges = [(0.0, 5.0), (115.0, 120.0)]
        controller.set_excluded_ranges(ranges, save=False)
        assert controller.get_excluded_ranges() == ranges

    def test_is_time_excluded(self):
        """测试时间点是否被排除"""
        controller = sc.SegmentController()
        controller.excluded_ranges = [(10.0, 20.0), (50.0, 60.0)]
        assert controller._is_time_excluded(15.0) is True
        assert controller._is_time_excluded(30.0) is False
        assert controller._is_time_excluded(55.0) is True
        assert controller._is_time_excluded(70.0) is False

    def test_merge_excluded_ranges(self):
        """测试排除区间合并"""
        controller = sc.SegmentController()
        controller.excluded_ranges = [(0.0, 5.0), (3.0, 8.0), (20.0, 30.0)]
        merged = controller._merge_excluded_ranges()
        # 合并后应为 [(0.0, 8.0), (20.0, 30.0)]
        assert merged == [(0.0, 8.0), (20.0, 30.0)]

    # ============================================================
    # 撤销/重做测试
    # ============================================================

    def test_undo_redo_stack_initially_empty(self):
        """测试撤销/重做栈初始为空"""
        controller = sc.SegmentController()
        assert controller.can_undo() is False
        assert controller.can_redo() is False

    def test_push_action_limits_stack_size(self):
        """测试撤销栈大小限制（最多100个）"""
        controller = sc.SegmentController()
        for i in range(150):
            action = sc.Action(
                type='favorite',
                video_id=1,
                seg_label='A',
                timestamp_ms=i * 1000,
                old_state=False,
                new_state=True
            )
            controller._push_action(action)
        assert len(controller.undo_stack) <= 100

    # ============================================================
    # 收藏管理测试（模拟数据库）
    # ============================================================

    @patch('src.controllers.segment_controller.Database')
    def test_favorite_selected(self, MockDatabase):
        """测试收藏选中的截图"""
        # 模拟数据库
        mock_db = MagicMock()
        MockDatabase.return_value = mock_db
        mock_db.is_favorite.return_value = False
        mock_db.add_favorite.return_value = 1

        controller = sc.SegmentController()
        controller.video_id = 1
        controller.video_path = "test.mp4"
        controller.screenshots = {
            'A': [
                {'time': 10.0, 'path': '/tmp/frame1.jpg', 'favorite': False},
                {'time': 20.0, 'path': '/tmp/frame2.jpg', 'favorite': False},
            ]
        }
        controller.favorites = []

        added, skipped = controller.favorite_selected('A', [0, 1])
        assert added == 2
        assert skipped == 0
        assert controller.screenshots['A'][0]['favorite'] is True
        assert controller.screenshots['A'][1]['favorite'] is True
        assert len(controller.favorites) == 2

    @patch('src.controllers.segment_controller.Database')
    def test_unfavorite_selected(self, MockDatabase):
        """测试取消收藏选中的截图"""
        mock_db = MagicMock()
        MockDatabase.return_value = mock_db
        mock_db.is_favorite.return_value = True

        controller = sc.SegmentController()
        controller.video_id = 1
        controller.video_path = "test.mp4"
        controller.screenshots = {
            'A': [
                {'time': 10.0, 'path': '/tmp/frame1.jpg', 'favorite': True},
                {'time': 20.0, 'path': '/tmp/frame2.jpg', 'favorite': True},
            ]
        }
        controller.favorites = [
            {'video_path': 'test.mp4', 'segment': 'A', 'time': 10.0, 'path': '/tmp/fav1.jpg'},
            {'video_path': 'test.mp4', 'segment': 'A', 'time': 20.0, 'path': '/tmp/fav2.jpg'},
        ]

        removed = controller.unfavorite_selected('A', [0])
        assert removed == 1
        assert controller.screenshots['A'][0]['favorite'] is False
        assert controller.screenshots['A'][1]['favorite'] is True
        assert len(controller.favorites) == 1

    # ============================================================
    # 锁定/解锁测试
    # ============================================================

    def test_lock_selected(self):
        """测试锁定选中的截图"""
        controller = sc.SegmentController()
        controller.screenshots = {
            'A': [
                {'time': 10.0, 'path': '/tmp/frame1.jpg', 'locked': False},
                {'time': 20.0, 'path': '/tmp/frame2.jpg', 'locked': False},
            ]
        }
        count = controller.lock_selected('A', [0, 1])
        assert count == 2
        assert controller.screenshots['A'][0]['locked'] is True
        assert controller.screenshots['A'][1]['locked'] is True

    def test_unlock_selected(self):
        """测试解锁选中的截图"""
        controller = sc.SegmentController()
        controller.screenshots = {
            'A': [
                {'time': 10.0, 'path': '/tmp/frame1.jpg', 'locked': True},
                {'time': 20.0, 'path': '/tmp/frame2.jpg', 'locked': False},
            ]
        }
        count = controller.unlock_selected('A', [0])
        assert count == 1
        assert controller.screenshots['A'][0]['locked'] is False

    # ============================================================
    # 导出测试
    # ============================================================

    def test_export_selected(self):
        """测试导出选中的截图"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建临时图片文件
            img1 = os.path.join(tmpdir, "frame1.jpg")
            Path(img1).touch()
            img2 = os.path.join(tmpdir, "frame2.jpg")
            Path(img2).touch()

            controller = sc.SegmentController()
            controller.video_path = "test.mp4"
            controller.screenshots = {
                'A': [
                    {'time': 10.0, 'path': img1, 'exported': False},
                    {'time': 20.0, 'path': img2, 'exported': False},
                ]
            }

            exported, exported_list = controller.export_selected('A', [0], export_dir=tmpdir)
            assert exported == 1
            assert len(exported_list) == 1
            assert controller.screenshots['A'][0]['exported'] is True
            assert controller.screenshots['A'][1]['exported'] is False

    # ============================================================
    # 缓存大小测试
    # ============================================================

    def test_get_cache_size(self):
        """测试获取缓存大小"""
        controller = sc.SegmentController()
        # 默认缓存目录为临时目录
        size = controller.get_cache_size()
        assert size >= 0

    def test_get_cache_file_count(self):
        """测试获取缓存文件数量"""
        controller = sc.SegmentController()
        count = controller.get_cache_file_count()
        assert count >= 0

    # ============================================================
    # 视频状态测试
    # ============================================================

    @patch('src.controllers.segment_controller.Database')
    def test_get_video_state_icon(self, MockDatabase):
        """测试获取视频状态图标"""
        mock_db = MagicMock()
        MockDatabase.return_value = mock_db
        mock_db.get_video_by_path.return_value = {
            'is_exported': 0,
            'is_starred': 1,
            'is_viewed': 0
        }

        controller = sc.SegmentController()
        icon = controller.get_video_state_icon("test.mp4")
        assert icon == "⭐"

    @patch('src.controllers.segment_controller.Database')
    def test_get_video_state_icon_exported_priority(self, MockDatabase):
        """测试导出状态优先于其他状态"""
        mock_db = MagicMock()
        MockDatabase.return_value = mock_db
        mock_db.get_video_by_path.return_value = {
            'is_exported': 1,
            'is_starred': 1,
            'is_viewed': 1
        }

        controller = sc.SegmentController()
        icon = controller.get_video_state_icon("test.mp4")
        # 导出状态优先级最高
        assert icon == "✅"