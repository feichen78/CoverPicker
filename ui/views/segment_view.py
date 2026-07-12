# ui/views/segment_view.py

import os
import asyncio
import random
import tempfile
import shutil
import logging
import traceback
from typing import Dict, List, Set, Tuple
from functools import partial
from datetime import timedelta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGridLayout, QScrollArea, QFrame, QMessageBox, QApplication,
    QSplitter, QListWidget, QListWidgetItem, QSizePolicy, QDialog
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap, QFont, QColor, QPainter, QPen, QBrush, QKeyEvent, QResizeEvent

from src.video_scanner import scan_videos, get_video_duration, calculate_segments, extract_frame
from src.database import Database
from ui.views.zoom_dialog import ZoomDialog
from ui.views.zoom_preview import ZoomPreviewDialog

# 配置日志 - 输出到文件和控制台
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "coverpicker.log")
LOG_FILE = os.path.normpath(LOG_FILE)

log_dir = os.path.dirname(LOG_FILE)
if log_dir:
    os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"=== CoverPicker 日志开始 ===")
logger.info(f"日志文件: {LOG_FILE}")


class ClickableLabel(QLabel):
    """可点击的截图标签 - 固定尺寸，图片居中保持宽高比"""
    clicked = Signal()
    double_clicked = Signal()

    def __init__(self, pixmap: QPixmap, time_sec: float, index: int = 0, parent=None):
        super().__init__(parent)
        self.time_sec = time_sec
        self.index = index
        self.is_selected = False
        self.is_locked = False
        self.is_favorite = False
        self.is_exported = False

        self.original_pixmap = pixmap
        self.display_pixmap = QPixmap()
        self.time_text = f"{time_sec:.1f}s"

        self.setMinimumSize(160, 120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("border: 1px solid #ccc; background: #2a2a2a;")

        self._update_display_pixmap()

    def _update_display_pixmap(self):
        if self.original_pixmap.isNull():
            self.display_pixmap = QPixmap(200, 150)
            self.display_pixmap.fill(QColor(60, 60, 60))
            self.update()
            return

        w = self.width() - 2
        h = self.height() - 2
        if w < 10 or h < 10:
            w, h = 200, 150

        scaled = self.original_pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        self.display_pixmap = QPixmap(w, h)
        self.display_pixmap.fill(QColor(30, 30, 30))

        painter = QPainter(self.display_pixmap)
        x = (w - scaled.width()) // 2
        y = (h - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.end()

        self.update()

    def set_original_pixmap(self, pixmap: QPixmap):
        self.original_pixmap = pixmap
        self._update_display_pixmap()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_display_pixmap()

    def paintEvent(self, event):
        if self.display_pixmap.isNull():
            self._update_display_pixmap()
            if self.display_pixmap.isNull():
                painter = QPainter(self)
                painter.fillRect(self.rect(), QColor(60, 60, 60))
                painter.end()
                return

        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.display_pixmap)

        painter.setRenderHint(QPainter.Antialiasing)

        if self.is_selected:
            painter.setBrush(QBrush(QColor(33, 150, 243)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(6, 6, 14, 14)

        painter.setPen(Qt.white)
        painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
        seq_rect_x = 6
        seq_rect_y = 24 if self.is_selected else 6
        seq_rect_w = 24
        seq_rect_h = 18
        painter.drawRoundedRect(seq_rect_x, seq_rect_y, seq_rect_w, seq_rect_h, 3, 3)
        painter.setPen(Qt.white)
        painter.setFont(QFont("Arial", 9, QFont.Bold))
        painter.drawText(seq_rect_x + 4, seq_rect_y + 13, f"{self.index}")

        painter.setPen(Qt.white)
        painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
        painter.drawRoundedRect(4, self.height() - 22, 60, 18, 3, 3)
        painter.setPen(Qt.white)
        painter.setFont(QFont("Arial", 8))
        painter.drawText(6, self.height() - 7, self.time_text)

        if self.is_locked:
            painter.setFont(QFont("Segoe UI Emoji", 13))
            painter.setPen(QColor(255, 200, 0))
            painter.drawText(self.width() - 28, 24, "🔒")

        if self.is_favorite:
            painter.setFont(QFont("Segoe UI Emoji", 16))
            painter.setPen(QColor(255, 215, 0))
            painter.drawText(self.width() - 24, 22, "⭐")

        if self.is_exported:
            painter.setBrush(QBrush(QColor(0, 200, 0)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(self.width() - 14, self.height() - 14, 10, 10)

        painter.end()

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


class FavImageLabel(QLabel):
    """收藏弹窗中的图片标签 - 固定尺寸，图片居中保持宽高比"""
    clicked = Signal()
    double_clicked = Signal()

    def __init__(self, pixmap: QPixmap, time_sec: float, parent=None):
        super().__init__(parent)
        self.time_sec = time_sec
        self.is_selected = False
        self.time_text = f"{time_sec:.1f}s"

        self.original_pixmap = pixmap
        self.display_pixmap = QPixmap()
        self.current_img_w = 160
        self.current_img_h = 120

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setStyleSheet("border: 1px solid #ccc; background: #2a2a2a;")

        self._update_display_pixmap()

    def set_image_size(self, w: int, h: int):
        if w != self.current_img_w or h != self.current_img_h:
            self.current_img_w = w
            self.current_img_h = h
            self.setFixedSize(w + 2, h + 2)
            self._update_display_pixmap()

    def _update_display_pixmap(self):
        if self.original_pixmap.isNull():
            self.display_pixmap = QPixmap(self.current_img_w, self.current_img_h)
            self.display_pixmap.fill(QColor(60, 60, 60))
            self.update()
            return

        w = max(10, self.current_img_w)
        h = max(10, self.current_img_h)

        scaled = self.original_pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        self.display_pixmap = QPixmap(w, h)
        self.display_pixmap.fill(QColor(30, 30, 30))

        painter = QPainter(self.display_pixmap)
        x = (w - scaled.width()) // 2
        y = (h - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.end()

        self.update()

    def set_original_pixmap(self, pixmap: QPixmap):
        self.original_pixmap = pixmap
        self._update_display_pixmap()

    def paintEvent(self, event):
        if self.display_pixmap.isNull():
            self._update_display_pixmap()
            if self.display_pixmap.isNull():
                painter = QPainter(self)
                painter.fillRect(self.rect(), QColor(60, 60, 60))
                painter.end()
                return

        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.display_pixmap)

        painter.setRenderHint(QPainter.Antialiasing)

        if self.is_selected:
            painter.setBrush(QBrush(QColor(33, 150, 243)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(6, 6, 14, 14)

        painter.setPen(Qt.white)
        painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
        painter.drawRoundedRect(4, self.height() - 22, 60, 18, 3, 3)
        painter.setPen(Qt.white)
        painter.setFont(QFont("Arial", 8))
        painter.drawText(6, self.height() - 7, self.time_text)

        painter.end()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit()

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.update()


class FavoritesDialog(QDialog):
    def __init__(self, favorites: List[dict], video_name: str, export_base: str, video_path: str, parent=None):
        super().__init__(parent)
        self.favorites = favorites
        self.export_base = export_base
        self.video_path = video_path
        self.parent_view = parent
        self.selected_indices: set = set()
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._on_resize_timeout)
        self._image_labels: List[FavImageLabel] = []
        self._grid_widgets: List[QWidget] = []
        self._loaded = False
        self._last_cols = 0
        self._all_items: List[dict] = []

        self.MAX_COLS = 9
        self.MIN_IMG_W = 160
        self.MIN_IMG_H = int(self.MIN_IMG_W * 0.75)
        self.IMG_ASPECT = 0.75

        self.setWindowTitle(f"收藏截图 - {video_name}")
        self.setModal(True)
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowCloseButtonHint |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint
        )
        self.resize(1100, 900)
        self.setMinimumSize(800, 700)

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(6)

        top_bar = QHBoxLayout()
        self.info_label = QLabel("共 0 张收藏截图")
        self.info_label.setFont(QFont("Arial", 12, QFont.Bold))
        top_bar.addWidget(self.info_label)
        top_bar.addStretch()

        self.select_all_btn = QPushButton("☑ 全选")
        self.select_all_btn.clicked.connect(self.select_all)
        self.select_all_btn.setEnabled(False)
        top_bar.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("☐ 取消全选")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        self.deselect_all_btn.setEnabled(False)
        top_bar.addWidget(self.deselect_all_btn)

        self.unfavorite_btn = QPushButton("☆ 取消收藏")
        self.unfavorite_btn.clicked.connect(self.unfavorite_selected)
        self.unfavorite_btn.setEnabled(False)
        top_bar.addWidget(self.unfavorite_btn)

        self.export_btn = QPushButton("📥 导出选中")
        self.export_btn.clicked.connect(self.export_selected)
        self.export_btn.setEnabled(False)
        top_bar.addWidget(self.export_btn)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        top_bar.addWidget(close_btn)

        main_layout.addLayout(top_bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.content_widget = QWidget()
        self.content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setSpacing(4)
        self.content_layout.setContentsMargins(0, 2, 0, 2)
        self.content_layout.setAlignment(Qt.AlignTop)

        self.scroll.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll, 1)

        bottom_bar = QHBoxLayout()
        self.selected_label = QLabel("已选: 0 张")
        bottom_bar.addWidget(self.selected_label)
        bottom_bar.addStretch()
        main_layout.addLayout(bottom_bar)

    def _flatten_items(self) -> List[dict]:
        result = []
        for item in self.favorites:
            result.append({
                'segment': item.get('segment', 'A'),
                'time': item['time'],
                'path': item.get('path', ''),
            })
        return result

    def select_all(self):
        self.selected_indices = set(range(len(self._all_items)))
        self._update_selection_states()
        self.selected_label.setText(f"已选: {len(self.selected_indices)} 张")
        self.export_btn.setEnabled(len(self.selected_indices) > 0)
        self.unfavorite_btn.setEnabled(len(self.selected_indices) > 0)
        self.select_all_btn.setEnabled(False)
        self.deselect_all_btn.setEnabled(True)

    def deselect_all(self):
        self.selected_indices.clear()
        self._update_selection_states()
        self.selected_label.setText("已选: 0 张")
        self.export_btn.setEnabled(False)
        self.unfavorite_btn.setEnabled(False)
        self.select_all_btn.setEnabled(True)
        self.deselect_all_btn.setEnabled(False)

    def _update_selection_states(self):
        for idx, label in enumerate(self._image_labels):
            label.set_selected(idx in self.selected_indices)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loaded:
            QTimer.singleShot(100, self.load_favorites)
            self._loaded = True

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._resize_timer.start(100)

    def _on_resize_timeout(self):
        if not self._image_labels:
            return

        vw, vh = self._get_viewport_size()
        if vw < 100 or vh < 100:
            return

        total_items = len(self._image_labels)
        cols, img_w, img_h = self._calculate_optimal_layout(vw, vh, total_items)

        if cols != self._last_cols:
            self._last_cols = cols
            self.load_favorites()
        else:
            for label in self._image_labels:
                label.set_image_size(img_w, img_h)
            self._update_grid_cols(cols)
            self._update_inner_widgets(img_w, img_h)

    def _get_viewport_size(self) -> Tuple[int, int]:
        vw = self.scroll.viewport().width() - 10
        vh = self.scroll.viewport().height() - 10
        window_w = self.width()
        window_h = self.height()

        logger.debug(f"[收藏弹窗] _get_viewport_size: vw={vw}, vh={vh}, window_w={window_w}, window_h={window_h}")

        if vw < 100 or vw < window_w * 0.85:
            old_vw = vw
            vw = window_w - 20
            logger.debug(f"[收藏弹窗] vw 从 {old_vw} 修正为 {vw} (使用窗口宽度)")

        if vh < 100:
            vh = 700

        return vw, vh

    def _calculate_optimal_layout(self, viewport_width: int, viewport_height: int, total_items: int) -> Tuple[int, int, int]:
        logger.debug(f"[收藏弹窗] _calculate_optimal_layout: viewport_width={viewport_width}, viewport_height={viewport_height}, total_items={total_items}")

        if viewport_width < 100 or viewport_height < 100:
            viewport_width = 1000
            viewport_height = 700

        spacing = 4
        padding = 6
        title_height = 26
        seg_spacing = 4

        grouped = self._get_seg_items()
        seg_count = len(grouped)

        header_height = seg_count * (title_height + seg_spacing)
        img_available_height = max(100, viewport_height - 10 - header_height)

        max_cols_by_width = (viewport_width - padding * 2 + spacing) // (self.MIN_IMG_W + spacing)
        max_cols_by_width = max(1, min(self.MAX_COLS, max_cols_by_width))
        logger.debug(f"[收藏弹窗] max_cols_by_width={max_cols_by_width}, img_available_height={img_available_height}")

        max_rows_by_height = max(1, img_available_height // (self.MIN_IMG_H + 10))
        logger.debug(f"[收藏弹窗] max_rows_by_height={max_rows_by_height}")

        best_cols = max_cols_by_width
        best_img_w = self.MIN_IMG_W
        best_img_h = self.MIN_IMG_H
        found_valid = False

        for cols in range(max_cols_by_width, 0, -1):
            rows = (total_items + cols - 1) // cols

            if rows > max_rows_by_height:
                logger.debug(f"[收藏弹窗] cols={cols}, rows={rows} > max_rows_by_height={max_rows_by_height}, 跳过")
                continue

            found_valid = True

            scrollbar_width = 12
            available_width = viewport_width - padding * 2 - scrollbar_width
            
            img_w = (available_width - spacing * (cols - 1)) // cols
            img_h = int(img_w * self.IMG_ASPECT)
            logger.debug(f"[收藏弹窗] 尝试 cols={cols}, rows={rows}, img_w={img_w}, img_h={img_h}")

            total_img_height = rows * img_h + (rows - 1) * 4
            if total_img_height > img_available_height and img_available_height > 0:
                img_h = max(self.MIN_IMG_H, (img_available_height - (rows - 1) * 4) // rows)
                img_w = int(img_h / self.IMG_ASPECT)
                logger.debug(f"[收藏弹窗] 高度修正: img_h={img_h}, img_w={img_w}")

            img_w = max(self.MIN_IMG_W, img_w)
            img_h = max(self.MIN_IMG_H, img_h)

            max_img_w = (available_width - spacing * (cols - 1)) // cols
            if img_w > max_img_w:
                img_w = max_img_w
                img_h = int(img_w * self.IMG_ASPECT)
                img_h = max(self.MIN_IMG_H, img_h)
                img_w = max(self.MIN_IMG_W, img_w)
                logger.debug(f"[收藏弹窗] 宽度修正: img_w={img_w}, img_h={img_h}")

            current_area = img_w * img_h
            best_area = best_img_w * best_img_h
            if current_area > best_area:
                best_cols = cols
                best_img_w = img_w
                best_img_h = img_h
                logger.debug(f"[收藏弹窗] 更新 best: cols={best_cols}, img_w={best_img_w}, img_h={best_img_h}")

        if not found_valid:
            logger.warning(f"[收藏弹窗] 所有列数都被跳过，使用兜底逻辑: 选择最大列数 {max_cols_by_width}")
            best_cols = max_cols_by_width
            scrollbar_width = 12
            available_width = viewport_width - padding * 2 - scrollbar_width
            best_img_w = max(self.MIN_IMG_W, (available_width - spacing * (best_cols - 1)) // best_cols)
            best_img_h = max(self.MIN_IMG_H, int(best_img_w * self.IMG_ASPECT))
            logger.info(f"[收藏弹窗] 兜底布局: cols={best_cols}, img_w={best_img_w}, img_h={best_img_h}")

        best_img_w = max(self.MIN_IMG_W, best_img_w)
        best_img_h = max(self.MIN_IMG_H, best_img_h)
        logger.info(f"[收藏弹窗] 最终布局: cols={best_cols}, img_w={best_img_w}, img_h={best_img_h}, total_items={total_items}")

        return best_cols, best_img_w, best_img_h

    def _update_grid_cols(self, cols: int):
        for widget in self._grid_widgets:
            if widget and widget.layout() and isinstance(widget.layout(), QGridLayout):
                grid_layout = widget.layout()
                for col in range(grid_layout.columnCount()):
                    grid_layout.setColumnStretch(col, 0)
                for col in range(cols):
                    grid_layout.setColumnStretch(col, 1)

    def _update_inner_widgets(self, img_w: int, img_h: int):
        inner_height = img_h + 22
        for widget in self.findChildren(QWidget):
            if widget.property("is_inner_container") == True:
                widget.setFixedSize(img_w + 2, inner_height)

    def _get_seg_items(self) -> Dict[str, List[dict]]:
        grouped = {}
        for item in self.favorites:
            seg = item.get('segment', 'A')
            if seg not in grouped:
                grouped[seg] = []
            grouped[seg].append(item)
        return grouped

    def load_favorites(self):
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._image_labels = []
        self._grid_widgets = []
        self._all_items = self._flatten_items()

        if not self.favorites:
            label = QLabel("暂无收藏截图")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-size: 16px; color: #999; padding: 40px;")
            self.content_layout.addWidget(label)
            self.info_label.setText("共 0 张收藏截图")
            self.select_all_btn.setEnabled(False)
            self.deselect_all_btn.setEnabled(False)
            self.unfavorite_btn.setEnabled(False)
            return

        grouped = self._get_seg_items()
        total = len(self.favorites)
        self.info_label.setText(f"共 {total} 张收藏截图")

        vw, vh = self._get_viewport_size()
        if vw < 100 or vh < 100:
            vw = 1000
            vh = 700

        cols, img_w, img_h = self._calculate_optimal_layout(vw, vh, total)
        self._last_cols = cols
        inner_height = img_h + 22

        for seg_label in sorted(grouped.keys()):
            items = grouped[seg_label]

            seg_title = QLabel(f"【{seg_label} 区】 {len(items)} 张")
            seg_title.setFont(QFont("Arial", 11, QFont.Bold))
            seg_title.setStyleSheet("color: #555; margin-top: 2px; padding: 2px 0 2px 0; border-bottom: 1px solid #ddd;")
            self.content_layout.addWidget(seg_title)

            grid_widget = QWidget()
            grid_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            grid_layout = QGridLayout(grid_widget)
            grid_layout.setSpacing(4)
            grid_layout.setContentsMargins(2, 2, 2, 2)

            for col in range(self.MAX_COLS):
                grid_layout.setColumnStretch(col, 1 if col < cols else 0)

            rows = (len(items) + cols - 1) // cols
            for row in range(rows):
                grid_layout.setRowStretch(row, 1)

            for pos, item in enumerate(items):
                row = pos // cols
                col = pos % cols

                pixmap = QPixmap()
                if item.get('path') and os.path.exists(item['path']):
                    loaded = QPixmap(item['path'])
                    if not loaded.isNull():
                        pixmap = loaded

                cell_widget = QWidget()
                cell_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                cell_layout = QHBoxLayout(cell_widget)
                cell_layout.setSpacing(0)
                cell_layout.setContentsMargins(0, 0, 0, 0)
                cell_layout.setAlignment(Qt.AlignCenter)

                inner_widget = QWidget()
                inner_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                inner_widget.setFixedSize(img_w + 2, inner_height)
                inner_widget.setProperty("is_inner_container", True)
                inner_layout = QVBoxLayout(inner_widget)
                inner_layout.setSpacing(2)
                inner_layout.setContentsMargins(0, 0, 0, 0)

                img_label = FavImageLabel(pixmap, item['time'])
                img_label.setObjectName(f"{seg_label}_{pos}")
                img_label.clicked.connect(partial(self.on_fav_item_click, seg_label, pos, img_label))
                img_label.double_clicked.connect(partial(self.preview_fav_item, seg_label, pos))
                img_label.set_image_size(img_w, img_h)
                self._image_labels.append(img_label)

                time_label = QLabel(f"{item['time']:.1f}s")
                time_label.setAlignment(Qt.AlignCenter)
                time_label.setStyleSheet("font-size: 9px; color: #888; padding: 1px 0;")

                inner_layout.addWidget(img_label, 0, Qt.AlignCenter)
                inner_layout.addWidget(time_label, 0, Qt.AlignCenter)

                cell_layout.addWidget(inner_widget)

                grid_layout.addWidget(cell_widget, row, col)

            self.content_layout.addWidget(grid_widget)
            self._grid_widgets.append(grid_widget)

        self.selected_label.setText("已选: 0 张")
        self.export_btn.setEnabled(False)
        self.unfavorite_btn.setEnabled(False)
        self.select_all_btn.setEnabled(len(self.favorites) > 0)
        self.deselect_all_btn.setEnabled(False)

    def on_fav_item_click(self, seg_label: str, pos: int, label: FavImageLabel):
        start_idx = 0
        for item in self.favorites:
            if item.get('segment') == seg_label:
                break
            start_idx += 1
        global_idx = start_idx + pos

        if global_idx in self.selected_indices:
            self.selected_indices.remove(global_idx)
            label.set_selected(False)
        else:
            self.selected_indices.add(global_idx)
            label.set_selected(True)

        count = len(self.selected_indices)
        self.selected_label.setText(f"已选: {count} 张")
        self.export_btn.setEnabled(count > 0)
        self.unfavorite_btn.setEnabled(count > 0)
        self.select_all_btn.setEnabled(count < len(self._all_items))
        self.deselect_all_btn.setEnabled(count > 0)

    def preview_fav_item(self, seg_label: str, pos: int):
        items = [item for item in self.favorites if item.get('segment') == seg_label]
        if pos < len(items):
            item = items[pos]
            if item.get('path') and os.path.exists(item['path']):
                pixmap = QPixmap(item['path'])
                if not pixmap.isNull():
                    dlg = ZoomPreviewDialog(pixmap, item['time'], self)
                    dlg.exec()

    def unfavorite_selected(self):
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选中要取消收藏的截图。")
            return

        to_remove = []
        for idx in self.selected_indices:
            if idx < len(self._all_items):
                item = self._all_items[idx]
                to_remove.append((item['segment'], item['time']))

        if not to_remove:
            return

        reply = QMessageBox.question(
            self, "确认取消收藏",
            f"确定要取消收藏选中的 {len(to_remove)} 张截图吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        removed = 0
        for seg_label, time_sec in to_remove:
            self.favorites = [
                f for f in self.favorites
                if not (f.get('segment') == seg_label and abs(f.get('time', 0) - time_sec) < 0.01)
            ]

            if self.parent_view and self.parent_view.video_id:
                timestamp_ms = int(time_sec * 1000)
                self.parent_view.db.remove_favorite(self.parent_view.video_id, seg_label, timestamp_ms)

            if self.parent_view:
                items = self.parent_view.screenshots.get(seg_label, [])
                for item in items:
                    if abs(item['time'] - time_sec) < 0.01:
                        item['favorite'] = False
                        break
            removed += 1

        if self.parent_view:
            self.parent_view.favorites = [
                f for f in self.parent_view.favorites
                if not any(
                    f.get('segment') == seg_label and abs(f.get('time', 0) - time_sec) < 0.01
                    for seg_label, time_sec in to_remove
                )
            ]
            self.parent_view._update_fav_count()
            self.parent_view._update_seg_buttons()
            if self.parent_view.video_path:
                self.parent_view._update_video_list_icon(self.parent_view.video_path)
            self.parent_view._save_state_to_db()

        self.selected_indices.clear()
        self.selected_label.setText("已选: 0 张")
        self.export_btn.setEnabled(False)
        self.unfavorite_btn.setEnabled(False)

        self.load_favorites()

        QMessageBox.information(self, "完成", f"成功取消收藏 {removed} 张截图。")

    def export_selected(self):
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选中要导出的截图。")
            return

        logger.info(f"[收藏弹窗导出] 开始导出，selected_count={len(self.selected_indices)}")

        export_paths = []
        for idx in self.selected_indices:
            if idx < len(self._all_items):
                item = self._all_items[idx]
                if item.get('path') and os.path.exists(item['path']):
                    export_paths.append((item['time'], item['path'], item['segment']))
                    logger.debug(f"[收藏弹窗导出] 导出项: time={item['time']}, segment={item['segment']}, path={item['path']}")

        if not export_paths:
            QMessageBox.warning(self, "警告", "选中的截图文件不存在。")
            return

        video_name = os.path.splitext(os.path.basename(self.video_path))[0]
        if not video_name:
            video_name = "favorites"
        export_dir = os.path.join(self.export_base, video_name)
        os.makedirs(export_dir, exist_ok=True)

        exported = 0
        skipped = 0
        for time_sec, src_path, seg_label in export_paths:
            # 检查是否已导出
            is_exported = False
            for item in self.favorites:
                if item.get('segment') == seg_label and abs(item.get('time', 0) - time_sec) < 0.01:
                    if item.get('exported', False):
                        is_exported = True
                        logger.debug(f"[收藏弹窗导出] 跳过已导出: time={time_sec}, segment={seg_label}")
                        break
            
            if is_exported:
                skipped += 1
                continue

            dest_name = f"cover_{time_sec:.2f}s.jpg"
            dest_path = os.path.join(export_dir, dest_name)
            try:
                shutil.copy2(src_path, dest_path)
                exported += 1
                # 标记为已导出
                for item in self.favorites:
                    if item.get('segment') == seg_label and abs(item.get('time', 0) - time_sec) < 0.01:
                        item['exported'] = True
                        logger.debug(f"[收藏弹窗导出] 标记 self.favorites 为已导出: time={time_sec}, segment={seg_label}")
                        break
            except Exception as e:
                print(f"导出失败 {src_path}: {e}")

        logger.info(f"[收藏弹窗导出] 导出完成: exported={exported}, skipped={skipped}")

        QMessageBox.information(
            self, 
            "导出完成", 
            f"成功导出 {exported} 张截图到:\n{export_dir}\n\n跳过已导出: {skipped} 张"
        )

        # 更新父视图
        if self.parent_view:
            logger.info(f"[收藏弹窗导出] 父视图存在，video_path={self.parent_view.video_path}, video_id={self.parent_view.video_id}")
            
            old_count = len(self.parent_view.favorites)
            logger.debug(f"[收藏弹窗导出] 父视图 favorites 旧数量: {old_count}")
            
            # 同步导出的收藏状态到父视图
            for time_sec, _, seg_label in export_paths:
                # 更新父视图的 favorites
                for fav in self.parent_view.favorites:
                    if (fav.get('video_path') == self.parent_view.video_path and
                        fav.get('segment') == seg_label and
                        abs(fav.get('time', 0) - time_sec) < 0.01):
                        fav['exported'] = True
                        logger.debug(f"[收藏弹窗导出] 标记父视图 favorites 为已导出: time={time_sec}, segment={seg_label}")
                        break
                
                # 更新父视图的 screenshots
                items = self.parent_view.screenshots.get(seg_label, [])
                for item in items:
                    if abs(item['time'] - time_sec) < 0.01:
                        item['exported'] = True
                        logger.debug(f"[收藏弹窗导出] 标记父视图 screenshots 为已导出: time={time_sec}, segment={seg_label}")
                        break
            
            new_count = len(self.parent_view.favorites)
            logger.debug(f"[收藏弹窗导出] 父视图 favorites 新数量: {new_count}")
            logger.info(f"[收藏弹窗导出] 父视图 favorites 已更新: old_count={old_count}, new_count={new_count}")
            
            # 刷新父视图
            logger.info("[收藏弹窗导出] 准备更新父视图")
            self.parent_view._refresh_grid(self.parent_view.current_seg_index)
            self.parent_view._update_seg_buttons()
            self.parent_view._update_video_list_icon(self.parent_view.video_path)
            
            if self.parent_view.video_id:
                logger.info("[收藏弹窗导出] 调用 _save_state_to_db()")
                self.parent_view._save_state_to_db()
                logger.info("[收藏弹窗导出] _save_state_to_db() 完成")
        else:
            logger.warning("[收藏弹窗导出] 父视图不存在")

        # 清空选中并刷新当前弹窗
        self.selected_indices.clear()
        self.load_favorites()
        logger.info("[收藏弹窗导出] 完成")

    def _mark_favorite_exported(self, seg_label: str, time_sec: float):
        if not self.parent_view:
            return
        items = self.parent_view.screenshots.get(seg_label, [])
        for item in items:
            if abs(item['time'] - time_sec) < 0.01:
                item['exported'] = True
                break


class SegmentView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        print("SegmentView __init__ start")
        logger.info("=== SegmentView 初始化 ===")

        self.db = Database()

        self.video_path = None
        self.video_id = None
        self.duration = 0.0
        self.segments = []
        self.current_seg_index = 0
        self.density = 9

        self.screenshots: Dict[str, List[dict]] = {}
        self.selected_indices: Set[tuple] = set()
        self.all_videos = []

        self.favorites: List[dict] = []

        self.temp_dir = tempfile.mkdtemp(prefix="CoverPicker_")
        self.export_base = os.path.join(os.getcwd(), "StillPic")

        self._load_task = None
        self._loaded_segments: Set[str] = set()

        self.skip_ratio = 0.15
        self.excluded_ranges: List[Tuple[float, float]] = []

        self.all_videos = scan_videos("Z:\\")
        logger.info(f"扫描到 {len(self.all_videos)} 个视频")
        print(f"扫描到 {len(self.all_videos)} 个视频")

        self.setup_ui()
        self.setFocusPolicy(Qt.StrongFocus)
        print("SegmentView __init__ done")

    def load_first_video(self):
        print("load_first_video called")
        if self.all_videos:
            asyncio.create_task(self.load_video(self.all_videos[0]))

    def setup_ui(self):
        print("setup_ui start")
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        left_panel = QWidget()
        left_panel.setFixedWidth(280)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        title = QLabel("📹 视频库")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        left_layout.addWidget(title)

        self.video_list = QListWidget()
        self.video_list.setFont(QFont("Arial", 11))
        self.video_list.setStyleSheet("QListWidget::item { padding: 4px; }")
        self.video_list.itemDoubleClicked.connect(self.on_video_selected)
        for path in self.all_videos:
            name = os.path.basename(path)
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, path)
            video_data = self.db.get_video_by_path(path)
            if video_data:
                state_icon = self._get_state_icon(video_data)
                if state_icon:
                    item.setText(f"{state_icon} {name}")
            self.video_list.addItem(item)
        left_layout.addWidget(self.video_list)

        info_group = QFrame()
        info_group.setFrameShape(QFrame.StyledPanel)
        info_group.setStyleSheet("background: #f8f8f8; border-radius: 4px;")
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(2)

        self.info_name = QLabel("未选择")
        self.info_name.setFont(QFont("Arial", 11, QFont.Bold))
        info_layout.addWidget(self.info_name)

        self.info_duration = QLabel("时长: --")
        self.info_size = QLabel("大小: --")
        self.info_path = QLabel("路径: --")
        self.info_path.setWordWrap(True)
        self.info_path.setStyleSheet("font-size: 9px; color: #666;")

        info_layout.addWidget(self.info_duration)
        info_layout.addWidget(self.info_size)
        info_layout.addWidget(self.info_path)
        info_layout.addStretch()
        left_layout.addWidget(info_group)

        self.progress_label_left = QLabel("")
        self.progress_label_left.setStyleSheet("color: #666; font-size: 10px; padding: 4px;")
        self.progress_label_left.setWordWrap(True)
        left_layout.addWidget(self.progress_label_left)

        stat_layout = QHBoxLayout()
        self.stat_locked = QLabel("锁定: 0")
        self.stat_fav = QLabel("收藏: 0")
        stat_layout.addWidget(self.stat_locked)
        stat_layout.addWidget(self.stat_fav)
        left_layout.addLayout(stat_layout)

        left_layout.addStretch()

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(6)

        top_bar = QHBoxLayout()
        self.video_name_label = QLabel("请选择视频")
        self.video_name_label.setFont(QFont("Arial", 14, QFont.Bold))
        top_bar.addWidget(self.video_name_label)
        top_bar.addStretch()
        self.time_display = QLabel("00:00:00")
        self.time_display.setStyleSheet("font-family: monospace; font-size: 14px; color: #333;")
        top_bar.addWidget(self.time_display)
        right_layout.addLayout(top_bar)

        control_bar = QHBoxLayout()
        control_bar.setSpacing(8)

        seg_group = QHBoxLayout()
        seg_group.setSpacing(4)
        self.seg_buttons = []
        for label in ['A', 'B', 'C', 'D', 'E']:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedSize(55, 30)
            btn.setFont(QFont("Arial", 11, QFont.Bold))
            btn.clicked.connect(lambda checked, lbl=label: self.on_seg_clicked(lbl))
            seg_group.addWidget(btn)
            self.seg_buttons.append(btn)
        control_bar.addLayout(seg_group)

        control_bar.addStretch()

        dens_label = QLabel("密度:")
        control_bar.addWidget(dens_label)
        self.density_buttons = []
        for d in [9, 12, 16, 25]:
            btn = QPushButton(str(d))
            btn.setCheckable(True)
            btn.setFixedSize(35, 26)
            btn.setFont(QFont("Arial", 9))
            if d == 9:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, val=d: self.on_density_changed(val))
            control_bar.addWidget(btn)
            self.density_buttons.append(btn)

        right_layout.addLayout(control_bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.grid_widget = QWidget()
        self.grid_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(4)
        self.grid_layout.setContentsMargins(2, 2, 2, 2)

        self.scroll.setWidget(self.grid_widget)
        right_layout.addWidget(self.scroll, 1)

        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        self.selected_label = QLabel("已选: 0 张")
        bottom_bar.addWidget(self.selected_label)

        self.select_all_btn = QPushButton("☑ 全选")
        self.select_all_btn.clicked.connect(self.select_all)
        self.select_all_btn.setEnabled(False)
        bottom_bar.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("☐ 取消全选")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        self.deselect_all_btn.setEnabled(False)
        bottom_bar.addWidget(self.deselect_all_btn)

        bottom_bar.addStretch()

        view_fav_btn = QPushButton("⭐ 查看收藏")
        view_fav_btn.clicked.connect(self.show_favorites)
        bottom_bar.addWidget(view_fav_btn)

        zoom_btn = QPushButton("🔍 细选")
        zoom_btn.clicked.connect(self.zoom_selected)
        zoom_btn.setStyleSheet("background: #2196F3; color: white; font-weight: bold;")
        bottom_bar.addWidget(zoom_btn)

        fav_btn = QPushButton("⭐ 收藏")
        fav_btn.clicked.connect(self.favorite_selected)
        bottom_bar.addWidget(fav_btn)

        unfav_btn = QPushButton("☆ 取消收藏")
        unfav_btn.clicked.connect(self.unfavorite_selected)
        bottom_bar.addWidget(unfav_btn)

        lock_btn = QPushButton("🔒 锁定")
        lock_btn.clicked.connect(self.lock_selected)
        bottom_bar.addWidget(lock_btn)

        unlock_btn = QPushButton("🔓 解锁")
        unlock_btn.clicked.connect(self.unlock_selected)
        bottom_bar.addWidget(unlock_btn)

        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(lambda: asyncio.create_task(self.refresh_unlocked()))
        bottom_bar.addWidget(refresh_btn)

        reset_btn = QPushButton("♻️ 重抽")
        reset_btn.clicked.connect(lambda: asyncio.create_task(self.reset_all()))
        bottom_bar.addWidget(reset_btn)

        export_btn = QPushButton("📥 导出")
        export_btn.clicked.connect(self.export_selected)
        bottom_bar.addWidget(export_btn)

        right_layout.addLayout(bottom_bar)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([280, 1020])
        main_layout.addWidget(splitter)

        for btn in self.seg_buttons:
            btn.setEnabled(False)

        print("setup_ui done")

    def _get_state_icon(self, video_data: dict) -> str:
        if video_data.get('is_exported', 0):
            return "✅"
        elif video_data.get('is_starred', 0):
            return "⭐"
        elif video_data.get('is_viewed', 0):
            return "👁️"
        return ""

    def _update_video_list_icon(self, file_path: str):
        video_data = self.db.get_video_by_path(file_path)
        if not video_data:
            return
        icon = self._get_state_icon(video_data)
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            if item.data(Qt.UserRole) == file_path:
                name = os.path.basename(file_path)
                item.setText(f"{icon} {name}" if icon else name)
                break

    def _mark_favorite_exported(self, seg_label: str, time_sec: float):
        items = self.screenshots.get(seg_label, [])
        for item in items:
            if abs(item['time'] - time_sec) < 0.01:
                item['exported'] = True
                break

    def select_all(self):
        seg_idx = self.current_seg_index
        seg_label = self.segments[seg_idx][0]
        items = self.screenshots.get(seg_label, [])
        for pos in range(len(items)):
            self.selected_indices.add((seg_idx, pos))
        self._refresh_grid(seg_idx)
        self._update_selected_count()
        self.select_all_btn.setEnabled(False)
        self.deselect_all_btn.setEnabled(True)

    def deselect_all(self):
        self.selected_indices.clear()
        self._refresh_grid(self.current_seg_index)
        self._update_selected_count()
        self.select_all_btn.setEnabled(True)
        self.deselect_all_btn.setEnabled(False)

    def show_favorites(self):
        if not self.video_path:
            QMessageBox.information(self, "提示", "请先加载视频。")
            return
        current_favs = [f for f in self.favorites if f.get('video_path') == self.video_path]
        if not current_favs:
            QMessageBox.information(self, "提示", "当前视频没有收藏截图。")
            return
        dlg = FavoritesDialog(current_favs, os.path.basename(self.video_path), self.export_base, self.video_path, self)
        dlg.exec()
        self._refresh_grid(self.current_seg_index)
        self._update_seg_buttons()

    def _update_fav_count(self):
        if not self.video_path:
            self.stat_fav.setText("收藏: 0")
            return
        count = sum(1 for f in self.favorites if f.get('video_path') == self.video_path)
        self.stat_fav.setText(f"收藏: {count}")

    def _save_state_to_db(self):
        if not self.video_path or not self.video_id:
            logger.debug(f"[保存状态] 跳过: video_path={self.video_path}, video_id={self.video_id}")
            return

        logger.info(f"[保存状态] 开始保存: video_path={self.video_path}, video_id={self.video_id}")

        seg_states = {}
        for seg_label, items in self.screenshots.items():
            has_starred = any(item.get('favorite', False) for item in items)
            has_exported = any(item.get('exported', False) for item in items)
            seg_states[seg_label] = {
                'is_viewed': seg_label in self._loaded_segments,
                'has_starred': has_starred,
                'has_exported': has_exported
            }
            logger.debug(f"[保存状态] 分区 {seg_label}: has_starred={has_starred}, has_exported={has_exported}")

        # 修复：从 screenshots 中检查是否有任何收藏，而不是从 self.favorites
        is_starred = any(
            item.get('favorite', False)
            for seg_label, items in self.screenshots.items()
            for item in items
        )

        is_exported = any(
            item.get('exported', False)
            for seg_label, items in self.screenshots.items()
            for item in items
        )

        logger.info(f"[保存状态] is_starred={is_starred}, is_exported={is_exported}")

        self.db.update_video_state(self.video_id, is_viewed=bool(self._loaded_segments),
                                   is_starred=is_starred, is_exported=is_exported)

        for seg_label, state in seg_states.items():
            self.db.update_segment_state(self.video_id, seg_label,
                                         is_viewed=state['is_viewed'],
                                         has_starred=state['has_starred'],
                                         has_exported=state['has_exported'])

        self._update_video_list_icon(self.video_path)
        logger.info(f"[保存状态] 完成")

    def favorite_selected(self):
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选中要收藏的截图。")
            return

        seg_label = self.segments[self.current_seg_index][0]
        items = self.screenshots.get(seg_label, [])
        processed_keys = set()
        added_count = 0
        skipped_count = 0

        logger.info(f"[收藏操作] 开始收藏: seg_label={seg_label}, selected_indices数量={len(self.selected_indices)}, items数量={len(items)}")

        for (seg_idx, pos) in list(self.selected_indices):
            if seg_idx == self.current_seg_index and pos < len(items):
                item = items[pos]
                key = (self.video_path, seg_label, item['time'])

                if key in processed_keys:
                    skipped_count += 1
                    logger.debug(f"[收藏操作] 跳过重复: time={item['time']}, pos={pos}")
                    continue
                processed_keys.add(key)

                if not item.get('favorite', False):
                    item['favorite'] = True
                    if self.video_id:
                        timestamp_ms = int(item['time'] * 1000)
                        if not self.db.is_favorite(self.video_id, seg_label, timestamp_ms):
                            self.db.add_favorite(self.video_id, seg_label, timestamp_ms, item.get('path', ''))
                        else:
                            logger.warning(f"[收藏操作] 数据库中已存在: time={item['time']}")
                    self.favorites.append({
                        'video_path': self.video_path,
                        'segment': seg_label,
                        'time': item['time'],
                        'path': item['path'],
                    })
                    added_count += 1
                    logger.debug(f"[收藏操作] 添加收藏: time={item['time']}, pos={pos}")
                else:
                    logger.debug(f"[收藏操作] 已收藏: time={item['time']}, pos={pos}")

        logger.info(f"[收藏操作] 完成: 添加={added_count}, 跳过重复={skipped_count}, 已收藏={len(processed_keys) - added_count - skipped_count}")

        if added_count > 0:
            self._refresh_grid(self.current_seg_index)
            self._update_seg_buttons()
            self._update_fav_count()
            self._save_state_to_db()
            logger.info(f"收藏成功: {added_count} 张")
        else:
            logger.info("没有新的收藏添加")

    def unfavorite_selected(self):
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选中要取消收藏的截图。")
            return
        seg_label = self.segments[self.current_seg_index][0]
        items = self.screenshots.get(seg_label, [])
        removed_count = 0

        for (seg_idx, pos) in list(self.selected_indices):
            if seg_idx == self.current_seg_index and pos < len(items):
                item = items[pos]
                if item.get('favorite', False):
                    item['favorite'] = False
                    if self.video_id:
                        timestamp_ms = int(item['time'] * 1000)
                        self.db.remove_favorite(self.video_id, seg_label, timestamp_ms)
                    self.favorites = [
                        f for f in self.favorites
                        if not (f.get('video_path') == self.video_path and
                                f.get('segment') == seg_label and
                                abs(f.get('time', 0) - item['time']) < 0.01)
                    ]
                    removed_count += 1

        if removed_count > 0:
            self._refresh_grid(self.current_seg_index)
            self._update_seg_buttons()
            self._update_fav_count()
            self._save_state_to_db()
            logger.info(f"取消收藏成功: {removed_count} 张")
        else:
            logger.info("没有收藏被取消")

    def _restore_favorites_from_db(self):
        if not self.video_path or not self.video_id:
            return
        db_favs = self.db.get_favorites(self.video_id)
        for fav in db_favs:
            exists = any(
                f.get('segment') == fav['segment_label'] and
                abs(f.get('time', 0) - fav['timestamp_ms'] / 1000) < 0.01
                for f in self.favorites if f.get('video_path') == self.video_path
            )
            if not exists:
                self.favorites.append({
                    'video_path': self.video_path,
                    'segment': fav['segment_label'],
                    'time': fav['timestamp_ms'] / 1000,
                    'path': fav['thumbnail_path'],
                })

    def _restore_favorites_to_screenshots(self):
        if not self.video_path:
            return
        fav_items = [f for f in self.favorites if f.get('video_path') == self.video_path]
        if not fav_items:
            return
        for seg_label, items in self.screenshots.items():
            for item in items:
                for fav in fav_items:
                    if fav.get('segment') == seg_label and abs(fav.get('time', 0) - item['time']) < 0.01:
                        item['favorite'] = True
                        break

    def zoom_selected(self):
        if len(self.selected_indices) > 1:
            QMessageBox.information(self, "提示", "细选只能针对单张截图，请只选中一张截图。")
            return
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选中一张截图，然后点击'细选'。")
            return
        seg_idx, pos = next(iter(self.selected_indices))
        seg_label = self.segments[seg_idx][0]
        items = self.screenshots.get(seg_label, [])
        if pos >= len(items):
            return
        item = items[pos]
        if not item.get('path') or not os.path.exists(item['path']):
            QMessageBox.warning(self, "警告", "图片文件不存在。")
            return

        dlg = ZoomDialog(
            video_path=self.video_path,
            time_sec=item['time'],
            segment_label=seg_label,
            segments=self.segments,
            screenshots=self.screenshots,
            temp_dir=self.temp_dir,
            export_base=self.export_base,
            parent=self
        )
        dlg.exec()
        self._refresh_grid(self.current_seg_index)

    def on_video_selected(self, item: QListWidgetItem):
        path = item.data(Qt.UserRole)
        if path:
            asyncio.create_task(self.load_video(path))

    async def load_video(self, video_path: str):
        """加载视频 - 修复：添加任务取消逻辑防止协程冲突"""
        # 取消正在进行的加载任务（修复快速切换视频时的协程冲突）
        if self._load_task and not self._load_task.done():
            self._load_task.cancel()
            logger.debug(f"取消之前的加载任务: {self.video_path}")
        self._load_task = None

        logger.info(f"加载视频: {video_path}")
        print(f"加载视频: {video_path}")
        self.video_path = video_path
        self.video_name_label.setText(os.path.basename(video_path))
        self.info_name.setText(os.path.basename(video_path))
        self.info_path.setText(f"路径: {video_path}")
        self._clear_grid()
        self.progress_label_left.setText("加载中...")

        # 再次检查并取消可能残留的任务
        if self._load_task and not self._load_task.done():
            self._load_task.cancel()
        self._load_task = None

        duration = get_video_duration(video_path)
        if duration is None:
            QMessageBox.critical(self, "错误", f"无法获取视频时长: {video_path}")
            return
        self.duration = duration
        self.segments = calculate_segments(duration)

        self.info_duration.setText(f"时长: {str(timedelta(seconds=int(duration)))}")
        size_mb = os.path.getsize(video_path) / (1024*1024)
        self.info_size.setText(f"大小: {size_mb:.2f} MB")

        file_name = os.path.basename(video_path)
        self.video_id = self.db.get_or_create_video(
            video_path, file_name, int(duration), "", int(os.path.getsize(video_path)), int(os.path.getmtime(video_path))
        )

        # 从数据库恢复当前视频的收藏
        self.favorites = []
        self._restore_favorites_from_db()

        self.screenshots = {}
        self.selected_indices = set()
        self._loaded_segments = set()

        self.select_all_btn.setEnabled(False)
        self.deselect_all_btn.setEnabled(False)

        for btn in self.seg_buttons:
            btn.setEnabled(True)

        self.current_seg_index = 0
        self._update_seg_buttons()
        
        # 创建加载任务并保存引用
        self._load_task = asyncio.create_task(self._load_segment(0, restore_locks=True, randomize=False))
        await self._load_task
        self._load_task = None
        
        self._restore_favorites_to_screenshots()
        self._refresh_grid(0)
        # 更新收藏计数
        self._update_fav_count()

        if self._loaded_segments:
            self.db.update_video_state(self.video_id, is_viewed=True)
        self._update_video_list_icon(video_path)

        self.progress_label_left.setText("加载完成")

    def _clear_grid(self):
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.progress_label_left.setText("")

    def on_seg_clicked(self, label: str):
        idx = ord(label) - ord('A')
        if 0 <= idx < len(self.segments):
            self.current_seg_index = idx
            self._update_seg_buttons()
            if self._load_task and not self._load_task.done():
                self._load_task.cancel()
                logger.debug(f"取消分段切换前的任务")
            self._load_task = asyncio.create_task(self._load_segment(idx, restore_locks=True, randomize=False))

    def _update_seg_buttons(self):
        if not self.video_path or not self.segments:
            return
        for i, btn in enumerate(self.seg_buttons):
            label = chr(ord('A') + i)
            if i < len(self.segments):
                seg_label = self.segments[i][0]
                state = self._get_seg_state(seg_label)
                btn.setText(f"{label}{state}")
                btn.setVisible(True)
                btn.setEnabled(True)
            else:
                btn.setVisible(False)
                btn.setEnabled(False)
            btn.setChecked(i == self.current_seg_index)

    def _get_seg_state(self, seg_label: str) -> str:
        if not self.video_path:
            return ""

        is_viewed = seg_label in self._loaded_segments

        has_fav = any(
            f.get('segment') == seg_label
            for f in self.favorites
            if f.get('video_path') == self.video_path
        )

        items = self.screenshots.get(seg_label, [])
        has_export = any(item.get('exported', False) for item in items)

        state = ""
        if is_viewed:
            state += "✓"
        if has_fav:
            state += "★"
        if has_export:
            state += "▼"
        return state

    def _filter_excluded_random(self, times: List[float], start: float, end: float, target_count: int) -> List[float]:
        if not self.excluded_ranges:
            return times
        valid = []
        for t in times:
            excluded = False
            for low, high in self.excluded_ranges:
                if low <= t <= high:
                    excluded = True
                    break
            if not excluded:
                valid.append(t)
        while len(valid) < target_count:
            t = random.uniform(start, end)
            excluded = False
            for low, high in self.excluded_ranges:
                if low <= t <= high:
                    excluded = True
                    break
            if not excluded:
                valid.append(t)
        if len(valid) > target_count:
            valid = valid[:target_count]
        valid.sort()
        return valid

    async def _load_segment(self, seg_idx: int, restore_locks: bool = True, randomize: bool = False):
        """加载分段 - 修复：添加取消检查和异常处理"""
        if not self.video_path or not self.segments:
            return

        # 检查当前任务是否被取消
        current_task = asyncio.current_task()
        if current_task and current_task.cancelled():
            logger.debug(f"分段 {seg_idx} 加载被取消（任务状态检查）")
            return

        self.current_seg_index = seg_idx

        label, start, end = self.segments[seg_idx]
        offset = (end - start) * self.skip_ratio
        start_cropped = start + offset
        end_cropped = end - offset
        if end_cropped <= start_cropped:
            start_cropped = start
            end_cropped = end
        logger.info(f"加载分段 {label}: {start_cropped:.1f}s - {end_cropped:.1f}s")

        duration_seg = end_cropped - start_cropped
        count = self.density

        seg_key = label
        old_items = self.screenshots.get(seg_key, [])

        new_times = [random.uniform(start_cropped, end_cropped) for _ in range(count)]
        new_times.sort()
        new_times = self._filter_excluded_random(new_times, start_cropped, end_cropped, count)

        new_items = []
        total = len(new_times)
        for idx, t in enumerate(new_times):
            # 检查是否被取消
            if current_task and current_task.cancelled():
                logger.debug(f"分段 {seg_idx} 加载被取消（循环中检查）")
                return

            matched = None
            if restore_locks:
                for item in old_items:
                    if abs(item['time'] - t) < 0.5:
                        matched = item
                        break
            if matched:
                new_items.append({
                    'time': matched['time'],
                    'path': matched['path'],
                    'locked': matched.get('locked', False),
                    'favorite': matched.get('favorite', False),
                    'exported': matched.get('exported', False),
                })
                continue

            self.progress_label_left.setText(f"正在生成 {label} 第 {idx+1}/{total} 张 @ {t:.2f}s")
            QApplication.processEvents()

            temp_path = os.path.join(self.temp_dir, f"seg_{label}_{t:.2f}.jpg")
            
            try:
                success = await asyncio.to_thread(extract_frame, self.video_path, t, temp_path)
                if success:
                    new_items.append({
                        'time': t,
                        'path': temp_path,
                        'locked': False,
                        'favorite': False,
                        'exported': False,
                    })
                    self.progress_label_left.setText(f"截图成功: {label} {idx} @ {t:.2f}s")
                    logger.info(f"截图成功: {label} {idx} @ {t:.2f}s")
                else:
                    new_items.append({
                        'time': t,
                        'path': None,
                        'locked': False,
                        'favorite': False,
                        'exported': False,
                    })
                    logger.warning(f"截图失败: {label} {idx} @ {t:.2f}s")
            except asyncio.CancelledError:
                logger.debug(f"截图任务被取消: {label} {idx} @ {t:.2f}s")
                # 清理临时文件
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                # 重新抛出以便上层处理
                raise

        # 再次检查是否被取消
        if current_task and current_task.cancelled():
            logger.debug(f"分段 {seg_idx} 加载被取消（完成后检查）")
            return

        self.screenshots[seg_key] = new_items
        self.selected_indices = set()

        self._loaded_segments.add(label)

        self._restore_favorites_to_screenshots()

        self._refresh_grid(seg_idx)
        self._update_seg_buttons()
        self.progress_label_left.setText(f"{label} 分段加载完成 ({len(new_items)} 张)")

    def _refresh_grid(self, seg_idx: int):
        try:
            logger.info(f"刷新网格开始, seg_idx={seg_idx}")
            if seg_idx < 0 or seg_idx >= len(self.segments):
                logger.error(f"无效的 seg_idx: {seg_idx}")
                return

            while self.grid_layout.count():
                child = self.grid_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            seg_label, _, _ = self.segments[seg_idx]
            items = self.screenshots.get(seg_label, [])
            count = len(items)

            if self.density == 9:
                cols = 3
            elif self.density == 12:
                cols = 3
            elif self.density == 16:
                cols = 4
            elif self.density == 25:
                cols = 5
            else:
                cols = 4

            for col in range(cols):
                self.grid_layout.setColumnStretch(col, 1)

            locked_count = sum(1 for it in items if it.get('locked', False))
            self.stat_locked.setText(f"锁定: {locked_count}")

            self.select_all_btn.setEnabled(count > 0 and len(self.selected_indices) < count)
            self.deselect_all_btn.setEnabled(len(self.selected_indices) > 0)

            for pos, item in enumerate(items):
                row = pos // cols
                col = pos % cols

                pixmap = QPixmap(200, 150)
                pixmap.fill(QColor(60, 60, 60))
                if item.get('path') and os.path.exists(item['path']):
                    loaded = QPixmap(item['path'])
                    if not loaded.isNull():
                        pixmap = loaded

                index_num = pos + 1
                label = ClickableLabel(pixmap, item['time'], index_num)
                label.setObjectName(f"{seg_idx}_{pos}")
                label.set_locked(item.get('locked', False))
                label.set_favorite(item.get('favorite', False))
                label.set_exported(item.get('exported', False))
                if (seg_idx, pos) in self.selected_indices:
                    label.set_selected(True)

                label.clicked.connect(partial(self.on_image_click, seg_idx, pos))
                label.double_clicked.connect(partial(self.preview_image, seg_idx, pos))
                self.grid_layout.addWidget(label, row, col)

            self._update_selected_count()
            self.grid_widget.updateGeometry()
            self.grid_widget.update()
            self.scroll.update()
            QApplication.processEvents()
            logger.info("刷新网格完成")
        except Exception as e:
            logger.error(f"刷新网格整体出错: {e}\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"显示截图时出错: {str(e)}")

    def on_image_click(self, seg_idx: int, pos: int):
        key = (seg_idx, pos)
        if key in self.selected_indices:
            self.selected_indices.remove(key)
        else:
            self.selected_indices.add(key)
        self._refresh_grid(seg_idx)

    def preview_image(self, seg_idx: int, pos: int):
        seg_label = self.segments[seg_idx][0]
        items = self.screenshots.get(seg_label, [])
        if pos >= len(items):
            return
        item = items[pos]
        if not item.get('path') or not os.path.exists(item['path']):
            QMessageBox.warning(self, "警告", "图片文件不存在。")
            return

        pixmap = QPixmap(item['path'])
        if pixmap.isNull():
            return
        dlg = ZoomPreviewDialog(pixmap, item['time'], self)
        dlg.exec()

    def lock_selected(self):
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选中要锁定的截图。")
            return
        seg_label = self.segments[self.current_seg_index][0]
        items = self.screenshots.get(seg_label, [])
        for (seg_idx, pos) in list(self.selected_indices):
            if seg_idx == self.current_seg_index and pos < len(items):
                items[pos]['locked'] = True
        self._refresh_grid(self.current_seg_index)
        self._update_seg_buttons()

    def unlock_selected(self):
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选中要解锁的截图。")
            return
        seg_label = self.segments[self.current_seg_index][0]
        items = self.screenshots.get(seg_label, [])
        for (seg_idx, pos) in list(self.selected_indices):
            if seg_idx == self.current_seg_index and pos < len(items):
                items[pos]['locked'] = False
        self._refresh_grid(self.current_seg_index)
        self._update_seg_buttons()

    async def refresh_unlocked(self):
        try:
            seg_idx = self.current_seg_index
            seg_label, start, end = self.segments[seg_idx]
            offset = (end - start) * self.skip_ratio
            start_cropped = start + offset
            end_cropped = end - offset
            if end_cropped <= start_cropped:
                start_cropped = start
                end_cropped = end

            items = self.screenshots.get(seg_label, [])
            unlocked_positions = [i for i, item in enumerate(items) if not item.get('locked', False)]
            if not unlocked_positions:
                QMessageBox.information(self, "提示", "当前分段没有未锁定的截图。")
                return

            locked_times = [item['time'] for item in items if item.get('locked', False)]
            total = len(unlocked_positions)
            for idx, pos in enumerate(unlocked_positions):
                self.progress_label_left.setText(f"刷新未锁定 {idx+1}/{total}")
                QApplication.processEvents()
                for _ in range(20):
                    t = random.uniform(start_cropped, end_cropped)
                    excluded = False
                    for low, high in self.excluded_ranges:
                        if low <= t <= high:
                            excluded = True
                            break
                    if not excluded and all(abs(t - lt) > 0.5 for lt in locked_times):
                        break
                temp_path = os.path.join(self.temp_dir, f"seg_{seg_label}_{t:.2f}_new.jpg")
                try:
                    success = await asyncio.to_thread(extract_frame, self.video_path, t, temp_path)
                    if success:
                        items[pos]['time'] = t
                        items[pos]['path'] = temp_path
                        items[pos]['locked'] = False
                        self.progress_label_left.setText(f"刷新成功: {seg_label} {pos} @ {t:.2f}s")
                        logger.info(f"刷新未锁定: {seg_label} {pos} -> {t:.2f}s")
                    else:
                        logger.warning(f"刷新未锁定失败: {seg_label} {pos}")
                except asyncio.CancelledError:
                    logger.debug(f"刷新未锁定被取消: {seg_label} {pos}")
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except:
                            pass
                    raise
            self._refresh_grid(seg_idx)
            self._update_seg_buttons()
            self.progress_label_left.setText("刷新完成")
        except asyncio.CancelledError:
            logger.debug("refresh_unlocked 被取消")
        except Exception as e:
            logger.error(f"refresh_unlocked error: {e}")

    async def reset_all(self):
        try:
            seg_idx = self.current_seg_index
            seg_label = self.segments[seg_idx][0]
            logger.info(f"全部重抽: 分段 {seg_label}")
            self.screenshots[seg_label] = []
            self.selected_indices = set()
            if self._load_task and not self._load_task.done():
                self._load_task.cancel()
            self._load_task = asyncio.create_task(self._load_segment(seg_idx, restore_locks=False, randomize=True))
            await self._load_task
            self._refresh_grid(seg_idx)
            self._update_seg_buttons()
            logger.info(f"全部重抽完成: 分段 {seg_label}")
        except asyncio.CancelledError:
            logger.debug("reset_all 被取消")
        except Exception as e:
            logger.error(f"reset_all error: {e}")

    def export_selected(self):
        try:
            if not self.selected_indices:
                QMessageBox.information(self, "提示", "请先选中要导出的截图。")
                return

            seg_label = self.segments[self.current_seg_index][0]
            items = self.screenshots.get(seg_label, [])
            export_paths = []
            for (seg_idx, pos) in self.selected_indices:
                if seg_idx == self.current_seg_index and pos < len(items):
                    item = items[pos]
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
                    items[pos]['exported'] = True
                except Exception as e:
                    logger.error(f"导出失败 {src_path}: {e}")

            if self.video_id:
                seg_items = self.screenshots.get(seg_label, [])
                has_export = any(item.get('exported', False) for item in seg_items)
                self.db.update_segment_state(self.video_id, seg_label, has_exported=has_export)
                all_exported = any(
                    item.get('exported', False)
                    for seg, items in self.screenshots.items()
                    for item in items
                )
                self.db.update_video_state(self.video_id, is_exported=all_exported)

            QMessageBox.information(self, "导出完成", f"成功导出 {exported} 张截图到:\n{export_dir}")
            self.selected_indices.clear()
            self._refresh_grid(self.current_seg_index)
            self._update_seg_buttons()
            self._update_video_list_icon(self.video_path)

        except Exception as e:
            logger.error(f"export_selected error: {e}")

    def on_density_changed(self, val: int):
        self.density = val
        for btn in self.density_buttons:
            btn.setChecked(int(btn.text()) == val)
        if self.video_path:
            if self._load_task and not self._load_task.done():
                self._load_task.cancel()
            self._load_task = asyncio.create_task(self._load_segment(self.current_seg_index, restore_locks=True, randomize=False))

    def _update_selected_count(self):
        count = len(self.selected_indices)
        self.selected_label.setText(f"已选: {count} 张")

    def closeEvent(self, event):
        try:
            # 取消正在进行的任务
            if self._load_task and not self._load_task.done():
                self._load_task.cancel()
            
            if self.video_id and self.video_path:
                self._save_state_to_db()
            if hasattr(self, 'db'):
                self.db.close()
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except:
            pass
        event.accept()