# CoverPicker v3.1 Global Config
# All quantitative thresholds unified here, modify only this file
import os
from pathlib import Path

# ====================== BASE PATH ======================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
THUMBNAIL_DIR = DATA_DIR / "thumbnails"
CLIP_DIR = DATA_DIR / "clips"
DB_PATH = DATA_DIR / "app_state.db"

# Auto create dirs
for _dir in [DATA_DIR, CACHE_DIR, THUMBNAIL_DIR, CLIP_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

# ====================== CACHE RULES ======================
CACHE_MAX_PER_VIDEO_GB = 2.0
CACHE_EXPIRE_DAYS = 7
CACHE_CLEAN_ON_START = True

# ====================== SAMPLING FILTER THRESHOLD ======================
FRAME_DUPLICATE_THRESHOLD_SEC = 0.8
BLACK_FRAME_BRIGHTNESS_THRESHOLD = 5

# ====================== SEGMENT RULE ======================
SEGMENT_COUNT_FIX = 5
MIN_SEGMENT_DURATION_SEC = 60

# ====================== ZOOM LEVEL DEFINITION ======================
ZOOM_LEVELS = {
    1: {"name": "L1 ±2s", "range": 2.0, "cross_segment": False},
    2: {"name": "L2 ±8s", "range": 8.0, "cross_segment": False},
    3: {"name": "L3 Cross Seg", "range": 12.0, "cross_segment": True},
    4: {"name": "L4 Global Resample", "range": -1, "cross_segment": True},
}

# ====================== GRID DEFAULT ======================
DEFAULT_GRID_SIZE = 16
SUPPORT_GRID_SIZES = [9, 12, 16, 25]

# ====================== THREAD CONCURRENCY (SMB / WebDAV split) ======================
LOCAL_SMB_MAX_WORKERS = 4
WEBDAV_MAX_WORKERS = 1
NETWORK_PATH_KEYWORDS = ["\\\\", "http://", "https://", "DavWWWRoot"]

# ====================== FFmpeg ======================
FFMPEG_RETRY_COUNT = 3
FFMPEG_RETRY_DELAY_SEC = 1.2
FFMPEG_COPY_ARG = "-c copy"

# ====================== OPERATION PRIORITY (Orchestrator) ======================
OP_PRIORITY = {
    "zoom": 10,
    "select_favorite": 9,
    "select_lock": 9,
    "optimize": 7,
    "sampling": 5,
    "cache_bg_clean": 1
}

# ====================== EXPORT SETTING ======================
EXPORT_IMAGE_FORMAT = "jpg"
EXPORT_IMAGE_QUALITY = 95
CLIP_DURATION_OPTIONS = [10, 15, 20]

# ====================== APP CONST ======================
APP_VERSION = "v3.1-stage1"