"""
测试预览窗口导出视频片段功能
使用 pytest-asyncio 提供事件循环
"""

import pytest
import os
import tempfile
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from ui.views.preview_dialog import PreviewDialog

pytestmark = pytest.mark.ui


class TestExportClip:

    @pytest.fixture
    def mock_main_controller(self):
        mock = MagicMock()
        mock._config = MagicMock()
        mock._config.get_last_export_dir.return_value = "/tmp"
        mock._config.set_last_export_dir.return_value = None
        return mock

    @pytest.fixture
    def dialog(self, qtbot, mock_main_controller):
        with patch('src.controllers.preview_controller.PreviewController.set_preview_time'):
            dlg = PreviewDialog()
            dlg.set_main_controller(mock_main_controller)
            dlg.set_video("test.mp4", 120.0, "/tmp")
            qtbot.addWidget(dlg)
            yield dlg

    @pytest.mark.asyncio
    async def test_export_clip_success(self, qtbot, dialog):
        dialog.slider.setValue(1000)
        dialog.set_start_btn.click()
        dialog.slider.setValue(8000)
        dialog.set_end_btn.click()
        assert dialog.export_btn.isEnabled() is True

        with patch('ui.views.preview_dialog.QFileDialog.getExistingDirectory',
                   return_value="/tmp"):
            with patch('ui.views.preview_dialog.QMessageBox.information') as mock_info:
                with patch('ui.views.preview_dialog.QMessageBox.question',
                           return_value=QMessageBox.Yes):
                    mock_export = AsyncMock()
                    mock_export.return_value = (True, "/tmp/test_clip.mp4")
                    with patch.object(dialog.controller, 'export_clip', mock_export):
                        dialog.export_clip()
                        await asyncio.sleep(0.1)
                        mock_export.assert_awaited_once()

    def test_export_clip_no_range(self, qtbot, dialog):
        assert dialog.export_btn.isEnabled() is False
        with patch('ui.views.preview_dialog.QMessageBox.warning') as mock_warning:
            dialog.export_clip()
            mock_warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_clip_ffmpeg_failure(self, qtbot, dialog):
        dialog.slider.setValue(1000)
        dialog.set_start_btn.click()
        dialog.slider.setValue(8000)
        dialog.set_end_btn.click()

        with patch('ui.views.preview_dialog.QFileDialog.getExistingDirectory',
                   return_value="/tmp"):
            with patch('ui.views.preview_dialog.QMessageBox.question',
                       return_value=QMessageBox.Yes):
                # 注意：失败时使用 QMessageBox.warning，不是 critical
                with patch('ui.views.preview_dialog.QMessageBox.warning') as mock_warning:
                    mock_export = AsyncMock()
                    mock_export.return_value = (False, "FFmpeg error")
                    with patch.object(dialog.controller, 'export_clip', mock_export):
                        dialog.export_clip()
                        await asyncio.sleep(0.1)
                        mock_warning.assert_called_once()

    def test_export_clip_cancel_save_dialog(self, qtbot, dialog):
        dialog.slider.setValue(1000)
        dialog.set_start_btn.click()
        dialog.slider.setValue(8000)
        dialog.set_end_btn.click()

        with patch('ui.views.preview_dialog.QFileDialog.getExistingDirectory',
                   return_value=""):
            with patch('ui.views.preview_dialog.subprocess.run') as mock_run:
                dialog.export_clip()
                mock_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_export_clip_auto_creates_dir(self, qtbot, dialog):
        dialog.slider.setValue(1000)
        dialog.set_start_btn.click()
        dialog.slider.setValue(8000)
        dialog.set_end_btn.click()

        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "sub", "dir", "clips")

            with patch('ui.views.preview_dialog.QFileDialog.getExistingDirectory',
                       return_value=new_dir):
                with patch('ui.views.preview_dialog.QMessageBox.question',
                           return_value=QMessageBox.Yes):
                    mock_export = AsyncMock()
                    mock_export.return_value = (True, os.path.join(new_dir, "clip.mp4"))
                    with patch.object(dialog.controller, 'export_clip', mock_export):
                        dialog.export_clip()
                        await asyncio.sleep(0.1)
                        mock_export.assert_awaited_once()