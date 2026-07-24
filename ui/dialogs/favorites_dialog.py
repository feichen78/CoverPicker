# ui/dialogs/favorites_dialog.py
# 完整文件，可直接覆盖
# 修复：多选时 zoom_btn 不禁用，让 zoom_selected 负责提示
# 修复：取消收藏时直接删除NAS文件（兜底逻辑）

import os
import logging
from typing import List, Dict, Optional, Set, Tuple
from functools import partial

from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, QTimer, QSize, QPoint, QRect
from PySide6.QtGui import QPixmap, QFont, QColor, QKeyEvent, QResizeEvent, QPainter

from ui.widgets import FavImageLabel
from ui.views.zoom_dialog import ZoomDialog
from ui.views.zoom_preview import ZoomPreviewDialog

logger = logging.getLogger(__name__)


class FavoritesDialog(QDialog):
    def __init__(self, favorites: List[dict], video_name: str, export_base: str, video_path: str, parent=None):
        super().__init__(parent)
        self.video_name = video_name
        self.setWindowTitle(f"⭐ 收藏 - {video_name} ({len(favorites)} 张)")

        self.setMinimumSize(700, 500)
        self.resize(900, 650)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)

        self.parent_view = parent
        self.controller = parent.controller if parent else None
        self.video_path = video_path
        self.export_base = export_base

        # 修复旧数据错误绿点
        self._fix_old_exported(favorites)

        self.current_favorites = favorites.copy()
        self.selected_indices: Set[int] = set()
        self.image_labels: List[tuple] = []  # 每个元素为 (label, seg_label, idx_in_segment)

        # 动态缩略图尺寸
        self.thumb_width = 400
        self.thumb_height = 225

        # 防抖定时器
        self._refresh_timer = QTimer()
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._refresh_favorites)

        self.setup_ui()
        self._first_show = True

        print("[DEBUG] FavoritesDialog __init__: 修复后数据:")
        for i, fav in enumerate(self.current_favorites):
            print(f"  fav[{i}]: seg={fav.get('segment')}, exported={fav.get('exported')}")

    def _fix_old_exported(self, favorites: List[dict]):
        """修复旧收藏的错误绿点：将所有 exported=True 的记录重置为 False"""
        if not self.controller or not self.controller.video_id:
            return

        fixed_count = 0
        for fav in favorites:
            if fav.get('exported', False):
                seg = fav.get('segment')
                time_sec = fav.get('time', 0)
                timestamp_ms = int(time_sec * 1000)
                try:
                    conn = self.controller.db._conn
                    conn.execute(
                        "UPDATE favorites SET is_exported = 0 WHERE video_id = ? AND segment_label = ? AND timestamp_ms = ?",
                        (self.controller.video_id, seg, timestamp_ms)
                    )
                    conn.commit()
                    fav['exported'] = False
                    for cfav in self.controller.favorites:
                        if (cfav.get('segment') == seg and
                            abs(cfav.get('time', 0) - time_sec) < 0.01):
                            cfav['exported'] = False
                            break
                    fixed_count += 1
                except Exception as e:
                    logger.error(f"修复绿点失败: {e}")
                    print(f"[ERROR] 修复绿点失败: {e}")

        if fixed_count > 0:
            self.controller._save_state_to_db()
            print(f"[DEBUG] 修复了 {fixed_count} 个旧收藏的绿点标记")
        else:
            print("[DEBUG] 无需修复旧绿点")

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # 标题行
        title_layout = QHBoxLayout()
        self.title_label = QLabel(f"⭐ 收藏截图 ({len(self.current_favorites)} 张)")
        self.title_label.setFont(QFont("Arial", 12, QFont.Bold))
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()

        self.count_label = QLabel("已选: 0 张")
        self.count_label.setFont(QFont("Arial", 10))
        title_layout.addWidget(self.count_label)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet("QPushButton{border:none;font-size:16px;border-radius:4px;}QPushButton:hover{background:#e74c3c;color:white;}")
        close_btn.clicked.connect(self.reject)
        title_layout.addWidget(close_btn)
        main_layout.addLayout(title_layout)

        # 滚动区域
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.container_widget = QWidget()
        self.container_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.container_layout = QVBoxLayout(self.container_widget)
        self.container_layout.setSpacing(8)
        self.container_layout.setContentsMargins(4, 4, 4, 4)

        self.scroll.setWidget(self.container_widget)
        main_layout.addWidget(self.scroll, 1)

        # 底部操作栏（移除替换原图按钮）
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(6)
        bottom_bar.addStretch()

        self.select_all_btn = QPushButton("☑ 全选")
        self.select_all_btn.setCheckable(True)
        self.select_all_btn.clicked.connect(self.toggle_select_all)
        bottom_bar.addWidget(self.select_all_btn)

        self.fav_btn = QPushButton("⭐ 收藏")
        self.fav_btn.setStyleSheet("background:#FF9800;color:white;font-weight:bold;")
        self.fav_btn.clicked.connect(self.favorite_selected)
        bottom_bar.addWidget(self.fav_btn)

        self.unfav_btn = QPushButton("☆ 取消收藏")
        self.unfav_btn.setStyleSheet("background:#e74c3c;color:white;font-weight:bold;")
        self.unfav_btn.clicked.connect(self.unfavorite_selected)
        bottom_bar.addWidget(self.unfav_btn)

        self.export_btn = QPushButton("📥 导出")
        self.export_btn.setStyleSheet("background:#2196F3;color:white;font-weight:bold;")
        self.export_btn.clicked.connect(self.export_selected)
        bottom_bar.addWidget(self.export_btn)

        self.zoom_btn = QPushButton("🔍 细选")
        self.zoom_btn.setStyleSheet("background:#4CAF50;color:white;font-weight:bold;")
        self.zoom_btn.clicked.connect(self.zoom_selected)
        bottom_bar.addWidget(self.zoom_btn)

        bottom_bar.addStretch()
        main_layout.addLayout(bottom_bar)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color:#888;font-size:11px;padding:2px;")
        main_layout.addWidget(self.progress_label)

        self.setFocusPolicy(Qt.StrongFocus)

    def showEvent(self, event):
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            QTimer.singleShot(50, self._refresh_favorites)
        else:
            self._refresh_timer.start(50)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._refresh_timer.start(200)

    def _refresh_favorites(self):
        """重新构建收藏布局，使用 QGridLayout，强制左对齐，小间距，保留选中状态"""
        print("[DEBUG] _refresh_favorites called")

        # 保存当前选中项的标识 (seg_label, time)
        selected_ids: Set[Tuple[str, float]] = set()
        for idx in self.selected_indices:
            if idx < len(self.image_labels):
                label, seg_label, _ = self.image_labels[idx]
                selected_ids.add((seg_label, label.timestamp))

        # 清空旧内容
        while self.container_layout.count():
            child = self.container_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.image_labels.clear()
        self.selected_indices.clear()

        count = len(self.current_favorites)
        self.setWindowTitle(f"⭐ 收藏 - {self.video_name} ({count} 张)")
        self.title_label.setText(f"⭐ 收藏截图 ({count} 张)")

        if count == 0:
            empty_label = QLabel("暂无收藏截图")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color:#888;font-size:14px;padding:40px;")
            self.container_layout.addWidget(empty_label)
            self._update_selected_count()
            self._update_button_states()
            self.container_widget.setFixedHeight(100)
            return

        groups: Dict[str, List[dict]] = {}
        for fav in self.current_favorites:
            seg = fav.get('segment', 'Unknown')
            if seg not in groups:
                groups[seg] = []
            groups[seg].append(fav)

        sorted_segments = sorted(groups.keys(), key=lambda x: (len(x), x) if x.isalpha() else (99, x))

        max_count = max(len(items) for items in groups.values())
        cols = max(1, min(5, max_count))
        print(f"[DEBUG] max_count={max_count}, cols={cols}")

        viewport_width = self.scroll.viewport().width()
        avail_width = viewport_width - 20
        if avail_width <= 0:
            avail_width = self.width() - 40
        if avail_width <= 0:
            avail_width = 800
        print(f"[DEBUG] avail_width={avail_width}")

        spacing_h = 2
        width_by_cols = (avail_width - (cols - 1) * spacing_h) / cols
        width_by_5cols = (avail_width - 4 * spacing_h) / 5
        self.thumb_width = int(max(width_by_cols, width_by_5cols))
        self.thumb_width = max(80, min(self.thumb_width, 600))
        self.thumb_height = int(self.thumb_width * 225 / 400)
        print(f"[DEBUG] thumb_size={self.thumb_width}x{self.thumb_height}")

        total_height = 0
        new_selected_indices: Set[int] = set()

        for seg_label in sorted_segments:
            items = groups[seg_label]
            if not items:
                continue
            items.sort(key=lambda x: x.get('time', 0))

            title_label = QLabel(f"{seg_label}区 ({len(items)} 张)")
            title_label.setFont(QFont("Arial", 11, QFont.Bold))
            title_label.setStyleSheet("color:#FF9800;padding:4px 0 2px 0;")
            self.container_layout.addWidget(title_label)
            total_height += title_label.sizeHint().height() + 8

            grid_widget = QWidget()
            grid_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
            grid_layout = QGridLayout(grid_widget)
            grid_layout.setSpacing(spacing_h)
            grid_layout.setContentsMargins(2, 2, 2, 2)
            grid_layout.setAlignment(Qt.AlignLeft)
            for c in range(cols):
                grid_layout.setColumnStretch(c, 0)

            row = 0
            col = 0
            for idx, fav in enumerate(items):
                path = fav.get('path')
                time_sec = fav.get('time', 0)
                exported = fav.get('exported', False)
                exported_bool = bool(exported)
                print(f"[DEBUG] fav idx={idx}, seg={seg_label}, exported_raw={exported}, exported_bool={exported_bool}")

                if path and os.path.exists(path):
                    pixmap = QPixmap(path)
                    if pixmap.isNull():
                        pixmap = QPixmap(self.thumb_width, self.thumb_height)
                        pixmap.fill(QColor(60, 60, 60))
                    else:
                        scaled = pixmap.scaled(
                            self.thumb_width,
                            self.thumb_height,
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation
                        )
                        canvas = QPixmap(self.thumb_width, self.thumb_height)
                        canvas.fill(QColor(30, 30, 30))
                        painter = QPainter(canvas)
                        x = (self.thumb_width - scaled.width()) // 2
                        y = (self.thumb_height - scaled.height()) // 2
                        painter.drawPixmap(x, y, scaled)
                        painter.end()
                        pixmap = canvas
                else:
                    pixmap = QPixmap(self.thumb_width, self.thumb_height)
                    pixmap.fill(QColor(60, 60, 60))

                global_idx = len(self.image_labels)
                label = FavImageLabel(pixmap, time_sec, idx + 1)
                label.set_favorite(True)
                label.set_exported(exported_bool)
                label.setFixedSize(self.thumb_width, self.thumb_height)
                if (seg_label, time_sec) in selected_ids:
                    label.set_selected(True)
                    new_selected_indices.add(global_idx)
                label.clicked.connect(partial(self.on_image_click, global_idx))
                label.double_clicked.connect(partial(self.preview_image, global_idx))

                grid_layout.addWidget(label, row, col)
                grid_layout.setAlignment(label, Qt.AlignLeft | Qt.AlignTop)
                self.image_labels.append((label, seg_label, idx))

                col += 1
                if col >= cols:
                    col = 0
                    row += 1

            self.container_layout.addWidget(grid_widget)
            rows = (len(items) + cols - 1) // cols
            grid_height = rows * (self.thumb_height + spacing_h) + 4
            total_height += grid_height + 6

        self.selected_indices = new_selected_indices
        print(f"[DEBUG] Restored selected_indices: {self.selected_indices}")

        self.container_layout.addStretch()
        self._update_selected_count()
        self._update_button_states()

        final_height = max(total_height + 50, 200)
        self.container_widget.setFixedHeight(final_height)
        self.container_widget.updateGeometry()
        self.scroll.update()
        self.scroll.viewport().update()
        print(f"[DEBUG] _refresh_favorites finished, fixed height={final_height}")

    def _update_selected_count(self):
        count = len(self.selected_indices)
        self.count_label.setText(f"已选: {count} 张")

    def _update_button_states(self):
        has_selected = len(self.selected_indices) > 0
        self.fav_btn.setEnabled(has_selected)
        self.unfav_btn.setEnabled(has_selected)
        self.export_btn.setEnabled(has_selected)
        self.zoom_btn.setEnabled(True)

        count = len(self.current_favorites)
        if count == 0:
            self.select_all_btn.setEnabled(False)
            self.select_all_btn.setChecked(False)
            return
        self.select_all_btn.setEnabled(True)
        all_selected = len(self.selected_indices) == count
        self.select_all_btn.setChecked(all_selected)

    def on_image_click(self, global_idx: int, idx=None):
        print(f"[DEBUG] on_image_click: before toggle, selected_indices={self.selected_indices}")
        if global_idx in self.selected_indices:
            self.selected_indices.remove(global_idx)
        else:
            self.selected_indices.add(global_idx)
        print(f"[DEBUG] on_image_click: after toggle, selected_indices={self.selected_indices}")
        for i, (label, seg_label, item_idx) in enumerate(self.image_labels):
            label.set_selected(i in self.selected_indices)
        self._update_selected_count()
        self._update_button_states()

    def preview_image(self, global_idx: int, idx=None):
        if global_idx >= len(self.image_labels):
            return
        label, seg_label, item_idx = self.image_labels[global_idx]
        fav = None
        for f in self.current_favorites:
            if f.get('segment') == seg_label and abs(f.get('time', 0) - label.timestamp) < 0.01:
                fav = f
                break
        if not fav:
            return
        path = fav.get('path')
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "警告", "图片文件不存在。")
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return
        dlg = ZoomPreviewDialog(pixmap, fav.get('time', 0), self)
        dlg.exec()

    def toggle_select_all(self):
        count = len(self.current_favorites)
        if count == 0:
            return
        if self.select_all_btn.isChecked():
            self.selected_indices = set(range(len(self.image_labels)))
        else:
            self.selected_indices.clear()
        print(f"[DEBUG] toggle_select_all: selected_indices={self.selected_indices}")
        for i, (label, seg_label, item_idx) in enumerate(self.image_labels):
            label.set_selected(i in self.selected_indices)
        self._update_selected_count()
        self._update_button_states()

    def favorite_selected(self):
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选中要收藏的截图。")
            return

        selected_items = []
        for global_idx in self.selected_indices:
            if global_idx < len(self.image_labels):
                label, seg_label, item_idx = self.image_labels[global_idx]
                for fav in self.current_favorites:
                    if fav.get('segment') == seg_label and abs(fav.get('time', 0) - label.timestamp) < 0.01:
                        selected_items.append(fav)
                        break

        added = 0
        for fav in selected_items:
            seg_label = fav.get('segment')
            timestamp_ms = int(fav.get('time', 0) * 1000)
            if self.controller:
                if self.controller.db.is_favorite(self.controller.video_id, seg_label, timestamp_ms):
                    continue
                self.controller.db.add_favorite(
                    self.controller.video_id,
                    seg_label,
                    timestamp_ms,
                    fav.get('path', ''),
                    os.path.basename(fav.get('path', '')),
                    fav.get('exported', False)
                )
                self.controller.favorites.append({
                    'video_path': self.controller.video_path,
                    'segment': seg_label,
                    'time': fav.get('time', 0),
                    'path': fav.get('path', ''),
                    'exported': fav.get('exported', False)
                })
                items = self.controller.screenshots.get(seg_label, [])
                for item in items:
                    if abs(item.get('time', 0) - fav.get('time', 0)) < 0.01:
                        item['favorite'] = True
                        break
                added += 1

        if added > 0:
            self.controller._save_state_to_db()
            self.controller._notify_data_changed()
            QMessageBox.information(self, "完成", f"成功收藏 {added} 张截图。")
            self.current_favorites = self.controller.get_current_favorites()
            self._refresh_favorites()
        else:
            QMessageBox.information(self, "提示", "选中的截图已经收藏过了。")

    def unfavorite_selected(self):
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选中要取消收藏的截图。")
            return

        reply = QMessageBox.question(
            self,
            "确认取消收藏",
            f"确定要取消收藏选中的 {len(self.selected_indices)} 张截图吗？\n对应的图片文件将从NAS中删除。",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        selected_favs = []
        for global_idx in self.selected_indices:
            if global_idx < len(self.image_labels):
                label, seg_label, item_idx = self.image_labels[global_idx]
                for fav in self.current_favorites:
                    if fav.get('segment') == seg_label and abs(fav.get('time', 0) - label.timestamp) < 0.01:
                        selected_favs.append(fav)
                        break

        removed_count = 0
        for fav in selected_favs:
            # ===== 修复：直接删除文件（兜底逻辑）=====
            path = fav.get('path')
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    logger.info(f"取消收藏: 已删除文件 {path}")
                except Exception as e:
                    logger.error(f"取消收藏: 删除文件失败 {path}: {e}")
            # ===== 修复结束 =====

            seg_label = fav.get('segment')
            timestamp_ms = int(fav.get('time', 0) * 1000)
            if self.controller.unfavorite_by_time(seg_label, timestamp_ms):
                removed_count += 1
                if fav in self.current_favorites:
                    self.current_favorites.remove(fav)

        self.selected_indices.clear()
        self._refresh_favorites()
        self._update_selected_count()
        self._update_button_states()

        if removed_count > 0:
            QMessageBox.information(self, "完成", f"成功取消收藏 {removed_count} 张截图。")
        else:
            QMessageBox.warning(self, "警告", "取消收藏失败，请重试。")

    def export_selected(self):
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选中要导出的截图。")
            return

        default_dir = os.path.expanduser("~")
        if self.parent_view and hasattr(self.parent_view, 'config'):
            config = self.parent_view.config
            last_image_dir = config.get('last_image_export_dir', None)
            if last_image_dir and os.path.exists(last_image_dir):
                default_dir = last_image_dir
            else:
                last_export = config.get_last_export_dir()
                if last_export and os.path.exists(last_export):
                    default_dir = last_export

        export_dir = QFileDialog.getExistingDirectory(
            self,
            "选择导出目录",
            default_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if not export_dir:
            return

        if self.parent_view and hasattr(self.parent_view, 'config'):
            self.parent_view.config.set('last_image_export_dir', export_dir)

        selected_favs = []
        for global_idx in self.selected_indices:
            if global_idx < len(self.image_labels):
                label, seg_label, item_idx = self.image_labels[global_idx]
                for fav in self.current_favorites:
                    if fav.get('segment') == seg_label and abs(fav.get('time', 0) - label.timestamp) < 0.01:
                        selected_favs.append(fav)
                        break

        exported = 0
        video_name = os.path.splitext(os.path.basename(self.video_path))[0]
        export_dir = os.path.join(export_dir, video_name)
        os.makedirs(export_dir, exist_ok=True)

        for fav in selected_favs:
            src_path = fav.get('path')
            if not src_path or not os.path.exists(src_path):
                continue
            time_sec = fav.get('time', 0)
            dest_name = f"cover_{time_sec:.2f}s.jpg"
            dest_path = os.path.join(export_dir, dest_name)
            try:
                import shutil
                shutil.copy2(src_path, dest_path)
                exported += 1
                seg_label = fav.get('segment')
                timestamp_ms = int(time_sec * 1000)
                if self.controller:
                    self.controller.db.update_favorite_exported(
                        self.controller.video_id,
                        seg_label,
                        timestamp_ms
                    )
                    fav['exported'] = True
            except Exception as e:
                logger.error(f"导出失败: {e}")

        if exported > 0:
            if self.controller:
                self.controller._save_state_to_db()
                self.controller._notify_data_changed()
            self._refresh_favorites()
            QMessageBox.information(self, "导出完成", f"成功导出 {exported} 张截图到:\n{export_dir}")
        else:
            QMessageBox.warning(self, "警告", "导出失败，请检查文件是否存在。")

    def zoom_selected(self):
        print(f"[DEBUG] zoom_selected called, selected_indices={self.selected_indices}, len={len(self.selected_indices)}")
        if len(self.selected_indices) != 1:
            QMessageBox.warning(self, "提示", "细选只能针对单张截图，请只选中一张截图。")
            return

        global_idx = next(iter(self.selected_indices))
        if global_idx >= len(self.image_labels):
            return

        label, seg_label, item_idx = self.image_labels[global_idx]
        fav = None
        for f in self.current_favorites:
            if f.get('segment') == seg_label and abs(f.get('time', 0) - label.timestamp) < 0.01:
                fav = f
                break
        if not fav:
            QMessageBox.warning(self, "警告", "未找到对应的收藏数据。")
            return

        seg_idx = 0
        pos_in_segment = 0
        if self.controller:
            segments = self.controller.get_segments()
            for i, (s_label, _, _) in enumerate(segments):
                if s_label == seg_label:
                    seg_idx = i
                    break
            items = self.controller.screenshots.get(seg_label, [])
            found = False
            for i, item in enumerate(items):
                if abs(item.get('time', 0) - fav.get('time', 0)) < 0.01:
                    pos_in_segment = i
                    found = True
                    break
            if not found:
                pos_in_segment = 0

        dlg = ZoomDialog(
            controller=self.controller,
            seg_label=seg_label,
            seg_idx=seg_idx,
            pos=pos_in_segment,
            center_time=fav.get('time', 0),
            level=1,
            parent=self,
            source="favorites",
            original_fav_item=fav,
            original_fav_time=fav.get('time', 0)
        )
        dlg.exec()
        if self.controller:
            self.current_favorites = self.controller.get_current_favorites()
        self._refresh_favorites()

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key_A and event.modifiers() == Qt.ControlModifier:
            self.select_all_btn.setChecked(not self.select_all_btn.isChecked())
            self.toggle_select_all()
            return
        if key == Qt.Key_Delete:
            self.unfavorite_selected()
            return
        if key == Qt.Key_Escape:
            self.reject()
        super().keyPressEvent(event)

    def closeEvent(self, event):
        event.accept()