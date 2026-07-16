# src/video_scanner.py

import os
import json
import subprocess
import logging
import time
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Windows 下隐藏控制台窗口
if os.name == 'nt':
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0

# 支持的视频格式（v1.3 扩展）
SUPPORTED_VIDEO_EXTENSIONS = {
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm',
    '.m4v', '.mpg', '.mpeg', '.ts', '.m2ts', '.3gp', '.3g2',
    '.asf', '.vob', '.ogv', '.ogg', '.divx', '.xvid', '.mts',
    '.m2v', '.m4p', '.m4b', '.m4r', '.mpv', '.mpe', '.mxf',
    '.rm', '.rmvb', '.swf', '.f4v', '.f4p', '.f4a', '.f4b'
}


def scan_videos(directory: str, extensions: set = None) -> List[str]:
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


def get_video_duration(video_path: str, retries: int = 1) -> Optional[float]:
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
    
    for attempt in range(retries + 1):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=30,
                creationflags=CREATE_NO_WINDOW
            )
            if result.returncode == 0 and result.stdout.strip():
                duration = float(result.stdout.strip())
                return duration
            else:
                if attempt < retries:
                    logger.warning(f"FFprobe 获取时长失败 (重试 {attempt+1}/{retries}): {video_path}")
                    time.sleep(0.5)
                else:
                    logger.error(f"FFprobe 获取时长失败: {video_path}, stderr: {result.stderr}")
                    return None
        except subprocess.TimeoutExpired:
            if attempt < retries:
                logger.warning(f"FFprobe 超时 (重试 {attempt+1}/{retries}): {video_path}")
                time.sleep(0.5)
            else:
                logger.error(f"FFprobe 超时: {video_path}")
                return None
        except Exception as e:
            logger.error(f"FFprobe 异常: {video_path}, {e}")
            return None
    return None


def get_video_info(video_path: str) -> Optional[dict]:
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
            timeout=30,
            creationflags=CREATE_NO_WINDOW
        )
        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout)
            return data
        return None
    except Exception as e:
        logger.error(f"FFprobe 获取信息失败: {video_path}, {e}")
        return None


def extract_frame(video_path: str, timestamp: float, output_path: str, retries: int = 1) -> bool:
    """
    提取视频帧（快速 Seek + 跳过非关键帧）
    - -skip_frame nokey: 只解码关键帧，大幅加速大文件定位
    - -ss 在 -i 之前: 快速定位到关键帧附近
    """
    for attempt in range(retries + 1):
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-skip_frame", "nokey",          # 只解码关键帧，加速
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
                timeout=60,
                creationflags=CREATE_NO_WINDOW
            )
            if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return True
            else:
                if attempt < retries:
                    logger.warning(f"提取帧失败 (重试 {attempt+1}/{retries}): {video_path} @ {timestamp}s")
                    time.sleep(0.5)
                else:
                    logger.error(f"提取帧失败: {video_path} @ {timestamp}s, stderr: {result.stderr}")
                    return False
        except subprocess.TimeoutExpired:
            if attempt < retries:
                logger.warning(f"FFmpeg 提取帧超时 (重试 {attempt+1}/{retries}): {video_path} @ {timestamp}s")
                time.sleep(0.5)
            else:
                logger.error(f"FFmpeg 提取帧超时: {video_path} @ {timestamp}s")
                return False
        except Exception as e:
            logger.error(f"FFmpeg 提取帧异常: {video_path} @ {timestamp}s, {e}")
            return False
    return False


def extract_frames_batch(video_path: str, timestamps: List[float], output_dir: str) -> List[str]:
    """批量提取视频帧（逐个调用，兼容性好）"""
    outputs = []
    total = len(timestamps)
    for i, ts in enumerate(timestamps):
        output_path = os.path.join(output_dir, f"frame_{i:03d}.jpg")
        if extract_frame(video_path, ts, output_path):
            outputs.append(output_path)
    return outputs


def extract_frames_batch_fast(video_path: str, timestamps: List[float], output_dir: str) -> List[str]:
    """
    单次 FFmpeg 调用批量提取多帧（更快，适合密度 >= 12）
    使用 fps filter 一次性提取所有帧
    """
    if not timestamps:
        return []
    
    count = len(timestamps)
    
    # 密度 <= 9 时，逐个提取更精确
    if count <= 9:
        return extract_frames_batch(video_path, timestamps, output_dir)
    
    # 计算时间范围
    sorted_times = sorted(timestamps)
    start = sorted_times[0]
    end = sorted_times[-1]
    duration = end - start
    
    # 如果时间跨度太小（< 1秒），退回到逐个提取
    if duration < 1.0:
        logger.debug(f"时间跨度 {duration:.2f}s < 1s，使用逐个提取")
        return extract_frames_batch(video_path, timestamps, output_dir)
    
    # 计算帧率：帧数 / 时间跨度，并稍微调整确保能提取到所有帧
    fps = count / duration
    
    # 添加额外帧确保覆盖所有时间点
    # 输出模板
    output_template = os.path.join(output_dir, "frame_%d.jpg")
    
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-skip_frame", "nokey",              # 只解码关键帧，加速
        "-ss", str(start - 0.5),             # 稍微提前开始，确保覆盖
        "-i", video_path,
        "-t", str(duration + 1.0),           # 稍微延长，确保覆盖
        "-vf", f"fps={fps},scale=-1:-1",     # 保持原始分辨率，fps 控制帧数
        "-q:v", "2",
        "-frames:v", str(count + 2),         # 多提取几帧备用
        "-y",
        output_template
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=120,
            creationflags=CREATE_NO_WINDOW
        )
        if result.returncode != 0:
            logger.warning(f"批量提取失败，回退到逐个提取: {video_path}")
            return extract_frames_batch(video_path, timestamps, output_dir)
        
        # 收集输出文件
        all_outputs = []
        for i in range(count + 3):
            out_path = os.path.join(output_dir, f"frame_{i}.jpg")
            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                all_outputs.append(out_path)
        
        if len(all_outputs) < count:
            logger.warning(f"批量提取数量不足 ({len(all_outputs)}/{count})，回退到逐个提取")
            return extract_frames_batch(video_path, timestamps, output_dir)
        
        # 取前 count 个
        outputs = all_outputs[:count]
        
        # 删除多余的帧
        for out_path in all_outputs[count:]:
            try:
                os.remove(out_path)
            except:
                pass
        
        logger.debug(f"批量提取成功: {len(outputs)} 帧，耗时单次 FFmpeg 调用")
        return outputs
    except Exception as e:
        logger.error(f"批量提取异常，回退到逐个提取: {e}")
        return extract_frames_batch(video_path, timestamps, output_dir)


def extract_video_clip(video_path: str, start_time: float, end_time: float, output_path: str, re_encode: bool = False) -> bool:
    if not os.path.exists(video_path):
        logger.error(f"视频文件不存在: {video_path}")
        return False
    
    duration = end_time - start_time
    if duration <= 0:
        logger.error("起始时间必须小于结束时间")
        return False
    
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    if re_encode:
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
        # 检测音频流
        probe_cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        try:
            result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW)
            has_audio = "audio" in result.stdout
        except Exception:
            has_audio = True
        
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
            cmd.extend(["-an"])
        cmd.extend(["-avoid_negative_ts", "make_zero", "-y", output_path])
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=300,
            creationflags=CREATE_NO_WINDOW
        )
        success = result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
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
    if duration <= 0 or num_segments <= 0:
        return []
    
    if duration < 60:
        return [("A", 0.0, duration)]
    
    segment_duration = duration / num_segments
    segments = []
    for i in range(num_segments):
        start = i * segment_duration
        end = start + segment_duration
        label = chr(ord('A') + i)
        segments.append((label, start, end))
    return segments