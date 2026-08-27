"""
排除区间对话框测试 - 不显示窗口，直接测试逻辑
"""

import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt, QTime
from PySide6.QtWidgets import QPushButton, QLabel, QMessageBox
from ui.views.exclude_dialog import ExcludeDialog

pytestmark = pytest.mark.ui


@pytest.fixture
def sample_ranges():
    return [(5.0, 10.0), (20.0, 30.0), (50.0, 60.0)]


@pytest.fixture
def dialog(qtbot, sample_ranges):
    dlg = ExcludeDialog(sample_ranges, duration=120.0, parent=None)
    # 不显示窗口
    qtbot.addWidget(dlg)
    return dlg


def test_init_displays_ranges(qtbot, dialog, sample_ranges):
    assert dialog.list_widget.count() == len(sample_ranges)
    for i, (start, end) in enumerate(sample_ranges):
        item = dialog.list_widget.item(i)
        widget = dialog.list_widget.itemWidget(item)
        labels = widget.findChildren(QLabel)
        assert len(labels) >= 1
        label_text = labels[0].text()
        assert dialog._format_time(start) in label_text
        assert dialog._format_time(end) in label_text


def test_add_range_success(qtbot, dialog):
    initial_count = dialog.list_widget.count()
    dialog.start_time_edit.setTime(QTime(0, 1, 0))
    dialog.end_time_edit.setTime(QTime(0, 2, 0))
    dialog.add_btn.click()
    assert dialog.list_widget.count() == initial_count + 1
    ranges = dialog.get_ranges()
    assert (60.0, 120.0) in ranges


def test_add_range_overlap_fails(qtbot, dialog, sample_ranges):
    initial_count = dialog.list_widget.count()
    dialog.start_time_edit.setTime(QTime(0, 0, 6))
    dialog.end_time_edit.setTime(QTime(0, 0, 8))
    dialog.add_btn.click()
    assert dialog.list_widget.count() == initial_count
    assert dialog.get_ranges() == sample_ranges


def test_add_range_invalid_order_fails(qtbot, dialog):
    initial_count = dialog.list_widget.count()
    dialog.start_time_edit.setTime(QTime(0, 0, 10))
    dialog.end_time_edit.setTime(QTime(0, 0, 5))
    dialog.add_btn.click()
    assert dialog.list_widget.count() == initial_count


def test_add_range_exceeds_duration_fails(qtbot, dialog):
    initial_count = dialog.list_widget.count()
    dialog.start_time_edit.setTime(QTime(0, 1, 0))
    dialog.end_time_edit.setTime(QTime(0, 2, 30))
    dialog.add_btn.click()
    assert dialog.list_widget.count() == initial_count


def test_edit_range_via_double_click(qtbot, dialog, sample_ranges):
    item = dialog.list_widget.item(0)
    dialog._on_item_double_clicked(item)

    assert dialog._editing_index == 0
    assert dialog.update_btn.isEnabled() is True
    assert dialog.cancel_edit_btn.isEnabled() is True
    assert dialog.add_btn.isEnabled() is False

    start, end = sample_ranges[0]
    expected_start = dialog._seconds_to_time(start)
    expected_end = dialog._seconds_to_time(end)
    assert dialog.start_time_edit.time().hour() == expected_start.hour()
    assert dialog.start_time_edit.time().minute() == expected_start.minute()
    assert dialog.start_time_edit.time().second() == expected_start.second()


def test_edit_range_via_edit_button(qtbot, dialog, sample_ranges):
    item = dialog.list_widget.item(0)
    widget = dialog.list_widget.itemWidget(item)
    edit_btn = None
    for child in widget.children():
        if isinstance(child, QPushButton) and child.text() == "✏️ 编辑":
            edit_btn = child
            break
    assert edit_btn is not None
    edit_btn.click()

    assert dialog._editing_index == 0
    assert dialog.update_btn.isEnabled() is True
    assert dialog.cancel_edit_btn.isEnabled() is True
    assert dialog.add_btn.isEnabled() is False


def test_update_range(qtbot, dialog, sample_ranges):
    item = dialog.list_widget.item(0)
    widget = dialog.list_widget.itemWidget(item)
    edit_btn = None
    for child in widget.children():
        if isinstance(child, QPushButton) and child.text() == "✏️ 编辑":
            edit_btn = child
            break
    assert edit_btn is not None
    edit_btn.click()

    dialog.start_time_edit.setTime(QTime(0, 0, 8))
    dialog.end_time_edit.setTime(QTime(0, 0, 12))
    dialog.update_btn.click()

    ranges = dialog.get_ranges()
    assert (8.0, 12.0) in ranges
    assert (5.0, 10.0) not in ranges

    assert dialog.update_btn.isEnabled() is True
    assert dialog.cancel_edit_btn.isEnabled() is True
    assert dialog.add_btn.isEnabled() is False
    assert dialog._editing_index is not None


def test_cancel_edit(qtbot, dialog, sample_ranges):
    item = dialog.list_widget.item(0)
    widget = dialog.list_widget.itemWidget(item)
    edit_btn = None
    for child in widget.children():
        if isinstance(child, QPushButton) and child.text() == "✏️ 编辑":
            edit_btn = child
            break
    assert edit_btn is not None
    edit_btn.click()

    assert dialog._editing_index == 0
    dialog.cancel_edit_btn.click()

    assert dialog._editing_index is None
    assert dialog.update_btn.isEnabled() is False
    assert dialog.cancel_edit_btn.isEnabled() is False
    assert dialog.add_btn.isEnabled() is True


def test_remove_selected(qtbot, dialog, sample_ranges):
    initial_count = dialog.list_widget.count()
    dialog.list_widget.setCurrentRow(0)

    all_buttons = dialog.findChildren(QPushButton)
    remove_btn = None
    for btn in all_buttons:
        if btn.text() == "删除选中":
            remove_btn = btn
            break
    assert remove_btn is not None

    remove_btn.click()

    assert dialog.list_widget.count() == initial_count - 1
    ranges = dialog.get_ranges()
    assert len(ranges) == initial_count - 1
    assert sample_ranges[0] not in ranges


def test_remove_selected_while_editing_fails(qtbot, dialog):
    item = dialog.list_widget.item(0)
    widget = dialog.list_widget.itemWidget(item)
    edit_btn = None
    for child in widget.children():
        if isinstance(child, QPushButton) and child.text() == "✏️ 编辑":
            edit_btn = child
            break
    assert edit_btn is not None
    edit_btn.click()

    all_buttons = dialog.findChildren(QPushButton)
    remove_btn = None
    for btn in all_buttons:
        if btn.text() == "删除选中":
            remove_btn = btn
            break
    assert remove_btn is not None

    initial_count = dialog.list_widget.count()
    remove_btn.click()

    assert dialog.list_widget.count() == initial_count


def test_clear_all(qtbot, dialog):
    if dialog._editing_index is not None:
        dialog._cancel_edit()

    all_buttons = dialog.findChildren(QPushButton)
    clear_btn = None
    for btn in all_buttons:
        if btn.text() == "清空所有":
            clear_btn = btn
            break
    assert clear_btn is not None

    with patch('ui.views.exclude_dialog.QMessageBox.question', return_value=QMessageBox.Yes):
        clear_btn.click()
    assert dialog.list_widget.count() == 0
    assert dialog.get_ranges() == []


def test_get_ranges_returns_correct_list(qtbot, dialog, sample_ranges):
    assert dialog.get_ranges() == sample_ranges


def test_accept_saves_ranges(qtbot, dialog, sample_ranges):
    mock_parent = MagicMock()
    mock_parent.controller = MagicMock()
    dialog.parent_view = mock_parent

    dialog.accept()

    mock_parent.controller.set_excluded_ranges.assert_called_once_with(
        sample_ranges, save=True
    )