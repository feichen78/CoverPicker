# SegmentEngine 自动均分A/B/C/D/E分区生成
from typing import List
from config import SEGMENT_COUNT_FIX, MIN_SEGMENT_DURATION_SEC
from core.state_manager import Segment

class SegmentEngine:
    @staticmethod
    def build_segments(total_duration: float) -> List[Segment]:
        segments = []
        if total_duration < MIN_SEGMENT_DURATION_SEC:
            seg = Segment(id="A", start_time=0.0, end_time=total_duration)
            segments.append(seg)
            return segments

        seg_len = total_duration / SEGMENT_COUNT_FIX
        seg_labels = ["A", "B", "C", "D", "E"]
        for idx, label in enumerate(seg_labels):
            s_start = idx * seg_len
            s_end = (idx + 1) * seg_len
            seg = Segment(id=label, start_time=s_start, end_time=s_end)
            segments.append(seg)
        return segments

    @staticmethod
    def get_segment_by_time(segments: List[Segment], t: float) -> Segment:
        for seg in segments:
            if seg.start_time <= t <= seg.end_time:
                return seg
        return segments[0]