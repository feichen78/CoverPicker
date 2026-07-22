# ui/dialogs/favorites_dialog.py
# 所有收藏截图统一缩放到 400x225，QFlowLayout 排列（每行最多5列），滚动查看

import os
import logging
from typing import List, Dict, Optional, Set
from functools import partial

from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, QTimer, QSize, QPoint, QRect
from PySide6.QtGui import QPixmap, QFont, QColor, QAction, QKeyEvent, QResizeEvent, QPainter

from ui.widgets import FavImageLabel
from ui.views.zoom_dialog import ZoomDialog
from ui.views.zoom_preview import ZoomPreviewDialog

logger = logging.getLogger(__name__)


class QFlowLayout(QLayout):
    """简单的流式布局，每行最多5列"""
    def __init__(self, parent=None, margin=4, h_spacing=6, v_spacing=6, max_cols=5):
        super().__init__(parent)
        self._items = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._max_cols = max_cols
        if parent:
            self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        if width <= 0:
            return 100  # 返回一个默认高度，避免初始化时高度为0
        return self._do_layout(QRect(0, 0, max(width, 100), 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margin = self.contentsMargins()
        size += QSize(margin.left() + margin.right(), margin.top() + margin.bottom())
        return size

    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0
        items_in_row = 0
        spacing = self._h_spacing
        margin = self.contentsMargins()
        x += margin.left()
        y += margin.top()
        max_width = rect.width() - margin.left() - margin.right()

        for item in self._items:
            widget = item.widget()
            if widget and not widget.isVisible():
                continue
            item_size = item.sizeHint()
            item_width = item_size.width()
            item_height = item_size.height()

            # 每行最多 _max_cols 列
            next_x = x + item_width + spacing
            if (next_x - spacing > max_width or items_in_row >= self._max_cols) and line_height > 0:
                x = rect.x() + margin.left()
                y = y + line_height + self._v_spacing
                next_x = x + item_width + spacing
                line_height = 0
                items_in_row = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item_size))
            x = next_x
            line_height = max(line_height, item_height)
            items_in_row += 1

        return y + line_height - rect.y()


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
        self.current_favorites = favorites.copy()
        self.export_base = export_base
        self.video_path = video_path
        self.selected_indices: Set[int] = set()
        self.image_labels: List[tuple] = []

        # 固定缩略图尺寸（保持宽高比）
        self.thumb_width = 400
        self.thumb_height = 225

        self.setup_ui()
        self._refresh_favorites()
        self._update_selected_count()
        self._update_button_states()

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

        # 底部操作栏
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

        self.replace_btn = QPushButton("🔄 替换原图")
        self.replace_btn.setStyleSheet("background:#9C27B0;color:white;font-weight:bold;")
        self.replace_btn.clicked.connect(self.replace_selected)
        bottom_bar.addWidget(self.replace_btn)

        bottom_bar.addStretch()

        main_layout.addLayout(bottom_bar)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color:#888;font-size:11px;padding:2px;")
        main_layout.addWidget(self.progress_label)

        self.setFocusPolicy(Qt.StrongFocus)

    def _refresh_favorites(self):
        """使用 QFlowLayout 排列所有收藏截图，每行最多5列"""
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
            return

        # 按分区分组
        groups: Dict[str, List[dict]] = {}
        for fav in self.current_favorites:
            seg = fav.get('segment', 'Unknown')
            if seg not in groups:
                groups[seg] = []
            groups[seg].append(fav)

        sorted_segments = sorted(groups.keys(), key=lambda x: (len(x), x) if x.isalpha() else (99, x))

        for seg_label in sorted_segments:
            items = groups[seg_label]
            if not items:
                continue

            items.sort(key=lambda x: x.get('time', 0))

            # 分区标题
            title_label = QLabel(f"{seg_label}区 ({len(items)} 张)")
            title_label.setFont(QFont("Arial", 11, QFont.Bold))
            title_label.setStyleSheet("color:#FF9800;padding:4px 0 2px 0;")
            self.container_layout.addWidget(title_label)

            # 该分区的截图使用流式布局，每行最多5列
            flow_widget = QWidget()
            flow_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
            flow_layout = QFlowLayout(flow_widget, margin=2, h_spacing=6, v_spacing=6, max_cols=5)

            for idx, fav in enumerate(items):
                path = fav.get('path')
                time_sec = fav.get('time', 0)
                exported = fav.get('exported', False)

                # 加载图片并缩放到统一尺寸（保持宽高比）
                if path and os.path.exists(path):
                    pixmap = QPixmap(path)
                    if pixmap.isNull():
                        pixmap = QPixmap(self.thumb_width, self.thumb_height)
                        pixmap.fill(QColor(60, 60, 60))
                    else:
                        # 缩放，保持宽高比
                        scaled = pixmap.scaled(
                            self.thumb_width,
                            self.thumb_height,
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation
                        )
                        # 创建目标尺寸的画布，居中放置缩放后的图片
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

                # 使用 FavImageLabel（无背景，但已缩放）
                label = FavImageLabel(pixmap, time_sec, idx + 1)
                label.set_favorite(True)
                label.set_exported(exported)  # 正确设置 exported 状态
                label.setFixedSize(self.thumb_width, self.thumb_height)
                if global_idx in self.selected_indices:
                    label.set_selected(True)
                label.clicked.connect(partial(self.on_image_click, global_idx))
                label.double_clicked.connect(partial(self.preview_image, global_idx))

                flow_layout.addWidget(label)
                self.image_labels.append((label, seg_label, idx))

            self.container_layout.addWidget(flow_widget)

        self.container_layout.addStretch()

        self._update_selected_count()
        self._update_button_states()

    def _update_selected_count(self):
        count = len(self.selected_indices)
        self.count_label.setText(f"已选: {count} 张")

    def _update_button_states(self):
        has_selected = len(self.selected_indices) > 0
        self.fav_btn.setEnabled(has_selected)
        self.unfav_btn.setEnabled(has_selected)
        self.export_btn.setEnabled(has_selected)
        self.zoom_btn.setEnabled(len(self.selected_indices) == 1)
        self.replace_btn.setEnabled(len(self.selected_indices) == 1)

        count = len(self.current_favorites)
        if count == 0:
            self.select_all_btn.setEnabled(False)
            self.select_all_btn.setChecked(False)
            return
        self.select_all_btn.setEnabled(True)
        all_selected = len(self.selected_indices) == count
        self.select_all_btn.setChecked(all_selected)

    def on_image_click(self, global_idx: int, idx=None):
        if global_idx in self.selected_indices:
            self.selected_indices.remove(global_idx)
        else:
            self.selected_indices.add(global_idx)
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

        if self.parent_view and hasattr(self.parent_view, 'config'):
            default_dir = self.parent_view.config.get_last_export_dir() or os.path.expanduser("~")
        else:
            default_dir = os.path.expanduser("~")

        export_dir = QFileDialog.getExistingDirectory(
            self,
            "选择导出目录",
            default_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if not export_dir:
            return
        if self.parent_view and hasattr(self.parent_view, 'config'):
            self.parent_view.config.set_last_export_dir(export_dir)

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
        if len(self.selected_indices) != 1:
            QMessageBox.information(self, "提示", "细选只能针对单张截图，请只选中一张截图。")
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
            return

        seg_idx = 0
        if self.controller:
            segments = self.controller.get_segments()
            for i, (s_label, _, _) in enumerate(segments):
                if s_label == seg_label:
                    seg_idx = i
                    break

        items = self.controller.screenshots.get(seg_label, [])
        pos_in_segment = -1
        for i, item in enumerate(items):
            if abs(item.get('time', 0) - fav.get('time', 0)) < 0.01:
                pos_in_segment = i
                break

        if pos_in_segment == -1:
            QMessageBox.warning(self, "警告", "未找到对应的截图位置。")
            return

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

    def replace_selected(self):
        if len(self.selected_indices) != 1:
            QMessageBox.information(self, "提示", "替换只能针对单张截图，请只选中一张截图。")
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
            return

        old_time = fav.get('time', 0)

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择替换图片",
            os.path.expanduser("~"),
            "图片文件 (*.jpg *.jpeg *.png *.bmp)"
        )
        if not file_path:
            return

        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            QMessageBox.warning(self, "警告", "无法加载图片文件。")
            return

        new_time = old_time + 0.01
        import shutil
        temp_path = os.path.join(self.controller.temp_dir, f"fav_replace_{new_time:.2f}.jpg")
        try:
            shutil.copy2(file_path, temp_path)
        except Exception as e:
            QMessageBox.warning(self, "警告", f"复制图片失败: {e}")
            return

        if self.controller.replace_favorite_screenshot(seg_label, old_time, new_time, temp_path):
            QMessageBox.information(self, "完成", "收藏截图替换成功！")
            self.current_favorites = self.controller.get_current_favorites()
            self._refresh_favorites()
        else:
            QMessageBox.warning(self, "错误", "替换失败，请重试。")

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

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        QTimer.singleShot(50, self._refresh_favorites)

    def closeEvent(self, event):
        event.accept()