"""
CoverPicker v3.2
Core Data Models

所有 Engine、StateManager、UI 共用的数据结构。

原则：
- 使用 dataclass
- Frame 不可修改（frozen=True）
- 不依赖 GUI
- 不依赖 ffmpeg
"""

from dataclasses import dataclass, field
from typing import List, Optional


# ==========================================================
# Frame
# ==========================================================

@dataclass(frozen=True)
class Frame:
    """
    一个视频截图（不可变）
    """

    timestamp: float
    image_path: str
    segment_id: str = ""
    score: float = 0.0


# ==========================================================
# Slot
# ==========================================================

@dataclass
class Slot:
    """
    Grid中的一个位置。

    Slot可以变化，
    Frame不可变化。
    """

    index: int

    frame: Optional[Frame] = None

    locked: bool = False
    favorite: bool = False

    visible: bool = True

    score: float = 0.0

    generation: int = 0

    def is_empty(self) -> bool:
        return self.frame is None


# ==========================================================
# Grid
# ==========================================================

@dataclass
class Grid:
    """
    一个Segment当前显示的候选集合。
    """

    rows: int = 3
    cols: int = 3

    segment_id: str = ""

    generation: int = 0

    slots: List[Slot] = field(default_factory=list)

    @property
    def capacity(self) -> int:
        return self.rows * self.cols

    def ensure_slots(self):
        """
        根据rows/cols自动补齐Slot。
        """
        while len(self.slots) < self.capacity:
            self.slots.append(Slot(index=len(self.slots)))

        if len(self.slots) > self.capacity:
            self.slots = self.slots[:self.capacity]


# ==========================================================
# Segment
# ==========================================================

@dataclass
class Segment:
    """
    视频时间分区。
    """

    id: str

    start_time: float
    end_time: float

    visited: bool = False

    has_favorite: bool = False

    has_clip: bool = False

    grid: Grid = field(default_factory=Grid)


# ==========================================================
# Clip
# ==========================================================

@dataclass(frozen=True)
class Clip:
    """
    导出的视频片段。
    """

    start_time: float

    end_time: float

    output_path: str


# ==========================================================
# ZoomSession
# ==========================================================

@dataclass
class ZoomSession:
    """
    Zoom工作状态。

    一次Zoom只围绕一个中心Frame展开。
    """

    active: bool = False

    level: int = 0

    center_frame: Optional[Frame] = None

    history: List[Frame] = field(default_factory=list)

    def reset(self):
        self.active = False
        self.level = 0
        self.center_frame = None
        self.history.clear()


# ==========================================================
# Video
# ==========================================================

@dataclass
class Video:
    """
    当前打开的视频。
    """

    path: str

    duration: float

    segments: List[Segment] = field(default_factory=list)

    current_segment: int = 0


# ==========================================================
# ProjectState
# ==========================================================

@dataclass
class ProjectState:
    """
    整个工程运行状态。

    v3.2开始，
    StateManager将维护它。
    """

    video: Optional[Video] = None

    best_frame: Optional[Frame] = None

    zoom: ZoomSession = field(default_factory=ZoomSession)