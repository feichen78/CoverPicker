"""
UI 层测试 - 显示窗口但安全清理（修正可见性问题）
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton

pytestmark = pytest.mark.ui


class TestSegmentView:

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
        # 添加 db mock 以便关闭
        mock.db = MagicMock()
        mock.db.close = MagicMock()
        yield mock
        # 测试结束后关闭数据库连接
        if hasattr(mock, 'db') and hasattr(mock.db, 'close'):
            mock.db.close()

    @pytest.fixture
    def view(self, qtbot, mock_controller):
        from ui.views.segment_view import SegmentView
        view = SegmentView()
        view.controller = mock_controller
        view._rebuild_seg_buttons()
        view._refresh_video_list()
        view.show()
        qtbot.addWidget(view)
        yield view
        # 清理
        view.close()
        QApplication.processEvents()

    def test_video_list_display(self, qtbot, view):
        assert view.video_list is not None
        assert view.info_name is not None
        assert view.info_duration is not None
        assert view.info_resolution is not None
        assert view.info_size is not None
        assert view.info_path is not None

    def test_seg_buttons_exist(self, qtbot, view):
        assert len(view.seg_buttons) == 3
        assert view.seg_buttons[0].text().startswith("A")
        assert view.seg_buttons[1].text().startswith("B")
        assert view.seg_buttons[2].text().startswith("C")

    def test_density_buttons_exist(self, qtbot, view):
        assert len(view.density_buttons) == 4
        assert view.density_buttons[0].isChecked() is True

    def test_bottom_buttons_exist(self, qtbot, view):
        assert view.select_all_btn is not None, "全选按钮不存在"
        assert view.undo_btn is not None, "撤销按钮不存在"
        assert view.redo_btn is not None, "重做按钮不存在"

        all_buttons = view.findChildren(QPushButton)
        export_btn = None
        for btn in all_buttons:
            if "导出" in btn.text():
                export_btn = btn
                break
        assert export_btn is not None, "未找到导出按钮"

    def test_search_input_clear_button(self, qtbot, view):
        # 初始状态：清空按钮不可见
        assert view.clear_search_btn.isVisible() is False

        # 模拟输入文字
        view._on_search_text_changed("test")
        assert view.clear_search_btn.isVisible() is True

        # 清空文字
        view._on_search_text_changed("")
        assert view.clear_search_btn.isVisible() is False

        view.clear_search_btn.setVisible(True)
        assert view.clear_search_btn.isVisible() is True
        view.clear_search_btn.setVisible(False)
        assert view.clear_search_btn.isVisible() is False

    def test_select_all_button_toggle(self, qtbot, view):
        view.controller.get_segment_items.return_value = [
            {'time': 10.0, 'path': None, 'locked': False, 'favorite': False, 'exported': False},
            {'time': 20.0, 'path': None, 'locked': False, 'favorite': False, 'exported': False},
        ]
        view.controller.current_seg_index = 0
        view._on_data_changed()
        assert view.select_all_btn.isEnabled() is True
        view.select_all_btn.click()
        assert len(view.selected_indices) == 2
        view.select_all_btn.click()
        assert len(view.selected_indices) == 0


@pytest.mark.asyncio
class TestSegmentViewAsync:

    @pytest.fixture
    def mock_controller_async(self):
        mock = MagicMock()
        mock.density = 9
        mock.num_segments = 3
        mock.current_seg_index = 0
        mock.get_segments.return_value = [
            ("A", 0.0, 40.0),
            ("B", 40.0, 80.0),
            ("C", 80.0, 120.0),
        ]
        mock.get_segment_items.return_value = []
        mock.get_video_name.return_value = "test.mp4"
        mock.get_video_path.return_value = "test.mp4"
        mock.get_video_state_icon.return_value = ""
        mock.get_favorites_count.return_value = 0
        mock.can_undo.return_value = False
        mock.can_redo.return_value = False
        mock.load_video = MagicMock(return_value=True)
        mock.load_segment = MagicMock(return_value=None)
        mock.refresh_unlocked = MagicMock(return_value=0)
        mock.reset_segment = MagicMock(return_value=None)
        mock.db = MagicMock()
        mock.db.close = MagicMock()
        yield mock
        if hasattr(mock, 'db') and hasattr(mock.db, 'close'):
            mock.db.close()

    @patch('ui.views.segment_view.SegmentView._load_video')
    async def test_on_video_selected_calls_load(self, mock_load_video, qtbot):
        from ui.views.segment_view import SegmentView
        view = SegmentView()
        view._load_video = mock_load_video
        mock_item = MagicMock()
        mock_item.data.return_value = "test_video.mp4"
        view.on_video_selected(mock_item)
        await asyncio.sleep(0.1)
        mock_load_video.assert_called_once_with("test_video.mp4")
        view.close()
        QApplication.processEvents()