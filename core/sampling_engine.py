# SamplingEngine 路径兼容修复版
import random
from pathlib import Path
from typing import List
from config import ZOOM_LEVELS, FRAME_DUPLICATE_THRESHOLD_SEC
from core.state_manager import Video, Segment, Frame
from core.ffmpeg_engine import FFmpegEngine

class SamplingEngine:
    def __init__(self, ffmpeg: FFmpegEngine, cache_mgr):
        self.ffmpeg = ffmpeg
        self.cache_mgr = cache_mgr
        random.seed(42)

    def _normalize_path(self, p: str) -> str:
        # 统一路径分隔符，消除正反斜杠混合导致ffmpeg读取失败
        return str(Path(p).resolve())

    def _filter_duplicate_time(self, ts_list: List[float]) -> List[float]:
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

    def sample_segment(self, video: Video, target_seg: Segment, grid_size: int, gen_id: int) -> List[Frame]:
        vid_path = self._normalize_path(video.path)
        seg_start = target_seg.start_time
        seg_end = target_seg.end_time
        sample_count = grid_size * 3
        ts_candidates = []
        for _ in range(sample_count):
            t = random.uniform(seg_start, seg_end)
            ts_candidates.append(t)
        unique_ts = self._filter_duplicate_time(ts_candidates)
        frame_list = []
        for ts in unique_ts:
            cache_path = self.cache_mgr.get_frame_cache_path(video.file_hash, gen_id, ts)
            if self.cache_mgr.cache_exists(cache_path):
                bright = self.ffmpeg.calc_frame_brightness(cache_path)
                if not self.ffmpeg.is_black_frame(cache_path):
                    frame_list.append(Frame(timestamp=ts, cache_path=cache_path))
                continue
            # 抽帧
            try:
                self.ffmpeg.extract_frame(vid_path, ts, cache_path)
            except Exception as e:
                print(f"[SAMPLING SKIP] 抽帧失败 ts={ts}, err={str(e)}")
                continue
            bright = self.ffmpeg.calc_frame_brightness(cache_path)
            self.cache_mgr.add_cache_record(cache_path, video.file_hash)
            if not self.ffmpeg.is_black_frame(cache_path):
                frame_list.append(Frame(timestamp=ts, cache_path=cache_path))
        return frame_list[:grid_size]