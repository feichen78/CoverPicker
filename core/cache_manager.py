# CacheManager Stage5 增强：磁盘容错、超限清理、离线缓存兼容
import os
import psutil
from pathlib import Path
from config import CACHE_DIR, CACHE_MAX_PER_VIDEO_GB, CACHE_EXPIRE_DAYS
from core.persist_manager import PersistManager

GB_TO_BYTE = 1024 ** 3

class CacheManager:
    def __init__(self, persist: PersistManager = None):
        self.persist = persist
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def get_frame_cache_path(self, video_hash: str, gen_id: int, ts: float) -> str:
        sub_dir = CACHE_DIR / video_hash / f"gen_{gen_id}"
        try:
            sub_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        fname = f"{ts:.3f}.jpg"
        return str(sub_dir / fname)

    def cache_exists(self, cache_path: str) -> bool:
        try:
            return Path(cache_path).exists()
        except Exception:
            return False

    def get_folder_size_gb(self, folder: Path) -> float:
        total = 0
        try:
            for root, _, files in os.walk(folder):
                for f in files:
                    fp = Path(root) / f
                    try:
                        total += fp.stat().st_size
                    except FileNotFoundError:
                        continue
        except Exception:
            return 0.0
        return total / GB_TO_BYTE

    def clean_video_cache_over_limit(self, video_hash: str):
        vid_cache = CACHE_DIR / video_hash
        if not vid_cache.exists():
            return
        current_gb = self.get_folder_size_gb(vid_cache)
        if current_gb <= CACHE_MAX_PER_VIDEO_GB:
            return
        # 超限清空当前视频缓存
        try:
            for root, _, files in os.walk(vid_cache):
                for f in files:
                    fpath = Path(root) / f
                    try:
                        os.unlink(fpath)
                    except Exception:
                        continue
        except Exception:
            pass
        if self.persist:
            self.persist.delete_cache_record("*" + video_hash + "*")

    def auto_clean_expired(self):
        if not self.persist:
            return
        try:
            expired_paths = self.persist.get_expired_cache_paths()
            for p in expired_paths:
                fp = Path(p)
                if fp.exists():
                    try:
                        os.unlink(fp)
                    except Exception:
                        pass
                self.persist.delete_cache_record(p)
        except Exception:
            pass

    def add_cache_record(self, cache_path: str, video_hash: str):
        if not self.persist:
            return
        try:
            self.persist.add_cache_record(cache_path, video_hash)
        except Exception:
            pass