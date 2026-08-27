"""
测试自定义分区功能（基于实际 PreviewDialog 方法名和行为）
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QDialog

from ui.views.preview_dialog import PreviewDialog

pytestmark = pytest.mark.ui


class TestCustomSegments:

    @pytest.fixture
    def mock_main_controller(self):
        mock = MagicMock()
        mock._config = MagicMock()
        mock.get_segments = MagicMock(return_value=[
            ("A", 0.0, 40.0),
            ("B", 40.0, 80.0),
            ("C", 80.0, 120.0),
        ])
        mock.num_segments = 3
        mock.segments = [("A", 0.0, 40.0), ("B", 40.0, 80.0), ("C", 80.0, 120.0)]
        mock.screenshots = {}
        mock.loaded_segments = set()
        mock.current_seg_index = 0
        mock.video_path = "test.mp4"
        mock.load_segment = MagicMock()
        return mock

    @pytest.fixture
    def dialog(self, qtbot, mock_main_controller):
        with patch('src.controllers.preview_controller.PreviewController.set_preview_time'):
            dlg = PreviewDialog()
            dlg.main_controller = mock_main_controller
            dlg.set_video("test.mp4", 120.0, "/tmp")
            qtbot.addWidget(dlg)
            yield dlg

    def test_add_split_point(self, qtbot, dialog):
        """测试添加分割点"""
        initial_count = len(dialog.split_points)
        dialog.slider.setValue(2000)
        with patch('ui.views.preview_dialog.QMessageBox.information') as mock_info:
            dialog.add_split_btn.click()
            assert len(dialog.split_points) == initial_count + 1
            mock_info.assert_called_once()

    def test_add_split_point_duplicate(self, qtbot, dialog):
        """测试添加重复分割点被阻止（实际使用 QMessageBox.information）"""
        dialog.slider.setValue(2000)
        dialog.add_split_btn.click()
        with patch('ui.views.preview_dialog.QMessageBox.information') as mock_info:
            dialog.add_split_btn.click()
            mock_info.assert_called_once()

    def test_add_split_point_out_of_range(self, qtbot, dialog):
        """测试添加超出范围的分割点被阻止"""
        dialog.slider.setValue(0)
        with patch('ui.views.preview_dialog.QMessageBox.warning') as mock_warning:
            dialog.add_split_btn.click()
            mock_warning.assert_called_once()

        dialog.slider.setValue(10000)
        with patch('ui.views.preview_dialog.QMessageBox.warning') as mock_warning:
            dialog.add_split_btn.click()
            mock_warning.assert_called_once()

    def test_clear_splits(self, qtbot, dialog):
        """测试清除所有分割点"""
        dialog.slider.setValue(2000)
        dialog.add_split_btn.click()
        dialog.slider.setValue(5000)
        dialog.add_split_btn.click()
        assert len(dialog.split_points) == 2

        with patch('ui.views.preview_dialog.QMessageBox.information') as mock_info:
            dialog.clear_splits_btn.click()
            assert len(dialog.split_points) == 0
            mock_info.assert_called_once()

    def test_apply_custom_segments(self, qtbot, dialog):
        """测试应用自定义分区（实际方法名：apply_split_points）"""
        dialog.slider.setValue(2000)
        dialog.add_split_btn.click()
        dialog.slider.setValue(5000)
        dialog.add_split_btn.click()

        mock_controller = dialog.main_controller

        with patch('ui.views.preview_dialog.QMessageBox.information'):
            with patch('asyncio.create_task'):
                dialog.apply_split_points()
                assert mock_controller.num_segments == -1
                segments = mock_controller.segments
                assert len(segments) == 3
                assert segments[0][0] == "A"
                assert abs(segments[0][1] - 0.0) < 0.01
                assert abs(segments[0][2] - 24.0) < 0.01

    def test_apply_custom_segments_no_splits(self, qtbot, dialog):
        """测试无分割点时应用被阻止"""
        with patch('ui.views.preview_dialog.QMessageBox.warning') as mock_warning:
            dialog.apply_split_points()
            mock_warning.assert_called_once()

    def test_apply_custom_segments_clear_first(self, qtbot, dialog):
        """测试应用前清空截图"""
        dialog.slider.setValue(2000)
        dialog.add_split_btn.click()

        mock_controller = dialog.main_controller
        initial_segments = mock_controller.segments.copy()

        with patch('ui.views.preview_dialog.QMessageBox.information'):
            with patch('asyncio.create_task'):
                dialog.apply_split_points()
                assert mock_controller.segments != initial_segments
                assert mock_controller.screenshots == {}

    def test_split_points_persist_in_preview(self, qtbot, dialog):
        """测试分割点在预览窗口中持久显示"""
        dialog.slider.setValue(2000)
        dialog.add_split_btn.click()
        dialog.slider.setValue(5000)
        dialog.add_split_btn.click()
        dialog._update_tick_positions()
        assert len(dialog.split_points) == 2