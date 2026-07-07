# FFmpegEngine 带全量日志打印，定位抽帧失败原因
import os
import time
import subprocess
from pathlib import Path
from typing import Tuple
from PIL import Image
from config import (
    FFMPEG_RETRY_COUNT, FFMPEG_RETRY_DELAY_SEC,
    NETWORK_PATH_KEYWORDS, BLACK_FRAME_BRIGHTNESS_THRESHOLD
)

FFMPEG_BIN = r"C:\ffmpeg\bin\ffmpeg.exe"

def is_network_path(path: str) -> bool:
    for kw in NETWORK_PATH_KEYWORDS:
        if kw in path:
            return True
    return False

class FFmpegEngine:
    def __init__(self):
        print(f"[FFMPEG INIT] 使用路径：{FFMPEG_BIN}")

    def _run_cmd_with_retry(self, cmd: list) -> Tuple[bool, str]:
        err_msg = ""
        for i in range(FFMPEG_RETRY_COUNT):
            print(f"\n[FFMPEG RUN] 第{i+1}次执行命令: {' '.join(cmd)}")
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                out, err = proc.communicate()
                print(f"[FFMPEG STDOUT]\n{out}")
                print(f"[FFMPEG STDERR]\n{err}")
                if proc.returncode == 0:
                    return True, out
                err_msg = f"返回码非0: {proc.returncode}"
            except Exception as e:
                err_msg = f"启动进程异常:{str(e)}"
                print(f"[FFMPEG EXCEPTION] {err_msg}")
            time.sleep(FFMPEG_RETRY_DELAY_SEC)
        return False, err_msg

    def get_video_duration(self, video_path: str) -> float:
        cmd = [
            FFMPEG_BIN,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            "-i", video_path
        ]
        ok, output = self._run_cmd_with_retry(cmd)
        if not ok or not output.strip():
            raise RuntimeError(f"读取视频时长失败: {output}")
        return float(output.strip())

    def extract_frame(self, video_path: str, timestamp: float, out_img_path: str):
        out_p = Path(out_img_path)
        out_p.parent.mkdir(exist_ok=True)
        print(f"[EXTRACT FRAME] 输出路径: {out_img_path}")
        cmd = [
            FFMPEG_BIN,
            "-ss", str(timestamp),
            "-i", video_path,
            "-frames:v", "1",
            "-y", out_img_path
        ]
        ok, msg = self._run_cmd_with_retry(cmd)
        if not ok:
            raise RuntimeError(f"抽帧失败 {timestamp}s: {msg}")
        if not Path(out_img_path).exists():
            raise RuntimeError("FFmpeg执行完成，但输出图片不存在")

    def calc_frame_brightness(self, img_path: str) -> float:
        try:
            img = Image.open(img_path).convert("L")
            hist = img.histogram()
            total = sum(i * v for i, v in enumerate(hist))
            pix_cnt = sum(hist)
            if pix_cnt == 0:
                return 0.0
            return total / pix_cnt
        except Exception:
            return 0.0

    def is_black_frame(self, img_path: str) -> bool:
        br = self.calc_frame_brightness(img_path)
        return br < BLACK_FRAME_BRIGHTNESS_THRESHOLD

    def extract_clip_lossless(self, video_path: str, start: float, duration: float, out_path: str):
        out_p = Path(out_path)
        out_p.parent.mkdir(exist_ok=True)
        cmd = [
            FFMPEG_BIN,
            "-ss", str(start),
            "-t", str(duration),
            "-i", video_path,
            "-c", "copy",
            "-y", out_path
        ]
        ok, msg = self._run_cmd_with_retry(cmd)
        if not ok:
            raise RuntimeError(f"导出片段失败: {msg}")