"""
UI 交互测试 - 修正 export_selected 的 patch 路径
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton, QMessageBox
from ui.views.segment_view import SegmentView

pytestmark = pytest.mark.ui


class TestSegmentViewInteraction:

    @pytest.fixture
    def mock_controller(self):
        mock = MagicMock()
        mock.density = 9
        mock.num_segments = 3
        mock.current_seg_index = 0
        mock.get_segments.return_value = [
            ("A", 0.0, 40.0),
            ("B", 40.0, 80.0),
            ("C", 80.0, 120.0),
        ]
        mock.get_segment_items.return_value = [
            {'time': 10.0, 'path': None, 'locked': False, 'favorite': False, 'exported': False},
            {'time': 20.0, 'path': None, 'locked': False, 'favorite': False, 'exported': False},
            {'time': 30.0, 'path': None, 'locked': False, 'favorite': False, 'exported': False},
        ]
        mock.get_video_name.return_value = "test.mp4"
        mock.get_video_path.return_value = "test.mp4"
        mock.get_video_state_icon.return_value = ""
        mock.get_favorites_count.return_value = 0
        mock.can_undo.return_value = False
        mock.can_redo.return_value = False
        mock.get_cache_size_mb.return_value = 0.0
        mock.get_cache_file_count.return_value = 0
        mock.get_current_segment.return_value = ("A", 0.0, 40.0)
        mock.load_segment = AsyncMock(return_value=None)
        mock.favorite_selected = MagicMock(return_value=(1, 0))
        mock.unfavorite_selected = MagicMock(return_value=1)
        mock.lock_selected = MagicMock(return_value=1)
        mock.unlock_selected = MagicMock(return_value=1)
        mock.export_selected = MagicMock(return_value=(1, []))
        return mock

    @pytest.fixture
    def view(self, qtbot, mock_controller):
        view = SegmentView()
        view.controller = mock_controller
        view._rebuild_seg_buttons()
        view._refresh_video_list()
        view.show()
        qtbot.addWidget(view)
        return view

    @pytest.mark.asyncio
    async def test_seg_button_click(self, qtbot, view):
        assert len(view.seg_buttons) >= 2
        view.seg_buttons[1].click()
        await asyncio.sleep(0.1)
        view.controller.load_segment.assert_called_once_with(1, restore_locks=True, randomize=False)

    def test_grid_refresh_after_data_change(self, qtbot, view):
        view._on_data_changed()
        assert view.grid_layout.count() >= 3

    def test_favorite_selected(self, qtbot, view):
        with patch('ui.views.segment_view.QMessageBox.information'):
            with patch('ui.views.segment_view.QMessageBox.warning'):
                view.selected_indices.add((0, 0))
                view._refresh_grid()
                all_buttons = view.findChildren(QPushButton)
                fav_btn = None
                for btn in all_buttons:
                    if "收藏" in btn.text() and "取消" not in btn.text():
                        fav_btn = btn
                        break
                assert fav_btn is not None
                fav_btn.click()
                view.controller.favorite_selected.assert_called_once_with("A", [0])

    def test_unfavorite_selected(self, qtbot, view):
        with patch('ui.views.segment_view.QMessageBox.question', return_value=QMessageBox.Yes):
            with patch('ui.views.segment_view.QMessageBox.information'):
                with patch('ui.views.segment_view.QMessageBox.warning'):
                    view.selected_indices.add((0, 0))
                    view._refresh_grid()
                    all_buttons = view.findChildren(QPushButton)
                    unfav_btn = None
                    for btn in all_buttons:
                        if "取消收藏" in btn.text():
                            unfav_btn = btn
                            break
                    assert unfav_btn is not None
                    unfav_btn.click()
                    view.controller.unfavorite_selected.assert_called_once_with("A", [0])

    def test_lock_selected(self, qtbot, view):
        view.selected_indices.add((0, 0))
        view._refresh_grid()
        all_buttons = view.findChildren(QPushButton)
        lock_btn = None
        for btn in all_buttons:
            if "锁定" in btn.text():
                lock_btn = btn
                break
        assert lock_btn is not None
        lock_btn.click()
        view.controller.lock_selected.assert_called_once_with("A", [0])

    def test_unlock_selected(self, qtbot, view):
        view.selected_indices.add((0, 0))
        view._refresh_grid()
        all_buttons = view.findChildren(QPushButton)
        unlock_btn = None
        for btn in all_buttons:
            if "解锁" in btn.text():
                unlock_btn = btn
                break
        assert unlock_btn is not None
        unlock_btn.click()
        view.controller.unlock_selected.assert_called_once_with("A", [0])

    def test_export_selected(self, qtbot, view):
        view.selected_indices.add((0, 0))
        view._refresh_grid()
        # 模拟 QFileDialog.getExistingDirectory 和 QMessageBox 对话框
        with patch('ui.views.segment_view.QFileDialog.getExistingDirectory', return_value="/tmp"):
            with patch('ui.views.segment_view.QMessageBox.information'):
                with patch('ui.views.segment_view.QMessageBox.warning'):
                    all_buttons = view.findChildren(QPushButton)
                    export_btn = None
                    for btn in all_buttons:
                        if "导出" in btn.text():
                            export_btn = btn
                            break
                    assert export_btn is not None
                    export_btn.click()
                    view.controller.export_selected.assert_called_once()
                    args, _ = view.controller.export_selected.call_args
                    assert args[0] == "A"

    def test_select_all_toggle(self, qtbot, view):
        view.controller.get_segment_items.return_value = [
            {'time': 10.0, 'path': None, 'locked': False, 'favorite': False, 'exported': False},
            {'time': 20.0, 'path': None, 'locked': False, 'favorite': False, 'exported': False},
        ]
        view._on_data_changed()
        select_all_btn = view.select_all_btn
        assert select_all_btn.isEnabled() is True
        select_all_btn.click()
        assert len(view.selected_indices) == 2
        select_all_btn.click()
        assert len(view.selected_indices) == 0