# core/state_manager.py

import json
import os


class StateManager:

    def __init__(self):
        self.data_file = "cache/state.json"

        os.makedirs("cache", exist_ok=True)

        if not os.path.exists(self.data_file):
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump({}, f)

        self.data = self._load()

    def _load(self):
        with open(self.data_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self):
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    # ---------------- 收藏 ----------------
    def add_favorite(self, video_id, path):

        self.data.setdefault(video_id, {})
        self.data[video_id].setdefault("favorites", [])

        if path not in self.data[video_id]["favorites"]:
            self.data[video_id]["favorites"].append(path)

        self._save()

    def get_favorites(self, video_id):
        return self.data.get(video_id, {}).get("favorites", [])

    # ---------------- 抽样记录 ----------------
    def add_sample_time(self, video_id, t):

        self.data.setdefault(video_id, {})
        self.data[video_id].setdefault("sample_times", [])

        self.data[video_id]["sample_times"].append(t)
        self._save()

    def get_sampled_times(self, video_id):
        return self.data.get(video_id, {}).get("sample_times", [])

    # ---------------- 局部历史栈（v2.0新增） ----------------
    def push_local_stack(self, video_id, images):

        self.data.setdefault(video_id, {})
        self.data[video_id].setdefault("local_stack", [])

        self.data[video_id]["local_stack"].append(images)

        self._save()

    def pop_local_stack(self, video_id):

        stack = self.data.get(video_id, {}).get("local_stack", [])

        if len(stack) <= 1:
            return None

        stack.pop()
        self._save()

        return stack[-1]