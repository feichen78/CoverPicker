# core/frame_sampler.py

import random
import subprocess
import os


class FrameSampler:
    """
    改进版抽帧：
    - 避免重复时间点
    - 支持区间抽帧
    """

    def __init__(self, ffmpeg_path="ffmpeg"):
        self.ffmpeg = ffmpeg_path

    def sample_frames(self, video_path, segment, count, output_dir, used_times=None):
        """
        在 segment 区间抽取 count 帧
        """

        os.makedirs(output_dir, exist_ok=True)

        used_times = used_times or []

        duration = segment.end - segment.start

        results = []

        tries = 0

        while len(results) < count and tries < count * 10:

            t = segment.start + random.random() * duration

            # 避免重复时间点
            if any(abs(t - u) < 1.0 for u in used_times):
                tries += 1
                continue

            output_file = os.path.join(
                output_dir,
                f"frame_{len(results)}.jpg"
            )

            cmd = [
                self.ffmpeg,
                "-ss", str(t),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                "-y",
                output_file
            ]

            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            if os.path.exists(output_file):
                results.append({
                    "time": t,
                    "path": output_file
                })

                used_times.append(t)

            tries += 1

        return results