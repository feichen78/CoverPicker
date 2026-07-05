# core/segment_engine.py

from dataclasses import dataclass


@dataclass
class Segment:
    name: str
    start: float
    end: float


class SegmentEngine:
    """
    将视频划分为 A-E 五个可浏览区间
    默认跳过头尾 10%
    """

    def __init__(self, skip_head=0.1, skip_tail=0.1, segments=5):
        self.skip_head = skip_head
        self.skip_tail = skip_tail
        self.segments = segments

    def build_segments(self, duration: float):
        """
        返回 A-E 分区
        """
        start = duration * self.skip_head
        end = duration * (1 - self.skip_tail)

        total = end - start
        step = total / self.segments

        result = []

        for i in range(self.segments):
            seg_start = start + i * step
            seg_end = start + (i + 1) * step

            name = chr(ord("A") + i)

            result.append(
                Segment(name=name, start=seg_start, end=seg_end)
            )

        return result

    def get_segment_by_name(self, segments, name: str):
        for s in segments:
            if s.name == name:
                return s
        return None