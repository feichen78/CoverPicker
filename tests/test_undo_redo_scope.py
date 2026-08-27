"""
测试撤销/重做范围 - 验证哪些操作可撤销、哪些不可撤销
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.controllers.segment_controller import SegmentController
from src.database import Database

pytestmark = pytest.mark.ui


class TestUndoRedoScope:

    @pytest.fixture
    def temp_db_path(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except PermissionError:
            pass

    @pytest.fixture
    def controller(self, temp_db_path):
        db = Database(db_path=temp_db_path)
        video_id = db.get_or_create_video(
            file_path="test.mp4",
            file_name="test.mp4",
            duration=120,
            resolution="1920x1080",
            file_size=100,
            modified_time=1234567890
        )
        controller = SegmentController()
        controller.db = db
        controller.video_id = video_id
        controller.video_path = "test.mp4"
        controller.duration = 120.0
        controller.screenshots = {
            'A': [
                {'time': 10.0, 'path': '/tmp/frame1.jpg', 'locked': False, 'favorite': False, 'exported': False},
                {'time': 20.0, 'path': '/tmp/frame2.jpg', 'locked': False, 'favorite': False, 'exported': False},
            ]
        }
        controller.favorites = []
        controller.undo_stack.clear()
        controller.redo_stack.clear()
        yield controller
        # 关闭数据库连接
        db.close()

    def test_favorite_undo_redo(self, controller):
        with patch.object(controller.db, 'is_favorite', return_value=False):
            with patch.object(controller.db, 'add_favorite', return_value=1):
                added, _ = controller.favorite_selected('A', [0])
                assert added == 1
                assert controller.can_undo() is True

                controller.undo()
                assert controller.screenshots['A'][0]['favorite'] is False
                assert controller.can_redo() is True

                controller.redo()
                assert controller.screenshots['A'][0]['favorite'] is True

    def test_lock_undo_redo(self, controller):
        controller.undo_stack.clear()
        controller.redo_stack.clear()

        count = controller.lock_selected('A', [0, 1])
        assert count == 2
        assert controller.can_undo() is True

        controller.undo()
        assert controller.screenshots['A'][0]['locked'] is True
        assert controller.screenshots['A'][1]['locked'] is False
        assert controller.can_redo() is True

        controller.undo()
        assert controller.screenshots['A'][0]['locked'] is False
        assert controller.screenshots['A'][1]['locked'] is False
        assert controller.can_undo() is False

        controller.redo()
        assert controller.screenshots['A'][0]['locked'] is True
        assert controller.screenshots['A'][1]['locked'] is False

        controller.redo()
        assert controller.screenshots['A'][0]['locked'] is True
        assert controller.screenshots['A'][1]['locked'] is True

    def test_unlock_undo_redo(self, controller):
        controller.lock_selected('A', [0])
        controller.undo_stack.clear()
        controller.redo_stack.clear()

        count = controller.unlock_selected('A', [0])
        assert count == 1
        assert controller.can_undo() is True

        controller.undo()
        assert controller.screenshots['A'][0]['locked'] is True
        assert controller.can_redo() is True

        controller.redo()
        assert controller.screenshots['A'][0]['locked'] is False

    def test_unfavorite_undo_redo(self, controller):
        with patch.object(controller.db, 'is_favorite', return_value=False):
            with patch.object(controller.db, 'add_favorite', return_value=1):
                controller.favorite_selected('A', [0])
        controller.undo_stack.clear()
        controller.redo_stack.clear()

        with patch.object(controller.db, 'remove_favorite', return_value=None):
            with patch.object(controller.db, 'is_favorite', return_value=True):
                removed = controller.unfavorite_selected('A', [0])
                assert removed == 1
                assert controller.can_undo() is True

                controller.undo()
                assert controller.screenshots['A'][0]['favorite'] is True
                assert controller.can_redo() is True

                controller.redo()
                assert controller.screenshots['A'][0]['favorite'] is False

    def test_export_not_undoable(self, controller):
        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = os.path.join(tmpdir, "frame1.jpg")
            Path(img_path).touch()

            controller.screenshots['A'][0]['path'] = img_path
            controller.screenshots['A'][0]['exported'] = False

            exported, _ = controller.export_selected('A', [0], export_dir=tmpdir)
            assert exported == 1
            assert controller.can_undo() is False

    def test_refresh_not_undoable(self, controller):
        controller.refresh_unlocked = MagicMock(return_value=0)
        controller.refresh_unlocked('A')
        assert controller.can_undo() is False

    def test_resegment_not_undoable(self, controller):
        controller.reset_segment = MagicMock(return_value=None)
        controller.reset_segment('A')
        assert controller.can_undo() is False

    def test_multiple_operations_stack_limit(self, controller):
        with patch.object(controller.db, 'is_favorite', return_value=False):
            with patch.object(controller.db, 'add_favorite', return_value=1):
                for i in range(150):
                    controller.favorite_selected('A', [0])
                    controller.screenshots['A'][0]['favorite'] = False
                assert len(controller.undo_stack) <= 100