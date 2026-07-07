# CacheManager 缓存生命周期、容量控制、过期清理、路径生成
import os
import psutil
from pathlib import Path
from config import CACHE_DIR, CACHE_MAX_PER_VIDEO_GB, CACHE_EXPIRE_DAYS
from core.persist_manager import PersistManager

GB_TO_BYTE = 1024 ** 3

class CacheManager:
    def __init__(self, persist: PersistManager = None):
        self.persist = persist

    def get_frame_cache_path(self, video_hash: str, gen_id: int, ts: float) -> str:
        sub_dir = CACHE_DIR / video_hash / f"gen_{gen_id}"
        sub_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{ts:.3f}.jpg"
        return str(sub_dir / fname)

    def cache_exists(self, cache_path: str) -> bool:
        return Path(cache_path).exists()

    def get_folder_size_gb(self, folder: Path) -> float:
        total = 0
        for root, _, files in os.walk(folder):
            for f in files:
                fp = Path(root) / f
                total += fp.stat().st_size
        return total / GB_TO_BYTE

    def clean_video_cache_over_limit(self, video_hash: str):
        vid_cache = CACHE_DIR / video_hash
        if not vid_cache.exists():
            return
        current_gb = self.get_folder_size_gb(vid_cache)
        if current_gb <= CACHE_MAX_PER_VIDEO_GB:
            return
        # 超限直接清空该视频缓存
        for root, _, files in os.walk(vid_cache):
            for f in files:
                os.unlink(Path(root) / f)
        if self.persist:
            self.persist.delete_cache_record("*" + video_hash + "*")

    def auto_clean_expired(self):
        if not self.persist:
            return
        expired_paths = self.persist.get_expired_cache_paths()
        for p in expired_paths:
            fp = Path(p)
            if fp.exists():
                os.unlink(fp)
            self.persist.delete_cache_record(p)