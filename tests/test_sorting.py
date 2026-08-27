"""
测试视频列表排序 - 移除 qtbot.wait，避免崩溃
"""

import pytest
import os
from PySide6.QtCore import Qt
from ui.views.segment_view import SegmentView
from src.config_manager import ConfigManager

pytestmark = pytest.mark.ui


class TestSorting:

    @pytest.fixture
    def view_with_config(self, qtbot, mock_controller):
        config = ConfigManager()
        config.set_watch_dirs(["C:/movies", "D:/tv"])
        view = SegmentView()
        view.controller = mock_controller
        view.config = config
        view.all_videos = [
            "C:/movies/action/avengers.mp4",
            "C:/movies/comedy/friends.mp4",
            "D:/tv/breaking_bad.mp4",
            "D:/tv/game_of_thrones.mp4",
            "E:/other/random.mp4",
        ]
        view.filtered_videos = view.all_videos.copy()
        view._refresh_video_list()
        view.show()
        qtbot.addWidget(view)
        return view

    def test_sorting_group_order(self, qtbot, view_with_config):
        view = view_with_config
        items = [view.video_list.item(i).data(Qt.UserRole) for i in range(view.video_list.count())]
        groups = [view._get_video_group_key(path)[0] for path in items]
        assert groups == sorted(groups)

    def test_sorting_within_group_alphabetical(self, qtbot, view_with_config):
        view = view_with_config
        items = [view.video_list.item(i).data(Qt.UserRole) for i in range(view.video_list.count())]
        c_movies = [p for p in items if p.startswith("C:/movies")]
        subdirs = [os.path.basename(os.path.dirname(p)) for p in c_movies]
        assert subdirs == sorted(subdirs)

    def test_other_group_at_end(self, qtbot, view_with_config):
        view = view_with_config
        items = [view.video_list.item(i).data(Qt.UserRole) for i in range(view.video_list.count())]
        groups = [view._get_video_group_key(path)[0] for path in items]
        last_group = groups[-1]
        assert last_group == 999, f"最后一项的组索引是 {last_group}，应为 999"

    def test_search_filter_preserves_sorting(self, qtbot, view_with_config):
        view = view_with_config
        view.search_input.setText("breaking")
        items = [view.video_list.item(i).data(Qt.UserRole) for i in range(view.video_list.count())]
        assert len(items) == 1
        assert "breaking_bad" in items[0]
        view.search_input.setText("")
        items2 = [view.video_list.item(i).data(Qt.UserRole) for i in range(view.video_list.count())]
        assert len(items2) == 5