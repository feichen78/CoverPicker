from PySide6.QtWidgets import (
    QMainWindow, QLabel, QFileDialog,
    QListWidget, QSplitter, QWidget, QGridLayout
)
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtCore import Qt, QTimer

import os
import subprocess

from core.scanner import scan_videos


# =========================
# CoverPicker v1.8.2 FIX ZOOM STATE BUG
# =========================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("CoverPicker v1.8.2 Stable Fix")
        self.resize(1300, 850)

        # ---------- UI ----------
        self.video_list = QListWidget()
        self.video_list.itemClicked.connect(self.on_video_click)

        self.main_widget = QWidget()
        self.main_grid = QGridLayout()
        self.main_widget.setLayout(self.main_grid)

        self.zoom_widget = QWidget()
        self.zoom_grid = QGridLayout()
        self.zoom_widget.setLayout(self.zoom_grid)

        root = QSplitter()
        right = QSplitter(Qt.Vertical)

        right.addWidget(self.main_widget)
        right.addWidget(self.zoom_widget)

        root.addWidget(self.video_list)
        root.addWidget(right)
        root.setSizes([300, 1000])

        self.setCentralWidget(root)

        # ---------- STATE ----------
        self.videos = []
        self.current_video = None

        self.zoom_level = 0
        self.max_zoom = 2

        self.selected_path = None

        # 🔥 改成“按视频重置”
        self.zoom_cache = {}
        self.current_center = None

        # ---------- MENU ----------
        menu = self.menuBar().addMenu("文件")
        open_action = QAction("打开目录", self)
        open_action.triggered.connect(self.open_folder)
        menu.addAction(open_action)

    # =========================
    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择视频目录")
        if not folder:
            return

        self.videos = scan_videos(folder)

        self.video_list.clear()
        for v in self.videos:
            self.video_list.addItem(v)

        self.statusBar().showMessage(f"已加载 {len(self.videos)} 个视频")

    # =========================
    def on_video_click(self, item):
        self.current_video = item.text()

        self.zoom_level = 0
        self.selected_path = None
        self.current_center = None

        # 🔥 每个视频独立 cache
        self.zoom_cache = {}

        self.clear(self.main_grid)
        self.clear(self.zoom_grid)

        self.build_l0(self.current_video)

    # =========================
    # CACHE PATH
    # =========================
    def cache_path(self, folder, i):
        base = os.path.join("cache", self.safe_name(self.current_video), folder)
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, f"{i}.jpg")

    def safe_name(self, s):
        return str(abs(hash(s)))

    # =========================
    def build_l0(self, video):
        duration = self.get_duration(video)
        if not duration:
            return

        start = duration * 0.1
        end = duration * 0.9

        times = [start + (end - start) * i / 8 for i in range(9)]

        for i, t in enumerate(times):
            path = self.extract(video, t, "l0", i)
            self.add_frame(path, t, self.main_grid, i, level=0)

    # =========================
    # ZOOM (彻底修复)
    # =========================
    def build_zoom(self, video, center, level):

        # 🔥 强制更新 center
        self.current_center = center

        key = f"{center:.2f}_{level}"

        # ❌ 不再阻止重复（修复你现在bug）
        # if key in self.zoom_cache:
        #     return

        self.zoom_cache[key] = True

        self.clear(self.zoom_grid)

        duration = self.get_duration(video)
        if not duration:
            return

        ratio = 0.03 / (level + 1)

        times = [
            center - 3 * ratio * duration,
            center - 2 * ratio * duration,
            center - 1 * ratio * duration,
            center,
            center + 1 * ratio * duration,
            center + 2 * ratio * duration,
            center + 3 * ratio * duration,
        ]

        for i, t in enumerate(times):
            t = max(0, min(duration, t))
            path = self.extract(video, t, f"l{level}", i)
            self.add_frame(path, t, self.zoom_grid, i, level)

    # =========================
    def handle_click(self, path, time, level):

        if not self.current_video:
            return

        # 🔥 关键修复：必须更新 center
        self.current_center = time

        if level < self.max_zoom:
            self.zoom_level = level + 1
            self.build_zoom(self.current_video, time, self.zoom_level)
            return

        self.selected_path = path
        self.statusBar().showMessage(f"已选中: {path}")

    # =========================
    def save_selected(self, path):
        if not self.current_video or not path:
            return

        name = os.path.splitext(os.path.basename(self.current_video))[0]
        out_dir = os.path.join("StillPic", name)
        os.makedirs(out_dir, exist_ok=True)

        idx = len(os.listdir(out_dir)) + 1
        out = os.path.join(out_dir, f"cover_{idx:02d}.jpg")

        with open(path, "rb") as f1:
            data = f1.read()
        with open(out, "wb") as f2:
            f2.write(data)

        self.statusBar().showMessage(f"已保存: {out}")

    # =========================
    def extract(self, video, t, folder, i):
        out = self.cache_path(folder, i)

        if os.path.exists(out):
            return out

        subprocess.run([
            "ffmpeg",
            "-ss", str(t),
            "-i", video,
            "-frames:v", "1",
            "-q:v", "2",
            "-y",
            out
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        return out

    # =========================
    def get_duration(self, video):
        try:
            return float(subprocess.check_output([
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video
            ]).decode().strip())
        except:
            return None

    # =========================
    def clear(self, layout):
        while layout.count():
            w = layout.takeAt(0).widget()
            if w:
                w.deleteLater()

    def add_frame(self, path, time, grid, i, level):
        label = Clickable(self, path, time, level)
        label.setFixedSize(300, 170)

        if os.path.exists(path):
            label.setPixmap(QPixmap(path).scaled(300, 170, Qt.KeepAspectRatio))

        grid.addWidget(label, i // 4, i % 4)


# =========================
class Clickable(QLabel):
    def __init__(self, parent, path, time, level):
        super().__init__()
        self.parent = parent
        self.path = path
        self.time = time
        self.level = level

    def mousePressEvent(self, event):
        QTimer.singleShot(180, self._do_click)

    def _do_click(self):
        self.parent.handle_click(self.path, self.time, self.level)

    def mouseDoubleClickEvent(self, event):
        self.parent.save_selected(self.path)