# region --- 截图生成引擎 (修复中文路径编码问题) ---
import subprocess
import os
from pathlib import Path

class FrameGenerator:
    """
    负责在指定的时间点生成视频截图。
    """
    @staticmethod
    def generate(video_path, timestamp_sec, output_path):
        """
        在指定时间点生成截图。
        :param video_path: 视频文件路径
        :param timestamp_sec: 截图时间点（秒）
        :param output_path: 截图保存路径
        :return: True (成功) / False (失败)
        """
        # 确保输出目录存在
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            'ffmpeg',
            '-ss', str(timestamp_sec),  # 跳转到指定时间点
            '-i', video_path,           # 输入文件
            '-vf', 'scale=320:-1',      # 缩放宽度为 320，保持比例
            '-vframes', '1',            # 只取 1 帧
            '-y',                       # 覆盖已有文件
            output_path
        ]

        try:
            # 【关键修复】强制指定 encoding='utf-8'，防止 Windows 下中文路径导致 GBK 解码崩溃
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0:
                return True
            else:
                print(f"  [警告] FFmpeg 截图失败: {video_path} @ {timestamp_sec}s")
                return False
        except Exception as e:
            print(f"  [错误] 截图异常: {e}")
            return False

# endregion