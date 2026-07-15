# ui/views/preview_panel.py

import os
import asyncio
import logging
from typing import Optional, Tuple, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSlider, QFrame, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap, QFont, QResizeEvent

from src.controllers.preview_controller import PreviewController

logger = logging.getLogger(__name__)


class PreviewPanel(QWidget):
    """右侧预览面板 - 视频帧预览 + 时间轴片段选择 + 自定义分区"""

    export_clip_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)

        self.controller = PreviewController()
        self.controller.set_progress_callback(self._on_progress_update)

        # 主控制器引用（由 SegmentView 设置）
        self.main_controller = None

        self.duration: float = 0.0
        self.video_path: Optional[str] = None
        self.temp_dir: Optional[str] = None

        self._slider_update_timer = QTimer()
        self._slider_update_timer.setSingleShot(True)
        self._slider_update_timer.timeout.connect(self._on_slider_timeout)

        self._pending_time: float = 0.0
        self._is_dragging: bool = False

        # 分割点列表（自定义分区用）
        self.split_points: List[float] = []

        self.setup_ui()
        self.setMinimumWidth(380)

    def set_main_controller(self, controller):
        """设置主控制器引用（由 SegmentView 调用）"""
        self.main_controller = controller

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(6)

        # ===== 标题栏 =====
        title_layout = QHBoxLayout()
        title_label = QLabel("🎬 视频预览")
        title_label.setFont(QFont("Arial", 13, QFont.Bold))
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("""
            QPushButton { 
                border: none; 
                font-size: 14px; 
                border-radius: 4px;
            } 
            QPushButton:hover { 
                background: #e74c3c; 
                color: white; 
            }
        """)
        close_btn.clicked.connect(self.hide_panel)
        title_layout.addWidget(close_btn)
        main_layout.addLayout(title_layout)

        # ===== 预览画面 =====
        self.preview_label = QLabel("选择视频后预览")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(200)
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_label.setStyleSheet("""
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 4px;
            color: #666;
            font-size: 15px;
        """)
        self.preview_label.setScaledContents(False)
        main_layout.addWidget(self.preview_label, 1)

        # ===== 时间信息 + 时间轴 =====
        time_info_layout = QHBoxLayout()
        self.position_label = QLabel("00:00:00")
        self.position_label.setFont(QFont("monospace", 12))
        self.position_label.setStyleSheet("color: #888;")
        time_info_layout.addWidget(self.position_label)
        time_info_layout.addStretch()
        self.duration_label = QLabel("00:00:00")
        self.duration_label.setFont(QFont("monospace", 12))
        self.duration_label.setStyleSheet("color: #888;")
        time_info_layout.addWidget(self.duration_label)
        main_layout.addLayout(time_info_layout)

        # 时间轴滑块
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 10000)
        self.slider.setValue(0)
        self.slider.setTracking(True)
        self.slider.setFixedHeight(26)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: #3a3a3a;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #2196F3;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider::sub-page:horizontal {
                background: #2196F3;
                border-radius: 3px;
            }
        """)
        self.slider.sliderPressed.connect(self._on_slider_pressed)
        self.slider.sliderReleased.connect(self._on_slider_released)
        self.slider.valueChanged.connect(self._on_slider_value_changed)
        main_layout.addWidget(self.slider)

        # ===== 范围状态标签 =====
        self.range_label = QLabel("🎯 在时间轴上拖动浏览，点击按钮设置片段范围")
        self.range_label.setStyleSheet("color: #666; font-size: 11px;")
        self.range_label.setWordWrap(True)
        main_layout.addWidget(self.range_label)

        # ===== 按钮行（所有按钮直接添加，中间加 stretch） =====
        btn_row = QHBoxLayout()
        btn_row.setSpacing(5)

        # ---- 左侧：分割点管理 ----
        split_label = QLabel("🔪 分区分割点:")
        split_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        split_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        btn_row.addWidget(split_label)

        self.add_split_btn = QPushButton("📍 添加分割点")
        self.add_split_btn.setStyleSheet("""
            QPushButton {
                background: #FF9800;
                color: white;
                font-weight: bold;
                padding: 5px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover { background: #F57C00; }
            QPushButton:disabled { background: #555; color: #888; }
        """)
        self.add_split_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.add_split_btn.clicked.connect(self.add_split_point)
        btn_row.addWidget(self.add_split_btn)

        self.clear_splits_btn = QPushButton("🗑️")
        self.clear_splits_btn.setFixedSize(24, 24)
        self.clear_splits_btn.setToolTip("清除分割点")
        self.clear_splits_btn.setStyleSheet("""
            QPushButton {
                background: #e74c3c;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background: #c0392b; }
            QPushButton:disabled { background: #555; color: #888; }
        """)
        self.clear_splits_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.clear_splits_btn.clicked.connect(self.clear_split_points)
        btn_row.addWidget(self.clear_splits_btn)

        self.apply_splits_btn = QPushButton("✅ 应用分区")
        self.apply_splits_btn.setStyleSheet("""
            QPushButton {
                background: #9C27B0;
                color: white;
                font-weight: bold;
                padding: 5px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover { background: #7B1FA2; }
            QPushButton:disabled { background: #555; color: #888; }
        """)
        self.apply_splits_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.apply_splits_btn.clicked.connect(self.apply_split_points)
        btn_row.addWidget(self.apply_splits_btn)

        # ---- 弹性分隔 ----
        btn_row.addStretch()

        # ---- 右侧：片段操作 ----
        self.set_start_btn = QPushButton("📍 设起始")
        self.set_start_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 5px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover { background: #43a047; }
            QPushButton:disabled { background: #555; color: #888; }
        """)
        self.set_start_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.set_start_btn.clicked.connect(self.set_start)
        btn_row.addWidget(self.set_start_btn)

        self.set_end_btn = QPushButton("📍 设结束")
        self.set_end_btn.setStyleSheet("""
            QPushButton {
                background: #f44336;
                color: white;
                font-weight: bold;
                padding: 5px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover { background: #d32f2f; }
            QPushButton:disabled { background: #555; color: #888; }
        """)
        self.set_end_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.set_end_btn.clicked.connect(self.set_end)
        btn_row.addWidget(self.set_end_btn)

        self.clear_range_btn = QPushButton("✕ 清除")
        self.clear_range_btn.setStyleSheet("""
            QPushButton {
                background: #666;
                color: white;
                font-weight: bold;
                padding: 5px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover { background: #888; }
        """)
        self.clear_range_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.clear_range_btn.clicked.connect(self.clear_range)
        btn_row.addWidget(self.clear_range_btn)

        self.export_btn = QPushButton("📥 导出片段")
        self.export_btn.setEnabled(False)
        self.export_btn.setStyleSheet("""
            QPushButton {
                background: #2196F3;
                color: white;
                font-weight: bold;
                padding: 5px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover { background: #1976D2; }
            QPushButton:disabled { background: #555; color: #888; }
        """)
        self.export_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.export_btn.clicked.connect(self.export_clip)
        btn_row.addWidget(self.export_btn)

        main_layout.addLayout(btn_row)

        # ===== 分割点列表显示 =====
        self.split_list_label = QLabel("分割点: 无")
        self.split_list_label.setStyleSheet("color: #888; font-size: 10px; padding: 2px;")
        self.split_list_label.setWordWrap(True)
        main_layout.addWidget(self.split_list_label)

        # ===== 进度标签 =====
        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: #888; font-size: 10px; padding: 2px;")
        main_layout.addWidget(self.progress_label)

        self._update_split_buttons()
        self._update_split_display()

    # ============================================================
    # 公共接口
    # ============================================================

    def set_video(self, video_path: str, duration: float, temp_dir: str):
        self.video_path = video_path
        self.duration = duration
        self.temp_dir = temp_dir
        self.controller.set_video(video_path, duration, temp_dir)

        self._pending_time = 0.0
        self._is_dragging = False

        self.duration_label.setText(self._format_time(duration))
        self.position_label.setText("00:00:00")
        self.slider.setValue(0)
        self.preview_label.setText("加载预览中...")

        self._update_preview(0.0)
        self.clear_range()
        self.clear_split_points()
        self._update_split_buttons()

        # 强制布局更新
        if self.layout():
            self.layout().activate()
            self.updateGeometry()
            self.repaint()

    def show_panel(self):
        logger.info(f"[PreviewPanel] show_panel 被调用，当前宽度: {self.width()}")
        # 强制设置最小宽度，确保布局有足够空间
        self.setMinimumWidth(400)
        self.setVisible(True)
        # 立即强制布局
        if self.layout():
            self.layout().activate()
            self.updateGeometry()
            self.repaint()
        logger.info(f"[PreviewPanel] show_panel 设置可见后，宽度: {self.width()}")

    def hide_panel(self):
        self.setVisible(False)

    def is_visible(self) -> bool:
        return self.isVisible()

    # ============================================================
    # 事件重写
    # ============================================================

    def resizeEvent(self, event: QResizeEvent):
        old_w = event.oldSize().width()
        new_w = event.size().width()
        logger.info(f"[PreviewPanel] resizeEvent: {old_w} -> {new_w}")
        super().resizeEvent(event)
        if self.layout() and new_w > 50:
            self.layout().activate()
            self.updateGeometry()

    # ============================================================
    # 内部方法
    # ============================================================

    def _format_time(self, seconds: float) -> str:
        if seconds < 0:
            seconds = 0
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _update_preview(self, time_sec: float):
        if not self.video_path:
            return

        time_sec = max(0, min(self.duration, time_sec))
        self.position_label.setText(self._format_time(time_sec))

        if not self._is_dragging:
            slider_val = int((time_sec / self.duration) * 10000) if self.duration > 0 else 0
            self.slider.blockSignals(True)
            self.slider.setValue(slider_val)
            self.slider.blockSignals(False)

        frame_path = self.controller.set_preview_time(time_sec)

        if frame_path and os.path.exists(frame_path):
            pixmap = QPixmap(frame_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.preview_label.width() - 4,
                    self.preview_label.height() - 4,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.preview_label.setPixmap(scaled)
                return

        self.preview_label.setText("无法加载预览帧")

    def _on_slider_pressed(self):
        self._is_dragging = True
        self._slider_update_timer.stop()

    def _on_slider_released(self):
        self._is_dragging = False
        if self._pending_time >= 0:
            self._update_preview(self._pending_time)

    def _on_slider_value_changed(self, value: int):
        if self.duration <= 0:
            return

        time_sec = (value / 10000) * self.duration
        self._pending_time = time_sec
        self.position_label.setText(self._format_time(time_sec))

        if self._is_dragging:
            frame_path = self.controller._get_frame(time_sec)
            if frame_path and os.path.exists(frame_path):
                pixmap = QPixmap(frame_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        self.preview_label.width() - 4,
                        self.preview_label.height() - 4,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    self.preview_label.setPixmap(scaled)
            self._slider_update_timer.start(150)
        else:
            self._update_preview(time_sec)

    def _on_slider_timeout(self):
        if self._pending_time >= 0:
            self._update_preview(self._pending_time)

    def _on_progress_update(self, message: str):
        self.progress_label.setText(message)

    # ============================================================
    # 片段操作
    # ============================================================

    def set_start(self):
        if not self.video_path:
            QMessageBox.information(self, "提示", "请先加载视频")
            return

        time_sec = self._pending_time
        self.controller.set_start_time(time_sec)
        self._update_range_display()

        QMessageBox.information(self, "完成", f"已设置起始点: {self._format_time(time_sec)}")

    def set_end(self):
        if not self.video_path:
            QMessageBox.information(self, "提示", "请先加载视频")
            return

        time_sec = self._pending_time
        self.controller.set_end_time(time_sec)
        self._update_range_display()

        QMessageBox.information(self, "完成", f"已设置结束点: {self._format_time(time_sec)}")

    def clear_range(self):
        self.controller.clear_range()
        self._update_range_display()
        self.export_btn.setEnabled(False)

    def _update_range_display(self):
        start, end = self.controller.get_range()
        if self.controller.is_range_valid():
            self.range_label.setText(
                f"🎯 范围: {self._format_time(start)} → {self._format_time(end)}  "
                f"(时长: {end - start:.1f}s)"
            )
            self.range_label.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: bold;")
            self.export_btn.setEnabled(True)
        else:
            self.range_label.setText("🎯 在时间轴上拖动浏览，点击按钮设置片段范围")
            self.range_label.setStyleSheet("color: #666; font-size: 11px;")
            self.export_btn.setEnabled(False)

    def export_clip(self):
        if not self.video_path:
            QMessageBox.warning(self, "警告", "未加载视频")
            return

        if not self.controller.is_range_valid():
            QMessageBox.warning(self, "警告", "请先设置有效的片段范围（起始 < 结束）")
            return

        start, end = self.controller.get_range()
        if end - start < 0.5:
            QMessageBox.warning(self, "警告", f"片段太短（{end - start:.1f}s），请选择至少 0.5 秒")
            return

        reply = QMessageBox.question(
            self,
            "确认导出片段",
            f"将导出从 {self._format_time(start)} 到 {self._format_time(end)} 的片段\n"
            f"时长: {end - start:.1f} 秒\n\n"
            f"文件将保存到 CoverPicker/Clips/ 文件夹。\n\n继续吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_file_dir))
        clips_dir = os.path.join(project_root, "Clips")
        os.makedirs(clips_dir, exist_ok=True)

        self.export_btn.setEnabled(False)
        self.export_btn.setText("⏳ 导出中...")

        async def do_export():
            success, result = await self.controller.export_clip(clips_dir, re_encode=False)
            self.export_btn.setEnabled(True)
            self.export_btn.setText("📥 导出片段")

            if success:
                QMessageBox.information(self, "导出完成", f"片段已导出到:\n{result}")
                self.export_clip_requested.emit(result)
            else:
                QMessageBox.warning(self, "导出失败", result)

        asyncio.create_task(do_export())

    # ============================================================
    # 分割点管理
    # ============================================================

    def add_split_point(self):
        if not self.video_path:
            QMessageBox.information(self, "提示", "请先加载视频")
            return

        time_sec = self._pending_time
        if time_sec <= 0.1 or time_sec >= self.duration - 0.1:
            QMessageBox.warning(self, "提示", "不能在视频起点或终点附近添加分割点")
            return

        for existing in self.split_points:
            if abs(existing - time_sec) < 0.5:
                QMessageBox.information(self, "提示", f"已存在相近的分割点 {self._format_time(existing)}")
                return

        self.split_points.append(time_sec)
        self.split_points.sort()
        self._update_split_display()
        QMessageBox.information(self, "完成", f"已添加分割点: {self._format_time(time_sec)}")

    def clear_split_points(self):
        if not self.split_points:
            return
        self.split_points.clear()
        self._update_split_display()
        QMessageBox.information(self, "提示", "已清除所有分割点")

    def _clear_split_points_silent(self):
        self.split_points.clear()
        self._update_split_display()

    def apply_split_points(self):
        if not self.video_path:
            QMessageBox.information(self, "提示", "请先加载视频")
            return

        if len(self.split_points) < 1:
            QMessageBox.warning(self, "提示", "请至少添加一个分割点")
            return

        controller = self.main_controller
        if not controller:
            parent = self.parent()
            while parent:
                if hasattr(parent, 'controller'):
                    controller = parent.controller
                    break
                parent = parent.parent()

        if not controller:
            QMessageBox.warning(self, "警告", "无法找到主控制器")
            return

        points = [0.0] + self.split_points + [self.duration]
        points = sorted(set(points))
        filtered = []
        for p in points:
            if not filtered or p - filtered[-1] >= 0.5:
                filtered.append(p)
        if filtered[0] != 0.0:
            filtered.insert(0, 0.0)
        if filtered[-1] != self.duration:
            filtered.append(self.duration)

        segments = []
        for i in range(len(filtered) - 1):
            label = chr(ord('A') + i)
            segments.append((label, filtered[i], filtered[i+1]))

        controller.num_segments = -1
        controller.segments = segments
        controller.screenshots = {}
        controller.loaded_segments = set()
        controller.current_seg_index = 0
        controller._notify_data_changed()

        if controller.video_path:
            asyncio.create_task(controller.load_segment(0, restore_locks=True, randomize=False))

        QMessageBox.information(self, "完成", f"已应用自定义分区，共 {len(segments)} 个区")
        self._clear_split_points_silent()

    def _update_split_display(self):
        if self.split_points:
            times_str = ", ".join([self._format_time(t) for t in self.split_points])
            self.split_list_label.setText(f"分割点 ({len(self.split_points)}): {times_str}")
            self.split_list_label.setStyleSheet("color: #FF9800; font-size: 10px;")
            self.clear_splits_btn.setEnabled(True)
            self.apply_splits_btn.setEnabled(True)
        else:
            self.split_list_label.setText("分割点: 无")
            self.split_list_label.setStyleSheet("color: #888; font-size: 10px;")
            self.clear_splits_btn.setEnabled(False)
            self.apply_splits_btn.setEnabled(False)

    def _update_split_buttons(self):
        enabled = self.video_path is not None
        self.add_split_btn.setEnabled(enabled)