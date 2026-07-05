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

    # =========================
    # ⭐ 收藏池（候选）
    # =========================
    def add_candidate(self, video_id, path):

        self.data.setdefault(video_id, {})
        self.data[video_id].setdefault("candidates", [])

        if path not in self.data[video_id]["candidates"]:
            self.data[video_id]["candidates"].append(path)

        self._save()

    def remove_candidate(self, video_id, path):

        self.data.setdefault(video_id, {})
        self.data[video_id].setdefault("candidates", [])

        if path in self.data[video_id]["candidates"]:
            self.data[video_id]["candidates"].remove(path)

        self._save()

    def get_candidates(self, video_id):
        return self.data.get(video_id, {}).get("candidates", [])

    # =========================
    # 🔒 最终封面
    # =========================
    def set_final_cover(self, video_id, path):

        self.data.setdefault(video_id, {})
        self.data[video_id]["final_cover"] = path
        self._save()

    def get_final_cover(self, video_id):
        return self.data.get(video_id, {}).get("final_cover")

    # =========================
    # 🔁 局部历史栈
    # =========================
    def push_stack(self, video_id, images):

        self.data.setdefault(video_id, {})
        self.data[video_id].setdefault("stack", [])

        self.data[video_id]["stack"].append(images)
        self._save()

    def pop_stack(self, video_id):

        stack = self.data.get(video_id, {}).get("stack", [])

        if len(stack) <= 1:
            return None

        stack.pop()
        self._save()

        return stack[-1]