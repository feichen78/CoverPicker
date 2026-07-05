from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QLabel, QListWidget,
    QFileDialog, QHBoxLayout
)

import os
import subprocess
import random
import copy

from core.segment_engine import SegmentEngine
from core.frame_pipeline import FramePipeline
from core.slot_manager import SlotManager

from gui.segment_widget import SegmentWidget
from gui.thumbnail_grid import ThumbnailGrid


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("CoverPicker v2.6 Stable Core")

        self.pipeline = FramePipeline()
        self.seg_engine = SegmentEngine()
        self.slot_mgr = SlotManager()

        # ======================
        # 🧠 核心三层数据
        # ======================
        self.base_frames = []   # score依据（永不变）
        self.view_frames = []   # zoom用（可变）
        self.current_zoom = False

        self.current_segment = None
        self.video = None

        self.selected_idx = None

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
        self.btn_fav = QPushButton("Fav")

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
        self.btn_zoom.clicked.connect(self.zoom_toggle)
        self.btn_fav.clicked.connect(self.toggle_fav)

        self.grid.on_click = self.on_select
        self.list.itemClicked.connect(self.on_list_click)

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

        # 🧠 初始化三层
        self.base_frames = frames
        self.view_frames = copy.deepcopy(frames)

        self.slot_mgr.init_slots(frames)

        self.render()

    # =========================
    def render(self):

        frames = self.slot_mgr.get_frames()

        self.grid.set_images([f["path"] for f in frames])

        # ⭐ BEST（永远从 base_frames）
        if self.base_frames:
            best = max(self.base_frames, key=lambda x: x["score"])
            self.best_label.setText(
                "⭐ Best: " + os.path.basename(best["path"])
            )

        self.refresh_list()

    # =========================
    def on_select(self, idx):
        self.selected_idx = idx

    # =========================
    # =========================
    # ⭐ OPTIMIZE（真正有意义版本）
    # =========================
    def optimize(self):

        # 🧠 策略扰动（不是简单重拍）
        jitter = random.uniform(1.5, 4.0)

        new_frames = self.pipeline.sample(
            self.video,
            self.current_segment,
            9,
            os.path.join("cache_opt", os.path.basename(self.video)),
            jitter=jitter
        )

        # ✔ 只替换未锁定slot
        self.slot_mgr.replace_unlocked(new_frames)

        # ✔ 更新 base_frames（关键）
        self.base_frames = self.slot_mgr.get_frames()

        self.render()

    # =========================
    def lock_slot(self):

        if self.selected_idx is None:
            return

        self.slot_mgr.toggle_lock(self.selected_idx)
        self.render()

    # =========================
    # =========================
    # ⭐ ZOOM（纯view，不污染slot）
    # =========================
    def zoom_toggle(self):

        if self.selected_idx is None:
            return

        frames = self.slot_mgr.get_frames()

        if not self.current_zoom:
            start = max(0, self.selected_idx - 2)
            end = min(len(frames), self.selected_idx + 3)

            self.view_frames = frames[start:end]
            self.grid.set_images([f["path"] for f in self.view_frames])

        else:
            self.render()

        self.current_zoom = not self.current_zoom

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
    def on_list_click(self, item):

        text = item.text()

        for i in range(len(self.slot_mgr.slots)):
            if f"Slot {i}" in text:
                self.selected_idx = i
                break