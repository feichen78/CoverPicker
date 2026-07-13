# ui/views/zoom_dialog.py

import os
import asyncio
import logging
import random
import shutil
from typing import List, Optional, Tuple, Dict
from functools import partial

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGridLayout, QScrollArea, QFrame, QWidget, QSizePolicy,
    QMessageBox, QApplication
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap, QFont, QColor, QPainter, QBrush, QPen

from src.video_scanner import extract_frame
from ui.views.zoom_preview import ZoomPreviewDialog

logger = logging.getLogger(__name__)


class ZoomThumbLabel(QLabel):
    """Zoom 精修中的候选帧标签"""
    clicked = Signal()
    double_clicked = Signal()

    def __init__(self, pixmap: QPixmap, time_sec: float, index: int = 0, parent=None):
        super().__init__(parent)
        self.time_sec = time_sec
        self.index = index
        self.is_selected = False
        self.time_text = f"{time_sec:.1f}s"

        self.original_pixmap = pixmap
        self.display_pixmap = QPixmap()
        self.current_w = 180
        self.current_h = 135

        self.setFixedSize(self.current_w + 6, self.current_h + 6)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setStyleSheet("border: 2px solid #444; background: #2a2a2a; border-radius: 3px;")

        self._update_display_pixmap()

    def set_image_size(self, w: int, h: int):
        if w != self.current_w or h != self.current_h:
            self.current_w = w
            self.current_h = h
            self.setFixedSize(w + 6, h + 6)
            self._update_display_pixmap()

    def _update_display_pixmap(self):
        if self.original_pixmap.isNull():
            self.display_pixmap = QPixmap(self.current_w, self.current_h)
            self.display_pixmap.fill(QColor(60, 60, 60))
            self.update()
            return

        w = max(10, self.current_w)
        h = max(10, self.current_h)

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
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制背景和图片
        painter.fillRect(self.rect(), QColor(30, 30, 30))
        x = (self.width() - self.display_pixmap.width()) // 2
        y = (self.height() - self.display_pixmap.height()) // 2
        painter.drawPixmap(x, y, self.display_pixmap)

        # 选中状态：蓝色边框
        if self.is_selected:
            painter.setPen(QPen(QColor(33, 150, 243), 3))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(2, 2, self.width() - 5, self.height() - 5)

        # 序号（左上角）
        painter.setPen(Qt.white)
        painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
        painter.drawRoundedRect(4, 4, 22, 18, 3, 3)
        painter.setPen(Qt.white)
        painter.setFont(QFont("Arial", 9, QFont.Bold))
        painter.drawText(6, 17, f"{self.index}")

        # 时间戳（左下角）
        painter.setPen(Qt.white)
        painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
        painter.drawRoundedRect(4, self.height() - 22, 55, 18, 3, 3)
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


class ZoomDialog(QDialog):
    """
    Zoom 精修对话框 - 支持 L1~L4 四层递归精修
    
    L1: ±4秒, 间隔1秒
    L2: ±2秒, 间隔0.5秒
    L3: ±1秒, 间隔0.25秒
    L4: ±0.5秒, 间隔0.125秒
    """

    # 层级配置: (半范围, 间隔)
    LEVEL_CONFIG = {
        1: (4.0, 1.0),
        2: (2.0, 0.5),
        3: (1.0, 0.25),
        4: (0.5, 0.125),
    }

    def __init__(
        self,
        controller,
        seg_label: str,
        seg_idx: int,
        pos: int,
        center_time: float,
        level: int = 1,
        parent=None,
        source: str = "main",  # "main" 或 "favorites"
        favorites_data: Optional[List[dict]] = None,  # 收藏弹窗专用
        original_fav_item: Optional[dict] = None,  # 原始收藏项引用
    ):
        super().__init__(parent)
        self.controller = controller
        self.seg_label = seg_label
        self.seg_idx = seg_idx
        self.pos = pos
        self.center_time = center_time
        self.level = level
        self.source = source
        self.favorites_data = favorites_data
        self.original_fav_item = original_fav_item

        self.video_path = controller.get_video_path()
        self.temp_dir = controller.get_temp_dir()
        self.duration = controller.get_duration()
        self.export_base = controller.get_export_base()

        # 当前层级的范围配置
        half_range, step = self.LEVEL_CONFIG.get(level, (4.0, 1.0))
        self.half_range = half_range
        self.step = step

        # 计算搜索范围（边界裁剪）
        self.range_start = max(0, center_time - half_range)
        self.range_end = min(self.duration, center_time + half_range)

        # 如果范围太小，调整
        if self.range_end - self.range_start < 0.5:
            self.range_start = max(0, center_time - 0.25)
            self.range_end = min(self.duration, center_time + 0.25)

        # 状态
        self.candidate_items: List[dict] = []
        self.selected_index: Optional[int] = None
        self._load_task: Optional[asyncio.Task] = None
        self.is_loading = False

        # UI 标题
        level_names = {1: "L1 · 初选", 2: "L2 · 精选", 3: "L3 · 细选", 4: "L4 · 定稿"}
        self.setWindowTitle(
            f"🔍 {level_names.get(level, '精修')} - {seg_label}区 · {center_time:.2f}s"
        )
        self.setModal(True)
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowCloseButtonHint |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint
        )
        self.resize(1100, 850)
        self.setMinimumSize(800, 700)

        self.setup_ui()

        # 加载候选帧
        QTimer.singleShot(50, self.load_candidates)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # ===== 顶部信息栏 =====
        top_bar = QHBoxLayout()

        info_text = (
            f"📍 {self.seg_label}区  ·  "
            f"中心 {self.center_time:.2f}s  ·  "
            f"范围 {self.range_start:.2f}s - {self.range_end:.2f}s  "
            f"({self.range_end - self.range_start:.2f}s)  ·  "
            f"层级 L{self.level}  "
            f"({self.level}/4)"
        )
        self.info_label = QLabel(info_text)
        self.info_label.setFont(QFont("Arial", 11))
        top_bar.addWidget(self.info_label)
        top_bar.addStretch()

        # 层级指示器
        level_label = QLabel(f"L{self.level}")
        level_label.setFont(QFont("Arial", 12, QFont.Bold))
        level_label.setStyleSheet("color: #2196F3;")
        top_bar.addWidget(level_label)

        main_layout.addLayout(top_bar)

        # ===== 分隔线 =====
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line)

        # ===== 网格区域 =====
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.grid_widget = QWidget()
        self.grid_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(8)
        self.grid_layout.setContentsMargins(6, 6, 6, 6)

        self.scroll.setWidget(self.grid_widget)
        main_layout.addWidget(self.scroll, 1)

        # ===== 进度标签 =====
        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: #666; font-size: 12px; padding: 4px;")
        main_layout.addWidget(self.progress_label)

        # ===== 底部操作栏 =====
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        # 左侧：选中计数 + 操作按钮
        self.selected_label = QLabel("已选: 0 张")
        self.selected_label.setFont(QFont("Arial", 11))
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

        # 收藏按钮
        self.fav_btn = QPushButton("⭐ 收藏")
        self.fav_btn.setEnabled(False)
        self.fav_btn.clicked.connect(self.favorite_selected)
        bottom_bar.addWidget(self.fav_btn)

        # 导出按钮
        self.export_btn = QPushButton("📥 导出")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_selected)
        bottom_bar.addWidget(self.export_btn)

        # 预览按钮
        self.preview_btn = QPushButton("🔍 预览")
        self.preview_btn.setEnabled(False)
        self.preview_btn.clicked.connect(self.preview_selected)
        bottom_bar.addWidget(self.preview_btn)

        # 细选按钮（进入下一层）
        self.zoom_btn = QPushButton("🔍 细选 →")
        self.zoom_btn.setEnabled(False)
        self.zoom_btn.setStyleSheet("background: #FF9800; color: white; font-weight: bold;")
        self.zoom_btn.clicked.connect(self.zoom_selected)
        bottom_bar.addWidget(self.zoom_btn)

        # 替换按钮（替换原图）
        self.replace_btn = QPushButton("📥 替换原图")
        self.replace_btn.setEnabled(False)
        self.replace_btn.setStyleSheet("background: #2196F3; color: white; font-weight: bold; padding: 8px 20px;")
        self.replace_btn.clicked.connect(self.replace_selected)
        bottom_bar.addWidget(self.replace_btn)

        # 关闭按钮
        close_btn = QPushButton("✕ 关闭")
        close_btn.clicked.connect(self.reject)
        bottom_bar.addWidget(close_btn)

        main_layout.addLayout(bottom_bar)

        # ===== 底部提示 =====
        hint_label = QLabel("💡 单击选中 · 双击放大预览 · 通过按钮执行细选/替换/收藏/导出")
        hint_label.setStyleSheet("color: #888; font-size: 10px;")
        main_layout.addWidget(hint_label)

    # ============================================================
    # 候选帧加载
    # ============================================================

    def load_candidates(self):
        """加载当前层级的候选帧"""
        if self._load_task and not self._load_task.done():
            self._load_task.cancel()

        self._load_task = asyncio.create_task(self._load_candidates_async())
        self.is_loading = True
        self.progress_label.setText("正在加载...")
        self._check_task_complete()

    def _check_task_complete(self):
        """检查异步任务是否完成"""
        if self._load_task and self._load_task.done():
            try:
                self._load_task.result()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"加载候选帧失败: {e}")
                QMessageBox.critical(self, "错误", f"加载候选帧失败: {str(e)}")
            self._load_task = None
            self.is_loading = False
            self._render_grid()
            self.progress_label.setText(f"加载完成 ({len(self.candidate_items)} 张)")
        else:
            QTimer.singleShot(100, self._check_task_complete)

    async def _load_candidates_async(self):
        """异步加载候选帧"""
        # 生成 9 个时间点（3×3 网格）
        times = self._generate_times()
        items = []

        total = len(times)
        for idx, t in enumerate(times):
            if self._load_task and self._load_task.cancelled():
                self.progress_label.setText("加载已取消")
                return

            self.progress_label.setText(f"正在生成 {idx+1}/{total} 张 @ {t:.2f}s")
            QApplication.processEvents()

            temp_path = os.path.join(self.temp_dir, f"zoom_L{self.level}_{self.seg_label}_{t:.2f}_{idx}.jpg")
            try:
                success = await asyncio.to_thread(extract_frame, self.video_path, t, temp_path)
                if success:
                    items.append({'time': t, 'path': temp_path})
                else:
                    # 提取失败，使用备用时间
                    fallback_t = random.uniform(self.range_start, self.range_end)
                    fallback_path = os.path.join(
                        self.temp_dir, f"zoom_L{self.level}_{self.seg_label}_{fallback_t:.2f}_{idx}_fallback.jpg"
                    )
                    success2 = await asyncio.to_thread(extract_frame, self.video_path, fallback_t, fallback_path)
                    if success2:
                        items.append({'time': fallback_t, 'path': fallback_path})
                    else:
                        items.append({'time': t, 'path': None})
            except asyncio.CancelledError:
                self.progress_label.setText("加载已取消")
                raise

        self.candidate_items = items
        self.selected_index = None

    def _generate_times(self) -> List[float]:
        """
        生成 9 个时间点（3×3 网格）
        中心是 center_time，周围 8 个点均匀分布在范围内
        """
        half = self.half_range
        step = self.step

        if half < 0.1:
            return [self.center_time] * 9

        positions = []
        for i in range(9):
            offset = (i - 4) * step
            t = self.center_time + offset
            t = max(self.range_start, min(self.range_end, t))
            positions.append(t)

        # 去重并补全
        unique_positions = []
        seen = set()
        for t in positions:
            rounded = round(t, 3)
            if rounded not in seen:
                seen.add(rounded)
                unique_positions.append(t)

        while len(unique_positions) < 9:
            unique_positions.append(self.center_time)

        unique_positions.sort()
        return unique_positions[:9]

    # ============================================================
    # 网格渲染
    # ============================================================

    def _render_grid(self):
        """渲染候选帧网格"""
        # 清空网格
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        items = self.candidate_items
        count = len(items)

        if count == 0:
            label = QLabel("⚠️ 没有可用的候选帧\n请尝试关闭并重新打开")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-size: 16px; color: #999; padding: 40px;")
            self.grid_layout.addWidget(label, 0, 0)
            return

        # 3×3 网格
        cols = 3
        img_w, img_h = 250, 188

        viewport_width = self.scroll.viewport().width() - 20
        if viewport_width > 0:
            max_w = (viewport_width - 16) // 3 - 10
            if max_w > 150:
                img_w = min(max_w, 300)
                img_h = int(img_w * 0.75)

        for col in range(cols):
            self.grid_layout.setColumnStretch(col, 1)

        rows = (count + cols - 1) // cols
        for row in range(rows):
            self.grid_layout.setRowStretch(row, 1)

        for pos, item in enumerate(items):
            row = pos // cols
            col = pos % cols

            pixmap = QPixmap()
            if item.get('path') and os.path.exists(item['path']):
                loaded = QPixmap(item['path'])
                if not loaded.isNull():
                    pixmap = loaded

            index_num = pos + 1
            label = ZoomThumbLabel(pixmap, item['time'], index_num)
            label.set_image_size(img_w, img_h)
            label.setObjectName(f"zoom_{pos}")

            label.clicked.connect(partial(self.on_thumb_click, pos))
            label.double_clicked.connect(partial(self.preview_selected))

            if self.selected_index == pos:
                label.set_selected(True)

            self.grid_layout.addWidget(label, row, col)

        self._update_selected_count()

    # ============================================================
    # 交互事件
    # ============================================================

    def on_thumb_click(self, pos: int):
        """单击候选帧 - 选中/取消选中"""
        if self.selected_index == pos:
            self.selected_index = None
        else:
            self.selected_index = pos

        self._render_grid()
        self._update_selected_count()

    def _update_selected_count(self):
        """更新底部选中计数和按钮状态"""
        has_selected = self.selected_index is not None
        count = 1 if has_selected else 0

        self.selected_label.setText(f"已选: {count} 张")
        self.select_all_btn.setEnabled(len(self.candidate_items) > 0)
        self.deselect_all_btn.setEnabled(has_selected)
        self.fav_btn.setEnabled(has_selected)
        self.export_btn.setEnabled(has_selected)
        self.preview_btn.setEnabled(has_selected)
        self.zoom_btn.setEnabled(has_selected and self.level < 4)
        self.replace_btn.setEnabled(has_selected)

    # ============================================================
    # 全选 / 取消全选
    # ============================================================

    def select_all(self):
        """全选（Zoom 中只能选一个，选中第一个）"""
        if self.candidate_items:
            self.selected_index = 0
            self._render_grid()
            self._update_selected_count()

    def deselect_all(self):
        """取消全选"""
        self.selected_index = None
        self._render_grid()
        self._update_selected_count()

    # ============================================================
    # 收藏
    # ============================================================

    def favorite_selected(self):
        """收藏选中的候选帧"""
        if self.selected_index is None:
            return

        item = self.candidate_items[self.selected_index]
        time_sec = item['time']

        if self.source == "favorites":
            QMessageBox.information(self, "提示", "收藏弹窗中请直接使用'替换原图'，收藏操作请在主界面进行。")
            return

        # 主界面模式
        items = self.controller.get_segment_items(self.seg_label)
        original_item = items[self.pos] if self.pos < len(items) else None

        if original_item and not original_item.get('favorite', False):
            self.controller.favorite_selected(self.seg_label, [self.pos])
            QMessageBox.information(self, "完成", f"已收藏 {time_sec:.2f}s 的截图")
        elif original_item and original_item.get('favorite', False):
            QMessageBox.information(self, "提示", "该截图已收藏")
        else:
            QMessageBox.warning(self, "警告", "无法收藏：原截图不存在")

    # ============================================================
    # 导出
    # ============================================================

    def export_selected(self):
        """导出选中的候选帧"""
        if self.selected_index is None:
            return

        item = self.candidate_items[self.selected_index]
        time_sec = item['time']

        if not item.get('path') or not os.path.exists(item['path']):
            QMessageBox.warning(self, "警告", "图片文件不存在")
            return

        video_name = os.path.splitext(os.path.basename(self.video_path))[0]
        export_dir = os.path.join(self.export_base, video_name)
        os.makedirs(export_dir, exist_ok=True)

        dest_name = f"cover_{time_sec:.2f}s.jpg"
        dest_path = os.path.join(export_dir, dest_name)

        try:
            shutil.copy2(item['path'], dest_path)
            QMessageBox.information(self, "导出完成", f"已导出到:\n{dest_path}")
        except Exception as e:
            logger.error(f"导出失败: {e}")
            QMessageBox.warning(self, "错误", f"导出失败: {str(e)}")

    # ============================================================
    # 预览
    # ============================================================

    def preview_selected(self):
        """预览选中的候选帧"""
        if self.selected_index is None:
            return

        item = self.candidate_items[self.selected_index]
        if not item.get('path') or not os.path.exists(item['path']):
            QMessageBox.warning(self, "警告", "图片文件不存在")
            return

        pixmap = QPixmap(item['path'])
        if pixmap.isNull():
            QMessageBox.warning(self, "警告", "无法加载图片")
            return

        dlg = ZoomPreviewDialog(pixmap, item['time'], self)
        dlg.exec()

    # ============================================================
    # 细选（进入下一层）
    # ============================================================

    def zoom_selected(self):
        """进入下一层精修"""
        if self.selected_index is None:
            return
        if self.level >= 4:
            QMessageBox.information(self, "提示", "已达到最大层级 L4")
            return

        item = self.candidate_items[self.selected_index]
        next_level = self.level + 1

        # 关闭当前窗口，打开下一层
        dlg = ZoomDialog(
            controller=self.controller,
            seg_label=self.seg_label,
            seg_idx=self.seg_idx,
            pos=self.pos,
            center_time=item['time'],
            level=next_level,
            parent=self.parent(),
            source=self.source,
            favorites_data=self.favorites_data if self.source == "favorites" else None,
            original_fav_item=self.original_fav_item,
        )
        self.hide()
        result = dlg.exec()
        if result == QDialog.Rejected:
            self.show()

    # ============================================================
    # 替换原图
    # ============================================================

    def replace_selected(self):
        """替换原图（通过按钮执行）"""
        if self.selected_index is None:
            return

        item = self.candidate_items[self.selected_index]
        if not item.get('path') or not os.path.exists(item['path']):
            QMessageBox.warning(self, "警告", "图片文件不存在，无法替换")
            return

        time_sec = item['time']
        src_path = item['path']

        reply = QMessageBox.question(
            self,
            "确认替换",
            f"确定要将原截图（{self.center_time:.2f}s）替换为当前选中的截图（{time_sec:.2f}s）吗？\n\n此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            if self.source == "favorites":
                self._replace_in_favorites(time_sec, src_path)
            else:
                self._replace_in_main(time_sec, src_path)

            self.accept()

        except Exception as e:
            logger.error(f"替换失败: {e}")
            QMessageBox.critical(self, "错误", f"替换失败: {str(e)}")

    def _replace_in_main(self, time_sec: float, src_path: str):
        """替换主界面中的截图"""
        items = self.controller.get_segment_items(self.seg_label)
        if self.pos >= len(items):
            QMessageBox.warning(self, "警告", "原截图已不存在")
            return

        original = items[self.pos]

        locked = original.get('locked', False)
        favorite = original.get('favorite', False)
        exported = original.get('exported', False)

        new_path = os.path.join(self.temp_dir, f"seg_{self.seg_label}_{time_sec:.2f}_replaced.jpg")
        shutil.copy2(src_path, new_path)

        original['time'] = time_sec
        original['path'] = new_path
        original['locked'] = locked
        original['favorite'] = favorite
        original['exported'] = exported

        if favorite and self.controller.video_id:
            old_timestamp_ms = int(self.center_time * 1000)
            new_timestamp_ms = int(time_sec * 1000)
            self.controller.db.remove_favorite(
                self.controller.video_id,
                self.seg_label,
                old_timestamp_ms
            )
            self.controller.db.add_favorite(
                self.controller.video_id,
                self.seg_label,
                new_timestamp_ms,
                new_path,
                is_exported=exported
            )
            for fav in self.controller.favorites:
                if (fav.get('video_path') == self.controller.video_path and
                    fav.get('segment') == self.seg_label and
                    abs(fav.get('time', 0) - self.center_time) < 0.01):
                    fav['time'] = time_sec
                    fav['path'] = new_path
                    break

        self.controller._notify_data_changed()
        QMessageBox.information(self, "完成", f"已成功替换为 {time_sec:.2f}s 的截图")

    def _replace_in_favorites(self, time_sec: float, src_path: str):
        """替换收藏弹窗中的截图"""
        if not self.original_fav_item:
            QMessageBox.warning(self, "警告", "未找到原始收藏项，无法替换")
            return

        fav_item = self.original_fav_item
        old_time = fav_item.get('time', self.center_time)
        exported = fav_item.get('exported', False)

        new_path = os.path.join(self.temp_dir, f"fav_{self.seg_label}_{time_sec:.2f}_replaced.jpg")
        shutil.copy2(src_path, new_path)

        fav_item['time'] = time_sec
        fav_item['path'] = new_path
        fav_item['exported'] = exported

        if self.controller.video_id:
            old_timestamp_ms = int(old_time * 1000)
            new_timestamp_ms = int(time_sec * 1000)
            self.controller.db.remove_favorite(
                self.controller.video_id,
                self.seg_label,
                old_timestamp_ms
            )
            self.controller.db.add_favorite(
                self.controller.video_id,
                self.seg_label,
                new_timestamp_ms,
                new_path,
                is_exported=exported
            )

            if self.parent() and hasattr(self.parent(), 'favorites'):
                for fav in self.parent().favorites:
                    if (fav.get('segment') == self.seg_label and
                        abs(fav.get('time', 0) - old_time) < 0.01):
                        fav['time'] = time_sec
                        fav['path'] = new_path
                        fav['exported'] = exported
                        break

        if self.parent() and hasattr(self.parent(), 'load_favorites'):
            self.parent().load_favorites()

        QMessageBox.information(self, "完成", f"已成功替换收藏中的截图")

    # ============================================================
    # 关闭事件
    # ============================================================

    def closeEvent(self, event):
        if self._load_task and not self._load_task.done():
            self._load_task.cancel()
        event.accept()

    def reject(self):
        if self._load_task and not self._load_task.done():
            self._load_task.cancel()
        super().reject()