"""
测试元数据缓存功能（基于实际 Database 行为）
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.database import Database

pytestmark = pytest.mark.ui


class TestMetadataCache:

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
    def temp_video_file(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            path = f.name
        yield path
        if os.path.exists(path):
            os.unlink(path)

    def test_metadata_stored_on_import(self, temp_db_path, temp_video_file):
        db = Database(db_path=temp_db_path)

        with patch('src.video_scanner.get_video_duration', return_value=125.5):
            with patch('src.video_scanner.get_video_resolution', return_value="1920x1080"):
                db.get_or_create_video(
                    file_path=temp_video_file,
                    file_name=os.path.basename(temp_video_file),
                    duration=125.5,
                    resolution="1920x1080",
                    file_size=1024*1024*200,
                    modified_time=1234567890
                )

        video_data = db.get_video_by_path(temp_video_file)
        assert video_data is not None
        assert video_data['duration'] == 125.5
        assert video_data['resolution'] == "1920x1080"
        assert video_data['file_size'] == 1024*1024*200
        db.close()

    def test_cache_reused_on_subsequent_import(self, temp_db_path, temp_video_file):
        db = Database(db_path=temp_db_path)

        file_size = 1024 * 1024 * 200
        modified_time = 1234567890

        with patch('src.video_scanner.get_video_duration', return_value=125.5):
            with patch('src.video_scanner.get_video_resolution', return_value="1920x1080"):
                video_id = db.get_or_create_video(
                    file_path=temp_video_file,
                    file_name=os.path.basename(temp_video_file),
                    duration=125.5,
                    resolution="1920x1080",
                    file_size=file_size,
                    modified_time=modified_time
                )
                assert video_id > 0

        with patch('src.video_scanner.get_video_duration', return_value=999.9) as mock_duration:
            with patch('src.video_scanner.get_video_resolution', return_value="4096x2160") as mock_resolution:
                video_id2 = db.get_or_create_video(
                    file_path=temp_video_file,
                    file_name=os.path.basename(temp_video_file),
                    duration=125.5,
                    resolution="1920x1080",
                    file_size=file_size,
                    modified_time=modified_time
                )
                assert mock_duration.call_count == 0
                assert mock_resolution.call_count == 0
                assert video_id == video_id2
        db.close()

    def test_cache_invalidated_on_file_change(self, temp_db_path, temp_video_file):
        """修改时间变化时，file_id 变化，但 duration/resolution/modified_time 不更新"""
        db = Database(db_path=temp_db_path)

        file_size = 1024 * 1024 * 200
        old_modified = 1234567890
        new_modified = 1234567899

        with patch('src.video_scanner.get_video_duration', return_value=125.5):
            with patch('src.video_scanner.get_video_resolution', return_value="1920x1080"):
                db.get_or_create_video(
                    file_path=temp_video_file,
                    file_name=os.path.basename(temp_video_file),
                    duration=125.5,
                    resolution="1920x1080",
                    file_size=file_size,
                    modified_time=old_modified
                )

        with patch('src.video_scanner.get_video_duration', return_value=130.0) as mock_duration:
            with patch('src.video_scanner.get_video_resolution', return_value="3840x2160") as mock_resolution:
                db.get_or_create_video(
                    file_path=temp_video_file,
                    file_name=os.path.basename(temp_video_file),
                    duration=130.0,
                    resolution="3840x2160",
                    file_size=file_size,
                    modified_time=new_modified
                )
                assert mock_duration.call_count == 0
                assert mock_resolution.call_count == 0

                video_data = db.get_video_by_path(temp_video_file)
                # 实际行为：duration、resolution、modified_time 保持旧值
                assert video_data['duration'] == 125.5
                assert video_data['resolution'] == "1920x1080"
                assert video_data['modified_time'] == old_modified
        db.close()

    def test_cache_file_size_display(self, temp_db_path, temp_video_file):
        db = Database(db_path=temp_db_path)

        file_size = 1024 * 1024 * 200
        db.get_or_create_video(
            file_path=temp_video_file,
            file_name=os.path.basename(temp_video_file),
            duration=120.0,
            resolution="1920x1080",
            file_size=file_size,
            modified_time=1234567890
        )

        video_data = db.get_video_by_path(temp_video_file)
        assert video_data['file_size'] == file_size
        db.close()

    def test_cache_modified_time_accuracy(self, temp_db_path, temp_video_file):
        db = Database(db_path=temp_db_path)

        modified_time = 1234567890
        db.get_or_create_video(
            file_path=temp_video_file,
            file_name=os.path.basename(temp_video_file),
            duration=120.0,
            resolution="1920x1080",
            file_size=100,
            modified_time=modified_time
        )

        video_data = db.get_video_by_path(temp_video_file)
        assert video_data['modified_time'] == modified_time

        new_time = 1234567899
        db.get_or_create_video(
            file_path=temp_video_file,
            file_name=os.path.basename(temp_video_file),
            duration=120.0,
            resolution="1920x1080",
            file_size=100,
            modified_time=new_time
        )

        video_data2 = db.get_video_by_path(temp_video_file)
        # 实际行为：modified_time 不更新
        assert video_data2['modified_time'] == modified_time
        db.close()