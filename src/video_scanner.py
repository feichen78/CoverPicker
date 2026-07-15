# src/video_scanner.py

import os
import json
import asyncio
import subprocess
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# 支持的视频格式（v1.3 扩展）
SUPPORTED_VIDEO_EXTENSIONS = {
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm',
    '.m4v', '.mpg', '.mpeg', '.ts', '.m2ts', '.3gp', '.3g2',
    '.asf', '.vob', '.ogv', '.ogg', '.divx', '.xvid', '.mts',
    '.m2v', '.m4p', '.m4b', '.m4r', '.mpv', '.mpe', '.mxf',
    '.rm', '.rmvb', '.swf', '.f4v', '.f4p', '.f4a', '.f4b'
}


def scan_videos(directory: str, extensions: set = None) -> List[str]:
    """
    递归扫描目录中的所有视频文件
    
    Args:
        directory: 要扫描的目录路径
        extensions: 支持的文件扩展名集合，默认使用 SUPPORTED_VIDEO_EXTENSIONS
    
    Returns:
        视频文件路径列表
    """
    if extensions is None:
        extensions = SUPPORTED_VIDEO_EXTENSIONS
    
    video_files = []
    try:
        for root, dirs, files in os.walk(directory):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in extensions:
                    video_files.append(os.path.join(root, file))
    except Exception as e:
        logger.error(f"扫描目录失败 {directory}: {e}")
    return video_files


def scan_videos_in_directory(directory: str, extensions: set = None) -> List[str]:
    """扫描单个目录中的视频文件（非递归）"""
    if extensions is None:
        extensions = SUPPORTED_VIDEO_EXTENSIONS
    
    video_files = []
    try:
        for file in os.listdir(directory):
            ext = os.path.splitext(file)[1].lower()
            if ext in extensions:
                video_files.append(os.path.join(directory, file))
    except Exception as e:
        logger.error(f"扫描目录失败 {directory}: {e}")
    return video_files


def get_video_duration(video_path: str) -> Optional[float]:
    """使用 FFprobe 获取视频时长（秒）"""
    if not os.path.exists(video_path):
        logger.error(f"视频文件不存在: {video_path}")
        return None
    
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            duration = float(result.stdout.strip())
            return duration
        else:
            logger.error(f"FFprobe 获取时长失败: {video_path}, stderr: {result.stderr}")
            return None
    except subprocess.TimeoutExpired:
        logger.error(f"FFprobe 超时: {video_path}")
        return None
    except Exception as e:
        logger.error(f"FFprobe 异常: {video_path}, {e}")
        return None


def get_video_info(video_path: str) -> Optional[dict]:
    """获取视频详细信息"""
    if not os.path.exists(video_path):
        return None
    
    cmd = [
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        video_path
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=30
        )
        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout)
            return data
        return None
    except Exception as e:
        logger.error(f"FFprobe 获取信息失败: {video_path}, {e}")
        return None


def extract_frame(video_path: str, timestamp: float, output_path: str) -> bool:
    """提取视频帧"""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-ss", str(timestamp),
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        "-y",
        output_path
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=30
        )
        return result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except subprocess.TimeoutExpired:
        logger.error(f"FFmpeg 提取帧超时: {video_path} @ {timestamp}s")
        return False
    except Exception as e:
        logger.error(f"FFmpeg 提取帧异常: {video_path} @ {timestamp}s, {e}")
        return False


def extract_frames_batch(video_path: str, timestamps: List[float], output_dir: str) -> List[str]:
    """批量提取视频帧"""
    outputs = []
    for i, ts in enumerate(timestamps):
        output_path = os.path.join(output_dir, f"frame_{i:03d}.jpg")
        if extract_frame(video_path, ts, output_path):
            outputs.append(output_path)
    return outputs


def extract_video_clip(video_path: str, start_time: float, end_time: float, output_path: str, re_encode: bool = False) -> bool:
    """
    提取视频片段
    
    Args:
        video_path: 源视频路径
        start_time: 起始时间（秒）
        end_time: 结束时间（秒）
        output_path: 输出文件路径
        re_encode: 是否重新编码（True=重新编码，False=尝试无损复制）
    
    Returns:
        是否成功
    """
    if not os.path.exists(video_path):
        logger.error(f"视频文件不存在: {video_path}")
        return False
    
    duration = end_time - start_time
    if duration <= 0:
        logger.error("起始时间必须小于结束时间")
        return False
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    if re_encode:
        # 重新编码模式（兼容性更好）
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-ss", str(start_time),
            "-i", video_path,
            "-t", str(duration),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "fast",
            "-crf", "23",
            "-y",
            output_path
        ]
    else:
        # 尝试无损复制（更快）
        # 先检测音频流是否存在
        probe_cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        try:
            result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
            has_audio = "audio" in result.stdout
        except Exception:
            has_audio = True  # 保守起见
        
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-ss", str(start_time),
            "-i", video_path,
            "-t", str(duration),
            "-c:v", "copy",
        ]
        if has_audio:
            cmd.extend(["-c:a", "copy"])
        else:
            cmd.extend(["-an"])  # 无音频
        cmd.extend(["-avoid_negative_ts", "make_zero", "-y", output_path])
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=300  # 5分钟超时
        )
        success = result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
        # 如果无损复制失败，自动尝试重新编码
        if not success and not re_encode:
            logger.warning(f"无损复制失败，尝试重新编码: {video_path}")
            return extract_video_clip(video_path, start_time, end_time, output_path, re_encode=True)
        
        return success
    except subprocess.TimeoutExpired:
        logger.error(f"FFmpeg 导出片段超时: {video_path}")
        return False
    except Exception as e:
        logger.error(f"FFmpeg 导出片段异常: {video_path}, {e}")
        return False


def calculate_segments(duration: float, num_segments: int) -> List[Tuple[str, float, float]]:
    """将视频时长均分为指定数量的分段"""
    if duration <= 0 or num_segments <= 0:
        return []
    
    # 如果视频太短，合并为一个分段
    if duration < 60:  # 小于1分钟
        return [("A", 0.0, duration)]
    
    segment_duration = duration / num_segments
    segments = []
    for i in range(num_segments):
        start = i * segment_duration
        end = start + segment_duration
        label = chr(ord('A') + i)
        segments.append((label, start, end))
    return segments