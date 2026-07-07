# ClipEngine v3.1 无损视频片段导出
from pathlib import Path
from core.ffmpeg_engine import FFmpegEngine
from config import CLIP_DURATION_OPTIONS, CLIP_DIR, EXPORT_IMAGE_FORMAT, EXPORT_IMAGE_QUALITY

class ClipEngine:
    def __init__(self, ffmpeg: FFmpegEngine):
        self.ffmpeg = ffmpeg
        CLIP_DIR.mkdir(parents=True, exist_ok=True)

    def _get_unique_clip_path(self, video_hash: str, start: float, duration: float) -> str:
        """生成不重名导出片段路径"""
        target_folder = CLIP_DIR / video_hash
        target_folder.mkdir(exist_ok=True)
        idx = 1
        while True:
            fname = f"clip_{start:.1f}_{duration}_{idx}.mp4"
            full_path = target_folder / fname
            if not full_path.exists():
                return str(full_path)
            idx += 1

    def export_lossless_clip(self, video_path: str, video_hash: str, start_sec: float, duration_sec: float):
        """无损流复制导出片段，不二次编码"""
        out_path = self._get_unique_clip_path(video_hash, start_sec, duration_sec)
        self.ffmpeg.extract_clip_lossless(video_path, start_sec, duration_sec, out_path)
        return out_path

    def export_single_still(self, cache_img_path: str, save_folder: str, file_index: int):
        """导出单张剧照到指定目录"""
        from PIL import Image
        save_dir = Path(save_folder)
        save_dir.mkdir(parents=True, exist_ok=True)
        out_name = f"cover_{file_index:02d}.{EXPORT_IMAGE_FORMAT}"
        out_full = str(save_dir / out_name)
        img = Image.open(cache_img_path)
        img.save(out_full, quality=EXPORT_IMAGE_QUALITY)
        return out_full