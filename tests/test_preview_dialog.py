"""
预览窗口测试 - 完整模拟所有对话框（已修复 test_gif_export_dialog）
"""

import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QDialog
from ui.views.preview_dialog import PreviewDialog

pytestmark = pytest.mark.ui


class TestPreviewDialog:

    @pytest.fixture
    def mock_main_controller(self):
        mock = MagicMock()
        mock._config = MagicMock()
        mock._config.get_last_export_dir.return_value = "/tmp"
        mock._config.set_last_export_dir.return_value = None
        mock._config.get_last_gif_export_dir.return_value = "/tmp"
        mock._config.set_last_gif_export_dir.return_value = None
        return mock

    @pytest.fixture
    def dialog(self, qtbot, mock_main_controller):
        with patch('src.controllers.preview_controller.PreviewController.set_preview_time') as mock_set:
            mock_set.return_value = None
            dlg = PreviewDialog()
            dlg.set_main_controller(mock_main_controller)
            dlg.set_video("test.mp4", 120.0, "/tmp")
            qtbot.addWidget(dlg)
            yield dlg

    def test_window_title(self, qtbot, dialog):
        assert "🎬 视频预览" in dialog.windowTitle()

    def test_initial_time_display(self, qtbot, dialog):
        assert dialog.position_label.text() == "00:00"
        assert dialog.duration_label.text() == "02:00"

    def test_slider_range(self, qtbot, dialog):
        assert dialog.slider.minimum() == 0
        assert dialog.slider.maximum() == 10000
        assert dialog.slider.value() == 0

    def test_time_input_jump(self, qtbot, dialog):
        dialog.time_input.setText("01:30")
        dialog.jump_btn.click()
        assert dialog.time_input.text() == "01:30"
        assert dialog.position_label.text() == "01:30"

    def test_current_time_button(self, qtbot, dialog):
        dialog.slider.setValue(5000)
        dialog._pending_time = 60.0
        dialog.current_time_btn.click()
        assert dialog.time_input.text() == "01:00"

    def test_range_buttons(self, qtbot, dialog):
        with patch('ui.views.preview_dialog.QMessageBox.information') as mock_info:
            dialog.slider.setValue(1000)
            dialog.set_start_btn.click()
            dialog.slider.setValue(8000)
            dialog.set_end_btn.click()
            assert mock_info.call_count == 2
            assert dialog.export_btn.isEnabled() is True
            dialog.clear_range_btn.click()
            assert dialog.export_btn.isEnabled() is False

    def test_split_points(self, qtbot, dialog):
        with patch('ui.views.preview_dialog.QMessageBox.information') as mock_info:
            dialog.slider.setValue(2000)
            dialog.add_split_btn.click()
            assert len(dialog.split_points) == 1
            dialog.clear_splits_btn.click()
            assert len(dialog.split_points) == 0
            assert mock_info.call_count == 2

    def test_gif_export_dialog(self, qtbot, dialog):
        """测试 GIF 导出流程，完整模拟所有对话框。"""
        with patch('ui.views.preview_dialog.QMessageBox.information') as mock_info:
            dialog.slider.setValue(1000)
            dialog.set_start_btn.click()
            dialog.slider.setValue(8000)
            dialog.set_end_btn.click()
            assert mock_info.call_count == 2

            with patch('ui.views.preview_dialog.GIFExportDialog.exec', return_value=QDialog.Accepted) as mock_gif_exec:
                with patch('ui.views.preview_dialog.GIFExportDialog.get_params', return_value=(5, 0.25, 0)) as mock_get_params:
                    with patch('ui.views.preview_dialog.QMessageBox.question', return_value=QMessageBox.Yes) as mock_question:
                        with patch('ui.views.preview_dialog.QFileDialog.getSaveFileName',
                                   return_value=("/tmp/test.gif", "GIF")) as mock_get_save:
                            with patch('threading.Thread') as mock_thread:
                                dialog.export_gif_btn.click()
                                mock_gif_exec.assert_called_once()
                                mock_get_params.assert_called_once()
                                mock_question.assert_called_once()
                                mock_get_save.assert_called_once()
                                mock_thread.assert_called_once()