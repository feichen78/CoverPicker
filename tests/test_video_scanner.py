import pytest
import os
import subprocess
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import src.video_scanner as vs


class TestVideoScanner:

    # ---- 原有测试 ----

    def test_calculate_segments_default(self):
        segments = vs.calculate_segments(120.0, 3)
        assert len(segments) == 3
        assert segments[0][0] == "A"
        assert abs(segments[0][1] - 0.0) < 0.001
        assert abs(segments[0][2] - 40.0) < 0.001
        assert segments[1][0] == "B"
        assert abs(segments[1][1] - 40.0) < 0.001
        assert abs(segments[1][2] - 80.0) < 0.001
        assert segments[2][0] == "C"
        assert abs(segments[2][1] - 80.0) < 0.001
        assert abs(segments[2][2] - 120.0) < 0.001

    def test_calculate_segments_single(self):
        segments = vs.calculate_segments(180.0, 1)
        assert len(segments) == 1
        assert segments[0][0] == "A"
        assert segments[0][1] == 0.0
        assert segments[0][2] == 180.0

    def test_calculate_segments_five(self):
        segments = vs.calculate_segments(100.0, 5)
        assert len(segments) == 5
        assert segments[0][0] == "A"
        assert segments[4][0] == "E"
        assert abs(segments[4][1] - 80.0) < 0.001
        assert abs(segments[4][2] - 100.0) < 0.001

    def test_get_video_duration_success(self, monkeypatch):
        def mock_duration(path):
            return 123.45
        monkeypatch.setattr(vs, 'get_video_duration', mock_duration)
        duration = vs.get_video_duration("test.mp4")
        assert duration == 123.45

    def test_get_video_duration_failure(self, monkeypatch):
        def mock_duration(path):
            return None
        monkeypatch.setattr(vs, 'get_video_duration', mock_duration)
        duration = vs.get_video_duration("test.mp4")
        assert duration is None

    def test_get_video_resolution_success(self, monkeypatch):
        def mock_resolution(path):
            return "1920x1080"
        monkeypatch.setattr(vs, 'get_video_resolution', mock_resolution)
        resolution = vs.get_video_resolution("test.mp4")
        assert resolution == "1920x1080"

    def test_scan_videos_with_real_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            video_file = os.path.join(tmpdir, "test.mp4")
            Path(video_file).touch()
            text_file = os.path.join(tmpdir, "readme.txt")
            Path(text_file).touch()
            subdir = os.path.join(tmpdir, "subdir")
            os.makedirs(subdir)
            sub_video = os.path.join(subdir, "clip.mkv")
            Path(sub_video).touch()

            results = vs.scan_videos(tmpdir)
            assert len(results) == 2
            assert any(f.endswith("test.mp4") for f in results)
            assert any(f.endswith("clip.mkv") for f in results)

    # ---- 新增异常分支测试 ----

    @patch('src.video_scanner.subprocess.check_output')
    def test_get_video_duration_ffprobe_timeout(self, mock_check_output):
        mock_check_output.side_effect = subprocess.TimeoutExpired(cmd="ffprobe", timeout=10)
        duration = vs.get_video_duration("test.mp4")
        assert duration is None

    @patch('src.video_scanner.subprocess.check_output')
    def test_get_video_duration_ffprobe_oserror(self, mock_check_output):
        mock_check_output.side_effect = FileNotFoundError("ffprobe not found")
        duration = vs.get_video_duration("test.mp4")
        assert duration is None

    @patch('src.video_scanner.subprocess.check_output')
    def test_get_video_resolution_ffprobe_timeout(self, mock_check_output):
        mock_check_output.side_effect = subprocess.TimeoutExpired(cmd="ffprobe", timeout=10)
        resolution = vs.get_video_resolution("test.mp4")
        assert resolution == ""

    @patch('src.video_scanner.subprocess.check_output')
    def test_get_video_resolution_ffprobe_oserror(self, mock_check_output):
        mock_check_output.side_effect = FileNotFoundError("ffprobe not found")
        resolution = vs.get_video_resolution("test.mp4")
        assert resolution == ""

    @patch('src.video_scanner.subprocess.check_output')
    def test_get_video_duration_malformed_output(self, mock_check_output):
        mock_check_output.return_value = b"invalid json"
        duration = vs.get_video_duration("test.mp4")
        assert duration is None

    @patch('src.video_scanner.subprocess.check_output')
    def test_get_video_resolution_malformed_output(self, mock_check_output):
        mock_check_output.return_value = b"invalid json"
        resolution = vs.get_video_resolution("test.mp4")
        assert resolution == ""

    # ---- extract_frame_async 测试 ----
    # 注意：extract_frame_async 使用 asyncio.create_subprocess_exec，
    # 所以 patch 路径应为 'src.video_scanner.asyncio.create_subprocess_exec'

    @pytest.mark.asyncio
    async def test_extract_frame_async_success(self):
        """测试异步提取帧成功"""
        # 模拟 asyncio.create_subprocess_exec 返回模拟进程
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        with patch('src.video_scanner.asyncio.create_subprocess_exec', return_value=mock_process):
            with patch('os.path.exists', return_value=True):
                with patch('os.path.getsize', return_value=1024):
                    success, process = await vs.extract_frame_async("video.mp4", 10.0, "out.jpg")
                    assert success is True
                    assert process is mock_process

    @pytest.mark.asyncio
    async def test_extract_frame_async_failure(self):
        """测试异步提取帧失败（返回非0）"""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"error"))
        mock_process.returncode = 1

        with patch('src.video_scanner.asyncio.create_subprocess_exec', return_value=mock_process):
            success, process = await vs.extract_frame_async("video.mp4", 10.0, "out.jpg")
            assert success is False
            assert process is mock_process

    @pytest.mark.asyncio
    async def test_extract_frame_async_exception(self):
        """测试异步提取帧异常"""
        with patch('src.video_scanner.asyncio.create_subprocess_exec', side_effect=Exception("ffmpeg crash")):
            success, process = await vs.extract_frame_async("video.mp4", 10.0, "out.jpg")
            assert success is False
            assert process is None