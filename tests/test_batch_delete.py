"""
测试批量删除视频（多选+删除）
"""

import pytest
from unittest.mock import patch, MagicMock
from PySide6.QtCore import Qt, QItemSelectionModel
from PySide6.QtWidgets import QMessageBox
from ui.views.segment_view import SegmentView

pytestmark = pytest.mark.ui


class TestBatchDelete:

    @pytest.fixture
    def view_with_videos(self, qtbot, mock_controller):
        view = SegmentView()
        view.controller = mock_controller
        view.all_videos = [
            "C:/movies/action/avengers.mp4",
            "C:/movies/comedy/friends.mp4",
            "C:/movies/drama/inception.mp4",
        ]
        view.filtered_videos = view.all_videos.copy()
        view._refresh_video_list()
        view.show()
        qtbot.addWidget(view)
        return view

    def test_batch_delete_single(self, qtbot, view_with_videos):
        view = view_with_videos
        view.video_list.setCurrentRow(0)
        qtbot.wait(50)
        with patch('ui.views.segment_view.QMessageBox.question', return_value=QMessageBox.Yes):
            view.batch_remove_videos()
        qtbot.wait(100)
        assert len(view.all_videos) == 2
        assert "avengers.mp4" not in " ".join(view.all_videos)

    def test_batch_delete_multiple(self, qtbot, view_with_videos):
        view = view_with_videos
        view.video_list.setCurrentRow(0)
        view.video_list.setCurrentRow(1, QItemSelectionModel.Select | QItemSelectionModel.Rows)
        qtbot.wait(50)
        with patch('ui.views.segment_view.QMessageBox.question', return_value=QMessageBox.Yes):
            view.batch_remove_videos()
        qtbot.wait(100)
        assert len(view.all_videos) == 1
        assert "inception.mp4" in view.all_videos[0]

    def test_batch_delete_none_selected(self, qtbot, view_with_videos):
        view = view_with_videos
        view.video_list.clearSelection()
        view.batch_remove_videos()
        qtbot.wait(50)
        assert len(view.all_videos) == 3

    def test_batch_delete_cancel(self, qtbot, view_with_videos):
        view = view_with_videos
        view.video_list.setCurrentRow(0)
        with patch('ui.views.segment_view.QMessageBox.question', return_value=QMessageBox.No):
            view.batch_remove_videos()
        qtbot.wait(50)
        assert len(view.all_videos) == 3

    def test_batch_delete_failed(self, qtbot, view_with_videos):
        view = view_with_videos
        view.video_list.setCurrentRow(0)
        view.controller.remove_video = MagicMock(return_value=False)
        # 模拟警告框，避免弹出窗口
        with patch('ui.views.segment_view.QMessageBox.warning') as mock_warning:
            with patch('ui.views.segment_view.QMessageBox.question', return_value=QMessageBox.Yes):
                view.batch_remove_videos()
            qtbot.wait(50)
            # 验证警告框被调用
            mock_warning.assert_called_once()
        assert len(view.all_videos) == 3