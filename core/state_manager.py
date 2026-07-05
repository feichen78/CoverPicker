# core/state_manager.py

import os
import json
from collections import defaultdict


class StateManager:
    """
    记录：
    - 已浏览分区
    - 已抽帧时间点
    - 收藏图片
    """

    def __init__(self, base_dir="cache"):
        self.base_dir = base_dir
        self.state_file = os.path.join(base_dir, "state.json")

        self.data = {
            "segments_viewed": {},
            "sampled_times": {},
            "favorites": {}
        }

        self._load()

    # -------------------------
    # IO
    # -------------------------
    def _load(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, "r", encoding="utf-8") as f:
                self.data = json.load(f)

    def _save(self):
        os.makedirs(self.base_dir, exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    # -------------------------
    # Segment 状态
    # -------------------------
    def mark_segment_viewed(self, video_id, segment_name):
        self.data["segments_viewed"].setdefault(video_id, [])
        if segment_name not in self.data["segments_viewed"][video_id]:
            self.data["segments_viewed"][video_id].append(segment_name)
        self._save()

    def get_viewed_segments(self, video_id):
        return self.data["segments_viewed"].get(video_id, [])

    # -------------------------
    # 时间点记录（防重复抽帧）
    # -------------------------
    def add_sample_time(self, video_id, t):
        self.data["sampled_times"].setdefault(video_id, [])
        self.data["sampled_times"][video_id].append(t)
        self._save()

    def get_sampled_times(self, video_id):
        return self.data["sampled_times"].get(video_id, [])

    # -------------------------
    # 收藏
    # -------------------------
    def add_favorite(self, video_id, img_path):
        self.data["favorites"].setdefault(video_id, [])
        if img_path not in self.data["favorites"][video_id]:
            self.data["favorites"][video_id].append(img_path)
        self._save()

    def get_favorites(self, video_id):
        return self.data["favorites"].get(video_id, [])