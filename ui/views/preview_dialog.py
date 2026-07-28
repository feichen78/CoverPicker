# ui/views/preview_dialog.py
# v3.0.2: 300ms 防抖 + 低质量预览帧 (640x360)
# v3.2: GIF导出 + 片段夹/GIF夹 + 目录记忆
# v3.2.3: 使用 Signal 跨线程通知主线程（官方推荐方式）
# v3.2.4: 增加调试日志，确认执行路径
# v3.2.6: 将调试 print 改为 logger.debug (O1)

import os
import asyncio
import logging
import subprocess
from typing import Optional, List
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSlider, QSizePolicy, QMessageBox, QWidget, QFileDialog,
    QComboBox, QDialogButtonBox, QFormLayout
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap, QFont, QResizeEvent

from src.controllers.preview_controller import PreviewController

logger = logging.getLogger(__name__)


class GIFExportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("导出 GIF")
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["5", "10", "15", "24"])
        self.fps_combo.setCurrentIndex(1)
        form_layout.addRow("帧率 (fps):", self.fps_combo)

        self.size_combo = QComboBox()
        self.size_combo.addItems(["原尺寸", "50%", "25%"])
        self.size_combo.setCurrentIndex(0)
        form_layout.addRow("尺寸:", self.size_combo)

        self.loop_combo = QComboBox()
        self.loop_combo.addItems(["1", "3", "5", "无限"])
        self.loop_combo.setCurrentIndex(3)
        form_layout.addRow("循环次数:", self.loop_combo)

        layout.addLayout(form_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_params(self):
        fps = int(self.fps_combo.currentText())
        size_text = self.size_combo.currentText()
        if size_text == "原尺寸":
            scale = 1.0
        elif size_text == "50%":
            scale = 0.5
        else:
            scale = 0.25

        loop_text = self.loop_combo.currentText()
        if loop_text == "无限":
            loop = 0
        else:
            loop = int(loop_text)

        return fps, scale, loop


class PreviewDialog(QDialog):
    export_clip_requested = Signal(str)
    gif_export_finished = Signal(bool, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🎬 视频预览")
        self.setMinimumSize(500, 500)
        self.resize(900, 700)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)

        self.controller = PreviewController()
        self.controller.set_progress_callback(self._on_progress_update)

        self.main_controller = None

        self.duration: float = 0.0
        self.video_path: Optional[str] = None
        self.temp_dir: Optional[str] = None

        self._slider_update_timer = QTimer()
        self._slider_update_timer.setSingleShot(True)
        self._slider_update_timer.timeout.connect(self._on_slider_timeout)

        self._pending_time: float = 0.0
        self._is_dragging: bool = False

        self.split_points: List[float] = []

        self.gif_export_finished.connect(self._on_gif_export_finished)

        self.setup_ui()
        self._update_split_buttons()
        self._update_split_display()

    def set_main_controller(self, controller):
        self.main_controller = controller

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        self.preview_label = QLabel("选择视频后预览")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(250)
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_label.setStyleSheet("""
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 4px;
            color: #666;
            font-size: 16px;
        """)
        self.preview_label.setScaledContents(False)
        main_layout.addWidget(self.preview_label, 1)

        time_info_layout = QHBoxLayout()
        self.position_label = QLabel("00:00:00")
        self.position_label.setFont(QFont("monospace", 13))
        self.position_label.setStyleSheet("color: #888; font-size: 13px;")
        time_info_layout.addWidget(self.position_label)
        time_info_layout.addStretch()
        self.duration_label = QLabel("00:00:00")
        self.duration_label.setFont(QFont("monospace", 13))
        self.duration_label.setStyleSheet("color: #888; font-size: 13px;")
        time_info_layout.addWidget(self.duration_label)
        main_layout.addLayout(time_info_layout)

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

        self.tick_container = QWidget()
        self.tick_container.setFixedHeight(20)
        self.tick_container.setStyleSheet("background: transparent;")
        self.tick_labels = []
        tick_style = "color: #666; background: transparent; font-size: 13px; font-family: Arial;"
        for i in range(5):
            label = QLabel(self.tick_container)
            label.setStyleSheet(tick_style)
            label.setAlignment(Qt.AlignCenter)
            label.setFixedHeight(16)
            self.tick_labels.append(label)
        main_layout.addWidget(self.tick_container)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        self.split_list_label = QLabel("分割点: 无")
        self.split_list_label.setStyleSheet("color: #FF9800; font-size: 13px; font-family: Arial; font-weight: bold;")
        self.split_list_label.setWordWrap(False)
        btn_layout.addWidget(self.split_list_label)

        self.add_split_btn = QPushButton("添加分割点")
        self.add_split_btn.setStyleSheet("""
            QPushButton {
                font-size: 13px;
                font-family: Arial;
                background: #FF9800;
                color: white;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover { background: #F57C00; }
            QPushButton:disabled { background: #555; color: #888; }
        """)
        self.add_split_btn.clicked.connect(self.add_split_point)
        btn_layout.addWidget(self.add_split_btn)

        self.clear_splits_btn = QPushButton("删除分割点")
        self.clear_splits_btn.setStyleSheet("""
            QPushButton {
                font-size: 13px;
                font-family: Arial;
                background: #e74c3c;
                color: white;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover { background: #c0392b; }
            QPushButton:disabled { background: #555; color: #888; }
        """)
        self.clear_splits_btn.clicked.connect(self.clear_split_points)
        btn_layout.addWidget(self.clear_splits_btn)

        self.apply_splits_btn = QPushButton("应用分区")
        self.apply_splits_btn.setStyleSheet("""
            QPushButton {
                font-size: 13px;
                font-family: Arial;
                background: #9C27B0;
                color: white;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover { background: #7B1FA2; }
            QPushButton:disabled { background: #555; color: #888; }
        """)
        self.apply_splits_btn.clicked.connect(self.apply_split_points)
        btn_layout.addWidget(self.apply_splits_btn)

        self.set_start_btn = QPushButton("设起始")
        self.set_start_btn.setStyleSheet("""
            QPushButton {
                font-size: 13px;
                font-family: Arial;
                background: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover { background: #43a047; }
            QPushButton:disabled { background: #555; color: #888; }
        """)
        self.set_start_btn.clicked.connect(self.set_start)
        btn_layout.addWidget(self.set_start_btn)

        self.set_end_btn = QPushButton("设结束")
        self.set_end_btn.setStyleSheet("""
            QPushButton {
                font-size: 13px;
                font-family: Arial;
                background: #f44336;
                color: white;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover { background: #d32f2f; }
            QPushButton:disabled { background: #555; color: #888; }
        """)
        self.set_end_btn.clicked.connect(self.set_end)
        btn_layout.addWidget(self.set_end_btn)

        self.clear_range_btn = QPushButton("清除")
        self.clear_range_btn.setStyleSheet("""
            QPushButton {
                font-size: 13px;
                font-family: Arial;
                background: #666;
                color: white;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover { background: #888; }
        """)
        self.clear_range_btn.clicked.connect(self.clear_range)
        btn_layout.addWidget(self.clear_range_btn)

        self.export_btn = QPushButton("导出片段")
        self.export_btn.setEnabled(False)
        self.export_btn.setStyleSheet("""
            QPushButton {
                font-size: 13px;
                font-family: Arial;
                background: #2196F3;
                color: white;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover { background: #1976D2; }
            QPushButton:disabled { background: #555; color: #888; }
        """)
        self.export_btn.clicked.connect(self.export_clip)
        btn_layout.addWidget(self.export_btn)

        self.open_clip_folder_btn = QPushButton("📁 片段夹")
        self.open_clip_folder_btn.setEnabled(False)
        self.open_clip_folder_btn.setStyleSheet("""
            QPushButton {
                font-size: 13px;
                font-family: Arial;
                background: #607D8B;
                color: white;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover { background: #455A64; }
            QPushButton:disabled { background: #555; color: #888; }
        """)
        self.open_clip_folder_btn.clicked.connect(self.open_clip_folder)
        btn_layout.addWidget(self.open_clip_folder_btn)

        self.export_gif_btn = QPushButton("导出GIF")
        self.export_gif_btn.setEnabled(False)
        self.export_gif_btn.setStyleSheet("""
            QPushButton {
                font-size: 13px;
                font-family: Arial;
                background: #FF5722;
                color: white;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover { background: #E64A19; }
            QPushButton:disabled { background: #555; color: #888; }
        """)
        self.export_gif_btn.clicked.connect(self.export_gif)
        btn_layout.addWidget(self.export_gif_btn)

        self.open_gif_folder_btn = QPushButton("📁 GIF夹")
        self.open_gif_folder_btn.setEnabled(False)
        self.open_gif_folder_btn.setStyleSheet("""
            QPushButton {
                font-size: 13px;
                font-family: Arial;
                background: #FF8A65;
                color: white;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover { background: #E64A19; }
            QPushButton:disabled { background: #555; color: #888; }
        """)
        self.open_gif_folder_btn.clicked.connect(self.open_gif_folder)
        btn_layout.addWidget(self.open_gif_folder_btn)

        main_layout.addLayout(btn_layout)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: #888; font-size: 13px; font-family: Arial; padding: 2px;")
        main_layout.addWidget(self.progress_label)

        self.finished.connect(self.on_closed)

    def on_closed(self):
        parent = self.parent()
        if parent and hasattr(parent, 'preview_toggle_btn'):
            parent.preview_toggle_btn.setChecked(False)

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

        self._update_ticks()
        self._update_preview(0.0)
        self.clear_range()
        self.clear_split_points()
        self._update_split_buttons()
        self.export_gif_btn.setEnabled(True)
        self.open_clip_folder_btn.setEnabled(True)
        self.open_gif_folder_btn.setEnabled(True)
        QTimer.singleShot(50, self._update_tick_positions)

    def _update_ticks(self):
        if self.duration <= 0:
            for label in self.tick_labels:
                label.setText("")
                label.adjustSize()
            return

        positions = [0, 0.25, 0.5, 0.75, 1.0]
        for i, pos in enumerate(positions):
            time_sec = pos * self.duration
            if i < len(self.tick_labels):
                self.tick_labels[i].setText(self._format_time(time_sec))
                self.tick_labels[i].adjustSize()
        self._update_tick_positions()

    def _update_tick_positions(self):
        container_width = self.tick_container.width()
        if container_width < 50:
            return

        margin = 15
        available_width = container_width - margin * 2
        positions = [0, 0.25, 0.5, 0.75, 1.0]
        for i, pos in enumerate(positions):
            if i >= len(self.tick_labels):
                break
            label = self.tick_labels[i]
            x = margin + pos * available_width - label.width() // 2
            y = 0
            if x < 0:
                x = 0
            if x + label.width() > container_width:
                x = container_width - label.width()
            label.move(x, y)

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
            self._slider_update_timer.start(300)
        else:
            self._update_preview(time_sec)

    def _on_slider_timeout(self):
        if self._pending_time >= 0:
            self._update_preview(self._pending_time)

    def _on_progress_update(self, message: str):
        self.progress_label.setText(message)

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
            self.export_btn.setEnabled(True)
        else:
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

        default_dir = os.path.expanduser("~")
        if hasattr(self, 'main_controller') and self.main_controller:
            config = getattr(self.main_controller, '_config', None)
            if config and hasattr(config, 'get_last_export_dir'):
                default_dir = config.get_last_export_dir() or default_dir

        export_dir = QFileDialog.getExistingDirectory(
            self,
            "选择导出目录",
            default_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if not export_dir:
            return

        if hasattr(self, 'main_controller') and self.main_controller:
            config = getattr(self.main_controller, '_config', None)
            if config and hasattr(config, 'set_last_export_dir'):
                config.set_last_export_dir(export_dir)

        reply = QMessageBox.question(
            self,
            "确认导出片段",
            f"将导出从 {self._format_time(start)} 到 {self._format_time(end)} 的片段\n"
            f"时长: {end - start:.1f} 秒\n\n"
            f"文件将保存到:\n{export_dir}\n\n继续吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.export_btn.setEnabled(False)
        self.export_btn.setText("⏳ 导出中...")

        async def do_export():
            success, result = await self.controller.export_clip(export_dir, re_encode=False)
            self.export_btn.setEnabled(True)
            self.export_btn.setText("导出片段")
            if success:
                QMessageBox.information(self, "导出完成", f"片段已导出到:\n{result}")
                self.export_clip_requested.emit(result)
            else:
                QMessageBox.warning(self, "导出失败", result)

        asyncio.create_task(do_export())

    def open_clip_folder(self):
        config = self.main_controller._config if self.main_controller and hasattr(self.main_controller, '_config') else None
        target_dir = config.get_last_export_dir() if config else None
        if not target_dir or not os.path.exists(target_dir):
            QMessageBox.information(self, "提示", "尚未导出过片段或截图，目录不存在。")
            return
        try:
            os.startfile(target_dir)
        except AttributeError:
            import subprocess
            subprocess.Popen(["open", target_dir])
        except Exception as e:
            QMessageBox.warning(self, "无法打开目录", f"打开目录失败:\n{e}")

    def open_gif_folder(self):
        config = self.main_controller._config if self.main_controller and hasattr(self.main_controller, '_config') else None
        target_dir = config.get_last_gif_export_dir() if config else None
        if not target_dir or not os.path.exists(target_dir):
            QMessageBox.information(self, "提示", "尚未导出过GIF，目录不存在。")
            return
        try:
            os.startfile(target_dir)
        except AttributeError:
            import subprocess
            subprocess.Popen(["open", target_dir])
        except Exception as e:
            QMessageBox.warning(self, "无法打开目录", f"打开目录失败:\n{e}")

    def export_gif(self):
        if not self.video_path:
            QMessageBox.warning(self, "警告", "未加载视频")
            return

        if not self.controller.is_range_valid():
            QMessageBox.warning(self, "警告", "请先设置有效的片段范围（起始 < 结束）")
            return

        start, end = self.controller.get_range()
        duration = end - start
        if duration < 0.5:
            QMessageBox.warning(self, "警告", f"片段太短（{duration:.1f}s），请选择至少 0.5 秒")
            return

        clip_duration = duration
        clip_start = start
        if duration > 30.0:
            reply = QMessageBox.question(
                self,
                "片段超长",
                f"当前片段长度为 {duration:.1f} 秒，GIF 导出最长支持 30 秒。\n将自动裁剪前 30 秒。是否继续？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
            clip_duration = 30.0

        dlg = GIFExportDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        fps, scale, loop = dlg.get_params()

        config = self.main_controller._config if self.main_controller and hasattr(self.main_controller, '_config') else None
        default_dir = config.get_last_gif_export_dir() if config else None
        if not default_dir:
            default_dir = os.path.expanduser("~")

        video_name = os.path.splitext(os.path.basename(self.video_path))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"{video_name}_clip_{timestamp}.gif"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存 GIF",
            os.path.join(default_dir, default_filename),
            "GIF 文件 (*.gif)"
        )
        if not save_path:
            return

        save_dir = os.path.dirname(save_path)
        if config:
            config.set_last_gif_export_dir(save_dir)

        if scale == 1.0:
            scale_filter = f"fps={fps}"
        else:
            scale_expr = f"iw*{scale}:ih*{scale}"
            scale_filter = f"fps={fps},scale={scale_expr}"

        if loop == 0:
            loop_filter = "loop=-1:size=32767"
        else:
            loop_filter = f"loop={loop}:size={int(fps * clip_duration)}"

        cmd = [
            "ffmpeg", "-hide_banner",
            "-ss", str(clip_start),
            "-i", self.video_path,
            "-t", str(clip_duration),
            "-vf", f"{scale_filter},{loop_filter}",
            "-y", save_path
        ]

        self.export_gif_btn.setEnabled(False)
        self.export_gif_btn.setText("⏳ 生成中...")
        self.progress_label.setText("正在生成 GIF...")
        logger.debug("[GIF调试] 开始导出，按钮已禁用，进度标签已设置")

        def run_ffmpeg():
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='ignore',
                    timeout=180,
                    creationflags=0x08000000 if os.name == 'nt' else 0
                )
                logger.debug(f"[GIF调试] FFmpeg 完成, returncode={result.returncode}")
                return result.returncode == 0, result.stderr
            except subprocess.TimeoutExpired:
                logger.debug("[GIF调试] FFmpeg 超时")
                return False, "FFmpeg 超时"
            except Exception as e:
                logger.debug(f"[GIF调试] FFmpeg 异常: {e}")
                return False, str(e)

        import threading

        def do_export():
            success, error = run_ffmpeg()
            logger.debug(f"[GIF调试] do_export: success={success}, error={error[:100] if error else 'None'}")
            logger.debug("[GIF调试] 准备发射 gif_export_finished 信号")
            self.gif_export_finished.emit(success, error, save_path)
            logger.debug("[GIF调试] 信号已发射")

        threading.Thread(target=do_export, daemon=True).start()

    def _on_gif_export_finished(self, success: bool, error: str, save_path: str):
        logger.debug(f"[GIF调试] _on_gif_export_finished 被调用, success={success}")
        self.export_gif_btn.setEnabled(True)
        self.export_gif_btn.setText("导出GIF")
        self.progress_label.setText("")
        if success:
            self.progress_label.setText(f"✅ GIF 已保存: {os.path.basename(save_path)}")
            QMessageBox.information(self, "导出完成", f"GIF 已保存到:\n{save_path}")
            logger.debug("[GIF调试] 导出成功，提示框已显示")
        else:
            QMessageBox.warning(self, "导出失败", f"GIF 导出失败:\n{error}")
            logger.debug("[GIF调试] 导出失败")

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
            times_str = " ".join([f"{self._format_time(t)}" for t in self.split_points])
            self.split_list_label.setText(f"分割点: {times_str}")
            self.split_list_label.setStyleSheet("color: #FF9800; font-size: 13px; font-family: Arial; font-weight: bold;")
            self.clear_splits_btn.setEnabled(True)
            self.apply_splits_btn.setEnabled(True)
        else:
            self.split_list_label.setText("分割点: 无")
            self.split_list_label.setStyleSheet("color: #888; font-size: 13px; font-family: Arial;")
            self.clear_splits_btn.setEnabled(False)
            self.apply_splits_btn.setEnabled(False)

    def _update_split_buttons(self):
        enabled = self.video_path is not None
        self.add_split_btn.setEnabled(enabled)
        self.export_gif_btn.setEnabled(enabled)
        self.open_clip_folder_btn.setEnabled(enabled)
        self.open_gif_folder_btn.setEnabled(enabled)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        if self.layout() and self.width() > 50:
            self.layout().activate()
            if hasattr(self, '_pending_time') and self._pending_time >= 0:
                self._update_preview(self._pending_time)
            self._update_tick_positions()