import os
import asyncio
import random
import shutil
from typing import List, Tuple, Dict
from functools import partial

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGridLayout, QScrollArea, QFrame, QMessageBox, QApplication,
    QWidget, QCheckBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QFont, QColor

from src.video_scanner import extract_frame


class ZoomClickableLabel(QLabel):
    clicked = Signal()

    def __init__(self, pixmap: QPixmap, time_sec: float, parent=None):
        super().__init__(parent)
        self.time_sec = time_sec
        self.is_selected = False
        self.setPixmap(pixmap)
        self.setScaledContents(True)
        self.setMinimumSize(100, 80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("border: 1px solid #ccc; background: transparent;")
        self.time_text = f"{time_sec:.1f}s"

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.setStyleSheet(f"border: 3px solid {'#2196F3' if selected else '#ccc'}; background: transparent;")


class ZoomDialog(QDialog):
    def __init__(self, video_path: str, time_sec: float, segment_label: str,
                 segments: List[Tuple[str, float, float]],
                 screenshots: Dict[str, List[dict]],
                 temp_dir: str,
                 export_base: str,
                 parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.initial_time = time_sec
        self.center_time = time_sec
        self.segment_label = segment_label
        self.segments = segments
        self.parent_view = parent
        self.screenshots = screenshots
        self.temp_dir = temp_dir
        self.export_base = export_base

        self.current_level = 1
        self.zoom_items: List[dict] = []
        self.selected_indices: set = set()
        self._load_task = None

        self.setWindowTitle(f"Zoom 精修 - {os.path.basename(video_path)} @ {time_sec:.1f}s")
        self.setModal(True)
        self.resize(900, 700)
        self.setMinimumSize(700, 500)

        self.setup_ui()
        asyncio.create_task(self.load_level(1))

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        top_bar = QHBoxLayout()
        self.info_label = QLabel(f"中心: {self.center_time:.1f}s | 分段: {self.segment_label} | 层级: L1")
        self.info_label.setFont(QFont("Arial", 11))
        top_bar.addWidget(self.info_label)
        top_bar.addStretch()

        # 层级按钮
        self.level_buttons = []
        for level in [1, 2, 3, 4]:
            btn = QPushButton(f"L{level}")
            btn.setCheckable(True)
            btn.setFixedSize(40, 30)
            btn.clicked.connect(lambda checked, lv=level: self.on_level_clicked(lv))
            top_bar.addWidget(btn)
            self.level_buttons.append(btn)
        self.level_buttons[0].setChecked(True)

        reset_btn = QPushButton("重置中心")
        reset_btn.clicked.connect(self.reset_center)
        top_bar.addWidget(reset_btn)

        main_layout.addLayout(top_bar)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: #666; font-size: 10px;")
        main_layout.addWidget(self.progress_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(2)
        self.grid_layout.setContentsMargins(2, 2, 2, 2)

        self.scroll.setWidget(self.grid_widget)
        main_layout.addWidget(self.scroll, 1)

        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(10)

        self.selected_label = QLabel("已选: 0 张")
        bottom_bar.addWidget(self.selected_label)
        bottom_bar.addStretch()

        export_btn = QPushButton("📥 导出")
        export_btn.clicked.connect(self.export_selected)
        bottom_bar.addWidget(export_btn)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        bottom_bar.addWidget(close_btn)

        main_layout.addLayout(bottom_bar)

    def on_level_clicked(self, level: int):
        for i, btn in enumerate(self.level_buttons):
            btn.setChecked(i == (level - 1))
        self.current_level = level
        if self.selected_indices:
            pos = next(iter(self.selected_indices))
            if pos < len(self.zoom_items):
                self.center_time = self.zoom_items[pos]['time']
        else:
            if level == 1:
                self.center_time = self.initial_time
        asyncio.create_task(self.load_level(level))

    def reset_center(self):
        self.center_time = self.initial_time
        self.selected_indices.clear()
        self.current_level = 1
        for i, btn in enumerate(self.level_buttons):
            btn.setChecked(i == 0)
        asyncio.create_task(self.load_level(1))

    def _generate_times(self, center_time: float) -> List[float]:
        if not self.segments:
            return [center_time]

        total_duration = self.segments[-1][2]
        seg_start, seg_end = 0, 0
        for label, start, end in self.segments:
            if label == self.segment_label:
                seg_start, seg_end = start, end
                break

        # 固定 ±4 秒，9 张
        t0 = max(seg_start, center_time - 4)
        t1 = min(seg_end, center_time + 4)
        if t1 - t0 < 0.5:
            return [center_time]

        step = (t1 - t0) / 10
        times = [t0 + step * (i + 1) for i in range(9)]
        return [max(t0, min(t1, t)) for t in times]

    async def load_level(self, level: int):
        if not self.video_path:
            return

        times = self._generate_times(self.center_time)
        count = len(times)

        self.progress_label.setText(f"正在加载 L{level}，共 {count} 张...")
        QApplication.processEvents()

        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        new_items = []
        total = len(times)
        for idx, t in enumerate(times):
            self.progress_label.setText(f"正在生成 L{level} 第 {idx+1}/{total} 张 @ {t:.2f}s")
            QApplication.processEvents()
            temp_path = os.path.join(self.temp_dir, f"zoom_L{level}_{t:.2f}.jpg")
            success = await asyncio.to_thread(extract_frame, self.video_path, t, temp_path)
            if success:
                new_items.append({
                    'time': t,
                    'path': temp_path,
                    'locked': False,
                    'favorite': False,
                    'exported': False,
                })
            else:
                new_items.append({
                    'time': t,
                    'path': None,
                    'locked': False,
                    'favorite': False,
                    'exported': False,
                })

        self.zoom_items = new_items
        self.selected_indices.clear()
        self._refresh_grid()

        self.progress_label.setText(f"L{level} 加载完成 ({len(new_items)} 张)")
        self.info_label.setText(f"中心: {self.center_time:.1f}s | 分段: {self.segment_label} | 层级: L{level}")

    def _refresh_grid(self):
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        items = self.zoom_items
        count = len(items)
        if count == 0:
            return

        cols = 3
        for pos, item in enumerate(items):
            row = pos // cols
            col = pos % cols

            pixmap = QPixmap(200, 150)
            pixmap.fill(QColor(100, 100, 100))
            if item.get('path') and os.path.exists(item['path']):
                loaded = QPixmap(item['path'])
                if not loaded.isNull():
                    pixmap = loaded.scaled(200, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            label = ZoomClickableLabel(pixmap, item['time'])
            label.setObjectName(f"zoom_{pos}")
            if pos in self.selected_indices:
                label.set_selected(True)

            label.clicked.connect(partial(self.on_image_click, pos))
            self.grid_layout.addWidget(label, row, col)

        self.selected_label.setText(f"已选: {len(self.selected_indices)} 张")
        self.grid_widget.updateGeometry()
        self.grid_widget.update()
        self.scroll.update()
        QApplication.processEvents()

    def on_image_click(self, pos: int):
        if pos in self.selected_indices:
            self.selected_indices.remove(pos)
        else:
            self.selected_indices.add(pos)
        self._refresh_grid()

    def _sync_to_parent(self):
        if not self.parent_view:
            return
        for seg_label, items in self.screenshots.items():
            for item in items:
                for zoom_item in self.zoom_items:
                    if abs(zoom_item['time'] - item['time']) < 0.01 and zoom_item['path'] == item['path']:
                        item['locked'] = zoom_item.get('locked', False)
                        item['favorite'] = zoom_item.get('favorite', False)
                        item['exported'] = zoom_item.get('exported', False)
                        break

    def export_selected(self):
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选中要导出的截图。")
            return

        export_paths = []
        for pos in self.selected_indices:
            item = self.zoom_items[pos]
            if item.get('path') and os.path.exists(item['path']):
                export_paths.append((item['time'], item['path'], pos))

        if not export_paths:
            QMessageBox.warning(self, "警告", "选中的截图文件不存在。")
            return

        video_name = os.path.splitext(os.path.basename(self.video_path))[0]
        export_dir = os.path.join(self.export_base, video_name)
        os.makedirs(export_dir, exist_ok=True)

        exported = 0
        for time_sec, src_path, pos in export_paths:
            dest_name = f"cover_{time_sec:.2f}s.jpg"
            dest_path = os.path.join(export_dir, dest_name)
            try:
                shutil.copy2(src_path, dest_path)
                exported += 1
                self.zoom_items[pos]['exported'] = True
            except Exception as e:
                print(f"导出失败 {src_path}: {e}")

        QMessageBox.information(self, "导出完成", f"成功导出 {exported} 张截图到:\n{export_dir}")
        self.selected_indices.clear()
        self._refresh_grid()
        self._sync_to_parent()

    def closeEvent(self, event):
        self._sync_to_parent()
        event.accept()