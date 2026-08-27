"""
测试键盘快捷键（仅保留稳定测试，跳过 Delete 键测试）
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtWidgets import QMessageBox
from ui.views.segment_view import SegmentView

pytestmark = pytest.mark.ui


class TestKeyboardShortcuts:

    @pytest.fixture
    def view_with_grid(self, qtbot, mock_controller):
        view = SegmentView()
        view.controller = mock_controller
        view.controller.get_segments.return_value = [("A", 0.0, 40.0)]
        with tempfile.TemporaryDirectory() as tmpdir:
            items = []
            for i in range(9):
                path = os.path.join(tmpdir, f"frame_{i}.jpg")
                pixmap = QPixmap(100, 100)
                pixmap.fill(QColor(128 + i * 10, 128, 128))
                pixmap.save(path, "JPEG")
                items.append({'time': i*10.0, 'path': path, 'locked': False, 'favorite': False, 'exported': False})
            view.controller.get_segment_items.return_value = items
            view.controller.current_seg_index = 0
            view._refresh_video_list()
            view._rebuild_seg_buttons()
            view._refresh_grid()
            qtbot.addWidget(view)
            view._tmpdir = tmpdir
            yield view

    def test_ctrl_a_select_all(self, qtbot, view_with_grid):
        view = view_with_grid
        view.select_all()
        assert len(view.selected_indices) == 9

    def test_ctrl_d_deselect_all(self, qtbot, view_with_grid):
        view = view_with_grid
        view.select_all()
        view.deselect_all()
        assert len(view.selected_indices) == 0

    def test_space_opens_preview_single_selected(self, qtbot, view_with_grid):
        view = view_with_grid
        view.selected_indices.add((0, 4))
        view._refresh_grid()
        with patch('ui.views.segment_view.QMessageBox.warning'):
            with patch('ui.views.segment_view.ZoomPreviewDialog') as mock_preview:
                view._preview_selected_screenshot()
                mock_preview.assert_called_once()

    def test_arrow_keys_move_selection(self, qtbot, view_with_grid):
        view = view_with_grid
        view.selected_indices.add((0, 3))
        view._refresh_grid()
        view._move_selection(Qt.Key_Right)
        assert (0, 4) in view.selected_indices
        view._move_selection(Qt.Key_Left)
        assert (0, 3) in view.selected_indices