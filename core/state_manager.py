# StateManager: Single Source of Truth SSOT Stage2 修复循环导入版
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional
from config import DEFAULT_GRID_SIZE
from core.cache_manager import CacheManager
from core.persist_manager import PersistManager

# Data Class Models
@dataclass
class Frame:
    timestamp: float
    cache_path: str
    # Immutable, no setter

@dataclass
class Segment:
    id: str
    start_time: float
    end_time: float
    visited: bool = False

@dataclass
class Slot:
    id: int
    frame: Frame
    state: str
    locked: bool = False
    favorite: bool = False
    source_segment: str = ""
    generation_id: int = 0
    quality_score: float = 0.0

@dataclass
class Video:
    path: str
    duration: float
    file_hash: str
    segments: List[Segment] = field(default_factory=list)
    is_offline: bool = False

@dataclass
class AppState:
    current_video: Optional[Video] = None
    current_seg_id: Optional[str] = None
    grid_slots: List[Slot] = field(default_factory=list)
    current_zoom_level: int = 1
    best_slot_id: Optional[int] = None
    global_grid_size: int = DEFAULT_GRID_SIZE

class StateManager:
    def __init__(self, persist: PersistManager, cache_mgr: CacheManager):
        self.persist = persist
        self.cache_mgr = cache_mgr
        self.state = AppState()
        self._slot_id_auto_inc = 1

    def load_global_config(self):
        grid_size = self.persist.get_config("grid_size", DEFAULT_GRID_SIZE)
        self.state.global_grid_size = grid_size

    def save_global_config(self):
        self.persist.set_config("grid_size", self.state.global_grid_size)

    def _calc_file_hash(self, file_path: str) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def load_video(self, video_path: str, duration: float):
        file_hash = self._calc_file_hash(video_path)
        video = Video(path=video_path, duration=duration, file_hash=file_hash)
        self.state.current_video = video
        self.state.grid_slots.clear()
        self.state.current_seg_id = None
        self.state.best_slot_id = None
        self.persist.save_video_meta(file_hash, video_path, duration)
        return video

    def set_segment(self, seg_id: str):
        self.state.current_seg_id = seg_id

    def create_slot(self, frame: Frame, seg_id: str, gen_id: int) -> Slot:
        slot = Slot(
            id=self._slot_id_auto_inc,
            frame=frame,
            state="GENERATED",
            source_segment=seg_id,
            generation_id=gen_id
        )
        self._slot_id_auto_inc += 1
        self.state.grid_slots.append(slot)
        return slot

    def clear_all_slots(self):
        self.state.grid_slots.clear()

    def get_slot_by_id(self, slot_id: int) -> Optional[Slot]:
        for s in self.state.grid_slots:
            if s.id == slot_id:
                return s
        return None

    def update_slot_favorite(self, slot_id: int):
        slot = self.get_slot_by_id(slot_id)
        if not slot or slot.locked:
            return
        slot.favorite = not slot.favorite
        if slot.favorite:
            slot.state = "SELECTED"
        else:
            slot.state = "VIEWED"
        self.recompute_best()

    def update_slot_lock(self, slot_id: int):
        slot = self.get_slot_by_id(slot_id)
        if not slot:
            return
        slot.locked = not slot.locked
        if slot.locked:
            slot.state = "LOCKED"
        else:
            slot.state = "SELECTED" if slot.favorite else "VIEWED"
        self.recompute_best()

    def replace_unlocked_slots(self, new_frames: List[Frame], seg_id: str, gen_id: int):
        ptr = 0
        for slot in self.state.grid_slots:
            if slot.locked:
                continue
            if ptr >= len(new_frames):
                break
            slot.frame = new_frames[ptr]
            slot.state = "GENERATED"
            slot.generation_id = gen_id
            slot.source_segment = seg_id
            slot.quality_score = 0.0
            ptr += 1
        self.recompute_best()

    def set_slot_quality(self, slot_id: int, score: float):
        slot = self.get_slot_by_id(slot_id)
        if not slot:
            return
        slot.quality_score = score
        self.recompute_best()

    def recompute_best(self):
        # 局部导入消除循环依赖
        from core.best_engine import BestEngine
        best_id = BestEngine.compute_best_slot(self.state.grid_slots)
        self.state.best_slot_id = best_id

    def set_zoom_level(self, level: int):
        self.state.current_zoom_level = level

    def set_best_slot_id(self, slot_id: int):
        self.state.best_slot_id = slot_id

    def commit_video_state(self):
        if not self.state.current_video:
            return
        vhash = self.state.current_video.file_hash
        self.persist.batch_save_segments(vhash, self.state.current_video.segments)
        self.persist.batch_save_slots(vhash, self.state.grid_slots)