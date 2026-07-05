# core/local_refine_engine.py

import random
import os


class LocalRefineEngine:
    """
    局部强化抽帧：
    - 输入某个时间点
    - 生成 ±window 秒范围
    """

    def __init__(self, window=4):
        self.window = window

    def build_local_segment(self, base_time, video_duration):
        start = max(0, base_time - self.window)
        end = min(video_duration, base_time + self.window)

        return start, end

    def sample_local_times(self, start, end, count=9, used_times=None):
        used_times = used_times or []

        results = []
        tries = 0

        while len(results) < count and tries < count * 10:

            t = random.uniform(start, end)

            if any(abs(t - u) < 0.8 for u in used_times):
                tries += 1
                continue

            results.append(t)
            used_times.append(t)

            tries += 1

        return results