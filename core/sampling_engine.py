# SamplingEngine 均匀采样、去重、黑屏过滤、分区权重算法
import random
from typing import List
from config import FRAME_DUPLICATE_THRESHOLD_SEC
from core.state_manager import Video, Segment, Frame
from core.ffmpeg_engine import FFmpegEngine
from core.cache_manager import CacheManager

class SamplingEngine:
    def __init__(self, ffmpeg: FFmpegEngine, cache_mgr: CacheManager):
        self.ffmpeg = ffmpeg
        self.cache_mgr = cache_mgr
        random.seed(42)

    def _time_duplicate_filter(self, candidate_ts: List[float]) -> List[float]:
        clean = []
        for t in candidate_ts:
            dup = False
            for exist_t in clean:
                if abs(t - exist_t) < FRAME_DUPLICATE_THRESHOLD_SEC:
                    dup = True
                    break
            if not dup:
                clean.append(t)
        return clean

    def _gen_segment_weight(self, seg: Segment, unvisited_bonus: float = 0.3, fav_bonus: float = 0.5) -> float:
        weight = 1.0
        if not seg.visited:
            weight += unvisited_bonus
        return weight

    def sample_segment(self, video: Video, target_seg: Segment, grid_size: int, gen_id: int) -> List[Frame]:
        ts_candidates = []
        seg_start = target_seg.start_time
        seg_end = target_seg.end_time
        max_per_seg = int(grid_size / 3)

        for _ in range(grid_size * 3):
            t = random.uniform(seg_start, seg_end)
            ts_candidates.append(t)

        unique_ts = self._time_duplicate_filter(ts_candidates)
        unique_ts = unique_ts[:max_per_seg]

        frames = []
        for ts in unique_ts:
            cache_path = self.cache_mgr.get_frame_cache_path(video.file_hash, gen_id, ts)
            if self.cache_mgr.cache_exists(cache_path):
                if not self.ffmpeg.is_black_frame(cache_path):
                    frame = Frame(timestamp=ts, cache_path=cache_path)
                    frames.append(frame)
                continue
            # 生成新帧
            self.ffmpeg.extract_frame(video.path, ts, cache_path)
            self.cache_mgr.add_cache_record(cache_path, video.file_hash)
            if self.ffmpeg.is_black_frame(cache_path):
                continue
            frame = Frame(timestamp=ts, cache_path=cache_path)
            frames.append(frame)
        return frames[:grid_size]

    def sample_global(self, video: Video, grid_size: int, gen_id: int) -> List[Frame]:
        all_ts = []
        for seg in video.segments:
            w = self._gen_segment_weight(seg)
            seg_sample_cnt = int(grid_size * w / len(video.segments)) + 1
            for _ in range(seg_sample_cnt):
                t = random.uniform(seg.start_time, seg.end_time)
                all_ts.append(t)
        unique_ts = self._time_duplicate_filter(all_ts)
        frames = []
        for ts in unique_ts:
            cache_path = self.cache_mgr.get_frame_cache_path(video.file_hash, gen_id, ts)
            if self.cache_mgr.cache_exists(cache_path):
                if not self.ffmpeg.is_black_frame(cache_path):
                    frames.append(Frame(ts, cache_path))
                continue
            self.ffmpeg.extract_frame(video.path, ts, cache_path)
            self.cache_mgr.add_cache_record(cache_path, video.file_hash)
            if self.ffmpeg.is_black_frame(cache_path):
                continue
            frames.append(Frame(ts, cache_path))
        return frames[:grid_size]