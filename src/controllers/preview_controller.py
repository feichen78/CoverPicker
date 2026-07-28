# src/controllers/preview_controller.py
# v3.0.2: 低质量预览帧 (640x360)

import os
import asyncio
import logging
import subprocess
from typing import Optional, Tuple

from src.video_scanner import extract_frame, extract_video_clip

logger = logging.getLogger(__name__)


class PreviewController:
    """
    预览面板控制器 - 管理帧预览和视频片段导出
    """

    def __init__(self):
        self.video_path: Optional[str] = None
        self.duration: float = 0.0
        self.temp_dir: Optional[str] = None

        # 当前预览位置
        self.preview_time: float = 0.0

        # 片段选择范围
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.is_start_set: bool = False
        self.is_end_set: bool = False

        # 当前显示的帧路径
        self.current_frame_path: Optional[str] = None

        self._load_task: Optional[asyncio.Task] = None
        self._progress_callback: Optional[callable] = None

        if os.name == 'nt':
            self._CREATE_NO_WINDOW = 0x08000000
        else:
            self._CREATE_NO_WINDOW = 0

    def set_progress_callback(self, callback: callable):
        """注册进度更新回调"""
        self._progress_callback = callback

    def _notify_progress(self, message: str):
        if self._progress_callback:
            self._progress_callback(message)

    def set_video(self, video_path: str, duration: float, temp_dir: str):
        """设置当前视频"""
        self.video_path = video_path
        self.duration = duration
        self.temp_dir = temp_dir
        self.preview_time = 0.0
        self.start_time = 0.0
        self.end_time = 0.0
        self.is_start_set = False
        self.is_end_set = False
        self.current_frame_path = None

    def set_preview_time(self, time_sec: float) -> Optional[str]:
        """
        设置预览时间点，同步生成帧
        返回帧路径或 None
        v3.0.2: 使用低质量预览帧 (640x360)
        """
        if not self.video_path:
            return None

        time_sec = max(0, min(self.duration, time_sec))
        self.preview_time = time_sec

        frame_path = self._get_frame(time_sec)
        return frame_path

    def _get_frame(self, time_sec: float) -> Optional[str]:
        """v3.0.2: 获取指定时间点的帧，使用低质量预览帧 (640x360)"""
        if not self.video_path or not self.temp_dir:
            return None

        # 生成临时文件名（包含分辨率标识）
        frame_name = f"preview_{int(time_sec * 100)}_640.jpg"
        frame_path = os.path.join(self.temp_dir, frame_name)

        # 如果文件已存在且接近当前时间，直接返回
        if os.path.exists(frame_path):
            import time
            if time.time() - os.path.getmtime(frame_path) < 300:  # 5分钟缓存
                return frame_path

        # v3.0.2: 使用低质量预览帧（640x360）
        try:
            cmd = [
                "ffmpeg", "-hide_banner",
                "-skip_frame", "nokey",
                "-ss", str(time_sec),
                "-i", self.video_path,
                "-frames:v", "1",
                "-vf", "scale=640:-1",
                "-q:v", "6",
                "-y", frame_path
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='ignore',
                timeout=30, creationflags=self._CREATE_NO_WINDOW
            )
            if result.returncode == 0 and os.path.exists(frame_path) and os.path.getsize(frame_path) > 0:
                return frame_path
            else:
                return self._get_frame_original(time_sec)
        except Exception as e:
            logger.error(f"预览帧提取失败: {e}")
            return self._get_frame_original(time_sec)

    def _get_frame_original(self, time_sec: float) -> Optional[str]:
        """原始质量提取帧（回退方案）"""
        if not self.video_path or not self.temp_dir:
            return None

        frame_name = f"preview_{int(time_sec * 100)}.jpg"
        frame_path = os.path.join(self.temp_dir, frame_name)

        if os.path.exists(frame_path):
            import time
            if time.time() - os.path.getmtime(frame_path) < 300:
                return frame_path

        try:
            success = extract_frame(self.video_path, time_sec, frame_path)
            if success:
                return frame_path
        except Exception as e:
            logger.error(f"预览帧提取失败（原始质量）: {e}")

        return None

    async def load_frame_async(self, time_sec: float) -> Optional[str]:
        """异步加载帧（用于大跳转）"""
        if not self.video_path or not self.temp_dir:
            return None

        time_sec = max(0, min(self.duration, time_sec))
        self.preview_time = time_sec

        frame_name = f"preview_{int(time_sec * 100)}_640.jpg"
        frame_path = os.path.join(self.temp_dir, frame_name)

        if os.path.exists(frame_path):
            return frame_path

        try:
            self._notify_progress(f"正在加载预览帧 @ {time_sec:.1f}s")
            cmd = [
                "ffmpeg", "-hide_banner",
                "-skip_frame", "nokey",
                "-ss", str(time_sec),
                "-i", self.video_path,
                "-frames:v", "1",
                "-vf", "scale=640:-1",
                "-q:v", "6",
                "-y", frame_path
            ]

            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=30,
                creationflags=self._CREATE_NO_WINDOW
            )
            self._notify_progress("")
            if result.returncode == 0 and os.path.exists(frame_path) and os.path.getsize(frame_path) > 0:
                return frame_path
        except asyncio.CancelledError:
            return None
        except Exception as e:
            logger.error(f"异步加载预览帧失败: {e}")

        return None

    def set_start_time(self, time_sec: float):
        """设置片段起始点"""
        time_sec = max(0, min(self.duration, time_sec))
        self.start_time = time_sec
        self.is_start_set = True
        if not self.is_end_set or self.end_time < self.start_time:
            self.end_time = min(self.duration, self.start_time + 1.0)
            self.is_end_set = True

    def set_end_time(self, time_sec: float):
        """设置片段结束点"""
        time_sec = max(0, min(self.duration, time_sec))
        self.end_time = time_sec
        self.is_end_set = True
        if not self.is_start_set or self.start_time > self.end_time:
            self.start_time = max(0, self.end_time - 1.0)
            self.is_start_set = True

    def clear_range(self):
        """清除片段选择"""
        self.start_time = 0.0
        self.end_time = 0.0
        self.is_start_set = False
        self.is_end_set = False

    def get_range(self) -> Tuple[float, float]:
        """获取当前选择的片段范围 (start, end)"""
        if self.is_start_set and self.is_end_set:
            return (min(self.start_time, self.end_time), max(self.start_time, self.end_time))
        return (0.0, 0.0)

    def get_range_duration(self) -> float:
        """获取片段时长"""
        start, end = self.get_range()
        return end - start

    def is_range_valid(self) -> bool:
        """检查片段是否有效"""
        start, end = self.get_range()
        return self.is_start_set and self.is_end_set and (end - start) > 0.5

    async def export_clip(
        self,
        output_dir: str,
        re_encode: bool = False
    ) -> Tuple[bool, str]:
        """
        导出视频片段
        
        Returns:
            (是否成功, 输出路径或错误信息)
        """
        if not self.video_path:
            return (False, "未加载视频")

        if not self.is_range_valid():
            start, end = self.get_range()
            duration = end - start
            if duration <= 0:
                return (False, "请先选择有效的片段范围（起始点 < 结束点）")
            return (False, f"请先选择片段范围（当前范围: {start:.1f}s - {end:.1f}s，时长 {duration:.1f}s）")

        start, end = self.get_range()
        if end - start < 0.5:
            return (False, f"片段太短（{end - start:.1f}s），请选择至少 0.5 秒")

        video_name = os.path.splitext(os.path.basename(self.video_path))[0]
        output_filename = f"{video_name}_clip_{start:.1f}s_{end:.1f}s.mp4"
        output_path = os.path.join(output_dir, output_filename)

        self._notify_progress(f"正在导出片段 {start:.1f}s - {end:.1f}s ...")
        try:
            success = await asyncio.to_thread(
                extract_video_clip,
                self.video_path,
                start,
                end,
                output_path,
                re_encode
            )
            self._notify_progress("")
            if success:
                return (True, output_path)
            else:
                return (False, "导出失败，请检查视频格式是否支持无损复制。可尝试重新编码（暂不支持）")
        except Exception as e:
            self._notify_progress("")
            return (False, f"导出异常: {str(e)}")