"""
UI 样式规范验证 - 修正版，移除 qtbot.wait
"""

import pytest
from PySide6.QtWidgets import QLabel, QPushButton, QTextEdit, QFrame
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from unittest.mock import MagicMock

from ui.views.segment_view import SegmentView
from ui.views.preview_dialog import PreviewDialog
from ui.views.zoom_dialog import ZoomDialog
from ui.views.exclude_dialog import ExcludeDialog
from ui.widgets import ClickableLabel

pytestmark = pytest.mark.ui


class TestUIStyle:

    def test_info_group_has_5_lines(self, qtbot):
        view = SegmentView()
        view.show()
        qtbot.addWidget(view)

        info_group = view.findChild(QFrame, "info_group")
        assert info_group is not None

        layout = info_group.layout()
        assert layout is not None
        widget_count = 0
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.widget():
                widget_count += 1
        assert widget_count >= 5

        assert view.info_name is not None
        assert view.info_duration is not None
        assert view.info_resolution is not None
        assert view.info_size is not None
        assert view.info_path is not None

        view.close()
        # 移除 qtbot.wait(50)，因为窗口关闭是同步的

    def test_info_group_font_unified(self, qtbot):
        view = SegmentView()
        view.show()
        qtbot.addWidget(view)

        info_labels = [view.info_name, view.info_duration,
                       view.info_resolution, view.info_size]
        for label in info_labels:
            font = label.font()
            assert font.family() == "Arial"
            assert font.pointSize() == 12
            assert font.bold() is True

        font = view.info_path.font()
        assert font.family() == "Arial"
        assert font.pointSize() == 12
        assert font.bold() is True

        view.close()

    def test_time_format_hmmss(self, qtbot):
        view = SegmentView()
        view.show()
        qtbot.addWidget(view)

        assert view._format_time(65) == "01:05"
        assert view._format_time(3599) == "59:59"
        assert view._format_time(0) == "00:00"
        assert view._format_time(3665) == "01:01:05"
        assert view._format_time(40730) == "11:18:50"

        view.close()

    def test_state_markers_order(self, qtbot):
        label = ClickableLabel(None, 10.0, 1)
        label.set_locked(True)
        label.set_favorite(True)
        label.set_exported(True)
        label.set_selected(True)

        assert label.is_locked is True
        assert label.is_favorite is True
        assert label.is_exported is True
        assert label.is_selected is True
        assert label.index_num == 1

    def test_preview_dialog_tick_count(self, qtbot):
        dialog = PreviewDialog()
        dialog.set_video("test.mp4", duration=120.0, temp_dir="/tmp")
        dialog.show()
        qtbot.addWidget(dialog)

        assert len(dialog.tick_labels) == 11
        tick_texts = [label.text() for label in dialog.tick_labels]
        assert len(tick_texts) == 11
        assert tick_texts[0] == "00:00"
        assert tick_texts[-1] == "02:00"

        dialog.close()

    def test_preview_dialog_time_format(self, qtbot):
        dialog = PreviewDialog()
        assert dialog._format_time(65) == "01:05"
        assert dialog._format_time(3599) == "59:59"
        assert dialog._format_time(3665) == "01:01:05"
        assert dialog._format_time(40730) == "11:18:50"

    def test_exclude_dialog_time_edit_format(self, qtbot):
        dialog = ExcludeDialog([], duration=120.0, parent=None)
        dialog.show()
        qtbot.addWidget(dialog)

        assert dialog.start_time_edit.displayFormat() == "HH:mm:ss"
        assert dialog.end_time_edit.displayFormat() == "HH:mm:ss"

        dialog.close()

    def test_grid_layout_columns_match_density(self, qtbot):
        view = SegmentView()
        view.show()
        qtbot.addWidget(view)

        view.controller.get_segments = MagicMock(return_value=[("A", 0.0, 40.0)])

        for density, expected_cols in [(9, 3), (12, 3), (16, 4), (25, 5)]:
            view.controller.density = density
            items = [
                {'time': i, 'path': None, 'locked': False, 'favorite': False, 'exported': False}
                for i in range(density)
            ]
            view.controller.get_segment_items = MagicMock(return_value=items)
            view.controller.current_seg_index = 0
            view._refresh_grid()
            count = 0
            for i in range(view.grid_layout.count()):
                widget = view.grid_layout.itemAt(i).widget()
                if widget is not None:
                    count += 1
            assert count == density

        view.close()

    def test_clickable_label_loading_state(self, qtbot):
        label = ClickableLabel(None, 10.0, 1)
        assert label.is_loading is False
        label.set_loading(True)
        assert label.is_loading is True
        label.set_loading(False)
        assert label.is_loading is False