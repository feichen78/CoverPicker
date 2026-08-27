"""
测试搜索栏实时过滤功能 - 显示窗口但安全清理
"""

import pytest
from PySide6.QtCore import Qt
from ui.views.segment_view import SegmentView

pytestmark = pytest.mark.ui


class TestSearchFilter:

    @pytest.fixture
    def view_with_videos(self, qtbot, mock_controller):
        view = SegmentView()
        view.controller = mock_controller
        view.all_videos = [
            "C:/movies/action/avengers.mp4",
            "C:/movies/comedy/friends.mp4",
            "C:/movies/drama/inception.mp4",
            "D:/tv/breaking_bad.mp4",
            "D:/tv/game_of_thrones.mp4",
        ]
        view.filtered_videos = view.all_videos.copy()
        view._refresh_video_list()
        # 显示窗口，确保子控件可见性正确
        view.show()
        qtbot.addWidget(view)
        yield view
        # qtbot 会在测试结束后自动关闭窗口

    def test_search_filter_matches(self, qtbot, view_with_videos):
        view = view_with_videos
        view.search_input.setText("avengers")
        items = [view.video_list.item(i).text() for i in range(view.video_list.count())]
        assert len(items) == 1
        assert "avengers" in items[0].lower()

    def test_search_filter_case_insensitive(self, qtbot, view_with_videos):
        view = view_with_videos
        view.search_input.setText("GAME")
        items = [view.video_list.item(i).text() for i in range(view.video_list.count())]
        assert len(items) == 1
        assert "game_of_thrones" in items[0].lower()

    def test_search_filter_no_match(self, qtbot, view_with_videos):
        view = view_with_videos
        view.search_input.setText("nonexistent")
        assert view.video_list.count() == 0

    def test_search_filter_clear_button(self, qtbot, view_with_videos):
        view = view_with_videos
        view.search_input.setText("action")
        # 窗口可见，isVisible() 现在为 True
        assert view.clear_search_btn.isVisible() is True
        qtbot.mouseClick(view.clear_search_btn, Qt.LeftButton)
        assert view.clear_search_btn.isVisible() is False
        assert view.video_list.count() == len(view.all_videos)

    def test_search_filter_resets_on_empty(self, qtbot, view_with_videos):
        view = view_with_videos
        view.search_input.setText("inception")
        assert view.video_list.count() == 1
        view.search_input.setText("")
        assert view.video_list.count() == len(view.all_videos)