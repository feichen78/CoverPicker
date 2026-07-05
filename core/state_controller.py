import os
import json


class StateController:

    def __init__(self):
        self.data = {
            "video": None,
            "segment": None,
            "frames": [],
            "selected": None,
            "best": None,
            "candidates": set(),
            "local_stack": []  # 局部放大历史
        }

    # =========================
    def set_video(self, path):
        self.data["video"] = path
        self.data["candidates"] = set()
        self.data["local_stack"] = []

    # =========================
    def set_segment(self, name):
        self.data["segment"] = name
        self.data["frames"] = []
        self.data["selected"] = None
        self.data["best"] = None

    # =========================
    def set_frames(self, frames):
        self.data["frames"] = frames

        if frames:
            self.data["best"] = max(frames, key=lambda x: x["score"])

    # =========================
    def select(self, idx):
        self.data["selected"] = idx

    # =========================
    def get_selected(self):
        idx = self.data["selected"]
        if idx is None:
            return None
        return self.data["frames"][idx]

    # =========================
    def toggle_candidate(self, path):
        if path in self.data["candidates"]:
            self.data["candidates"].remove(path)
        else:
            self.data["candidates"].add(path)

    # =========================
    def get_candidates(self):
        return list(self.data["candidates"])

    # =========================
    def push_local(self, frames):
        self.data["local_stack"].append(self.data["frames"])
        self.data["frames"] = frames

    # =========================
    def pop_local(self):
        if not self.data["local_stack"]:
            return None

        self.data["frames"] = self.data["local_stack"].pop()
        return self.data["frames"]