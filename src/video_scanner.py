# src/video_scanner.py
# v3.2.12: 统一路径规范化（正斜杠），修复删除失败

import os
import subprocess
import asyncio
import tempfile
import time
import logging
from typing import List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# 支持的视频扩展名
VIDEO_EXTENSIONS = [
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm',
    '.m4v', '.mpg', '.mpeg', '.ts', '.m2ts', '.3gp', '.asf',
    '.vob', '.ogv', '.ogg', '.divx', '.xvid', '.mts', '.m2v',
    '.m4p', '.m4b', '.m4r', '.mpv', '.mpe', '.mxf', '.rm',
    '.rmvb', '.swf', '.f4v'
]


def normalize_path(path):
    """统一路径为正斜杠格式，用于内部存储和比较"""
    return os.path.normpath(path).replace('\\', '/')


def get_video_duration(video_path: str) -> Optional[float]:
    """使用 ffprobe 获取视频时长（秒）。"""
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries',
            'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, encoding='utf-8')
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
        return None
    except Exception:
        return None


def get_video_resolution(video_path: str) -> str:
    """使用 ffprobe 获取视频分辨率（宽x高）。"""
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, encoding='utf-8')
        if result.returncode == 0:
            lines = result.stdout.strip().splitlines()
            if len(lines) >= 2:
                return f"{lines[0]}x{lines[1]}"
        return ""
    except Exception:
        return ""


def calculate_segments(duration: float, num_segments: int) -> List[Tuple[str, float, float]]:
    """将视频时长均匀划分为指定数量的分区"""
    if duration <= 0 or num_segments <= 0:
        return []
    seg_duration = duration / num_segments
    segments = []
    for i in range(num_segments):
        label = chr(ord('A') + i)
        start = i * seg_duration
        end = (i + 1) * seg_duration
        segments.append((label, start, end))
    return segments


def scan_videos(directory: str, recursive: bool = True) -> List[str]:
    """
    扫描目录中的视频文件，返回规范化路径列表（统一为正斜杠）。
    """
    start_time = time.perf_counter()
    print(f"[PERF] scan_videos 开始: {directory}, recursive={recursive}")
    logger.info(f"扫描开始: {directory}")

    video_files = []
    video_exts = {ext.lower() for ext in VIDEO_EXTENSIONS}
    dir_count = 0
    file_count = 0
    permission_errors = 0

    def _scan(path):
        nonlocal dir_count, file_count, permission_errors
        dir_count += 1
        try:
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if recursive:
                                _scan(entry.path)
                            continue
                        if entry.is_file(follow_symlinks=False):
                            file_count += 1
                            ext = os.path.splitext(entry.name)[1].lower()
                            if ext in video_exts:
                                # 规范化路径
                                video_files.append(normalize_path(entry.path))
                    except (PermissionError, OSError):
                        permission_errors += 1
                        continue
        except (PermissionError, OSError):
            permission_errors += 1
            pass

        if dir_count % 1000 == 0:
            elapsed = time.perf_counter() - start_time
            print(f"[PERF] 已扫描 {dir_count} 个目录，找到 {len(video_files)} 个视频，耗时 {elapsed:.2f}s")

    _scan(directory)
    elapsed = time.perf_counter() - start_time
    print(f"[PERF] scan_videos 完成: 扫描了 {dir_count} 个目录，{file_count} 个文件，找到 {len(video_files)} 个视频，总耗时 {elapsed:.2f} 秒")
    logger.info(f"扫描完成: 目录数={dir_count}, 文件数={file_count}, 视频数={len(video_files)}, 耗时={elapsed:.2f}s")
    return video_files


def scan_videos_in_directory(directory: str) -> List[str]:
    """扫描单层目录（不递归），返回规范化路径列表"""
    return scan_videos(directory, recursive=False)


def extract_frame(video_path: str, time_sec: float, output_path: str) -> bool:
    """同步提取视频帧（使用 ffmpeg）"""
    try:
        cmd = [
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
            '-ss', str(time_sec),
            '-i', video_path,
            '-vframes', '1',
            '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuvj420p',
            '-strict', 'unofficial',
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        return result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception:
        return False


async def extract_frame_async(video_path: str, time_sec: float, output_path: str, retries: int = 1) -> Tuple[bool, Optional[asyncio.subprocess.Process]]:
    """异步提取视频帧（使用 ffmpeg）"""
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-ss', str(time_sec),
        '-i', video_path,
        '-vframes', '1',
        '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuvj420p',
        '-strict', 'unofficial',
        output_path
    ]
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True, process
        return False, process
    except Exception:
        return False, None


def extract_video_clip(video_path: str, start_time: float, end_time: float, output_path: str, re_encode: bool = False) -> bool:
    """提取视频片段（无损或有损）"""
    try:
        if re_encode:
            cmd = [
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-ss', str(start_time),
                '-i', video_path,
                '-to', str(end_time - start_time),
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                '-c:a', 'aac', '-b:a', '128k',
                output_path
            ]
        else:
            cmd = [
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-ss', str(start_time),
                '-i', video_path,
                '-to', str(end_time - start_time),
                '-c', 'copy',
                output_path
            ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        return result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception:
        return False


def extract_frames_batch(video_path: str, times: List[float], output_dir: str) -> List[str]:
    """批量提取帧（同步）"""
    results = []
    for t in times:
        output_path = os.path.join(output_dir, f"frame_{t:.2f}.jpg")
        if extract_frame(video_path, t, output_path):
            results.append(output_path)
    return results


async def extract_frames_batch_async(video_path: str, times: List[float], output_dir: str) -> List[str]:
    """批量提取帧（异步）"""
    tasks = []
    for t in times:
        output_path = os.path.join(output_dir, f"frame_{t:.2f}.jpg")
        tasks.append(extract_frame_async(video_path, t, output_path))
    results = []
    for task in asyncio.as_completed(tasks):
        success, _ = await task
        if success:
            # 实际获取路径需要从任务中提取，此处暂不实现
            pass
    return results