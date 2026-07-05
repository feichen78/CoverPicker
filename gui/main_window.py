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

        self.setWindowTitle("CoverPicker v2.1.1")

        self.segment_engine = SegmentEngine()
        self.frame_sampler = FrameSampler()
        self.state = StateManager()
        self.refiner = LocalRefineEngine()

        self.current_video = None
        self.current_segments = []
        self.current_segment = None

        self.selected_idx = None
        self.last_sample_times = []

        # UI
        self.container = QWidget()
        self.setCentralWidget(self.container)

        self.layout = QVBoxLayout()
        self.container.setLayout(self.layout)

        self.segment_widget = SegmentWidget(self.on_segment_click)
        self.layout.addWidget(self.segment_widget)

        self.grid = ThumbnailGrid(self.on_select)
        self.layout.addWidget(self.grid)

        # 按钮
        btn_layout = QHBoxLayout()

        self.btn_fav = QPushButton("⭐ 收藏/取消")
        self.btn_refine = QPushButton("🔍 局部强化")

        btn_layout.addWidget(self.btn_fav)
        btn_layout.addWidget(self.btn_refine)

        self.layout.addLayout(btn_layout)

        self.fav_list = QListWidget()
        self.layout.addWidget(self.fav_list)

        self.setStatusBar(QStatusBar())

        self.btn_fav.clicked.connect(self.toggle_favorite)
        self.btn_refine.clicked.connect(self.local_refine)

        # ⚠️ 这里必须先初始化再调用
        self.load_video()

    # =========================
    # ✅ FIX: 缺失函数（关键修复）
    # =========================
    def load_video(self):

        path, _ = QFileDialog.getOpenFileName(self, "选择视频")

        if not path:
            return

        self.current_video = path

        duration = self._get_duration(path)
        self.duration = duration

        self.current_segments = self.segment_engine.build_segments(duration)

        self.on_segment_click("A")

    # ---------------- ffprobe ----------------
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

    # ---------------- segment ----------------
    def on_segment_click(self, name):

        self.segment_widget.set_active(name)

        seg = next(s for s in self.current_segments if s.name == name)
        self.current_segment = seg

        video_id = os.path.basename(self.current_video)

        out_dir = os.path.join("cache", video_id, name)

        used_times = self.state.get_sampled_times(video_id)

        images = self.frame_sampler.sample_frames(
            self.current_video,
            seg,
            9,
            out_dir,
            used_times
        )

        self.last_sample_times = [i["time"] for i in images]

        self.grid.set_images([i["path"] for i in images])

        self._refresh_favorites(video_id)

    # ---------------- select ----------------
    def on_select(self, idx):
        self.selected_idx = idx

    # ---------------- favorite toggle ----------------
    def toggle_favorite(self):

        if self.selected_idx is None:
            return

        video_id = os.path.basename(self.current_video)

        cache_dir = os.path.join(
            "cache",
            video_id,
            self.current_segment.name
        )

        images = sorted(os.listdir(cache_dir))

        if self.selected_idx >= len(images):
            return

        img_path = os.path.join(cache_dir, images[self.selected_idx])

        favs = self.state.get_favorites(video_id)

        if img_path in favs:
            favs.remove(img_path)
        else:
            self.state.add_favorite(video_id, img_path)

        self._refresh_favorites(video_id)

    # ---------------- local refine ----------------
    def local_refine(self):

        if self.selected_idx is None:
            return

        video_id = os.path.basename(self.current_video)

        base_time = self.last_sample_times[self.selected_idx]

        start, end = self.refiner.build_local_segment(
            base_time,
            self.duration
        )

        local_times = self.refiner.sample_local_times(
            start,
            end,
            9,
            self.state.get_sampled_times(video_id)
        )

        new_images = []

        out_dir = os.path.join("cache", video_id, "local")
        os.makedirs(out_dir, exist_ok=True)

        for i, t in enumerate(local_times):

            out_path = os.path.join(out_dir, f"local_{i}.jpg")

            cmd = [
                "ffmpeg",
                "-ss", str(t),
                "-i", self.current_video,
                "-vframes", "1",
                "-q:v", "2",
                "-y",
                out_path
            ]

            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            new_images.append(out_path)

        self.grid.set_images(new_images)

    # ---------------- favorites ----------------
    def _refresh_favorites(self, video_id):

        self.fav_list.clear()

        for f in self.state.get_favorites(video_id):
            self.fav_list.addItem(os.path.basename(f))

    def showEvent(self, event):
        super().showEvent(event)