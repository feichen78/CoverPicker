import os
import subprocess
import json
import math
from typing import List, Tuple, Optional

# 支持的视频扩展名
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.ts'}


def scan_videos(directory: str) -> List[str]:
    """扫描目录下的所有视频文件，返回绝对路径列表"""
    videos = []
    if not os.path.isdir(directory):
        print(f"警告：目录不存在 {directory}")
        return videos
    for root, _, files in os.walk(directory):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                full_path = os.path.join(root, f)
                videos.append(full_path)
    return videos


def get_video_duration(filepath: str) -> Optional[float]:
    """通过 ffprobe 获取视频时长（秒）"""
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "json", filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        duration = float(data['format']['duration'])
        return duration
    except Exception as e:
        print(f"获取时长失败 {filepath}: {e}")
        return None


def calculate_segments(duration: float) -> List[Tuple[str, float, float]]:
    """
    根据视频时长计算 A/B/C/D/E 分区
    返回 [(标签, 起始秒, 结束秒), ...]
    如果 duration < 300 (5分钟)，仅返回一个分区 A
    """
    if duration < 300:  # <5分钟，合并为一个区
        return [("A", 0.0, duration)]
    # 均分5段
    seg_len = duration / 5
    segments = []
    for i in range(5):
        start = i * seg_len
        end = start + seg_len
        label = chr(ord('A') + i)
        segments.append((label, start, end))
    return segments


def extract_frame(video_path: str, time_sec: float, output_path: str) -> bool:
    """
    使用 ffmpeg 提取指定时间点的关键帧，保存为 jpg
    返回是否成功
    """
    try:
        cmd = [
            "ffmpeg", "-y", "-ss", str(time_sec), "-i", video_path,
            "-vframes", "1", "-q:v", "2", output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        return True
    except Exception as e:
        print(f"截图失败 {video_path} @ {time_sec}s: {e}")
        return False