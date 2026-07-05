import os

class CacheManager:

    def get_cache_dir(self, video_hash, level):
        path = f"cache/{video_hash}/l{level}"
        os.makedirs(path, exist_ok=True)
        return path

    def clear_unlocked(self, frame_state):
        frame_state.frames = []