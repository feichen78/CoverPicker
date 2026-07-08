# region --- 视频扫描引擎 (集成 5 分区计算) ---
import os
from pathlib import Path

class VideoScanner:
    """
    负责扫描指定目录，并过滤出支持的视频文件。
    """
    def __init__(self, config_manager):
        self.config = config_manager
        self.supported_extensions = self.config.get("supported_extensions", [])

    def scan(self, directory=None):
        """扫描目录并返回视频文件路径列表"""
        target_dir = directory or self.config.get("nas_video_path")
        video_files = []

        if not os.path.exists(target_dir):
            print(f"[错误] 目录不存在: {target_dir}")
            return video_files

        print(f"[扫描] 正在扫描目录: {target_dir} ...")
        try:
            for root, _, files in os.walk(target_dir):
                for file_name in files:
                    if Path(file_name).suffix.lower() in self.supported_extensions:
                        full_path = os.path.join(root, file_name)
                        video_files.append(full_path)
        except PermissionError:
            print("[警告] 遇到无权限访问的子文件夹，已跳过。")

        print(f"[完成] 共找到 {len(video_files)} 个视频文件。")
        return video_files

    @staticmethod
    def calculate_segments(duration_sec):
        """
        根据需求 6.1：将视频总时长自动均分为 5 个 Segment (A/B/C/D/E)。
        如果总时长 < 5 分钟 (300秒)，则合并为单一分区。
        """
        if duration_sec is None or duration_sec <= 0:
            return []

        # 小于 5 分钟，合并为单一分区
        if duration_sec < 300:
            return [{"name": "A", "start": 0, "end": duration_sec}]

        segment_duration = duration_sec / 5
        segments = []
        names = ["A", "B", "C", "D", "E"]
        
        for i in range(5):
            start = i * segment_duration
            end = (i + 1) * segment_duration if i < 4 else duration_sec
            segments.append({
                "name": names[i],
                "start": start,
                "end": end
            })
        
        return segments

# endregion