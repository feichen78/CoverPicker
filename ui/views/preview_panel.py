# ui/views/preview_panel.py

import os
import asyncio
import logging
from typing import Optional, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSlider, QFrame, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap, QFont, QColor

from src.controllers.preview_controller import PreviewController

logger = logging.getLogger(__name__)


class PreviewPanel(QWidget):
    """右侧预览面板 - 视频帧预览 + 时间轴片段选择"""

    export_clip_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)

        self.controller = PreviewController()
        self.controller.set_progress_callback(self._on_progress_update)

        self.duration: float = 0.0
        self.video_path: Optional[str] = None
        self.temp_dir: Optional[str] = None

        self._slider_update_timer = QTimer()
        self._slider_update_timer.setSingleShot(True)
        self._slider_update_timer.timeout.connect(self._on_slider_timeout)

        self._pending_time: float = 0.0
        self._is_dragging: bool = False

        self.setup_ui()
        self.setFixedWidth(360)
        self.setMinimumHeight(400)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        title_layout = QHBoxLayout()

        title_label = QLabel("🎬 视频预览")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("QPushButton { border: none; font-size: 14px; } QPushButton:hover { background: #e74c3c; color: white; border-radius: 4px; }")
        close_btn.clicked.connect(self.hide_panel)
        title_layout.addWidget(close_btn)

        main_layout.addLayout(title_layout)

        self.preview_label = QLabel("选择视频后预览")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(240)
        self.preview_label.setStyleSheet("""
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 4px;
            color: #666;
            font-size: 14px;
        """)
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(self.preview_label, 1)

        time_info_layout = QHBoxLayout()

        self.position_label = QLabel("00:00:00")
        self.position_label.setFont(QFont("monospace", 11))
        self.position_label.setStyleSheet("color: #888;")
        time_info_layout.addWidget(self.position_label)

        time_info_layout.addStretch()

        self.duration_label = QLabel("00:00:00")
        self.duration_label.setFont(QFont("monospace", 11))
        self.duration_label.setStyleSheet("color: #888;")
        time_info_layout.addWidget(self.duration_label)

        main_layout.addLayout(time_info_layout)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 10000)
        self.slider.setValue(0)
        self.slider.setTracking(True)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: #3a3a3a;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #2196F3;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
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

        range_layout = QHBoxLayout()

        range_info_text = "🎯 在时间轴上拖动浏览，点击下方按钮设置片段范围"
        self.range_label = QLabel(range_info_text)
        self.range_label.setStyleSheet("color: #666; font-size: 10px;")
        range_layout.addWidget(self.range_label)

        main_layout.addLayout(range_layout)

        marker_layout = QHBoxLayout()

        start_marker = QLabel("● 起始")
        start_marker.setStyleSheet("color: #4CAF50; font-size: 10px;")
        marker_layout.addWidget(start_marker)

        marker_layout.addStretch()

        end_marker = QLabel("● 结束")
        end_marker.setStyleSheet("color: #f44336; font-size: 10px;")
        marker_layout.addWidget(end_marker)

        main_layout.addLayout(marker_layout)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self.set_start_btn = QPushButton("📍 设起始")
        self.set_start_btn.setStyleSheet("background: #4CAF50; color: white; font-weight: bold; padding: 6px;")
        self.set_start_btn.clicked.connect(self.set_start)
        btn_layout.addWidget(self.set_start_btn)

        self.set_end_btn = QPushButton("📍 设结束")
        self.set_end_btn.setStyleSheet("background: #f44336; color: white; font-weight: bold; padding: 6px;")
        self.set_end_btn.clicked.connect(self.set_end)
        btn_layout.addWidget(self.set_end_btn)

        self.clear_range_btn = QPushButton("✕ 清除")
        self.clear_range_btn.clicked.connect(self.clear_range)
        btn_layout.addWidget(self.clear_range_btn)

        btn_layout.addStretch()

        self.export_btn = QPushButton("📥 导出片段")
        self.export_btn.setStyleSheet("background: #2196F3; color: white; font-weight: bold; padding: 8px 16px;")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_clip)
        btn_layout.addWidget(self.export_btn)

        main_layout.addLayout(btn_layout)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: #888; font-size: 10px;")
        main_layout.addWidget(self.progress_label)

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

    def show_panel(self):
        self.setVisible(True)

    def hide_panel(self):
        self.setVisible(False)

    def is_visible(self) -> bool:
        return self.isVisible()

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
            self.range_label.setStyleSheet("color: #4CAF50; font-size: 10px;")
            self.export_btn.setEnabled(True)
        else:
            self.range_label.setText("🎯 在时间轴上拖动浏览，点击按钮设置片段范围")
            self.range_label.setStyleSheet("color: #666; font-size: 10px;")
            self.export_btn.setEnabled(False)

    def export_clip(self):
        """导出视频片段到 CoverPicker/Clips/ 目录"""
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

        # 确认导出
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

        # 获取 CoverPicker 根目录（main.py 所在目录）
        # 从当前文件路径向上回溯到项目根目录
        current_file_dir = os.path.dirname(os.path.abspath(__file__))  # ui/views/
        project_root = os.path.dirname(os.path.dirname(current_file_dir))  # CoverPicker/
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