import os
import asyncio
import random
import shutil
import math
from typing import List, Tuple, Dict
from functools import partial

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGridLayout, QScrollArea, QFrame, QMessageBox, QApplication,
    QWidget, QCheckBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QFont, QPainter, QPen, QBrush, QColor, QKeyEvent

from src.video_scanner import extract_frame
from ui.views.zoom_preview import ZoomPreviewDialog


class ZoomClickableLabel(QLabel):
    clicked = Signal()
    double_clicked = Signal()

    def __init__(self, pixmap: QPixmap, time_sec: float, parent=None):
        super().__init__(parent)
        self.time_sec = time_sec
        self.is_selected = False
        self.is_locked = False
        self.is_favorite = False
        self.is_exported = False
        self.original_pixmap = pixmap.copy() if not pixmap.isNull() else QPixmap(200, 120)
        self.setFixedSize(200, 120)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("border: 1px solid #ccc; background: transparent;")
        self.setScaledContents(False)
        self.time_text = f"{time_sec:.1f}s"
        self._cached_scaled = None
        self.update_pixmap()

    def update_pixmap(self):
        try:
            if self.original_pixmap.isNull():
                return
            scaled = self.original_pixmap.scaled(
                self.width(), self.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self._cached_scaled = scaled
            self.setPixmap(scaled)
        except Exception as e:
            print(f"update_pixmap error: {e}")

    def resizeEvent(self, event):
        self.update_pixmap()
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit()

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.update()

    def set_locked(self, locked: bool):
        self.is_locked = locked
        self.update()

    def set_favorite(self, fav: bool):
        self.is_favorite = fav
        self.update()

    def set_exported(self, exp: bool):
        self.is_exported = exp
        self.update()

    def paintEvent(self, event):
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            if self._cached_scaled and not self._cached_scaled.isNull():
                rect = self.rect()
                img_rect = self._cached_scaled.rect()
                x = (rect.width() - img_rect.width()) // 2
                y = (rect.height() - img_rect.height()) // 2
                painter.drawPixmap(x, y, self._cached_scaled)
            else:
                painter.fillRect(self.rect(), QColor(100, 100, 100))

            # 选中边框（蓝色）
            if self.is_selected:
                pen = QPen(QColor(33, 150, 243), 3)
                painter.setPen(pen)
                painter.drawRect(2, 2, self.width()-4, self.height()-4)

            # 选中圆点
            if self.is_selected:
                painter.setBrush(QBrush(QColor(33, 150, 243)))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(6, 6, 12, 12)

            # 锁定图钉
            if self.is_locked:
                painter.setFont(QFont("Segoe UI Emoji", 16))
                painter.setPen(QColor(255, 0, 0))
                painter.drawText(self.width()-22, 22, "📌")

            # 时间戳
            if self.time_sec >= 0:
                painter.setPen(Qt.white)
                painter.setBrush(QBrush(QColor(0, 0, 0, 150)))
                painter.drawRect(4, self.height()-20, 60, 16)
                painter.setPen(Qt.white)
                painter.setFont(QFont("Arial", 8))
                painter.drawText(6, self.height()-6, self.time_text)

            # 收藏星标
            if self.is_favorite:
                painter.setFont(QFont("Arial", 14))
                painter.setPen(QColor(255, 215, 0))
                painter.drawText(6, 20, "★")

            # 已导出标记
            if self.is_exported:
                painter.setBrush(QBrush(QColor(0, 200, 0)))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(self.width()-14, self.height()-14, 10, 10)

            painter.end()
        except Exception as e:
            print(f"paintEvent error: {e}")
            super().paintEvent(event)


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
        self.global_mode = False
        self.zoom_items: List[dict] = []
        self.selected_indices: set = set()
        self._load_task = None

        self.setWindowTitle(f"Zoom 精修 - {os.path.basename(video_path)} @ {time_sec:.1f}s")
        self.setModal(True)
        self.resize(900, 700)
        self.setMinimumSize(700, 500)

        self.setup_ui()
        self.setFocusPolicy(Qt.StrongFocus)
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

        self.global_check = QCheckBox("全局探索模式")
        self.global_check.stateChanged.connect(self.on_global_mode_changed)
        top_bar.addWidget(self.global_check)

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
        # 间距设为0，使图片紧挨
        self.grid_layout.setSpacing(0)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll.setWidget(self.grid_widget)
        main_layout.addWidget(self.scroll, 1)

        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(10)

        self.selected_label = QLabel("已选: 0 张")
        bottom_bar.addWidget(self.selected_label)
        bottom_bar.addStretch()

        fav_btn = QPushButton("⭐ 收藏")
        fav_btn.clicked.connect(self.favorite_selected)
        bottom_bar.addWidget(fav_btn)

        unfav_btn = QPushButton("☆ 取消收藏")
        unfav_btn.clicked.connect(self.unfavorite_selected)
        bottom_bar.addWidget(unfav_btn)

        lock_btn = QPushButton("📌 锁定")
        lock_btn.clicked.connect(self.lock_selected)
        bottom_bar.addWidget(lock_btn)

        unlock_btn = QPushButton("🔓 解锁")
        unlock_btn.clicked.connect(self.unlock_selected)
        bottom_bar.addWidget(unlock_btn)

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

    def on_global_mode_changed(self, state):
        self.global_mode = (state == Qt.Checked)
        asyncio.create_task(self.load_level(self.current_level))

    def _generate_times(self, center_time: float) -> List[float]:
        if not self.segments:
            return [center_time]

        total_duration = self.segments[-1][2]
        if self.global_mode:
            t0 = max(0, center_time - 4)
            t1 = min(total_duration, center_time + 4)
        else:
            seg_start, seg_end = 0, 0
            for label, start, end in self.segments:
                if label == self.segment_label:
                    seg_start, seg_end = start, end
                    break
            if seg_start == seg_end:
                seg_start = 0
                seg_end = total_duration
            t0 = max(seg_start, center_time - 4)
            t1 = min(seg_end, center_time + 4)

        if t1 - t0 < 0.5:
            return [center_time]

        step = (t1 - t0) / 10
        times = [t0 + step * (i+1) for i in range(9)]
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

            pixmap = QPixmap(200, 120)
            pixmap.fill(QColor(100, 100, 100))
            if item.get('path') and os.path.exists(item['path']):
                loaded = QPixmap(item['path'])
                if not loaded.isNull():
                    pixmap = loaded

            label = ZoomClickableLabel(pixmap, item['time'])
            label.setObjectName(f"zoom_{pos}")
            label.set_locked(item.get('locked', False))
            label.set_favorite(item.get('favorite', False))
            label.set_exported(item.get('exported', False))
            if pos in self.selected_indices:
                label.set_selected(True)

            label.clicked.connect(partial(self.on_image_click, pos))
            label.double_clicked.connect(partial(self.zoom_image, pos))
            self.grid_layout.addWidget(label, row, col)

        self._update_selected_count()

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

    def zoom_image(self, pos: int):
        item = self.zoom_items[pos]
        if not item.get('path') or not os.path.exists(item['path']):
            QMessageBox.warning(self, "警告", "图片文件不存在。")
            return
        pixmap = QPixmap(item['path'])
        if pixmap.isNull():
            QMessageBox.warning(self, "警告", "无法加载图片。")
            return
        dlg = ZoomPreviewDialog(pixmap, item['time'], self)
        dlg.exec()

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
        if self.parent_view.segments and self.parent_view.current_seg_index < len(self.parent_view.segments):
            current_seg_label = self.parent_view.segments[self.parent_view.current_seg_index][0]
            if current_seg_label == self.segment_label:
                self.parent_view._refresh_grid(self.parent_view.current_seg_index)

    def favorite_selected(self):
        for pos in self.selected_indices:
            if pos < len(self.zoom_items):
                self.zoom_items[pos]['favorite'] = True
        self._refresh_grid()
        self._sync_to_parent()

    def unfavorite_selected(self):
        for pos in self.selected_indices:
            if pos < len(self.zoom_items):
                self.zoom_items[pos]['favorite'] = False
        self._refresh_grid()
        self._sync_to_parent()

    def lock_selected(self):
        for pos in self.selected_indices:
            if pos < len(self.zoom_items):
                self.zoom_items[pos]['locked'] = True
        self._refresh_grid()
        self._sync_to_parent()

    def unlock_selected(self):
        for pos in self.selected_indices:
            if pos < len(self.zoom_items):
                self.zoom_items[pos]['locked'] = False
        self._refresh_grid()
        self._sync_to_parent()

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

    def _update_selected_count(self):
        self.selected_label.setText(f"已选: {len(self.selected_indices)} 张")

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self._sync_to_parent()
        event.accept()