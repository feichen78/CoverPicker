# src/video_scanner.py

import os
import subprocess
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


def scan_videos(root_dir: str, extensions: tuple = None) -> List[str]:
    """
    扫描指定目录下的所有视频文件
    """
    if extensions is None:
        extensions = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm',
                      '.m4v', '.mpg', '.mpeg', '.ts', '.m2ts', '.3gp')

    video_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.lower().endswith(extensions):
                video_files.append(os.path.join(dirpath, filename))
    return video_files


def get_video_duration(video_path: str) -> Optional[float]:
    """
    使用 ffprobe 获取视频时长（秒）
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
        return None
    except Exception as e:
        logger.error(f"获取视频时长失败 {video_path}: {e}")
        return None


def calculate_segments(duration: float, num_segments: int = 5) -> List[Tuple[str, float, float]]:
    """
    将视频时长均分为指定数量的分段
    返回: [(标签, 起始时间, 结束时间), ...]
    视频时长 < 5 分钟时，只返回 1 个分段
    """
    if duration < 300:
        return [('A', 0.0, duration)]

    segment_duration = duration / num_segments
    segments = []
    for i in range(num_segments):
        start = i * segment_duration
        end = (i + 1) * segment_duration
        if i == num_segments - 1:
            end = duration
        label = chr(ord('A') + i)
        segments.append((label, start, end))
    return segments


def extract_frame(video_path: str, time_sec: float, output_path: str) -> bool:
    """
    使用 ffmpeg 提取视频帧
    """
    try:
        cmd = [
            'ffmpeg',
            '-y',
            '-ss', str(time_sec),
            '-i', video_path,
            '-vframes', '1',
            '-q:v', '2',
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        logger.error(f"提取帧失败 {video_path} @ {time_sec}s: {e}")
        return False


def extract_video_clip(
    video_path: str,
    start_time: float,
    end_time: float,
    output_path: str,
    re_encode: bool = False
) -> bool:
    """
    使用 ffmpeg 导出视频片段（无损复制）
    
    Args:
        video_path: 源视频路径
        start_time: 起始时间（秒）
        end_time: 结束时间（秒）
        output_path: 输出文件路径
        re_encode: 是否重新编码（默认 False，使用 -c copy 无损复制）
    
    Returns:
        是否成功
    """
    if start_time >= end_time:
        logger.error(f"无效的时间范围: {start_time} -> {end_time}")
        return False

    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    try:
        if re_encode:
            # 重新编码（兼容性更好，但慢且可能损失质量）
            cmd = [
                'ffmpeg',
                '-y',
                '-ss', str(start_time),
                '-to', str(end_time),
                '-i', video_path,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-preset', 'fast',
                output_path
            ]
        else:
            # 无损复制（快，但可能不支持所有格式）
            cmd = [
                'ffmpeg',
                '-y',
                '-ss', str(start_time),
                '-to', str(end_time),
                '-i', video_path,
                '-c', 'copy',
                output_path
            ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"视频片段导出成功: {output_path} ({start_time:.2f}s - {end_time:.2f}s)")
            return True
        else:
            logger.error(f"视频片段导出失败: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"视频片段导出超时")
        return False
    except Exception as e:
        logger.error(f"视频片段导出异常: {e}")
        return False