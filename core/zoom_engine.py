# ZoomEngine v3.1 四层分层精细采样，严格对齐文档L1~L4规则
import random
from typing import List
from config import ZOOM_LEVELS, FRAME_DUPLICATE_THRESHOLD_SEC
from core.state_manager import Video, Segment, Frame, Slot
from core.ffmpeg_engine import FFmpegEngine
from core.cache_manager import CacheManager

class ZoomEngine:
    def __init__(self, ffmpeg: FFmpegEngine, cache_mgr: CacheManager):
        self.ffmpeg = ffmpeg
        self.cache_mgr = cache_mgr
        random.seed(42)

    def _filter_similar_frames(self, base_ts: float, candidate_ts_list: List[float]) -> List[float]:
        """过滤和基准帧时间过近的重复帧"""
        filtered = []
        for t in candidate_ts_list:
            if abs(t - base_ts) < FRAME_DUPLICATE_THRESHOLD_SEC:
                continue
            filtered.append(t)
        return filtered

    def _build_target_segments(self, base_seg: Segment, all_segments: List[Segment], level_cfg) -> List[Segment]:
        """根据Zoom层级确定采样分区范围"""
        target_segs = [base_seg]
        if level_cfg["cross_segment"]:
            # 追加相邻分区
            seg_idx = all_segments.index(base_seg)
            if seg_idx - 1 >= 0:
                target_segs.append(all_segments[seg_idx - 1])
            if seg_idx + 1 < len(all_segments):
                target_segs.append(all_segments[seg_idx + 1])
            # L4全局模式加载全部分区
            if level_cfg["range"] == -1:
                target_segs = all_segments
        return target_segs

    def sample_zoom_frames(self, video: Video, base_timestamp: float, base_segment: Segment, grid_size: int, zoom_level: int, gen_id: int) -> List[Frame]:
        """核心Zoom采样入口，返回一批差异化候选帧"""
        level_cfg = ZOOM_LEVELS[zoom_level]
        target_segs = self._build_target_segments(base_segment, video.segments, level_cfg)
        ts_candidates = []

        for seg in target_segs:
            seg_start = seg.start_time
            seg_end = seg.end_time
            if level_cfg["range"] > 0:
                # 限定基准帧±range秒窗口
                window_low = max(seg_start, base_timestamp - level_cfg["range"])
                window_high = min(seg_end, base_timestamp + level_cfg["range"])
                sample_count = int(grid_size / len(target_segs)) + 2
                for _ in range(sample_count):
                    t = random.uniform(window_low, window_high)
                    ts_candidates.append(t)
            else:
                # L4全局无差别采样
                sample_count = int(grid_size / len(video.segments)) + 2
                for _ in range(sample_count):
                    t = random.uniform(seg_start, seg_end)
                    ts_candidates.append(t)

        # 去重、过滤和基准帧过于接近的时间点
        unique_ts = self._filter_similar_frames(base_timestamp, ts_candidates)
        unique_ts = self._filter_duplicate_time(unique_ts)
        frame_list = []

        for ts in unique_ts:
            cache_path = self.cache_mgr.get_frame_cache_path(video.file_hash, gen_id, ts)
            if self.cache_mgr.cache_exists(cache_path):
                if not self.ffmpeg.is_black_frame(cache_path):
                    frame_list.append(Frame(timestamp=ts, cache_path=cache_path))
                continue
            # 新抽帧并缓存
            self.ffmpeg.extract_frame(video.path, ts, cache_path)
            self.cache_mgr.add_cache_record(cache_path, video.file_hash)
            if self.ffmpeg.is_black_frame(cache_path):
                continue
            frame_list.append(Frame(timestamp=ts, cache_path=cache_path))

        return frame_list[:grid_size]

    def _filter_duplicate_time(self, ts_list: List[float]) -> List[float]:
        """全局时间重复过滤"""
        clean = []
        for t in ts_list:
            dup = False
            for exist in clean:
                if abs(t - exist) < FRAME_DUPLICATE_THRESHOLD_SEC:
                    dup = True
                    break
            if not dup:
                clean.append(t)
        return clean