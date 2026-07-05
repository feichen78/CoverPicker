from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QLabel, QListWidget,
    QFileDialog, QHBoxLayout
)

import os
import subprocess

from core.segment_engine import SegmentEngine
from core.frame_pipeline import FramePipeline
from core.slot_manager import SlotManager

from gui.segment_widget import SegmentWidget
from gui.thumbnail_grid import ThumbnailGrid


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("CoverPicker v3.0-lite Stable")

        # ======================
        # 🟢 CORE
        # ======================
        self.pipeline = FramePipeline()
        self.seg_engine = SegmentEngine()
        self.slot_mgr = SlotManager()

        self.video = None
        self.current_segment = None

        self.selected_idx = None

        self.zoom_mode = False
        self.zoom_frames = None

        self.favorites = set()

        # ======================
        # UI
        # ======================
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
        self.btn_save = QPushButton("Save")

        for b in [self.btn_load, self.btn_opt, self.btn_lock, self.btn_zoom, self.btn_save]:
            btns.addWidget(b)

        layout.addLayout(btns)

        self.list = QListWidget()
        layout.addWidget(self.list)

        # signals
        self.btn_load.clicked.connect(self.load)
        self.btn_opt.clicked.connect(self.optimize)
        self.btn_lock.clicked.connect(self.lock_slot)
        self.btn_zoom.clicked.connect(self.zoom)
        self.btn_save.clicked.connect(self.save)

        self.grid.on_click = self.on_select

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

        # 🟢 时间轴 = FramePipeline（关键修复）
        frames = self.pipeline.sample(
            self.video,
            self.current_segment,
            9,
            os.path.join("cache", os.path.basename(self.video), name),
            jitter=0.0
        )

        self.slot_mgr.init_slots(frames)

        self.zoom_mode = False
        self.zoom_frames = None

        self.render()

    # =========================
    def render(self):

        frames = self.zoom_frames if self.zoom_mode else self.slot_mgr.get_frames()

        self.grid.set_images([f["path"] for f in frames])

        best = self.compute_best()
        self.best_label.setText("⭐ Best: " + os.path.basename(best["path"]))

        self.refresh_list()

    # =========================
    def compute_best(self):

        slots = self.slot_mgr.slots

        # favorite优先
        for s in slots:
            if s["frame"]["path"] in self.favorites:
                return s["frame"]

        # locked优先
        for s in slots:
            if s["locked"]:
                return s["frame"]

        # fallback（避免f_0问题）
        return max(slots, key=lambda s: s["frame"].get("score", 0))["frame"]

    # =========================
    def optimize(self):

        # 🟢 真正“换时间点”，不是抖动
        frames = self.pipeline.sample(
            self.video,
            self.current_segment,
            9,
            os.path.join("cache_opt", os.path.basename(self.video)),
            jitter=3.0
        )

        self.slot_mgr.replace_unlocked(frames)
        self.render()

    # =========================
    def zoom(self):

        if self.selected_idx is None:
            return

        frames = self.slot_mgr.get_frames()

        start = max(0, self.selected_idx - 2)
        end = min(len(frames), self.selected_idx + 3)

        if not self.zoom_mode:
            self.zoom_frames = frames[start:end]
            self.zoom_mode = True
        else:
            self.zoom_mode = False
            self.zoom_frames = None

        self.render()

    # =========================
    def lock_slot(self):

        if self.selected_idx is None:
            return

        self.slot_mgr.toggle_lock(self.selected_idx)
        self.render()

    # =========================
    def save(self):

        best = self.compute_best()

        out = os.path.join(os.path.dirname(self.video), "cover.jpg")

        import shutil
        shutil.copy(best["path"], out)

        self.best_label.setText("💾 Saved cover.jpg")

    # =========================
    def on_select(self, idx):
        self.selected_idx = idx

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