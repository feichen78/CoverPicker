# FFmpegEngine 统一封装抽帧、读取元数据、网络重试、路径兼容
import os
import time
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
from config import (
    FFMPEG_RETRY_COUNT, FFMPEG_RETRY_DELAY_SEC,
    NETWORK_PATH_KEYWORDS, BLACK_FRAME_BRIGHTNESS_THRESHOLD
)

def is_network_path(path: str) -> bool:
    for kw in NETWORK_PATH_KEYWORDS:
        if kw in path:
            return True
    return False

class FFmpegEngine:
    def __init__(self):
        pass

    def _run_cmd_with_retry(self, cmd: list) -> Tuple[bool, str]:
        err_msg = ""
        for i in range(FFMPEG_RETRY_COUNT):
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                out, err = proc.communicate()
                if proc.returncode == 0:
                    return True, out
                err_msg = err
            except Exception as e:
                err_msg = str(e)
            time.sleep(FFMPEG_RETRY_DELAY_SEC)
        return False, err_msg

    def get_video_duration(self, video_path: str) -> float:
        cmd = [
            "ffmpeg",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            "-i", video_path
        ]
        ok, output = self._run_cmd_with_retry(cmd)
        if not ok:
            raise RuntimeError(f"读取视频时长失败: {output}")
        return float(output.strip())

    def extract_frame(self, video_path: str, timestamp: float, out_img_path: str):
        cmd = [
            "ffmpeg",
            "-ss", str(timestamp),
            "-i", video_path,
            "-frames:v", "1",
            "-y", out_img_path
        ]
        ok, msg = self._run_cmd_with_retry(cmd)
        if not ok:
            raise RuntimeError(f"抽帧失败 {timestamp}s: {msg}")

    def calc_frame_brightness(self, img_path: str) -> float:
        img = Image.open(img_path).convert("L")
        hist = img.histogram()
        total = sum(i * v for i, v in enumerate(hist))
        pix_cnt = sum(hist)
        if pix_cnt == 0:
            return 0.0
        return total / pix_cnt

    def is_black_frame(self, img_path: str) -> bool:
        br = self.calc_frame_brightness(img_path)
        return br < BLACK_FRAME_BRIGHTNESS_THRESHOLD

    def extract_clip_lossless(self, video_path: str, start: float, duration: float, out_path: str):
        cmd = [
            "ffmpeg",
            "-ss", str(start),
            "-t", str(duration),
            "-i", video_path,
            "-c", "copy",
            "-y", out_path
        ]
        ok, msg = self._run_cmd_with_retry(cmd)
        if not ok:
            raise RuntimeError(f"导出片段失败: {msg}")