import subprocess
import os

class FFmpegEngine:

    def extract_frame(self, video, t, output):
        cmd = [
            "ffmpeg",
            "-ss", str(t),
            "-i", video,
            "-vframes", "1",
            "-q:v", "2",
            output
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def extract_clip(self, video, start, end, output):
        cmd = [
            "ffmpeg",
            "-ss", str(start),
            "-to", str(end),
            "-i", video,
            "-c", "copy",
            output
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)