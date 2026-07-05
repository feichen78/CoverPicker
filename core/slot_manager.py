import random

class SlotManager:

    def __init__(self):
        self.slots = []

    # =========================
    def init_slots(self, frames):

        self.slots = []

        for f in frames:
            self.slots.append({
                "frame": f,
                "locked": False
            })

    # =========================
    def get_frames(self):

        return [s["frame"] for s in self.slots]

    # =========================
    def toggle_lock(self, idx):

        self.slots[idx]["locked"] = not self.slots[idx]["locked"]

    # =========================
    def replace_unlocked(self, new_frames):

        j = 0

        for i, s in enumerate(self.slots):

            if not s["locked"] and j < len(new_frames):

                self.slots[i]["frame"] = new_frames[j]
                j += 1

    # =========================
    def best(self):

        def score(s):
            return s["frame"]["score"]

        return max(self.slots, key=score)