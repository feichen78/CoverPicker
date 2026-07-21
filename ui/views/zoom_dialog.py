# ui/views/zoom_dialog.py
# 修复：单击选中、双击预览信号参数不匹配问题

import os, asyncio, shutil, random
from typing import List, Tuple, Optional
from functools import partial
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QFont, QColor
from src.controllers.segment_controller import SegmentController
from src.video_scanner import extract_frame
from ui.widgets import ClickableLabel
from ui.views.zoom_preview import ZoomPreviewDialog


class ZoomDialog(QDialog):
    def __init__(self, controller: SegmentController, seg_label: str, seg_idx: int, pos: int, center_time: float, level: int, parent=None, source: str = "main", original_fav_item: Optional[dict] = None, original_fav_time: Optional[float] = None):
        super().__init__(parent)
        self.controller = controller
        self.seg_label = seg_label
        self.seg_idx = seg_idx
        self.pos = pos
        self.center_time = center_time
        self.level = level
        self.source = source
        self.original_fav_item = original_fav_item
        self.original_fav_time = original_fav_time
        self.candidate_frames: List[dict] = []
        self.selected_indices: set = set()
        self.image_labels: List[ClickableLabel] = []
        self._loading = False

        self.setWindowTitle(f"Zoom 精修 L{self.level} - 帧筛选")
        self.setMinimumSize(800, 600)
        self.resize(900, 700)

        self.setup_ui()
        self.load_candidates()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        title_layout = QHBoxLayout()
        title = QLabel(f"🔍 精修 L{self.level}  (中心时间: {self._format_time(self.center_time)})")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        title_layout.addWidget(title)
        title_layout.addStretch()

        level_label = QLabel(f"层级: {self.level}/4")
        level_label.setStyleSheet("color:#888;font-size:12px;")
        title_layout.addWidget(level_label)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet("QPushButton{border:none;font-size:16px;border-radius:4px;}QPushButton:hover{background:#e74c3c;color:white;}")
        close_btn.clicked.connect(self.reject)
        title_layout.addWidget(close_btn)

        main_layout.addLayout(title_layout)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(6)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)
        self.grid_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scroll.setWidget(self.grid_widget)
        main_layout.addWidget(self.scroll, 1)

        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        self.selected_label = QLabel("已选: 0 张")
        bottom_bar.addWidget(self.selected_label)

        self.select_all_btn = QPushButton("☑ 全选")
        self.select_all_btn.setCheckable(True)
        self.select_all_btn.clicked.connect(self.toggle_select_all)
        bottom_bar.addWidget(self.select_all_btn)

        bottom_bar.addStretch()

        self.fav_btn = QPushButton("⭐ 收藏")
        self.fav_btn.setStyleSheet("background:#FF9800;color:white;font-weight:bold;")
        self.fav_btn.clicked.connect(self.favorite_selected)
        bottom_bar.addWidget(self.fav_btn)

        self.export_btn = QPushButton("📥 导出")
        self.export_btn.setStyleSheet("background:#2196F3;color:white;font-weight:bold;")
        self.export_btn.clicked.connect(self.export_selected)
        bottom_bar.addWidget(self.export_btn)

        self.replace_btn = QPushButton("🔄 替换原图")
        self.replace_btn.setStyleSheet("background:#9C27B0;color:white;font-weight:bold;")
        self.replace_btn.clicked.connect(self.replace_selected)
        bottom_bar.addWidget(self.replace_btn)

        if self.level < 4:
            self.next_level_btn = QPushButton("⬇ 细选下一层")
            self.next_level_btn.setStyleSheet("background:#4CAF50;color:white;font-weight:bold;")
            self.next_level_btn.clicked.connect(self.go_to_next_level)
            bottom_bar.addWidget(self.next_level_btn)

        main_layout.addLayout(bottom_bar)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color:#888;font-size:11px;padding:4px;")
        main_layout.addWidget(self.progress_label)

        self._update_buttons()
        self._update_select_all_state()

    def _format_time(self, seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def load_candidates(self):
        if self._loading:
            return
        self._loading = True
        self.progress_label.setText("正在生成候选帧...")
        self.setEnabled(False)
        asyncio.create_task(self._load_candidates_async())

    async def _load_candidates_async(self):
        try:
            ranges = {1: 4.0, 2: 2.0, 3: 1.0, 4: 0.5}
            half_range = ranges.get(self.level, 4.0)
            start = max(0, self.center_time - half_range)
            end = min(self.controller.duration, self.center_time + half_range)
            times = [random.uniform(start, end) for _ in range(9)]
            times.sort()

            self.candidate_frames = []
            total = len(times)
            video_path = self.controller.video_path

            for idx, t in enumerate(times):
                self.progress_label.setText(f"提取帧 {idx+1}/{total} @ {t:.2f}s")
                temp_path = os.path.join(self.controller.temp_dir, f"zoom_L{self.level}_{idx}_{t:.2f}.jpg")
                success = await asyncio.to_thread(extract_frame, video_path, t, temp_path)
                if success:
                    self.candidate_frames.append({'time': t, 'path': temp_path, 'favorite': False, 'exported': False})
                else:
                    self.candidate_frames.append({'time': t, 'path': None, 'favorite': False, 'exported': False})

            self._refresh_grid()
            self.progress_label.setText(f"L{self.level} 候选帧加载完成 ({len(self.candidate_frames)} 张)")
        except Exception as e:
            self.progress_label.setText(f"加载失败: {e}")
        finally:
            self._loading = False
            self.setEnabled(True)

    def _refresh_grid(self):
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.image_labels.clear()

        count = len(self.candidate_frames)
        if count == 0:
            self._update_select_all_state()
            return

        cols = 3
        for col in range(cols):
            self.grid_layout.setColumnStretch(col, 1)

        for pos, item in enumerate(self.candidate_frames):
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
            label.setObjectName(f"zoom_{pos}")
            label.set_favorite(item.get('favorite', False))
            label.set_exported(item.get('exported', False))

            if pos in self.selected_indices:
                label.set_selected(True)

            # 修复：使用 partial 绑定，函数签名接受额外参数
            label.clicked.connect(partial(self.on_label_click, pos))
            label.double_clicked.connect(partial(self._preview_single, pos))

            self.grid_layout.addWidget(label, row, col)
            self.image_labels.append(label)

        self._update_selected_count()
        self._update_buttons()
        self._update_select_all_state()

    # 修复：增加 idx=None 参数以接收信号传递的额外参数
    def _preview_single(self, pos: int, idx=None):
        if pos >= len(self.candidate_frames):
            return
        item = self.candidate_frames[pos]
        if not item.get('path') or not os.path.exists(item['path']):
            QMessageBox.warning(self, "警告", "图片文件不存在。")
            return
        pixmap = QPixmap(item['path'])
        if pixmap.isNull():
            return
        dlg = ZoomPreviewDialog(pixmap, item['time'], self)
        dlg.exec()

    # 修复：增加 idx=None 参数以接收信号传递的额外参数
    def on_label_click(self, pos: int, idx=None):
        if pos in self.selected_indices:
            self.selected_indices.remove(pos)
        else:
            self.selected_indices.add(pos)
        self._refresh_grid()

    def _update_selected_count(self):
        self.selected_label.setText(f"已选: {len(self.selected_indices)} 张")

    def _update_buttons(self):
        has_selected = len(self.selected_indices) > 0
        self.select_all_btn.setEnabled(len(self.candidate_frames) > 0)
        self.fav_btn.setEnabled(has_selected)
        self.export_btn.setEnabled(has_selected)
        self.replace_btn.setEnabled(len(self.selected_indices) == 1)

    def _update_select_all_state(self):
        count = len(self.candidate_frames)
        if count == 0:
            self.select_all_btn.setEnabled(False)
            self.select_all_btn.setChecked(False)
            return
        self.select_all_btn.setEnabled(True)
        all_selected = len(self.selected_indices) == count
        self.select_all_btn.setChecked(all_selected)

    def toggle_select_all(self):
        count = len(self.candidate_frames)
        if count == 0:
            return
        if self.select_all_btn.isChecked():
            self.selected_indices = set(range(count))
        else:
            self.selected_indices.clear()
        self._refresh_grid()

    def favorite_selected(self):
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选中要收藏的截图。")
            return
        selected_positions = list(self.selected_indices)
        added = 0
        for pos in selected_positions:
            item = self.candidate_frames[pos]
            if not item.get('path') or not os.path.exists(item['path']):
                continue
            if item.get('favorite', False):
                continue
            video_id = self.controller.video_id
            timestamp_ms = int(item['time'] * 1000)
            if not self.controller.db.is_favorite(video_id, self.seg_label, timestamp_ms):
                self.controller.db.add_favorite(video_id, self.seg_label, timestamp_ms, item['path'], is_exported=False)
                self.controller.favorites.append({
                    'video_path': self.controller.video_path,
                    'segment': self.seg_label,
                    'time': item['time'],
                    'path': item['path'],
                    'exported': False
                })
                item['favorite'] = True
                added += 1
        if added > 0:
            self.controller._save_state_to_db()
            self.controller._notify_data_changed()
            self._refresh_grid()
            QMessageBox.information(self, "完成", f"成功收藏 {added} 张截图。")
        else:
            QMessageBox.information(self, "提示", "选中的截图已经收藏过了。")

    def export_selected(self):
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选中要导出的截图。")
            return
        selected_positions = list(self.selected_indices)
        exported = 0
        video_name = os.path.splitext(os.path.basename(self.controller.video_path))[0]
        export_dir = os.path.join(self.controller.export_base, video_name)
        os.makedirs(export_dir, exist_ok=True)

        for pos in selected_positions:
            item = self.candidate_frames[pos]
            if not item.get('path') or not os.path.exists(item['path']):
                continue
            time_sec = item['time']
            dest_name = f"cover_{time_sec:.2f}s.jpg"
            dest_path = os.path.join(export_dir, dest_name)
            try:
                shutil.copy2(item['path'], dest_path)
                item['exported'] = True
                exported += 1
                if self.controller.video_id:
                    timestamp_ms = int(time_sec * 1000)
                    self.controller.db.update_favorite_exported(self.controller.video_id, self.seg_label, timestamp_ms)
                    for fav in self.controller.favorites:
                        if (fav.get('video_path') == self.controller.video_path and
                            fav.get('segment') == self.seg_label and
                            abs(fav.get('time', 0) - time_sec) < 0.01):
                            fav['exported'] = True
                            break
            except Exception:
                continue

        if exported > 0:
            self.controller._save_state_to_db()
            self.controller._notify_data_changed()
            self._refresh_grid()
            QMessageBox.information(self, "导出完成", f"成功导出 {exported} 张截图到:\n{export_dir}")
        else:
            QMessageBox.warning(self, "警告", "导出失败，请检查文件是否存在。")

    def replace_selected(self):
        if len(self.selected_indices) != 1:
            QMessageBox.information(self, "提示", "请只选中一张截图进行替换。")
            return

        pos = next(iter(self.selected_indices))
        item = self.candidate_frames[pos]
        if not item.get('path') or not os.path.exists(item['path']):
            QMessageBox.warning(self, "警告", "图片文件不存在。")
            return

        if self.source == "favorites":
            old_time = self.original_fav_time if self.original_fav_time is not None else self.center_time
            reply = QMessageBox.question(
                self,
                "确认替换",
                f"确定要用当前选中的帧替换收藏中的原图吗？\n原时间: {self._format_time(old_time)} → 新时间: {self._format_time(item['time'])}",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
            success = self.controller.replace_favorite_screenshot(self.seg_label, old_time, item['time'], item['path'])
            if success:
                QMessageBox.information(self, "完成", "收藏截图替换成功！")
                self.accept()
            else:
                QMessageBox.warning(self, "错误", "替换失败，请重试。")
        else:
            reply = QMessageBox.question(
                self,
                "确认替换",
                f"确定要用当前选中的帧替换主网格中的原图吗？\n原时间: {self._format_time(self.center_time)} → 新时间: {self._format_time(item['time'])}",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
            success = self.controller.replace_screenshot(self.seg_label, self.pos, item['time'], item['path'], self.center_time)
            if success:
                self.controller._save_state_to_db()
                self.controller._notify_data_changed()
                QMessageBox.information(self, "完成", "替换成功！")
                self.accept()
            else:
                QMessageBox.warning(self, "错误", "替换失败，请重试。")

    def go_to_next_level(self):
        if len(self.selected_indices) != 1:
            QMessageBox.information(self, "提示", "请选中一张截图进入下一层细选。")
            return
        pos = next(iter(self.selected_indices))
        item = self.candidate_frames[pos]
        if not item.get('path') or not os.path.exists(item['path']):
            QMessageBox.warning(self, "警告", "图片文件不存在。")
            return
        self.accept()
        next_level = self.level + 1
        fav_time = self.original_fav_time if self.source == "favorites" else None
        dlg = ZoomDialog(
            controller=self.controller,
            seg_label=self.seg_label,
            seg_idx=self.seg_idx,
            pos=self.pos,
            center_time=item['time'],
            level=next_level,
            parent=self.parent(),
            source=self.source,
            original_fav_item=self.original_fav_item,
            original_fav_time=fav_time
        )
        dlg.exec()