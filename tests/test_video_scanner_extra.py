"""
补充测试 video_scanner 未覆盖分支
"""

import os
import tempfile
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.video_scanner import (
    scan_videos, scan_videos_in_directory,
    extract_frame, extract_video_clip,
    normalize_path
)


class TestVideoScannerExtra:

    def test_scan_videos_recursive_handles_permission_error(self):
        """测试扫描时遇到权限错误时静默跳过"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建一个小目录结构
            subdir = os.path.join(tmpdir, "sub")
            os.makedirs(subdir)

            with patch('os.scandir') as mock_scandir:
                # 模拟 PermissionError
                mock_scandir.side_effect = PermissionError("Access denied")
                # 不应抛出异常
                result = scan_videos(tmpdir, recursive=True)
                assert result == []

    def test_scan_videos_ignores_non_video_files(self):
        """测试扫描只返回视频文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            video_file = os.path.join(tmpdir, "test.mp4")
            Path(video_file).touch()
            text_file = os.path.join(tmpdir, "readme.txt")
            Path(text_file).touch()

            result = scan_videos(tmpdir, recursive=False)
            # 应该只包含视频文件
            assert len(result) == 1
            assert result[0].endswith("test.mp4")

    def test_scan_videos_in_directory_non_recursive(self):
        """测试非递归扫描"""
        with tempfile.TemporaryDirectory() as tmpdir:
            video_file = os.path.join(tmpdir, "test.mp4")
            Path(video_file).touch()
            subdir = os.path.join(tmpdir, "sub")
            os.makedirs(subdir)
            sub_video = os.path.join(subdir, "clip.mp4")
            Path(sub_video).touch()

            result = scan_videos_in_directory(tmpdir)
            # 只应包含根目录的视频，不递归
            assert len(result) == 1
            assert result[0].endswith("test.mp4")

    def test_extract_frame_success(self):
        """测试同步提取帧成功"""
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "video.mp4")
            Path(video_path).touch()
            output_path = os.path.join(tmpdir, "frame.jpg")

            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                with patch('os.path.exists', return_value=True):
                    with patch('os.path.getsize', return_value=1024):
                        result = extract_frame(video_path, 10.0, output_path)
                        assert result is True

    def test_extract_frame_failure(self):
        """测试同步提取帧失败"""
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "video.mp4")
            Path(video_path).touch()
            output_path = os.path.join(tmpdir, "frame.jpg")

            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(returncode=1)
                result = extract_frame(video_path, 10.0, output_path)
                assert result is False

    def test_extract_frame_exception(self):
        """测试同步提取帧异常"""
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "video.mp4")
            Path(video_path).touch()
            output_path = os.path.join(tmpdir, "frame.jpg")

            with patch('subprocess.run', side_effect=Exception("FFmpeg error")):
                result = extract_frame(video_path, 10.0, output_path)
                assert result is False

    def test_extract_video_clip_success(self):
        """测试提取视频片段成功"""
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "video.mp4")
            Path(video_path).touch()
            output_path = os.path.join(tmpdir, "clip.mp4")

            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                with patch('os.path.exists', return_value=True):
                    with patch('os.path.getsize', return_value=1024):
                        result = extract_video_clip(video_path, 0, 10, output_path, re_encode=False)
                        assert result is True

    def test_extract_video_clip_failure(self):
        """测试提取视频片段失败"""
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "video.mp4")
            Path(video_path).touch()
            output_path = os.path.join(tmpdir, "clip.mp4")

            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(returncode=1)
                result = extract_video_clip(video_path, 0, 10, output_path, re_encode=False)
                assert result is False

    def test_extract_video_clip_exception(self):
        """测试提取视频片段异常"""
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "video.mp4")
            Path(video_path).touch()
            output_path = os.path.join(tmpdir, "clip.mp4")

            with patch('subprocess.run', side_effect=Exception("FFmpeg error")):
                result = extract_video_clip(video_path, 0, 10, output_path, re_encode=False)
                assert result is False

    def test_extract_video_clip_reencode(self):
        """测试重新编码提取视频片段"""
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "video.mp4")
            Path(video_path).touch()
            output_path = os.path.join(tmpdir, "clip.mp4")

            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                with patch('os.path.exists', return_value=True):
                    with patch('os.path.getsize', return_value=1024):
                        result = extract_video_clip(video_path, 0, 10, output_path, re_encode=True)
                        assert result is True