import subprocess
import os
import cv2
import numpy as np
import random


class FramePipeline:

    # =========================
    # ⭐ 改进采样（optimize真正生效）
    # =========================
    def sample(self, video, segment, count, out_dir, jitter=0.0):

        os.makedirs(out_dir, exist_ok=True)

        duration = segment.end - segment.start
        step = duration / count

        frames = []

        for i in range(count):

            base_t = segment.start + i * step

            # ⭐ OPTIMIZE核心：引入扰动（打破重复）
            t = base_t + random.uniform(-jitter, jitter)

            t = max(segment.start, min(segment.end, t))

            path = os.path.join(out_dir, f"f_{i}.jpg")

            subprocess.run([
                "ffmpeg",
                "-ss", str(t),
                "-i", video,
                "-vframes", "1",
                "-q:v", "2",
                "-y",
                path
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            frames.append({
                "time": t,
                "path": path,
                "score": self.score(path)
            })

        return frames

    # =========================
    # ⭐ 真正可区分评分（修复best）
    # =========================
    def score(self, path):

        img = cv2.imread(path)
        if img is None:
            return 0

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # edge（信息量）
        edges = cv2.Canny(gray, 80, 150)
        edge_density = np.mean(edges)

        # sharpness
        sharp = cv2.Laplacian(gray, cv2.CV_64F).var()

        # entropy（关键新增）
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist = hist / (hist.sum() + 1e-6)
        entropy = -np.sum(hist * np.log2(hist + 1e-6))

        return float(
            sharp * 0.5 +
            edge_density * 2.0 +
            entropy * 1.5
        )