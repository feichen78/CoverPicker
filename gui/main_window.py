from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QFileDialog,
    QStatusBar, QListWidget, QPushButton, QHBoxLayout
)

import os
import subprocess
import json

from gui.segment_widget import SegmentWidget
from gui.thumbnail_grid import ThumbnailGrid

from core.segment_engine import SegmentEngine
from core.frame_sampler import FrameSampler
from core.state_manager import StateManager
from core.local_refine_engine import LocalRefineEngine


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("CoverPicker v2.2")

        self.segment_engine = SegmentEngine()
        self.frame_sampler = FrameSampler()
        self.state = StateManager()
        self.refiner = LocalRefineEngine()

        self.current_video = None
        self.current_segment = None

        self.selected_idx = None
        self.last_sample_times = []
        self.current_images = []

        # UI
        self.container = QWidget()
        self.setCentralWidget(self.container)

        self.layout = QVBoxLayout()
        self.container.setLayout(self.layout)

        self.segment_widget = SegmentWidget(self.on_segment_click)
        self.layout.addWidget(self.segment_widget)

        self.grid = ThumbnailGrid(self.on_select)
        self.layout.addWidget(self.grid)

        # buttons
        btn = QHBoxLayout()

        self.btn_fav = QPushButton("⭐ 候选")
        self.btn_lock = QPushButton("🔒 封面")
        self.btn_refine = QPushButton("🔍 局部")

        btn.addWidget(self.btn_fav)
        btn.addWidget(self.btn_lock)
        btn.addWidget(self.btn_refine)

        self.layout.addLayout(btn)

        self.fav_list = QListWidget()
        self.layout.addWidget(self.fav_list)

        self.setStatusBar(QStatusBar())

        self.btn_fav.clicked.connect(self.toggle_candidate)
        self.btn_lock.clicked.connect(self.set_cover)
        self.btn_refine.clicked.connect(self.local_refine)

        self.load_video()

    # =========================
    def load_video(self):

        path, _ = QFileDialog.getOpenFileName(self, "选择视频")
        if not path:
            return

        self.current_video = path
        self.duration = self._get_duration(path)

        self.segments = self.segment_engine.build_segments(self.duration)

        self.on_segment_click("A")

    # =========================
    def on_segment_click(self, name):

        self.segment_widget.set_active(name)

        self.current_segment = next(s for s in self.segments if s.name == name)

        video_id = os.path.basename(self.current_video)

        out_dir = os.path.join("cache", video_id, name)

        images = self.frame_sampler.sample_frames(
            self.current_video,
            self.current_segment,
            9,
            out_dir,
            []
        )

        self.current_images = images
        self.last_sample_times = [i["time"] for i in images]

        self.grid.set_images([i["path"] for i in images])

    # =========================
    def on_select(self, idx):
        self.selected_idx = idx

    # =========================
    # ⭐ 候选池（可替换）
    # =========================
    def toggle_candidate(self):

        if self.selected_idx is None:
            return

        video_id = os.path.basename(self.current_video)

        img = self.current_images[self.selected_idx]["path"]

        candidates = self.state.get_candidates(video_id)

        if img in candidates:
            self.state.remove_candidate(video_id, img)
        else:
            self.state.add_candidate(video_id, img)

        self._refresh(video_id)

    # =========================
    # 🔒 封面锁定
    # =========================
    def set_cover(self):

        if self.selected_idx is None:
            return

        video_id = os.path.basename(self.current_video)

        img = self.current_images[self.selected_idx]["path"]

        self.state.set_final_cover(video_id, img)

        self.statusBar().showMessage("已设置封面", 2000)

    # =========================
    def local_refine(self):

        if self.selected_idx is None:
            return

        base_time = self.last_sample_times[self.selected_idx]

        start, end = self.refiner.build_local_segment(
            base_time,
            self.duration
        )

        times = self.refiner.sample_local_times(start, end, 9, [])

        new_images = []

        for i, t in enumerate(times):

            out = f"cache/local_{i}.jpg"

            subprocess.run([
                "ffmpeg", "-ss", str(t),
                "-i", self.current_video,
                "-vframes", "1",
                "-y", out
            ])

            new_images.append({"path": out})

        self.current_images = new_images
        self.grid.set_images([i["path"] for i in new_images])

    # =========================
    def _refresh(self, video_id):

        self.fav_list.clear()

        for f in self.state.get_candidates(video_id):
            self.fav_list.addItem(os.path.basename(f))

    # =========================
    def _get_duration(self, path):

        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)

        return float(data["format"]["duration"])

    def showEvent(self, event):
        super().showEvent(event)