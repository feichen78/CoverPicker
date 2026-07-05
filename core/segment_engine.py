import numpy as np

class SegmentEngine:
    def __init__(self, duration, skip_start=3):
        self.duration = duration
        self.skip_start = skip_start

    def build_segments(self, count=5):
        usable = self.duration - self.skip_start
        step = usable / count

        segments = []
        for i in range(count):
            start = self.skip_start + i * step
            end = self.skip_start + (i + 1) * step
            segments.append((start, end))

        return segments


def get_segment_label(index):
    return ["A", "B", "C", "D", "E"][index]