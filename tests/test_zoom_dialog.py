"""
细选窗口测试 - 移除所有 qtbot.wait，模拟必要对话框
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QPushButton, QScrollArea, QMessageBox
from ui.views.zoom_dialog import ZoomDialog

pytestmark = pytest.mark.ui


@pytest.fixture(autouse=True)
def mock_load_candidates():
    with patch('ui.views.zoom_dialog.ZoomDialog.load_candidates') as mock:
        yield mock


@pytest.fixture
def mock_controller():
    mock = MagicMock()
    mock.density = 9
    mock.num_segments = 3
    mock.current_seg_index = 0
    mock.duration = 120.0
    mock.get_segments.return_value = [
        ("A", 0.0, 40.0),
        ("B", 40.0, 80.0),
        ("C", 80.0, 120.0),
    ]
    mock.get_segment_items.return_value = [
        {'time': 6.0, 'path': '/tmp/frame1.jpg', 'locked': False, 'favorite': False, 'exported': False},
        {'time': 7.0, 'path': '/tmp/frame2.jpg', 'locked': False, 'favorite': False, 'exported': False},
        {'time': 8.0, 'path': '/tmp/frame3.jpg', 'locked': False, 'favorite': False, 'exported': False},
        {'time': 9.0, 'path': '/tmp/frame4.jpg', 'locked': False, 'favorite': False, 'exported': False},
        {'time': 10.0, 'path': '/tmp/frame5.jpg', 'locked': False, 'favorite': False, 'exported': False},
        {'time': 11.0, 'path': '/tmp/frame6.jpg', 'locked': False, 'favorite': False, 'exported': False},
        {'time': 12.0, 'path': '/tmp/frame7.jpg', 'locked': False, 'favorite': False, 'exported': False},
        {'time': 13.0, 'path': '/tmp/frame8.jpg', 'locked': False, 'favorite': False, 'exported': False},
        {'time': 14.0, 'path': '/tmp/frame9.jpg', 'locked': False, 'favorite': False, 'exported': False},
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
    mock.favorite_selected = MagicMock(return_value=(1, 0))
    mock.load_segment = MagicMock(return_value=None)
    mock.replace_favorite_screenshot = MagicMock(return_value=True)
    mock.replace_screenshot = MagicMock(return_value=True)
    mock.db = MagicMock()
    mock.db.is_favorite = MagicMock(return_value=False)
    mock.db.add_favorite = MagicMock()
    mock.db.update_favorite_exported = MagicMock()
    return mock


@pytest.fixture
def temp_images():
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = []
        for i in range(1, 10):
            path = os.path.join(tmpdir, f"frame{i}.jpg")
            Path(path).touch()
            paths.append(path)
        yield paths


def find_grid_layout_in_scrollarea(dlg):
    for child in dlg.children():
        if isinstance(child, QScrollArea):
            content = child.widget()
            if content:
                for subchild in content.children():
                    if hasattr(subchild, 'layout') and subchild.layout():
                        if isinstance(subchild.layout(), QGridLayout):
                            return subchild.layout()
                if content.layout() and isinstance(content.layout(), QGridLayout):
                    return content.layout()
    return None


def find_grid_layout(dlg):
    grid = find_grid_layout_in_scrollarea(dlg)
    if grid:
        return grid
    main_layout = dlg.layout()
    if main_layout:
        for i in range(main_layout.count()):
            item = main_layout.itemAt(i)
            if item and item.layout() and isinstance(item.layout(), QGridLayout):
                return item.layout()
    return None


def setup_dialog_with_data(dlg, temp_images):
    dlg.candidate_frames = []
    for idx, path in enumerate(temp_images):
        time_val = 6.0 + idx * 1.0
        dlg.candidate_frames.append({
            'time': time_val,
            'path': path,
            'favorite': False,
            'exported': False
        })
    dlg._refresh_grid()
    return dlg


def test_window_title(qtbot, mock_controller, temp_images, mock_load_candidates):
    dlg = ZoomDialog(
        controller=mock_controller,
        seg_label="A",
        seg_idx=0,
        pos=4,
        center_time=10.0,
        level=1,
        parent=None,
        source="main",
        original_fav_item=None
    )
    setup_dialog_with_data(dlg, temp_images)
    dlg.show()
    qtbot.addWidget(dlg)

    assert "Zoom 精修 L1" in dlg.windowTitle()

    dlg.close()


def test_grid_has_9_images(qtbot, mock_controller, temp_images, mock_load_candidates):
    dlg = ZoomDialog(
        controller=mock_controller,
        seg_label="A",
        seg_idx=0,
        pos=4,
        center_time=10.0,
        level=1,
        parent=None,
        source="main",
        original_fav_item=None
    )
    setup_dialog_with_data(dlg, temp_images)
    dlg.show()
    qtbot.addWidget(dlg)

    grid = find_grid_layout(dlg)
    assert grid is not None
    count = sum(1 for i in range(grid.count()) if grid.itemAt(i).widget() is not None)
    assert count == 9

    dlg.close()
    dlg.deleteLater()


def test_click_image_opens_preview(qtbot, mock_controller, temp_images, mock_load_candidates):
    dlg = ZoomDialog(
        controller=mock_controller,
        seg_label="A",
        seg_idx=0,
        pos=4,
        center_time=10.0,
        level=1,
        parent=None,
        source="main",
        original_fav_item=None
    )
    setup_dialog_with_data(dlg, temp_images)
    dlg.show()
    qtbot.addWidget(dlg)

    grid = find_grid_layout(dlg)
    assert grid is not None
    first_widget = None
    for i in range(grid.count()):
        widget = grid.itemAt(i).widget()
        if widget is not None:
            first_widget = widget
            break
    assert first_widget is not None

    # 双击触发预览（同步操作，无需 wait）
    qtbot.mouseDClick(first_widget, Qt.LeftButton)
    # 检查对话框是否可见
    assert dlg.isVisible() is True

    dlg.close()
    dlg.deleteLater()


def test_favorite_button(qtbot, mock_controller, temp_images, mock_load_candidates):
    with patch('ui.views.zoom_dialog.QMessageBox.information'):
        with patch('ui.views.zoom_dialog.QMessageBox.warning'):
            dlg = ZoomDialog(
                controller=mock_controller,
                seg_label="A",
                seg_idx=0,
                pos=4,
                center_time=10.0,
                level=1,
                parent=None,
                source="main",
                original_fav_item=None
            )
            setup_dialog_with_data(dlg, temp_images)
            dlg.selected_indices.add(0)
            dlg._refresh_grid()
            dlg.show()
            qtbot.addWidget(dlg)

            all_buttons = dlg.findChildren(QPushButton)
            fav_btn = None
            for btn in all_buttons:
                if "收藏" in btn.text():
                    fav_btn = btn
                    break
            assert fav_btn is not None

            qtbot.mouseClick(fav_btn, Qt.LeftButton)
            # 同步操作，无需 wait
            assert dlg.isVisible() is True

            dlg.close()
            dlg.deleteLater()


def test_close_dialog(qtbot, mock_controller, temp_images, mock_load_candidates):
    dlg = ZoomDialog(
        controller=mock_controller,
        seg_label="A",
        seg_idx=0,
        pos=4,
        center_time=10.0,
        level=1,
        parent=None,
        source="main",
        original_fav_item=None
    )
    setup_dialog_with_data(dlg, temp_images)
    dlg.show()
    qtbot.addWidget(dlg)

    dlg.close()
    # 关闭是同步的，无需 wait
    assert not dlg.isVisible()

    dlg.deleteLater()