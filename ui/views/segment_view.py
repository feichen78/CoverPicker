import os
import asyncio
import math
import tempfile
import shutil
import random
import logging
from typing import Dict, List, Set, Tuple
from functools import partial
from datetime import timedelta
import traceback

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGridLayout, QScrollArea, QFrame, QMessageBox, QApplication,
    QSplitter, QListWidget, QListWidgetItem, QSizePolicy, QDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QFont, QColor, QPainter, QPen, QBrush, QKeyEvent

from src.video_scanner import scan_videos, get_video_duration, calculate_segments, extract_frame
from ui.views.zoom_preview import ZoomPreviewDialog
from ui.views.exclude_dialog import ExcludeRangeDialog

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ClickableLabel(QLabel):
    clicked = Signal()
    double_clicked = Signal()

    def __init__(self, pixmap: QPixmap, time_sec: float, parent=None):
        super().__init__(parent)
        self.time_sec = time_sec
        self.is_selected = False
        self.is_locked = False
        self.is_favorite = False
        self.is_exported = False
        self.original_pixmap = pixmap.copy() if not pixmap.isNull() else QPixmap(300, 185)
        self.setFixedSize(300, 185)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("border: none; background: transparent;")
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
            logger.error(f"update_pixmap error: {e}")

    def resizeEvent(self, event):
        self.update_pixmap()
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)

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

            # 边框
            if self.is_locked:
                pen = QPen(QColor(255, 215, 0), 4)
                painter.setPen(pen)
                painter.drawRect(2, 2, self.width()-4, self.height()-4)
            elif self.is_selected:
                pen = QPen(QColor(33, 150, 243), 4)
                painter.setPen(pen)
                painter.drawRect(2, 2, self.width()-4, self.height()-4)

            # 选中圆点
            if self.is_selected:
                painter.setBrush(QBrush(QColor(33, 150, 243)))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(8, 8, 16, 16)

            # 时间戳
            if self.time_sec >= 0:
                painter.setPen(Qt.white)
                painter.setBrush(QBrush(QColor(0, 0, 0, 150)))
                painter.drawRect(4, self.height()-24, 80, 20)
                painter.setPen(Qt.white)
                painter.setFont(QFont("Arial", 10))
                painter.drawText(6, self.height()-6, self.time_text)

            # 收藏标记（★）
            if self.is_favorite:
                painter.setFont(QFont("Arial", 18))
                painter.setPen(QColor(255, 215, 0))
                painter.drawText(self.width()-30, 30, "★")

            # 已导出标记（绿点）
            if self.is_exported:
                painter.setBrush(QBrush(QColor(0, 200, 0)))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(self.width()-18, self.height()-18, 12, 12)

            painter.end()
        except Exception as e:
            logger.error(f"paintEvent error: {e}\n{traceback.format_exc()}")
            super().paintEvent(event)


class SegmentView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        print("SegmentView __init__ start")
        self.video_path = None
        self.duration = 0.0
        self.segments = []
        self.current_seg_index = 0
        self.density = 9

        self.screenshots: Dict[str, List[dict]] = {}
        self.selected_indices: Set[tuple] = set()
        self.all_videos = []

        self.temp_dir = tempfile.mkdtemp(prefix="CoverPicker_")
        self.export_base = os.path.join(os.getcwd(), "StillPic")

        self._load_task = None

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
        else:
            print("No videos found, please check path")

    def setup_ui(self):
        print("setup_ui start")
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ================= 左侧面板 =================
        left_panel = QWidget()
        left_panel.setFixedWidth(280)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        title = QLabel("📹 视频库")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        left_layout.addWidget(title)

        search_label = QLabel("Q搜索视频")
        search_label.setStyleSheet("color: #888; padding: 4px; border: 1px solid #ccc; border-radius: 4px;")
        left_layout.addWidget(search_label)

        self.video_list = QListWidget()
        self.video_list.setFont(QFont("Arial", 11))
        self.video_list.setStyleSheet("QListWidget::item { padding: 4px; }")
        self.video_list.itemDoubleClicked.connect(self.on_video_selected)
        for path in self.all_videos:
            name = os.path.basename(path)
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, path)
            self.video_list.addItem(item)
        left_layout.addWidget(self.video_list)

        # 视频信息组
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
        self.info_resolution = QLabel("分辨率: --")
        self.info_fps = QLabel("帧率: --")
        self.info_path = QLabel("路径: --")
        self.info_path.setWordWrap(True)
        self.info_path.setStyleSheet("font-size: 9px; color: #666;")

        info_layout.addWidget(self.info_duration)
        info_layout.addWidget(self.info_size)
        info_layout.addWidget(self.info_resolution)
        info_layout.addWidget(self.info_fps)
        info_layout.addWidget(self.info_path)
        info_layout.addStretch()
        left_layout.addWidget(info_group)

        # ---------- 新增：进度指示（移到左侧） ----------
        self.progress_label_left = QLabel("")
        self.progress_label_left.setStyleSheet("color: #666; font-size: 10px; padding: 4px;")
        self.progress_label_left.setWordWrap(True)
        left_layout.addWidget(self.progress_label_left)

        # 状态统计
        stat_layout = QHBoxLayout()
        self.stat_locked = QLabel("锁定: 0")
        self.stat_fav = QLabel("收藏: 0")
        self.stat_viewed = QLabel("已浏览: -")
        stat_layout.addWidget(self.stat_locked)
        stat_layout.addWidget(self.stat_fav)
        stat_layout.addWidget(self.stat_viewed)
        left_layout.addLayout(stat_layout)

        btn_import = QPushButton("导入视频")
        btn_clear_cache = QPushButton("清理缓存")
        left_layout.addWidget(btn_import)
        left_layout.addWidget(btn_clear_cache)
        left_layout.addStretch()

        # ================= 右侧主工作区 =================
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
        settings_btn = QPushButton("⚙")
        settings_btn.setFixedSize(30, 30)
        top_bar.addWidget(settings_btn)
        right_layout.addLayout(top_bar)

        # 控制栏
        control_bar = QHBoxLayout()
        control_bar.setSpacing(8)

        seg_group = QHBoxLayout()
        seg_group.setSpacing(4)
        self.seg_buttons = []
        for label in ['A', 'B', 'C', 'D', 'E']:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedSize(40, 26)
            btn.setFont(QFont("Arial", 10, QFont.Bold))
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
            btn.setFixedSize(32, 24)
            if d == 9:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, val=d: self.on_density_changed(val))
            control_bar.addWidget(btn)
            self.density_buttons.append(btn)

        control_bar.addStretch()
        exclude_btn = QPushButton("排除区间")
        exclude_btn.clicked.connect(self.show_exclude_dialog)
        control_bar.addWidget(exclude_btn)

        right_layout.addLayout(control_bar)

        # 网格
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(8)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)

        self.scroll.setWidget(self.grid_widget)
        right_layout.addWidget(self.scroll, 1)

        # ================= 底部状态栏 =================
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(12)

        self.selected_label = QLabel("已选: 0 张")
        bottom_bar.addWidget(self.selected_label)

        # 移除旧的进度标签，因为已经移到左侧
        # 改为在底部添加全选/取消全选按钮
        bottom_bar.addStretch()

        # 新增：全选按钮
        select_all_btn = QPushButton("☑ 全选")
        select_all_btn.clicked.connect(self.select_all)
        bottom_bar.addWidget(select_all_btn)

        # 新增：取消全选按钮
        deselect_all_btn = QPushButton("☐ 取消全选")
        deselect_all_btn.clicked.connect(self.deselect_all)
        bottom_bar.addWidget(deselect_all_btn)

        # 收藏按钮
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

        zoom_btn = QPushButton("进入Zoom精修>")
        zoom_btn.setStyleSheet("color: #2196F3;")
        bottom_bar.addWidget(zoom_btn)

        right_layout.addLayout(bottom_bar)

        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([280, 1020])
        main_layout.addWidget(splitter)

        for btn in self.seg_buttons:
            btn.setEnabled(False)

        print("setup_ui done")

    # ---------- 全选 / 取消全选 ----------
    def select_all(self):
        """选中当前分段的所有截图"""
        if not self.video_path or not self.segments:
            return
        seg_idx = self.current_seg_index
        seg_label = self.segments[seg_idx][0]
        items = self.screenshots.get(seg_label, [])
        for pos in range(len(items)):
            self.selected_indices.add((seg_idx, pos))
        self._refresh_grid(seg_idx)

    def deselect_all(self):
        """取消所有选中"""
        self.selected_indices.clear()
        if self.video_path and self.segments:
            self._refresh_grid(self.current_seg_index)
        else:
            self._update_selected_count()

    # ---------- 其余方法（保持不变） ----------
    def on_video_selected(self, item: QListWidgetItem):
        path = item.data(Qt.UserRole)
        if path:
            asyncio.create_task(self.load_video(path))

    async def load_video(self, video_path: str):
        logger.info(f"加载视频: {video_path}")
        print(f"加载视频: {video_path}")
        self.video_path = video_path
        self.video_name_label.setText(os.path.basename(video_path))
        self.info_name.setText(os.path.basename(video_path))
        self.info_path.setText(f"路径: {video_path}")
        self._clear_grid()
        self.progress_label_left.setText("加载中...")  # 改用左侧标签

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
        self.info_resolution.setText("分辨率: 1920×1080 (预估)")
        self.info_fps.setText("帧率: --")

        self.screenshots = {}
        self.selected_indices = set()

        for btn in self.seg_buttons:
            btn.setEnabled(True)

        self.current_seg_index = 0
        self._update_seg_buttons()
        self._load_task = asyncio.create_task(self._load_segment(0, restore_locks=True, randomize=False))
        await self._load_task
        self.progress_label_left.setText("加载完成")  # 改用左侧标签

    def _clear_grid(self):
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.progress_label_left.setText("")  # 清空左侧进度

    def on_seg_clicked(self, label: str):
        idx = ord(label) - ord('A')
        if 0 <= idx < len(self.segments):
            self.current_seg_index = idx
            self._update_seg_buttons()
            if self._load_task and not self._load_task.done():
                self._load_task.cancel()
            self._load_task = asyncio.create_task(self._load_segment(idx, restore_locks=True, randomize=False))

    def _update_seg_buttons(self):
        for i, btn in enumerate(self.seg_buttons):
            btn.setChecked(i == self.current_seg_index)

    def show_exclude_dialog(self):
        if not self.video_path:
            QMessageBox.information(self, "提示", "请先加载视频。")
            return
        dlg = ExcludeRangeDialog(self.excluded_ranges, self)
        if dlg.exec() == QDialog.Accepted:
            self.excluded_ranges = dlg.get_ranges()
            if self.video_path:
                if self._load_task and not self._load_task.done():
                    self._load_task.cancel()
                self._load_task = asyncio.create_task(self._load_segment(self.current_seg_index, restore_locks=True, randomize=False))

    def _filter_excluded(self, times: List[float], start: float, end: float) -> List[float]:
        if not self.excluded_ranges:
            return times
        filtered = []
        for t in times:
            excluded = False
            for low, high in self.excluded_ranges:
                if low <= t <= high:
                    excluded = True
                    break
            if not excluded:
                filtered.append(t)
        need = len(times) - len(filtered)
        if need > 0:
            available_ranges = [(start, end)]
            for low, high in self.excluded_ranges:
                new_ranges = []
                for a, b in available_ranges:
                    if high <= a or low >= b:
                        new_ranges.append((a, b))
                    else:
                        if a < low:
                            new_ranges.append((a, min(b, low)))
                        if b > high:
                            new_ranges.append((max(a, high), b))
                available_ranges = new_ranges
            for _ in range(need):
                if not available_ranges:
                    break
                total_len = sum(b-a for a,b in available_ranges)
                r = random.random() * total_len
                for a, b in available_ranges:
                    if r < (b-a):
                        t = random.uniform(a, b)
                        filtered.append(t)
                        break
                    r -= (b-a)
        filtered.sort()
        return filtered

    async def _load_segment(self, seg_idx: int, restore_locks: bool = True, randomize: bool = False):
        if not self.video_path or not self.segments:
            return

        label, start, end = self.segments[seg_idx]
        offset = (end - start) * self.skip_ratio
        start_cropped = start + offset
        end_cropped = end - offset
        if end_cropped <= start_cropped:
            start_cropped = start
            end_cropped = end
        logger.info(f"加载分段 {label}: {start_cropped:.1f}s - {end_cropped:.1f}s")
        self.progress_label_left.setText(f"正在加载 {label} 分段...")  # 左侧

        duration_seg = end_cropped - start_cropped
        count = self.density

        if randomize:
            times = [random.uniform(start_cropped, end_cropped) for _ in range(count)]
            times.sort()
        else:
            if count == 1:
                times = [(start_cropped + end_cropped) / 2]
            else:
                step = duration_seg / (count + 1)
                times = [start_cropped + step * (i+1) for i in range(count)]

        times = self._filter_excluded(times, start_cropped, end_cropped)
        while len(times) < count:
            t = random.uniform(start_cropped, end_cropped)
            excluded = False
            for low, high in self.excluded_ranges:
                if low <= t <= high:
                    excluded = True
                    break
            if not excluded:
                times.append(t)
        times.sort()
        times = times[:count]

        seg_key = label
        if seg_key not in self.screenshots:
            self.screenshots[seg_key] = []

        old_items = self.screenshots.get(seg_key, [])
        new_items = []
        step_half = step * 0.5 if not randomize and count > 1 else 1.0
        total = len(times)
        for idx, t in enumerate(times):
            self.progress_label_left.setText(f"正在生成 {label} 第 {idx+1}/{total} 张 @ {t:.2f}s")  # 左侧
            QApplication.processEvents()

            matched = None
            if restore_locks and not randomize:
                for item in old_items:
                    if abs(item['time'] - t) < step_half:
                        matched = item
                        break
            if matched:
                new_items.append(matched.copy())
                continue

            temp_path = os.path.join(self.temp_dir, f"seg_{label}_{t:.2f}.jpg")
            success = await asyncio.to_thread(extract_frame, self.video_path, t, temp_path)
            if success:
                new_items.append({
                    'time': t,
                    'path': temp_path,
                    'locked': False,
                    'favorite': False,
                    'exported': False,
                })
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

        self.screenshots[seg_key] = new_items
        self.selected_indices = set()
        self._refresh_grid(seg_idx)
        self.progress_label_left.setText(f"{label} 分段加载完成")  # 左侧

    def _refresh_grid(self, seg_idx: int):
        try:
            logger.info("刷新网格开始")
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

            locked_count = sum(1 for it in items if it.get('locked', False))
            fav_count = sum(1 for it in items if it.get('favorite', False))
            self.stat_locked.setText(f"锁定: {locked_count}")
            self.stat_fav.setText(f"收藏: {fav_count}")

            for pos, item in enumerate(items):
                try:
                    row = pos // cols
                    col = pos % cols

                    pixmap = QPixmap(300, 185)
                    pixmap.fill(QColor(100, 100, 100))
                    if item.get('path') and os.path.exists(item['path']):
                        loaded = QPixmap(item['path'])
                        if not loaded.isNull():
                            pixmap = loaded

                    label = ClickableLabel(pixmap, item['time'])
                    label.setObjectName(f"{seg_idx}_{pos}")
                    label.set_locked(item.get('locked', False))
                    label.set_favorite(item.get('favorite', False))
                    label.set_exported(item.get('exported', False))
                    if (seg_idx, pos) in self.selected_indices:
                        label.set_selected(True)

                    label.clicked.connect(partial(self.on_image_click, seg_idx, pos))
                    label.double_clicked.connect(partial(self.zoom_image, seg_idx, pos))
                    self.grid_layout.addWidget(label, row, col)
                except Exception as e:
                    logger.error(f"创建第 {pos} 个标签时出错: {e}")

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

    def zoom_image(self, seg_idx: int, pos: int):
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
            QMessageBox.warning(self, "警告", "无法加载图片。")
            return
        dlg = ZoomPreviewDialog(pixmap, item['time'], self)
        dlg.exec()

    # ---------- 收藏功能 ----------
    def favorite_selected(self):
        try:
            if not self.selected_indices:
                QMessageBox.information(self, "提示", "请先选中要收藏的截图。")
                return
            seg_label = self.segments[self.current_seg_index][0]
            items = self.screenshots.get(seg_label, [])
            for (seg_idx, pos) in list(self.selected_indices):
                if seg_idx == self.current_seg_index and pos < len(items):
                    items[pos]['favorite'] = True
            self._refresh_grid(self.current_seg_index)
            logger.info(f"收藏成功: {len(self.selected_indices)} 张")
        except Exception as e:
            logger.error(f"favorite_selected error: {e}\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"收藏失败: {str(e)}")

    def unfavorite_selected(self):
        try:
            if not self.selected_indices:
                QMessageBox.information(self, "提示", "请先选中要取消收藏的截图。")
                return
            seg_label = self.segments[self.current_seg_index][0]
            items = self.screenshots.get(seg_label, [])
            for (seg_idx, pos) in list(self.selected_indices):
                if seg_idx == self.current_seg_index and pos < len(items):
                    items[pos]['favorite'] = False
            self._refresh_grid(self.current_seg_index)
            logger.info(f"取消收藏成功: {len(self.selected_indices)} 张")
        except Exception as e:
            logger.error(f"unfavorite_selected error: {e}\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"取消收藏失败: {str(e)}")

    # ---------- 锁定/解锁 ----------
    def lock_selected(self):
        try:
            if not self.selected_indices:
                QMessageBox.information(self, "提示", "请先选中要锁定的截图。")
                return
            seg_label = self.segments[self.current_seg_index][0]
            items = self.screenshots.get(seg_label, [])
            for (seg_idx, pos) in list(self.selected_indices):
                if seg_idx == self.current_seg_index and pos < len(items):
                    items[pos]['locked'] = True
            self._refresh_grid(self.current_seg_index)
        except Exception as e:
            logger.error(f"lock_selected error: {e}")

    def unlock_selected(self):
        try:
            if not self.selected_indices:
                QMessageBox.information(self, "提示", "请先选中要解锁的截图。")
                return
            seg_label = self.segments[self.current_seg_index][0]
            items = self.screenshots.get(seg_label, [])
            for (seg_idx, pos) in list(self.selected_indices):
                if seg_idx == self.current_seg_index and pos < len(items):
                    items[pos]['locked'] = False
            self._refresh_grid(self.current_seg_index)
        except Exception as e:
            logger.error(f"unlock_selected error: {e}")

    # ---------- 刷新未锁定 ----------
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
                self.progress_label_left.setText(f"刷新未锁定 {idx+1}/{total}")  # 左侧
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
                success = await asyncio.to_thread(extract_frame, self.video_path, t, temp_path)
                if success:
                    items[pos]['time'] = t
                    items[pos]['path'] = temp_path
                    items[pos]['locked'] = False
                    logger.info(f"刷新未锁定: {seg_label} {pos} -> {t:.2f}s")
                else:
                    logger.warning(f"刷新未锁定失败: {seg_label} {pos}")
            self._refresh_grid(seg_idx)
            self.progress_label_left.setText("刷新完成")  # 左侧
        except Exception as e:
            logger.error(f"refresh_unlocked error: {e}\n{traceback.format_exc()}")

    # ---------- 全部重抽 ----------
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
            logger.info(f"全部重抽完成: 分段 {seg_label}")
        except Exception as e:
            logger.error(f"reset_all error: {e}\n{traceback.format_exc()}")

    # ---------- 导出选中 ----------
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

            QMessageBox.information(self, "导出完成", f"成功导出 {exported} 张截图到:\n{export_dir}")
            self.selected_indices.clear()
            self._refresh_grid(self.current_seg_index)
        except Exception as e:
            logger.error(f"export_selected error: {e}\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")

    # ---------- 密度切换 ----------
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
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except:
            pass
        event.accept()