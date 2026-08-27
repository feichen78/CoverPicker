import pytest
import os
from src.database import Database

class TestDatabase:

    def test_init_creates_db_file(self, temp_db):
        """测试数据库初始化是否正确创建文件"""
        db = Database(db_path=temp_db)
        assert os.path.exists(temp_db)
        db.close()

    def test_get_or_create_video_new(self, temp_db):
        """测试新增视频"""
        db = Database(db_path=temp_db)
        vid = db.get_or_create_video(
            file_path="C:/test/movie.mp4",
            file_name="movie.mp4",
            duration=120,
            resolution="1920x1080",
            file_size=1024*1024*100,
            modified_time=1234567890
        )
        assert vid > 0
        
        video_data = db.get_video_by_path("C:/test/movie.mp4")
        assert video_data is not None
        assert video_data['file_name'] == "movie.mp4"
        assert video_data['duration'] == 120
        db.close()

    def test_get_video_by_path_normalization(self, temp_db):
        """测试路径规范化修复功能（v3.0.2）"""
        db = Database(db_path=temp_db)
        db.get_or_create_video(
            file_path="C:/test/movie.mp4",
            file_name="movie.mp4",
            duration=120,
            resolution="1920x1080",
            file_size=100,
            modified_time=1234567890
        )
        # 使用反斜杠查询，应返回相同记录
        video_data = db.get_video_by_path("C:\\test\\movie.mp4")
        assert video_data is not None
        # 使用 os.path.normpath 进行跨平台比较
        assert os.path.normpath(video_data['file_path']) == os.path.normpath("C:/test/movie.mp4")
        db.close()

    def test_update_video_state(self, temp_db):
        """测试视频状态更新"""
        db = Database(db_path=temp_db)
        vid = db.get_or_create_video(
            file_path="C:/test/movie.mp4",
            file_name="movie.mp4",
            duration=120,
            resolution="1920x1080",
            file_size=100,
            modified_time=1234567890
        )
        db.update_video_state(vid, is_viewed=True, is_starred=True, is_exported=False)
        
        video_data = db.get_video_by_path("C:/test/movie.mp4")
        assert video_data['is_viewed'] == 1
        assert video_data['is_starred'] == 1
        assert video_data['is_exported'] == 0
        db.close()

    def test_excluded_ranges(self, temp_db):
        """测试排除区间的存储和读取"""
        db = Database(db_path=temp_db)
        vid = db.get_or_create_video(
            file_path="C:/test/movie.mp4",
            file_name="movie.mp4",
            duration=120,
            resolution="1920x1080",
            file_size=100,
            modified_time=1234567890
        )
        ranges = [[0.0, 5.0], [115.0, 120.0]]
        db.set_video_excluded_ranges(vid, ranges)
        
        retrieved = db.get_video_excluded_ranges(vid)
        # 从 JSON 加载后返回的是 list，类型保持一致
        assert retrieved == ranges
        db.close()

    def test_favorite_crud(self, temp_db):
        """测试收藏的增删改"""
        db = Database(db_path=temp_db)
        vid = db.get_or_create_video(
            file_path="C:/test/movie.mp4",
            file_name="movie.mp4",
            duration=120,
            resolution="1920x1080",
            file_size=100,
            modified_time=1234567890
        )
        db.add_favorite(vid, "A", 10000, "/tmp/thumb.jpg", "thumb.jpg")
        db.add_favorite(vid, "A", 20000, "/tmp/thumb2.jpg", "thumb2.jpg")
        db.add_favorite(vid, "B", 30000, "/tmp/thumb3.jpg", "thumb3.jpg")
        
        favorites = db.get_favorites(vid)
        assert len(favorites) == 3
        
        db.remove_favorite(vid, "A", 10000)
        favorites = db.get_favorites(vid)
        assert len(favorites) == 2
        db.close()