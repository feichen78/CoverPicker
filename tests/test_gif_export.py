"""
测试 GIF 导出对话框参数（不涉及 GUI 操作，避免批量测试崩溃）
"""

import pytest
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QDialog

from ui.views.preview_dialog import GIFExportDialog

pytestmark = pytest.mark.ui


class TestGIFExport:

    def test_gif_export_dialog_default_params(self, qtbot):
        dlg = GIFExportDialog(parent=None)
        qtbot.addWidget(dlg)

        assert dlg.fps_combo.currentText() == "5"
        assert dlg.size_combo.currentText() == "25%"
        assert dlg.loop_combo.currentText() == "无限"

        fps, scale, loop = dlg.get_params()
        assert fps == 5
        assert scale == 0.25
        assert loop == 0

        dlg.close()
        dlg.deleteLater()

    def test_gif_export_dialog_custom_params(self, qtbot):
        dlg = GIFExportDialog(parent=None)
        qtbot.addWidget(dlg)

        dlg.fps_combo.setCurrentText("15")
        dlg.size_combo.setCurrentText("50%")
        dlg.loop_combo.setCurrentText("3")

        fps, scale, loop = dlg.get_params()
        assert fps == 15
        assert scale == 0.5
        assert loop == 3

        dlg.close()
        dlg.deleteLater()

    def test_gif_export_dialog_scale_values(self, qtbot):
        dlg = GIFExportDialog(parent=None)
        qtbot.addWidget(dlg)

        dlg.size_combo.setCurrentText("原尺寸")
        _, scale, _ = dlg.get_params()
        assert scale == 1.0

        dlg.size_combo.setCurrentText("50%")
        _, scale, _ = dlg.get_params()
        assert scale == 0.5

        dlg.size_combo.setCurrentText("25%")
        _, scale, _ = dlg.get_params()
        assert scale == 0.25

        dlg.close()
        dlg.deleteLater()

    def test_gif_export_dialog_loop_values(self, qtbot):
        dlg = GIFExportDialog(parent=None)
        qtbot.addWidget(dlg)

        dlg.loop_combo.setCurrentText("1")
        _, _, loop = dlg.get_params()
        assert loop == 1

        dlg.loop_combo.setCurrentText("5")
        _, _, loop = dlg.get_params()
        assert loop == 5

        dlg.loop_combo.setCurrentText("无限")
        _, _, loop = dlg.get_params()
        assert loop == 0

        dlg.close()
        dlg.deleteLater()