"""
测试主窗口布局几何结构
"""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton

from ui.views.segment_view import SegmentView

pytestmark = pytest.mark.ui


class TestLayoutGeometry:

    @pytest.fixture
    def view(self, qtbot, mock_controller):
        view = SegmentView()
        view.controller = mock_controller
        # 模拟加载视频以生成分区按钮
        view.controller.get_segments.return_value = [
            ("A", 0.0, 40.0),
            ("B", 40.0, 80.0),
            ("C", 80.0, 120.0),
        ]
        view._rebuild_seg_buttons()
        view._refresh_video_list()
        view.show()
        qtbot.addWidget(view)
        return view

    def test_main_layout_has_two_panels(self, qtbot, view):
        main_layout = view.layout()
        assert main_layout is not None
        assert isinstance(main_layout, QHBoxLayout)
        assert main_layout.count() >= 2

        left_panel = main_layout.itemAt(0).widget()
        right_panel = main_layout.itemAt(1).widget()
        assert left_panel is not None
        assert right_panel is not None
        # 左面板宽度应为 220px
        assert left_panel.width() == 220 or left_panel.minimumWidth() == 220

    def test_left_panel_contains_video_list_and_info(self, qtbot, view):
        """验证左面板包含视频列表和信息区"""
        main_layout = view.layout()
        left_panel = main_layout.itemAt(0).widget()
        assert left_panel is not None
        left_layout = left_panel.layout()
        assert left_layout is not None
        assert isinstance(left_layout, QVBoxLayout)

        # 使用 findChild 查找 info_group（因为 setup_ui 中设置了 objectName）
        info_group = view.findChild(QWidget, "info_group")
        assert info_group is not None, "info_group 未找到（检查 objectName 是否为 'info_group'）"

        video_list = getattr(view, 'video_list', None)
        assert video_list is not None, "video_list 不存在"

        # 验证顺序：video_list 在 info_group 之上
        list_index = -1
        info_index = -1
        for i in range(left_layout.count()):
            widget = left_layout.itemAt(i).widget()
            if widget == video_list:
                list_index = i
            elif widget == info_group:
                info_index = i
        assert list_index != -1 and info_index != -1
        assert list_index < info_index

    def test_info_group_has_5_lines(self, qtbot, view):
        """验证信息区包含 5 行"""
        info_group = view.findChild(QWidget, "info_group")
        assert info_group is not None
        layout = info_group.layout()
        assert layout is not None

        # 验证具体控件存在
        assert view.info_name is not None
        assert view.info_duration is not None
        assert view.info_resolution is not None
        assert view.info_size is not None
        assert view.info_path is not None

    def test_right_panel_contains_top_bar_control_and_grid(self, qtbot, view):
        """验证右面板包含顶部文件名、控制栏和截图网格"""
        main_layout = view.layout()
        right_panel = main_layout.itemAt(1).widget()
        assert right_panel is not None
        right_layout = right_panel.layout()
        assert right_layout is not None
        assert isinstance(right_layout, QVBoxLayout)

        assert view.video_name_label is not None
        assert view.scroll is not None

        scroll_index = -1
        for i in range(right_layout.count()):
            widget = right_layout.itemAt(i).widget()
            if widget == view.scroll:
                scroll_index = i
                break
        assert scroll_index != -1

        scroll = view.scroll
        grid_widget = scroll.widget()
        assert grid_widget is not None
        assert grid_widget.layout() is not None

    def test_seg_buttons_layout_is_horizontal(self, qtbot, view):
        """验证分区按钮以水平布局排列"""
        seg_layout = view.seg_buttons_layout
        assert seg_layout is not None
        assert isinstance(seg_layout, QHBoxLayout)
        assert len(view.seg_buttons) >= 1

        for btn in view.seg_buttons:
            assert btn.parent() is not None

    def test_density_buttons_group(self, qtbot, view):
        """验证密度按钮组存在且互斥"""
        density_btns = view.density_buttons
        assert len(density_btns) == 4
        checked = [btn for btn in density_btns if btn.isChecked()]
        assert len(checked) == 1
        assert checked[0].text() == "9"

    def test_bottom_bar_buttons_exist(self, qtbot, view):
        """验证底部操作栏包含所有必需按钮"""
        required_buttons = [
            "收藏", "取消收藏", "收藏夹", "锁定", "解锁",
            "刷新", "重抽", "细选", "导出", "打开导出夹",
            "全选", "撤销", "重做"
        ]
        all_buttons = view.findChildren(QPushButton)
        button_texts = {btn.text() for btn in all_buttons}

        for req in required_buttons:
            found = any(req in text for text in button_texts)
            assert found, f"未找到按钮: {req}"

    def test_preview_toggle_button_present(self, qtbot, view):
        """验证预览切换按钮存在且可点击"""
        assert view.preview_toggle_btn is not None
        assert view.preview_toggle_btn.isCheckable() is True