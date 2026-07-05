class FrameState:
    def __init__(self):
        self.frames = []
        self.locked = set()
        self.excluded = set()
        self.sampled = False


class VideoState:
    def __init__(self):
        self.segments = {
            "A": FrameState(),
            "B": FrameState(),
            "C": FrameState(),
            "D": FrameState(),
            "E": FrameState(),
        }
        self.current_segment = "A"
        self.center_time = 0
        self.video_path = None


class StateManager:
    def __init__(self):
        self.videos = {}
        self.current_video = None

    def load_video(self, path):
        if path not in self.videos:
            self.videos[path] = VideoState()
        self.current_video = self.videos[path]
        self.current_video.video_path = path
        return self.videos[path]