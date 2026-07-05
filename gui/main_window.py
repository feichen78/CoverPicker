from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QLabel, QListWidget,
    QFileDialog, QHBoxLayout
)

import os
import subprocess
import copy

from core.segment_engine import SegmentEngine
from core.frame_pipeline import FramePipeline
from core.slot_manager import SlotManager

from gui.segment_widget import SegmentWidget
from gui.thumbnail_grid import ThumbnailGrid


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("CoverPicker v2.5.1 Stable Slot")

        self.pipeline = FramePipeline()
        self.seg_engine = SegmentEngine()
        self.slot_mgr = SlotManager()

        self.current_segment = None

        # 🟢 view layer（关键修复）
        self.base_view = []
        self.current_view = []
        self.zoom_history = []

        # 🟢 favorites（恢复）
        self.favorites = set()

        # UI
        root = QWidget()
        self.setCentralWidget(root)

        layout = QVBoxLayout()
        root.setLayout(layout)

        self.segment_ui = SegmentWidget(self.on_segment)
        layout.addWidget(self.segment_ui)

        self.best_label = QLabel("⭐ Best: -")
        layout.addWidget(self.best_label)

        self.grid = ThumbnailGrid(self.on_select)
        layout.addWidget(self.grid)

        btns = QHBoxLayout()

        self.btn_load = QPushButton("Load")
        self.btn_opt = QPushButton("Optimize")
        self.btn_lock = QPushButton("Lock")
        self.btn_zoom = QPushButton("Zoom")
        self.btn_fav = QPushButton("Favorite")

        btns.addWidget(self.btn_load)
        btns.addWidget(self.btn_opt)
        btns.addWidget(self.btn_lock)
        btns.addWidget(self.btn_zoom)
        btns.addWidget(self.btn_fav)

        layout.addLayout(btns)

        self.list = QListWidget()
        layout.addWidget(self.list)

        # signals
        self.btn_load.clicked.connect(self.load)
        self.btn_opt.clicked.connect(self.optimize)
        self.btn_lock.clicked.connect(self.lock_slot)
        self.btn_zoom.clicked.connect(self.zoom)
        self.btn_fav.clicked.connect(self.toggle_fav)

        self.grid.on_click = self.on_select

        self.selected_idx = None

    # =========================
    def load(self):

        path, _ = QFileDialog.getOpenFileName(self)
        if not path:
            return

        self.video = path

        self.duration = float(subprocess.check_output([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path
        ]))

        self.segments = self.seg_engine.build_segments(self.duration)

        self.on_segment("A")

    # =========================
    def on_segment(self, name):

        self.current_segment = next(s for s in self.segments if s.name == name)

        frames = self.pipeline.sample(
            self.video,
            self.current_segment,
            9,
            os.path.join("cache", os.path.basename(self.video), name),
            jitter=0.0
        )

        self.slot_mgr.init_slots(frames)

        self.base_view = frames
        self.current_view = copy.deepcopy(frames)
        self.zoom_history = []

        self.render()

    # =========================
    def render(self):

        frames = self.slot_mgr.get_frames()

        self.grid.set_images([f["path"] for f in frames])

        # ⭐ best 修复（slot稳定）
        best = self.slot_mgr.best()
        self.best_label.setText(
            "⭐ Best: " + os.path.basename(best["frame"]["path"])
        )

        self.refresh_list()

    # =========================
    def optimize(self):

        new_frames = self.pipeline.sample(
            self.video,
            self.current_segment,
            9,
            os.path.join("cache_opt", os.path.basename(self.video)),
            jitter=2.5
        )

        self.slot_mgr.replace_unlocked(new_frames)

        self.render()

    # =========================
    def lock_slot(self):

        if self.selected_idx is None:
            return

        self.slot_mgr.toggle_lock(self.selected_idx)
        self.render()

    # =========================
    def zoom(self):

        if self.selected_idx is None:
            return

        frames = self.slot_mgr.get_frames()

        start = max(0, self.selected_idx - 2)
        end = min(len(frames), self.selected_idx + 3)

        zoomed = frames[start:end]

        self.zoom_history.append(frames)

        # ⭐ 关键：zoom不破坏slot
        self.current_view = zoomed

        self.grid.set_images([f["path"] for f in zoomed])

    # =========================
    def toggle_fav(self):

        if self.selected_idx is None:
            return

        f = self.slot_mgr.slots[self.selected_idx]["frame"]["path"]

        if f in self.favorites:
            self.favorites.remove(f)
        else:
            self.favorites.add(f)

        self.refresh_list()

    # =========================
    def refresh_list(self):

        self.list.clear()

        for i, s in enumerate(self.slot_mgr.slots):

            p = s["frame"]["path"]

            tag = ""
            if s["locked"]:
                tag += "🔒"
            if p in self.favorites:
                tag += "⭐"

            self.list.addItem(f"{tag} Slot {i} | {os.path.basename(p)}")

    # =========================
    def on_select(self, idx):
        self.selected_idx = idx