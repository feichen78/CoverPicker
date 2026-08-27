"""
测试收藏夹弹窗 - 不显示窗口，直接测试逻辑
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QLabel, QWidget, QFileDialog
from ui.dialogs.favorites_dialog import FavoritesDialog
from ui.widgets import FavImageLabel

pytestmark = pytest.mark.ui


class TestFavoritesDialog:

    @pytest.fixture
    def sample_favorites(self):
        return [
            {'segment': 'A', 'time': 10.0, 'path': '/tmp/fav1.jpg', 'exported': False},
            {'segment': 'A', 'time': 20.0, 'path': '/tmp/fav2.jpg', 'exported': True},
            {'segment': 'B', 'time': 45.0, 'path': '/tmp/fav3.jpg', 'exported': False},
            {'segment': 'B', 'time': 55.0, 'path': '/tmp/fav4.jpg', 'exported': False},
            {'segment': 'C', 'time': 90.0, 'path': '/tmp/fav5.jpg', 'exported': True},
        ]

    @pytest.fixture
    def temp_images(self, sample_favorites):
        with tempfile.TemporaryDirectory() as tmpdir:
            for fav in sample_favorites:
                path = os.path.join(tmpdir, os.path.basename(fav['path']))
                Path(path).touch()
                fav['path'] = path
            yield sample_favorites

    @pytest.fixture
    def mock_controller_for_fav(self):
        mock = MagicMock()
        mock.video_id = 1
        mock.video_path = "test.mp4"
        mock.db = MagicMock()
        mock.db.is_favorite = MagicMock(return_value=False)
        mock.db.add_favorite = MagicMock(return_value=1)
        mock.get_current_favorites = MagicMock(return_value=[])
        mock.favorites = []
        mock.screenshots = {}
        mock._save_state_to_db = MagicMock()
        mock._notify_data_changed = MagicMock()
        mock.unfavorite_by_time = MagicMock(return_value=True)
        mock.get_segments = MagicMock(return_value=[("A", 0.0, 40.0)])
        mock.get_video_path = MagicMock(return_value="test.mp4")
        mock.export_base = "/tmp"
        return mock

    @pytest.fixture
    def real_parent(self, mock_controller_for_fav):
        parent = QWidget()
        parent.controller = mock_controller_for_fav
        parent.config = MagicMock()
        parent.config.get = MagicMock(return_value=None)
        parent.config.set = MagicMock()
        return parent

    @pytest.fixture
    def dialog(self, qtbot, temp_images, real_parent):
        dlg = FavoritesDialog(
            favorites=temp_images,
            video_name="test_video",
            export_base="/tmp",
            video_path="test.mp4",
            parent=real_parent
        )
        dlg._refresh_favorites()
        # 不显示窗口
        qtbot.addWidget(dlg)
        return dlg

    def test_window_title(self, qtbot, dialog):
        assert "test_video" in dialog.windowTitle()
        assert "5" in dialog.windowTitle()

    def test_groups_display(self, qtbot, dialog):
        from PySide6.QtWidgets import QLabel
        labels = dialog.findChildren(QLabel)
        group_titles = [l.text() for l in labels if "区" in l.text()]
        assert len(group_titles) >= 3

    def test_grid_has_all_favorites(self, qtbot, dialog):
        assert len(dialog.image_labels) == 5

    def test_select_favorite(self, qtbot, dialog):
        dialog.on_image_click(0)
        assert 0 in dialog.selected_indices
        dialog.on_image_click(0)
        assert 0 not in dialog.selected_indices

    def test_double_click_opens_preview(self, qtbot, dialog):
        with patch.object(dialog, 'preview_image', autospec=True) as mock_preview:
            dialog.preview_image(0)
            mock_preview.assert_called_once_with(0)

    @patch.object(FavoritesDialog, 'export_selected', autospec=True)
    def test_export_selected_favorites(self, mock_export, qtbot, dialog):
        dialog.selected_indices.add(0)
        dialog.selected_indices.add(1)
        dialog._update_selected_count()
        dialog._update_button_states()
        dialog.export_selected()
        mock_export.assert_called_once_with(dialog)

    def test_close_dialog(self, qtbot, dialog):
        dialog.close()
        # 直接检查可见性
        assert not dialog.isVisible()