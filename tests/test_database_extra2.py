"""
继续补充 database 未覆盖分支
"""

import os
import tempfile
import json
import pytest
from pathlib import Path

from src.database import Database, normalize_path


class TestDatabaseExtra2:

    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            path = f.name
        yield path
        import time
        time.sleep(0.05)
        if os.path.exists(path):
            try:
                os.unlink(path)
            except PermissionError:
                pass

    def test_get_or_create_video_existing_duplicate(self, temp_db):
        """测试已存在视频的更新"""
        db = Database(db_path=temp_db)
        video_id = db.get_or_create_video(
            file_path="test.mp4",
            file_name="test.mp4",
            duration=120,
            resolution="1920x1080",
            file_size=100,
            modified_time=1234567890
        )
        video_id2 = db.get_or_create_video(
            file_path="test.mp4",
            file_name="test.mp4",
            duration=120,
            resolution="1920x1080",
            file_size=100,
            modified_time=1234567890
        )
        assert video_id == video_id2
        db.close()

    def test_get_or_create_video_file_id_mismatch(self, temp_db):
        """
        测试 file_id 不匹配但 file_path 匹配时更新 file_id，
        但不更新 duration/resolution（实际行为）。
        """
        db = Database(db_path=temp_db)
        video_id = db.get_or_create_video(
            file_path="test.mp4",
            file_name="test.mp4",
            duration=120,
            resolution="1920x1080",
            file_size=100,
            modified_time=1234567890
        )
        # 修改 file_size 和 modified_time 使 file_id 变化
        video_id2 = db.get_or_create_video(
            file_path="test.mp4",
            file_name="test.mp4",
            duration=130,  # 传入新值，但实际不会更新
            resolution="1920x1080",
            file_size=200,
            modified_time=1234567899
        )
        assert video_id == video_id2
        # 验证 duration 保持不变（实际行为）
        video_data = db.get_video_by_path("test.mp4")
        assert video_data['duration'] == 120  # 未更新
        # 验证 file_id 已被更新（通过查询确保新 file_id 存在）
        # 获取更新后的 file_id
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT file_id FROM videos WHERE id = ?", (video_id,))
        row = cursor.fetchone()
        assert row is not None
        # 新 file_id 应基于新的 file_size 和 modified_time
        expected_file_id = db._compute_file_id("test.mp4", 200, 1234567899)
        assert row['file_id'] == expected_file_id
        db.close()

    def test_get_or_create_segment_existing(self, temp_db):
        """测试创建已存在的分段"""
        db = Database(db_path=temp_db)
        video_id = db.get_or_create_video(
            file_path="test.mp4",
            file_name="test.mp4",
            duration=120,
            resolution="1920x1080",
            file_size=100,
            modified_time=1234567890
        )
        seg_id = db.get_or_create_segment(video_id, "A", 0, 40)
        seg_id2 = db.get_or_create_segment(video_id, "A", 0, 40)
        assert seg_id == seg_id2
        db.close()

    def test_get_segment_state_not_found(self, temp_db):
        """测试查询不存在的分段状态"""
        db = Database(db_path=temp_db)
        video_id = db.get_or_create_video(
            file_path="test.mp4",
            file_name="test.mp4",
            duration=120,
            resolution="1920x1080",
            file_size=100,
            modified_time=1234567890
        )
        state = db.get_segment_state(video_id, "Z")
        assert state is None
        db.close()

    def test_clear_favorites(self, temp_db):
        """测试清空收藏"""
        db = Database(db_path=temp_db)
        video_id = db.get_or_create_video(
            file_path="test.mp4",
            file_name="test.mp4",
            duration=120,
            resolution="1920x1080",
            file_size=100,
            modified_time=1234567890
        )
        db.add_favorite(video_id, "A", 10000, "/tmp/fav.jpg", "fav.jpg")
        db.add_favorite(video_id, "B", 20000, "/tmp/fav2.jpg", "fav2.jpg")
        assert len(db.get_favorites(video_id)) == 2
        db.clear_favorites(video_id)
        assert len(db.get_favorites(video_id)) == 0
        db.close()

    def test_update_favorite_path(self, temp_db):
        """测试更新收藏路径"""
        db = Database(db_path=temp_db)
        video_id = db.get_or_create_video(
            file_path="test.mp4",
            file_name="test.mp4",
            duration=120,
            resolution="1920x1080",
            file_size=100,
            modified_time=1234567890
        )
        db.add_favorite(video_id, "A", 10000, "/tmp/fav.jpg", "fav.jpg")
        db.update_favorite_path(video_id, "A", 10000, "/tmp/new_fav.jpg")
        favorites = db.get_favorites(video_id)
        assert favorites[0]['thumbnail_path'] == "/tmp/new_fav.jpg"
        assert favorites[0]['thumbnail_name'] == "new_fav.jpg"
        db.close()

    def test_get_video_by_file_id_not_found(self, temp_db):
        """测试通过 file_id 查询不存在的视频"""
        db = Database(db_path=temp_db)
        result = db.get_video_by_file_id("nonexistent")
        assert result is None
        db.close()

    def test_get_video_id_by_path_or_file_id_not_found(self, temp_db):
        """测试通过路径或 file_id 查询不存在的视频"""
        db = Database(db_path=temp_db)
        result = db.get_video_id_by_path_or_file_id("nonexistent.mp4", 0, 0)
        assert result is None
        db.close()