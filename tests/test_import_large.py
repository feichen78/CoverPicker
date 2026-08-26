# tests/test_import_large.py
# 测试导入大量视频时的性能与稳定性（使用临时数据库）

import pytest
import os
import tempfile
import shutil
import time
from pathlib import Path
from src.video_scanner import scan_videos
from src.database import Database


class TestImportLarge:

    @classmethod
    def setup_class(cls):
        # 创建 1000 个假视频文件
        cls.temp_dir = tempfile.mkdtemp()
        cls.video_count = 1000
        for i in range(cls.video_count):
            Path(cls.temp_dir, f"video_{i:04d}.mp4").touch()

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_scan_1000_videos(self, tmp_path):
        """使用临时目录扫描视频（不依赖数据库）"""
        start = time.perf_counter()
        videos = scan_videos(self.temp_dir)
        elapsed = time.perf_counter() - start
        assert len(videos) == self.video_count
        print(f"扫描 {self.video_count} 个视频耗时 {elapsed:.2f} 秒")
        assert elapsed < 2.0

    def test_database_insert_1000(self, tmp_path):
        """使用临时数据库进行插入性能测试"""
        # 在临时目录中创建数据库文件
        db_path = tmp_path / "test.db"
        db = Database(db_path=str(db_path))
        start = time.perf_counter()
        for i in range(self.video_count):
            path = os.path.join(self.temp_dir, f"video_{i:04d}.mp4")
            db.get_or_create_video(path, os.path.basename(path), 0, "", 0, 0)
        elapsed = time.perf_counter() - start
        print(f"插入 {self.video_count} 条记录耗时 {elapsed:.2f} 秒")
        assert elapsed < 20.0
        db.close()