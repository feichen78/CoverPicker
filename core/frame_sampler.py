import subprocess
import numpy as np
import cv2


class FrameSampler:

    # =========================
    # 抽帧 + 评分
    # =========================
    def sample_frames(self, video, segment, count, out_dir, used_times):

        import os
        os.makedirs(out_dir, exist_ok=True)

        duration = segment.end - segment.start
        step = duration / count

        results = []

        for i in range(count):

            t = segment.start + i * step

            if any(abs(t - u) < 0.5 for u in used_times):
                continue

            path = os.path.join(out_dir, f"frame_{i}.jpg")

            subprocess.run([
                "ffmpeg",
                "-ss", str(t),
                "-i", video,
                "-vframes", "1",
                "-q:v", "2",
                "-y",
                path
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            score = self._score_frame(path)

            results.append({
                "time": t,
                "path": path,
                "score": score
            })

        # 按分数排序（核心升级）
        results.sort(key=lambda x: x["score"], reverse=True)

        return results

    # =========================
    # ⭐ 帧评分函数（v2.3核心）
    # =========================
    def _score_frame(self, path):

        try:
            img = cv2.imread(path)

            if img is None:
                return 0

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # 1️⃣ 清晰度（拉普拉斯）
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()

            # 2️⃣ 亮度
            brightness = np.mean(gray) / 255.0

            # 3️⃣ 对比度
            contrast = np.std(gray)

            # 综合评分
            score = (
                sharpness * 0.6 +
                contrast * 0.3 +
                brightness * 0.1
            )

            return float(score)

        except:
            return 0