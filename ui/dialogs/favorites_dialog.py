# ui/dialogs/favorites_dialog.py
# 直接从 segment_view.py 提取的 FavoritesDialog 类（含 FavImageLabel）

import os
import shutil
import logging
from typing import List, Dict, Optional, Tuple
from functools import partial
from collections import defaultdict

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGridLayout, QScrollArea, QFrame, QMessageBox, QSizePolicy,
    QWidget, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap, QFont, QColor, QPainter, QPen, QBrush, QResizeEvent

logger = logging.getLogger(__name__)


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
    """收藏弹窗 - 从 segment_view.py 提取的原始实现"""

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

            img_w = (viewport_width - padding * 2 - spacing * (cols - 1)) // cols
            img_h = int(img_w * self.IMG_ASPECT)
            logger.debug(f"[收藏弹窗] 尝试 cols={cols}, rows={rows}, img_w={img_w}, img_h={img_h}")

            total_img_height = rows * img_h + (rows - 1) * 4
            if total_img_height > img_available_height and img_available_height > 0:
                img_h = max(self.MIN_IMG_H, (img_available_height - (rows - 1) * 4) // rows)
                img_w = int(img_h / self.IMG_ASPECT)
                logger.debug(f"[收藏弹窗] 高度修正: img_h={img_h}, img_w={img_w}")

            img_w = max(self.MIN_IMG_W, img_w)
            img_h = max(self.MIN_IMG_H, img_h)

            max_img_w = (viewport_width - padding * 2 - spacing * (cols - 1)) // cols
            if img_w > max_img_w:
                img_w = max_img_w
                img_h = int(img_w * self.IMG_ASPECT)
                img_h = max(self.MIN_IMG_H, img_h)
                img_w = max(self.MIN_IMG_W, img_w)
                logger.debug(f"[收藏弹窗] 宽度修正: img_w={img_w}, img_h={img_h}")

            if img_w > best_img_w:
                best_cols = cols
                best_img_w = img_w
                best_img_h = img_h
                logger.debug(f"[收藏弹窗] 更新 best: cols={best_cols}, img_w={best_img_w}, img_h={best_img_h}")

        # 兜底逻辑
        if not found_valid:
            logger.warning(f"[收藏弹窗] 所有列数都被跳过，使用兜底逻辑: 选择最大列数 {max_cols_by_width}")
            best_cols = max_cols_by_width
            best_img_w = (viewport_width - padding * 2 - spacing * (best_cols - 1)) // best_cols
            best_img_h = int(best_img_w * self.IMG_ASPECT)
            best_img_w = max(self.MIN_IMG_W, best_img_w)
            best_img_h = max(self.MIN_IMG_H, best_img_h)
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
                    from ui.views.zoom_preview import ZoomPreviewDialog
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

        export_paths = []
        for idx in self.selected_indices:
            if idx < len(self._all_items):
                item = self._all_items[idx]
                if item.get('path') and os.path.exists(item['path']):
                    export_paths.append((item['time'], item['path'], item['segment']))

        if not export_paths:
            QMessageBox.warning(self, "警告", "选中的截图文件不存在。")
            return

        video_name = os.path.splitext(os.path.basename(self.video_path))[0]
        if not video_name:
            video_name = "favorites"
        export_dir = os.path.join(self.export_base, video_name)
        os.makedirs(export_dir, exist_ok=True)

        exported = 0
        for time_sec, src_path, seg_label in export_paths:
            dest_name = f"cover_{time_sec:.2f}s.jpg"
            dest_path = os.path.join(export_dir, dest_name)
            try:
                shutil.copy2(src_path, dest_path)
                exported += 1
                for item in self.favorites:
                    if item.get('segment') == seg_label and abs(item.get('time', 0) - time_sec) < 0.01:
                        item['exported'] = True
                        break
            except Exception as e:
                print(f"导出失败 {src_path}: {e}")

        QMessageBox.information(self, "导出完成", f"成功导出 {exported} 张截图到:\n{export_dir}")

        if self.parent_view:
            for seg_label, pos in self.selected_indices:
                items = [item for item in self.favorites if item.get('segment') == seg_label]
                if pos < len(items):
                    item = items[pos]
                    if self.parent_view.video_path:
                        self.parent_view._mark_favorite_exported(
                            seg_label, item['time']
                        )
            self.parent_view._refresh_grid(self.parent_view.current_seg_index)
            self.parent_view._update_seg_buttons()
            if self.parent_view.video_path:
                self.parent_view._update_video_list_icon(self.parent_view.video_path)
                if self.parent_view.video_id:
                    self.parent_view._save_state_to_db()

        self.selected_indices.clear()
        self.load_favorites()