# ui/dialogs/favorites_dialog.py

import os
import shutil
import logging
from typing import Dict, List, Tuple
from functools import partial

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGridLayout, QScrollArea, QFrame, QMessageBox, QSizePolicy, QDialog,
    QApplication
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QFont, QColor, QPainter, QBrush, QResizeEvent

from ui.widgets.image_labels import FavImageLabel
from ui.views.zoom_preview import ZoomPreviewDialog

logger = logging.getLogger(__name__)


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

        self.zoom_btn = QPushButton("🔍 细选")
        self.zoom_btn.clicked.connect(self.zoom_selected)
        self.zoom_btn.setEnabled(False)
        top_bar.addWidget(self.zoom_btn)

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
        video_name = os.path.splitext(os.path.basename(self.video_path))[0]
        export_dir = os.path.join(self.export_base, video_name)
        grouped = self._get_seg_items()
        for seg_label in sorted(grouped.keys()):
            for item in grouped[seg_label]:
                exported_val = item.get('exported', False)
                if exported_val:
                    expected_file = os.path.join(export_dir, f"cover_{item['time']:.2f}s.jpg")
                    if not os.path.exists(expected_file):
                        exported_val = False
                        item['exported'] = False
                result.append({
                    'segment': seg_label,
                    'time': item['time'],
                    'path': item.get('path', ''),
                    'exported': exported_val,
                    'original_item': item,
                })
        self._all_items = result
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
        self.zoom_btn.setEnabled(len(self.selected_indices) == 1)

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

        if vw < 100 or vw < window_w * 0.85:
            vw = window_w - 20
        if vh < 100:
            vh = 700
        return vw, vh

    def _calculate_optimal_layout(self, viewport_width: int, viewport_height: int, total_items: int) -> Tuple[int, int, int]:
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

        max_rows_by_height = max(1, img_available_height // (self.MIN_IMG_H + 10))

        best_cols = max_cols_by_width
        best_img_w = self.MIN_IMG_W
        best_img_h = self.MIN_IMG_H
        found_valid = False

        for cols in range(max_cols_by_width, 0, -1):
            rows = (total_items + cols - 1) // cols
            if rows > max_rows_by_height:
                continue
            found_valid = True

            scrollbar_width = 12
            available_width = viewport_width - padding * 2 - scrollbar_width
            img_w = (available_width - spacing * (cols - 1)) // cols
            img_h = int(img_w * self.IMG_ASPECT)

            total_img_height = rows * img_h + (rows - 1) * 4
            if total_img_height > img_available_height and img_available_height > 0:
                img_h = max(self.MIN_IMG_H, (img_available_height - (rows - 1) * 4) // rows)
                img_w = int(img_h / self.IMG_ASPECT)

            img_w = max(self.MIN_IMG_W, img_w)
            img_h = max(self.MIN_IMG_H, img_h)

            max_img_w = (available_width - spacing * (cols - 1)) // cols
            if img_w > max_img_w:
                img_w = max_img_w
                img_h = int(img_w * self.IMG_ASPECT)
                img_h = max(self.MIN_IMG_H, img_h)
                img_w = max(self.MIN_IMG_W, img_w)

            current_area = img_w * img_h
            best_area = best_img_w * best_img_h
            if current_area > best_area:
                best_cols = cols
                best_img_w = img_w
                best_img_h = img_h

        if not found_valid:
            best_cols = max_cols_by_width
            scrollbar_width = 12
            available_width = viewport_width - padding * 2 - scrollbar_width
            best_img_w = max(self.MIN_IMG_W, (available_width - spacing * (best_cols - 1)) // best_cols)
            best_img_h = max(self.MIN_IMG_H, int(best_img_w * self.IMG_ASPECT))

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
        previous_selected = set(self.selected_indices)

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

        global_idx = 0

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
                img_label.clicked.connect(partial(self.on_fav_item_click, global_idx, img_label))
                img_label.double_clicked.connect(partial(self.preview_fav_item, seg_label, pos))
                img_label.set_image_size(img_w, img_h)
                exported_val = item.get('exported', False)
                img_label.set_exported(exported_val)
                self._image_labels.append(img_label)

                time_label = QLabel(f"{item['time']:.1f}s")
                time_label.setAlignment(Qt.AlignCenter)
                time_label.setStyleSheet("font-size: 9px; color: #888; padding: 1px 0;")

                inner_layout.addWidget(img_label, 0, Qt.AlignCenter)
                inner_layout.addWidget(time_label, 0, Qt.AlignCenter)

                cell_layout.addWidget(inner_widget)
                grid_layout.addWidget(cell_widget, row, col)

                global_idx += 1

            self.content_layout.addWidget(grid_widget)
            self._grid_widgets.append(grid_widget)

        self.selected_indices = previous_selected & set(range(len(self._all_items)))
        self._update_selection_states()
        count = len(self.selected_indices)
        self.selected_label.setText(f"已选: {count} 张")
        self.export_btn.setEnabled(count > 0)
        self.unfavorite_btn.setEnabled(count > 0)
        self.select_all_btn.setEnabled(count < len(self._all_items))
        self.deselect_all_btn.setEnabled(count > 0)

    def on_fav_item_click(self, global_idx: int, label: FavImageLabel):
        if global_idx in self.selected_indices:
            self.selected_indices.remove(global_idx)
            label.set_selected(False)
        else:
            self.selected_indices.add(global_idx)
            label.set_selected(True)

        self._update_selection_states()
        count = len(self.selected_indices)
        self.selected_label.setText(f"已选: {count} 张")
        self.export_btn.setEnabled(count > 0)
        self.unfavorite_btn.setEnabled(count > 0)
        self.zoom_btn.setEnabled(count == 1)
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

    def zoom_selected(self):
        if len(self.selected_indices) != 1:
            QMessageBox.information(self, "提示", "请只选中一张截图进行细选。")
            return

        idx = next(iter(self.selected_indices))
        if idx >= len(self._all_items):
            return

        item = self._all_items[idx]
        time_sec = item['time']
        seg_label = item['segment']

        original_fav_item = item.get('original_item')
        if not original_fav_item:
            QMessageBox.warning(self, "警告", "无法获取原始收藏项")
            return

        if not item.get('path') or not os.path.exists(item['path']):
            QMessageBox.warning(self, "警告", "图片文件不存在。")
            return

        seg_idx = -1
        for i, (label, _, _) in enumerate(self.parent_view.controller.get_segments()):
            if label == seg_label:
                seg_idx = i
                break

        if seg_idx == -1:
            QMessageBox.warning(self, "警告", "未找到对应的分段")
            return

        from ui.views.zoom_dialog import ZoomDialog
        dlg = ZoomDialog(
            controller=self.parent_view.controller,
            seg_label=seg_label,
            seg_idx=seg_idx,
            pos=0,
            center_time=time_sec,
            level=1,
            parent=self,
            source="favorites",
            favorites_data=self.favorites,
            original_fav_item=original_fav_item,
        )
        dlg.exec()
        self.load_favorites()

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

            if self.parent_view and self.parent_view.controller.video_id:
                timestamp_ms = int(time_sec * 1000)
                self.parent_view.controller.db.remove_favorite(
                    self.parent_view.controller.video_id,
                    seg_label,
                    timestamp_ms
                )

            if self.parent_view:
                items = self.parent_view.controller.screenshots.get(seg_label, [])
                for item in items:
                    if abs(item['time'] - time_sec) < 0.01:
                        item['favorite'] = False
                        break
            removed += 1

        if self.parent_view:
            self.parent_view.controller.favorites = [
                f for f in self.parent_view.controller.favorites
                if not any(
                    f.get('segment') == seg_label and abs(f.get('time', 0) - time_sec) < 0.01
                    for seg_label, time_sec in to_remove
                )
            ]
            self.parent_view._update_fav_count()
            self.parent_view._update_seg_buttons_state()
            if self.parent_view.controller.video_path:
                self.parent_view._update_video_list_icon(self.parent_view.controller.video_path)
            self.parent_view.controller._save_state_to_db()

        self.selected_indices.clear()
        self.selected_label.setText("已选: 0 张")
        self.export_btn.setEnabled(False)
        self.unfavorite_btn.setEnabled(False)
        self.zoom_btn.setEnabled(False)

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

        if not export_paths:
            QMessageBox.warning(self, "警告", "选中的截图文件不存在。")
            return

        video_name = os.path.splitext(os.path.basename(self.video_path))[0]
        if not video_name:
            video_name = "favorites"
        export_dir = os.path.join(self.export_base, video_name)
        os.makedirs(export_dir, exist_ok=True)
        logger.info(f"[收藏弹窗导出] 导出目录: {export_dir}")

        exported = 0
        skipped = 0

        for time_sec, src_path, seg_label in export_paths:
            is_exported = False
            for item in self.favorites:
                if item.get('segment') == seg_label and abs(item.get('time', 0) - time_sec) < 0.01:
                    if item.get('exported', False):
                        is_exported = True
                        break
            if is_exported:
                skipped += 1
                continue

            dest_name = f"cover_{time_sec:.2f}s.jpg"
            dest_path = os.path.join(export_dir, dest_name)
            try:
                if not os.path.exists(src_path):
                    logger.error(f"[收藏弹窗导出] 源文件不存在: {src_path}")
                    continue
                shutil.copy2(src_path, dest_path)
                if os.path.exists(dest_path):
                    exported += 1
                    for item in self.favorites:
                        if item.get('segment') == seg_label and abs(item.get('time', 0) - time_sec) < 0.01:
                            item['exported'] = True
                            break
                    if self.parent_view and self.parent_view.controller.video_id:
                        timestamp_ms = int(time_sec * 1000)
                        self.parent_view.controller.db.update_favorite_exported(
                            self.parent_view.controller.video_id,
                            seg_label,
                            timestamp_ms
                        )
                    logger.info(f"[收藏弹窗导出] 成功导出: {dest_path}")
                else:
                    logger.error(f"[收藏弹窗导出] 复制后文件不存在: {dest_path}")
            except Exception as e:
                logger.error(f"[收藏弹窗导出] 导出失败 {src_path}: {e}")

        logger.info(f"[收藏弹窗导出] 导出完成: exported={exported}, skipped={skipped}")

        QMessageBox.information(
            self,
            "导出完成",
            f"成功导出 {exported} 张截图到:\n{export_dir}\n\n跳过已导出: {skipped} 张"
        )

        if self.parent_view:
            # 同步到父视图的 controller.favorites 和 controller.screenshots
            for time_sec, _, seg_label in export_paths:
                for fav in self.parent_view.controller.favorites:
                    if (fav.get('video_path') == self.parent_view.controller.video_path and
                        fav.get('segment') == seg_label and
                        abs(fav.get('time', 0) - time_sec) < 0.01):
                        fav['exported'] = True
                        break
                items = self.parent_view.controller.screenshots.get(seg_label, [])
                for item in items:
                    if abs(item['time'] - time_sec) < 0.01:
                        item['exported'] = True
                        break

            # 刷新视图
            self.parent_view._refresh_grid()
            self.parent_view._update_video_list_icon(self.parent_view.controller.video_path)
            # 调用 controller 的 _save_state_to_db
            self.parent_view.controller._save_state_to_db()
            # 强制刷新所有视频列表图标
            self.parent_view._refresh_all_video_icons()

        self.selected_indices.clear()
        self.load_favorites()
        self.update()