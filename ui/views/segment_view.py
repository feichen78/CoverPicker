# ui/views/segment_view.py

import os
import asyncio
import logging
import traceback
from typing import List, Set, Tuple
from functools import partial
from datetime import timedelta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGridLayout, QScrollArea, QFrame, QMessageBox, QApplication,
    QSplitter, QListWidget, QListWidgetItem, QSizePolicy, QComboBox,
    QLineEdit, QMenu, QFileDialog, QAbstractItemView
)
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QPixmap, QFont, QColor, QAction

from src.video_scanner import scan_videos, scan_videos_in_directory, get_video_duration
from src.controllers import SegmentController
from ui.views.zoom_dialog import ZoomDialog
from ui.views.zoom_preview import ZoomPreviewDialog
from ui.views.preview_dialog import PreviewDialog
from ui.views.exclude_dialog import ExcludeDialog
from ui.widgets import ClickableLabel
from ui.dialogs import FavoritesDialog

# 配置日志
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "coverpicker.log")
LOG_FILE = os.path.normpath(LOG_FILE)

log_dir = os.path.dirname(LOG_FILE)
if log_dir:
    os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SegmentView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        logger.info("=== SegmentView 初始化 ===")

        self.controller = SegmentController()
        self.controller.set_data_changed_callback(self._on_data_changed)
        self.controller.set_progress_callback(self._on_progress_update)

        self.selected_indices: Set[tuple] = set()
        self.all_videos: List[str] = []
        self.filtered_videos: List[str] = []

        self.seg_buttons_layout = QHBoxLayout()
        self.seg_buttons: List[QPushButton] = []

        self.preview_dialog = None

        db_videos = self.controller.db.get_all_videos()
        self.all_videos = [v['file_path'] for v in db_videos]
        self.filtered_videos = self.all_videos.copy()
        logger.info(f"从数据库加载了 {len(self.all_videos)} 个视频")

        self.setup_ui()
        self.setFocusPolicy(Qt.StrongFocus)

        self.video_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.video_list.customContextMenuRequested.connect(self._show_context_menu)
        self.video_list.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self._update_cache_info()

    # ============================================================
    # UI 构建
    # ============================================================

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===== 左侧面板 =====
        left_panel = QWidget()
        left_panel.setFixedWidth(220)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(4)

        # 标题栏
        title_layout = QHBoxLayout()
        title = QLabel("📹 视频库")
        title.setFont(QFont("Arial", 13, QFont.Bold))
        title_layout.addWidget(title)
        title_layout.addStretch()

        self.batch_delete_btn = QPushButton("🗑️")
        self.batch_delete_btn.setFixedSize(30, 30)
        self.batch_delete_btn.setToolTip("批量删除选中的视频（不删除文件）")
        self.batch_delete_btn.setEnabled(False)
        self.batch_delete_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #888;
                border-radius: 4px;
                background: transparent;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #e74c3c;
                color: white;
            }
            QPushButton:disabled {
                color: #666;
            }
        """)
        self.batch_delete_btn.clicked.connect(self.batch_remove_videos)
        title_layout.addWidget(self.batch_delete_btn)

        self.import_btn = QPushButton("+")
        self.import_btn.setFixedSize(30, 30)
        self.import_btn.setToolTip("导入视频")
        self.import_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #888;
                border-radius: 4px;
                background: transparent;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #3a3a3a;
                color: #2196F3;
            }
        """)
        self.import_btn.clicked.connect(self._show_import_menu)
        title_layout.addWidget(self.import_btn)

        self.preview_toggle_btn = QPushButton("🎬")
        self.preview_toggle_btn.setFixedSize(30, 30)
        self.preview_toggle_btn.setToolTip("打开/关闭预览窗口")
        self.preview_toggle_btn.setCheckable(True)
        self.preview_toggle_btn.setChecked(False)
        self.preview_toggle_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #888;
                border-radius: 4px;
                background: transparent;
                font-size: 14px;
            }
            QPushButton:checked {
                background: #2196F3;
                border-color: #2196F3;
                color: white;
            }
            QPushButton:hover {
                background: #3a3a3a;
            }
            QPushButton:checked:hover {
                background: #1a7ac4;
            }
        """)
        self.preview_toggle_btn.clicked.connect(self.toggle_preview_dialog)
        title_layout.addWidget(self.preview_toggle_btn)

        left_layout.addLayout(title_layout)

        # 搜索框
        search_layout = QHBoxLayout()
        search_layout.setSpacing(2)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索视频...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 4px 8px;
                border: 1px solid #555;
                border-radius: 4px;
                background: #2a2a2a;
                color: #eee;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #2196F3;
            }
        """)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        search_layout.addWidget(self.search_input)

        self.clear_search_btn = QPushButton("✕")
        self.clear_search_btn.setFixedSize(24, 24)
        self.clear_search_btn.setToolTip("清空搜索")
        self.clear_search_btn.setVisible(False)
        self.clear_search_btn.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 12px;
                background: #555;
                color: white;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #e74c3c;
            }
        """)
        self.clear_search_btn.clicked.connect(self._clear_search)
        search_layout.addWidget(self.clear_search_btn)
        left_layout.addLayout(search_layout)

        # 视频列表
        self.video_list = QListWidget()
        self.video_list.setFont(QFont("Arial", 10))
        self.video_list.setStyleSheet("""
            QListWidget::item { 
                padding: 3px 5px;
                border-radius: 2px;
            }
            QListWidget::item:selected {
                background: #2196F3;
                color: white;
            }
            QListWidget::item:hover {
                background: #3a3a3a;
            }
        """)
        self.video_list.itemDoubleClicked.connect(self.on_video_selected)
        self.video_list.itemSelectionChanged.connect(self._update_batch_delete_btn_state)
        self._refresh_video_list()
        left_layout.addWidget(self.video_list)

        # 信息组
        info_group = QFrame()
        info_group.setFrameShape(QFrame.StyledPanel)
        info_group.setStyleSheet("background: #f8f8f8; border-radius: 4px;")
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(1)

        self.info_name = QLabel("未选择")
        self.info_name.setFont(QFont("Arial", 10, QFont.Bold))
        self.info_name.setObjectName("info_name")
        info_layout.addWidget(self.info_name)

        self.info_duration = QLabel("时长: --")
        self.info_size = QLabel("大小: --")
        self.info_path = QLabel("路径: --")
        self.info_path.setWordWrap(True)
        self.info_path.setStyleSheet("font-size: 8px; color: #666;")

        info_layout.addWidget(self.info_duration)
        info_layout.addWidget(self.info_size)
        info_layout.addWidget(self.info_path)
        info_layout.addStretch()
        left_layout.addWidget(info_group)

        # 缓存大小标签
        self.cache_label = QLabel("缓存: --")
        self.cache_label.setStyleSheet("font-size: 9px; color: #888;")
        self.cache_label.setObjectName("cache_label")
        left_layout.addWidget(self.cache_label)

        # 进度标签
        self.progress_label_left = QLabel("")
        self.progress_label_left.setStyleSheet("color: #666; font-size: 13px; font-weight: bold; padding: 4px;")
        self.progress_label_left.setWordWrap(True)
        left_layout.addWidget(self.progress_label_left)

        # 统计行
        stat_layout = QHBoxLayout()
        self.stat_locked = QLabel("锁定: 0")
        self.stat_fav = QLabel("收藏: 0")
        stat_layout.addWidget(self.stat_locked)
        stat_layout.addWidget(self.stat_fav)
        left_layout.addLayout(stat_layout)
        left_layout.addStretch()

        # ===== 中间主工作区 =====
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(4)

        top_bar = QHBoxLayout()
        self.video_name_label = QLabel("请选择视频")
        self.video_name_label.setFont(QFont("Arial", 13, QFont.Bold))
        top_bar.addWidget(self.video_name_label)
        top_bar.addStretch()
        self.time_display = QLabel("00:00:00")
        self.time_display.setStyleSheet("font-family: monospace; font-size: 13px; color: #333;")
        top_bar.addWidget(self.time_display)
        right_layout.addLayout(top_bar)

        # 控制栏
        control_bar = QHBoxLayout()
        control_bar.setSpacing(6)

        seg_group = QHBoxLayout()
        seg_group.setSpacing(2)
        seg_group.setContentsMargins(0, 0, 0, 0)
        self.seg_buttons_layout = seg_group
        control_bar.addLayout(seg_group, 1)

        seg_count_label = QLabel("分区:")
        seg_count_label.setFont(QFont("Arial", 9))
        control_bar.addWidget(seg_count_label)

        self.seg_count_combo = QComboBox()
        self.seg_count_combo.setFixedWidth(44)
        self.seg_count_combo.setFont(QFont("Arial", 9))
        for i in range(3, 8):
            self.seg_count_combo.addItem(str(i), i)
        self.seg_count_combo.setCurrentIndex(self.seg_count_combo.findData(5))
        self.seg_count_combo.currentIndexChanged.connect(self.on_seg_count_changed)
        control_bar.addWidget(self.seg_count_combo)

        control_bar.addStretch()

        dens_label = QLabel("密度:")
        dens_label.setFont(QFont("Arial", 9))
        control_bar.addWidget(dens_label)

        self.density_buttons = []
        for d in [9, 12, 16, 25]:
            btn = QPushButton(str(d))
            btn.setCheckable(True)
            btn.setFixedSize(30, 24)
            btn.setFont(QFont("Arial", 8))
            if d == 9:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, val=d: self.on_density_changed(val))
            control_bar.addWidget(btn)
            self.density_buttons.append(btn)

        self.exclude_btn = QPushButton("⛔ 排除区间")
        self.exclude_btn.setToolTip("设置要排除的时间段（如片头片尾）")
        self.exclude_btn.setStyleSheet("""
            QPushButton {
                background: #666;
                color: white;
                font-weight: bold;
                padding: 2px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #888;
            }
        """)
        self.exclude_btn.clicked.connect(self.show_exclude_dialog)
        control_bar.addWidget(self.exclude_btn)

        right_layout.addLayout(control_bar)

        # 网格区域
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.grid_widget = QWidget()
        self.grid_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(4)
        self.grid_layout.setContentsMargins(2, 2, 2, 2)

        self.scroll.setWidget(self.grid_widget)
        right_layout.addWidget(self.scroll, 1)

        # 底部操作栏
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(6)

        self.selected_label = QLabel("已选: 0 张")
        bottom_bar.addWidget(self.selected_label)

        # 全选按钮（切换模式）
        self.select_all_btn = QPushButton("☑ 全选")
        self.select_all_btn.setCheckable(True)
        self.select_all_btn.setEnabled(False)
        self.select_all_btn.clicked.connect(self.toggle_select_all)
        bottom_bar.addWidget(self.select_all_btn)

        bottom_bar.addStretch()

        view_fav_btn = QPushButton("⭐ 查看收藏")
        view_fav_btn.clicked.connect(self.show_favorites)
        bottom_bar.addWidget(view_fav_btn)

        zoom_btn = QPushButton("🔍 细选")
        zoom_btn.clicked.connect(self.zoom_selected)
        zoom_btn.setStyleSheet("background: #2196F3; color: white; font-weight: bold;")
        bottom_bar.addWidget(zoom_btn)

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

        self.undo_btn = QPushButton("↩ 撤销")
        self.undo_btn.setEnabled(False)
        self.undo_btn.clicked.connect(self.undo_action)
        bottom_bar.addWidget(self.undo_btn)

        self.redo_btn = QPushButton("↪ 重做")
        self.redo_btn.setEnabled(False)
        self.redo_btn.clicked.connect(self.redo_action)
        bottom_bar.addWidget(self.redo_btn)

        clear_cache_btn = QPushButton("🗑️ 清理缓存")
        clear_cache_btn.clicked.connect(self.clear_cache)
        bottom_bar.addWidget(clear_cache_btn)

        right_layout.addLayout(bottom_bar)

        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)

        for btn in self.seg_buttons:
            btn.setEnabled(False)

    # ============================================================
    # 缓存信息更新
    # ============================================================

    def _update_cache_info(self):
        if hasattr(self, 'cache_label'):
            size_mb = self.controller.get_cache_size_mb()
            file_count = self.controller.get_cache_file_count()
            if size_mb > 1024:
                self.cache_label.setText(f"缓存: {size_mb/1024:.2f} GB ({file_count} 个文件)")
            else:
                self.cache_label.setText(f"缓存: {size_mb:.1f} MB ({file_count} 个文件)")

    # ============================================================
    # 排除区间对话框
    # ============================================================

    def show_exclude_dialog(self):
        dlg = ExcludeDialog(self.controller.excluded_ranges, self.controller.duration, self)
        if dlg.exec():
            new_ranges = dlg.get_ranges()
            self.controller.excluded_ranges = new_ranges
            if self.controller.get_video_path():
                asyncio.create_task(
                    self.controller.load_segment(
                        self.controller.current_seg_index,
                        restore_locks=True,
                        randomize=False
                    )
                )
            QMessageBox.information(self, "提示", "排除区间已更新，当前分区将重新生成。")

    # ============================================================
    # 批量删除
    # ============================================================

    def _update_batch_delete_btn_state(self):
        selected = self.video_list.selectedItems()
        self.batch_delete_btn.setEnabled(len(selected) > 0)

    def batch_remove_videos(self):
        selected_items = self.video_list.selectedItems()
        if not selected_items:
            return

        video_paths = [item.data(Qt.UserRole) for item in selected_items if item.data(Qt.UserRole)]
        if not video_paths:
            return

        count = len(video_paths)
        reply = QMessageBox.question(
            self,
            "确认批量删除",
            f"确定要从视频库中移除选中的 {count} 个视频吗？\n\n"
            "此操作仅删除数据库记录和列表条目，不会删除视频文件本身。",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        removed = 0
        failed = []
        current_path = self.controller.get_video_path()

        for video_path in video_paths:
            success = self.controller.remove_video(video_path)
            if success:
                removed += 1
                if video_path in self.all_videos:
                    self.all_videos.remove(video_path)
                if video_path in self.filtered_videos:
                    self.filtered_videos.remove(video_path)
            else:
                failed.append(os.path.basename(video_path))

        if current_path and current_path not in self.all_videos:
            self.video_name_label.setText("请选择视频")
            self.info_name.setText("未选择")
            self.info_duration.setText("时长: --")
            self.info_size.setText("大小: --")
            self.info_path.setText("路径: --")
            self._refresh_grid()
            for btn in self.seg_buttons:
                btn.setEnabled(False)
            if self.preview_dialog and self.preview_dialog.isVisible():
                self.preview_dialog.close()

        self._refresh_video_list()
        self._update_batch_delete_btn_state()

        if failed:
            QMessageBox.warning(
                self,
                "批量删除完成",
                f"成功删除 {removed} 个视频。\n"
                f"删除失败 {len(failed)} 个:\n" + "\n".join(failed)
            )
        else:
            QMessageBox.information(
                self,
                "批量删除完成",
                f"成功删除 {removed} 个视频。"
            )

    # ============================================================
    # 预览对话框控制
    # ============================================================

    def toggle_preview_dialog(self):
        if self.preview_dialog is None:
            self.preview_dialog = PreviewDialog(self)
            self.preview_dialog.set_main_controller(self.controller)
            self.preview_dialog.export_clip_requested.connect(self._on_clip_exported)
            self.preview_dialog.finished.connect(lambda: self.preview_toggle_btn.setChecked(False))
            if self.controller.get_video_path():
                self.preview_dialog.set_video(
                    self.controller.get_video_path(),
                    self.controller.get_duration(),
                    self.controller.get_temp_dir()
                )

        if self.preview_dialog.isVisible():
            self.preview_dialog.hide()
            self.preview_toggle_btn.setChecked(False)
        else:
            self.preview_dialog.show()
            self.preview_toggle_btn.setChecked(True)
            if self.controller.get_video_path():
                self.preview_dialog.set_video(
                    self.controller.get_video_path(),
                    self.controller.get_duration(),
                    self.controller.get_temp_dir()
                )

    def _on_clip_exported(self, output_path: str):
        pass

    # ============================================================
    # 导入功能
    # ============================================================

    def _show_import_menu(self):
        menu = QMenu(self)
        action_files = QAction("📄 导入视频文件", self)
        action_files.triggered.connect(self._import_video_files)
        menu.addAction(action_files)

        action_folder = QAction("📁 导入文件夹", self)
        action_folder.triggered.connect(self._import_folder)
        menu.addAction(action_folder)

        menu.exec(self.import_btn.mapToGlobal(self.import_btn.rect().bottomLeft()))

    def _import_video_files(self):
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("选择视频文件")
        file_dialog.setNameFilter(
            "视频文件 (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.mpg *.mpeg *.ts *.m2ts *.3gp *.asf *.vob *.ogv *.ogg *.divx *.xvid *.mts *.m2v *.m4p *.m4b *.m4r *.mpv *.mpe *.mxf *.rm *.rmvb *.swf *.f4v)"
        )
        file_dialog.setFileMode(QFileDialog.ExistingFiles)

        if file_dialog.exec():
            files = file_dialog.selectedFiles()
            if files:
                self._add_videos(files)

    def _import_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择包含视频的文件夹",
            "",
            QFileDialog.ShowDirsOnly
        )
        if folder:
            video_files = scan_videos_in_directory(folder)
            if video_files:
                self._add_videos(video_files)
                QMessageBox.information(
                    self,
                    "导入完成",
                    f"从文件夹中扫描到 {len(video_files)} 个视频文件。"
                )
            else:
                QMessageBox.information(
                    self,
                    "提示",
                    "该文件夹中没有找到视频文件。"
                )

    def _add_videos(self, video_paths: List[str]):
        existing_names = {os.path.basename(p).lower() for p in self.all_videos}
        added = 0
        skipped = 0

        for path in video_paths:
            name = os.path.basename(path)
            name_lower = name.lower()

            if name_lower in existing_names:
                skipped += 1
                continue

            self.all_videos.append(path)
            existing_names.add(name_lower)

            try:
                duration = get_video_duration(path)
                if duration is None:
                    duration = 0
                size = int(os.path.getsize(path))
                mtime = int(os.path.getmtime(path))
                self.controller.db.get_or_create_video(
                    path, name, int(duration), "", size, mtime
                )
                added += 1
            except Exception as e:
                logger.error(f"添加视频到数据库失败 {path}: {e}")
                if path in self.all_videos:
                    self.all_videos.remove(path)
                    existing_names.remove(name_lower)
                continue

        self.filtered_videos = self.all_videos.copy()
        self._refresh_video_list()

        if self.search_input.text().strip():
            self._on_search_text_changed(self.search_input.text())

        QMessageBox.information(
            self,
            "导入完成",
            f"成功导入 {added} 个视频。\n"
            f"跳过已存在（同名）: {skipped} 个。"
        )

    # ============================================================
    # 搜索功能
    # ============================================================

    def _on_search_text_changed(self, text: str):
        self.clear_search_btn.setVisible(len(text) > 0)

        if not text.strip():
            self.filtered_videos = self.all_videos.copy()
        else:
            search_text = text.strip().lower()
            self.filtered_videos = [
                path for path in self.all_videos
                if search_text in os.path.basename(path).lower()
            ]

        self._refresh_video_list()

        current_path = self.controller.get_video_path()
        if current_path and current_path not in self.filtered_videos:
            self.video_list.clearSelection()

    def _clear_search(self):
        self.search_input.clear()
        self.clear_search_btn.setVisible(False)
        self.filtered_videos = self.all_videos.copy()
        self._refresh_video_list()

    # ============================================================
    # 视频列表
    # ============================================================

    def _refresh_video_list(self):
        self.video_list.clear()
        for path in self.filtered_videos:
            name = os.path.basename(path)
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, path)
            icon = self.controller.get_video_state_icon(path)
            if icon:
                item.setText(f"{icon} {name}")
            self.video_list.addItem(item)

    def _update_video_list_icon(self, video_path: str):
        """更新单个视频项的图标（用于收藏弹窗导出后刷新）"""
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            if item.data(Qt.UserRole) == video_path:
                name = os.path.basename(video_path)
                icon = self.controller.get_video_state_icon(video_path)
                item.setText(f"{icon} {name}" if icon else name)
                break

    def _refresh_all_video_icons(self):
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            path = item.data(Qt.UserRole)
            if path:
                name = os.path.basename(path)
                icon = self.controller.get_video_state_icon(path)
                item.setText(f"{icon} {name}" if icon else name)

    # ============================================================
    # 右键菜单
    # ============================================================

    def _show_context_menu(self, pos: QPoint):
        item = self.video_list.itemAt(pos)
        if not item:
            return
        video_path = item.data(Qt.UserRole)
        if not video_path:
            return

        menu = QMenu(self)
        remove_action = QAction("❌ 从库中移除（不删除文件）", self)
        remove_action.triggered.connect(lambda: self._remove_video_from_library(video_path))
        menu.addAction(remove_action)

        if len(self.video_list.selectedItems()) > 1:
            batch_remove_action = QAction("🗑️ 批量删除选中", self)
            batch_remove_action.triggered.connect(self.batch_remove_videos)
            menu.addAction(batch_remove_action)

        menu.exec(self.video_list.mapToGlobal(pos))

    def _remove_video_from_library(self, video_path: str):
        reply = QMessageBox.question(
            self,
            "确认移除",
            f"确定要从视频库中移除 \"{os.path.basename(video_path)}\" 吗？\n\n"
            "此操作仅删除数据库记录和列表条目，不会删除视频文件本身。",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        success = self.controller.remove_video(video_path)
        if not success:
            QMessageBox.warning(self, "错误", "移除视频失败，可能该视频已不存在于数据库中。")
            return

        if video_path in self.all_videos:
            self.all_videos.remove(video_path)
        if video_path in self.filtered_videos:
            self.filtered_videos.remove(video_path)

        self._refresh_video_list()

        if self.controller.get_video_path() is None:
            self.video_name_label.setText("请选择视频")
            self.info_name.setText("未选择")
            self.info_duration.setText("时长: --")
            self.info_size.setText("大小: --")
            self.info_path.setText("路径: --")
            self._refresh_grid()
            for btn in self.seg_buttons:
                btn.setEnabled(False)
            if self.preview_dialog and self.preview_dialog.isVisible():
                self.preview_dialog.close()

        QMessageBox.information(self, "完成", f"已从库中移除 \"{os.path.basename(video_path)}\"")

    # ============================================================
    # 视频加载
    # ============================================================

    def on_video_selected(self, item: QListWidgetItem):
        path = item.data(Qt.UserRole)
        if path:
            asyncio.create_task(self._load_video(path))

    async def _load_video(self, video_path: str):
        self.progress_label_left.setText("加载中...")
        success = await self.controller.load_video(video_path)
        if not success:
            QMessageBox.critical(self, "错误", f"无法加载视频: {video_path}")
            self.progress_label_left.setText("加载失败")
            return

        video_name = self.controller.get_video_name()
        self.video_name_label.setText(video_name)
        self.info_name.setText(video_name)
        self.info_path.setText(f"路径: {video_path}")

        duration = self.controller.get_duration()
        self.info_duration.setText(f"时长: {str(timedelta(seconds=int(duration)))}")
        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        self.info_size.setText(f"大小: {size_mb:.2f} MB")

        self.selected_indices.clear()
        self._rebuild_seg_buttons()
        self._refresh_grid()
        self._update_fav_count()
        self._refresh_all_video_icons()
        self.progress_label_left.setText("加载完成")

        if self.preview_dialog and self.preview_dialog.isVisible():
            self.preview_dialog.set_video(video_path, duration, self.controller.get_temp_dir())

        for btn in self.seg_buttons:
            btn.setEnabled(True)

        self._update_undo_redo_buttons()
        self._update_select_all_state()

    # ============================================================
    # 分段按钮管理
    # ============================================================

    def _rebuild_seg_buttons(self):
        for btn in self.seg_buttons:
            self.seg_buttons_layout.removeWidget(btn)
            btn.deleteLater()
        self.seg_buttons.clear()

        segments = self.controller.get_segments()
        if not segments:
            return

        current_idx = self.controller.current_seg_index

        for i, (label, start, end) in enumerate(segments):
            time_range = f"{self._format_time(start)} - {self._format_time(end)}"
            btn = QPushButton(f"{label} {time_range}")
            btn.setCheckable(True)
            btn.setMinimumWidth(90)
            btn.setMaximumWidth(180)
            btn.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
            btn.setFixedHeight(34)
            btn.setFont(QFont("Arial", 9, QFont.Bold))
            btn.setChecked(i == current_idx)
            btn.clicked.connect(lambda checked, idx=i: self.on_seg_clicked(idx))
            self.seg_buttons_layout.addWidget(btn)
            self.seg_buttons.append(btn)

    def _update_seg_buttons_state(self):
        current_idx = self.controller.current_seg_index
        for i, btn in enumerate(self.seg_buttons):
            btn.setChecked(i == current_idx)

    def _format_time(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def on_seg_clicked(self, idx: int):
        if 0 <= idx < self.controller.get_segment_count():
            self.controller.current_seg_index = idx
            self._update_seg_buttons_state()
            asyncio.create_task(self.controller.load_segment(idx, restore_locks=True, randomize=False))

    # ============================================================
    # 分区数量变更
    # ============================================================

    def on_seg_count_changed(self, index: int):
        if index < 0:
            return
        new_count = self.seg_count_combo.itemData(index)
        if new_count is None:
            return

        current_count = self.controller.get_num_segments()
        if new_count == current_count:
            return

        if self.controller.get_video_path():
            reply = QMessageBox.question(
                self,
                "确认更改分区数",
                f"将分区数从 {current_count} 更改为 {new_count}，当前所有截图将被重置。\n确定要继续吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                self.seg_count_combo.setCurrentIndex(self.seg_count_combo.findData(current_count))
                return

        self.controller.set_num_segments(new_count)
        self._rebuild_seg_buttons()
        self.selected_indices.clear()
        self._update_select_all_state()

        if self.controller.get_video_path():
            asyncio.create_task(self.controller.load_segment(0, restore_locks=True, randomize=False))

    # ============================================================
    # 进度更新回调
    # ============================================================

    def _on_progress_update(self, message: str):
        self.progress_label_left.setText(message)

    # ============================================================
    # 数据变化回调
    # ============================================================

    def _on_data_changed(self):
        self._rebuild_seg_buttons()
        self._refresh_grid()
        self._update_fav_count()
        self._refresh_all_video_icons()
        self._update_undo_redo_buttons()
        self._update_cache_info()
        self._update_select_all_state()

    # ============================================================
    # 全选切换
    # ============================================================

    def _update_select_all_state(self):
        """更新全选按钮的选中状态"""
        seg_label, _, _ = self.controller.get_current_segment()
        if seg_label is None:
            self.select_all_btn.setEnabled(False)
            self.select_all_btn.setChecked(False)
            return
        items = self.controller.get_segment_items(seg_label)
        count = len(items)
        if count == 0:
            self.select_all_btn.setEnabled(False)
            self.select_all_btn.setChecked(False)
            return
        self.select_all_btn.setEnabled(True)
        all_selected = len(self.selected_indices) == count
        self.select_all_btn.setChecked(all_selected)

    def toggle_select_all(self):
        """切换全选状态"""
        seg_label, _, _ = self.controller.get_current_segment()
        items = self.controller.get_segment_items(seg_label)
        count = len(items)
        if count == 0:
            return

        if self.select_all_btn.isChecked():
            for pos in range(count):
                self.selected_indices.add((self.controller.current_seg_index, pos))
        else:
            self.selected_indices.clear()

        self._refresh_grid()
        self._update_select_all_state()

    # ============================================================
    # 网格刷新
    # ============================================================

    def _refresh_grid(self):
        try:
            segments = self.controller.get_segments()
            if not segments or self.controller.current_seg_index >= len(segments):
                self._update_select_all_state()
                return

            seg_label, _, _ = segments[self.controller.current_seg_index]
            items = self.controller.get_segment_items(seg_label)
            count = len(items)

            while self.grid_layout.count():
                child = self.grid_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            if count == 0:
                self._update_select_all_state()
                return

            density = self.controller.density
            if density == 9:
                cols = 3
            elif density == 12:
                cols = 3
            elif density == 16:
                cols = 4
            elif density == 25:
                cols = 5
            else:
                cols = 4

            for col in range(cols):
                self.grid_layout.setColumnStretch(col, 1)

            locked_count = sum(1 for it in items if it.get('locked', False))
            self.stat_locked.setText(f"锁定: {locked_count}")

            for pos, item in enumerate(items):
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
                label.setObjectName(f"{self.controller.current_seg_index}_{pos}")
                label.set_locked(item.get('locked', False))
                label.set_favorite(item.get('favorite', False))
                label.set_exported(item.get('exported', False))

                if (self.controller.current_seg_index, pos) in self.selected_indices:
                    label.set_selected(True)

                label.clicked.connect(partial(self.on_image_click, pos))
                label.double_clicked.connect(partial(self.preview_image, pos))
                self.grid_layout.addWidget(label, row, col)

            self._update_selected_count()
            self._update_select_all_state()
            self.grid_widget.updateGeometry()
            self.grid_widget.update()
            self.scroll.update()
            QApplication.processEvents()

        except Exception as e:
            logger.error(f"刷新网格出错: {e}\n{traceback.format_exc()}")

    def _update_fav_count(self):
        count = self.controller.get_favorites_count()
        self.stat_fav.setText(f"收藏: {count}")

    def _update_selected_count(self):
        count = len(self.selected_indices)
        self.selected_label.setText(f"已选: {count} 张")

    # ============================================================
    # 图片交互
    # ============================================================

    def on_image_click(self, pos: int):
        key = (self.controller.current_seg_index, pos)
        if key in self.selected_indices:
            self.selected_indices.remove(key)
        else:
            self.selected_indices.add(key)
        self._refresh_grid()

    def preview_image(self, pos: int):
        seg_label, _, _ = self.controller.get_current_segment()
        items = self.controller.get_segment_items(seg_label)
        if pos >= len(items):
            return
        item = items[pos]
        if not item.get('path') or not os.path.exists(item['path']):
            QMessageBox.warning(self, "警告", "图片文件不存在。")
            return

        pixmap = QPixmap(item['path'])
        if pixmap.isNull():
            return
        dlg = ZoomPreviewDialog(pixmap, item['time'], self)
        dlg.exec()

    # ============================================================
    # 选择操作
    # ============================================================

    def select_all(self):
        seg_label, _, _ = self.controller.get_current_segment()
        items = self.controller.get_segment_items(seg_label)
        for pos in range(len(items)):
            self.selected_indices.add((self.controller.current_seg_index, pos))
        self._refresh_grid()

    def deselect_all(self):
        self.selected_indices.clear()
        self._refresh_grid()

    # ============================================================
    # 收藏操作
    # ============================================================

    def show_favorites(self):
        if not self.controller.get_video_path():
            QMessageBox.information(self, "提示", "请先加载视频。")
            return

        current_favs = self.controller.get_current_favorites()
        if not current_favs:
            QMessageBox.information(self, "提示", "当前视频没有收藏截图。")
            return

        dlg = FavoritesDialog(
            current_favs,
            self.controller.get_video_name(),
            self.controller.get_export_base(),
            self.controller.get_video_path(),
            self
        )
        dlg.exec()
        self._refresh_grid()

    def favorite_selected(self):
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选中要收藏的截图。")
            return

        seg_label, _, _ = self.controller.get_current_segment()
        positions = [pos for (seg_idx, pos) in self.selected_indices
                     if seg_idx == self.controller.current_seg_index]

        added, skipped = self.controller.favorite_selected(seg_label, positions)
        if added > 0:
            self.selected_indices.clear()
            self._update_select_all_state()
            QMessageBox.information(self, "完成", f"成功收藏 {added} 张截图。")
        else:
            QMessageBox.information(self, "提示", "选中的截图已经收藏过了。")

    def unfavorite_selected(self):
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选中要取消收藏的截图。")
            return

        seg_label, _, _ = self.controller.get_current_segment()
        positions = [pos for (seg_idx, pos) in self.selected_indices
                     if seg_idx == self.controller.current_seg_index]

        removed = self.controller.unfavorite_selected(seg_label, positions)
        if removed > 0:
            self.selected_indices.clear()
            self._update_select_all_state()
            QMessageBox.information(self, "完成", f"成功取消收藏 {removed} 张截图。")

    # ============================================================
    # 锁定操作
    # ============================================================

    def lock_selected(self):
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选中要锁定的截图。")
            return

        seg_label, _, _ = self.controller.get_current_segment()
        positions = [pos for (seg_idx, pos) in self.selected_indices
                     if seg_idx == self.controller.current_seg_index]

        self.controller.lock_selected(seg_label, positions)
        self.selected_indices.clear()
        self._update_select_all_state()

    def unlock_selected(self):
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选中要解锁的截图。")
            return

        seg_label, _, _ = self.controller.get_current_segment()
        positions = [pos for (seg_idx, pos) in self.selected_indices
                     if seg_idx == self.controller.current_seg_index]

        self.controller.unlock_selected(seg_label, positions)
        self.selected_indices.clear()
        self._update_select_all_state()

    # ============================================================
    # 刷新 / 重抽
    # ============================================================

    async def refresh_unlocked(self):
        seg_idx = self.controller.current_seg_index
        refreshed = await self.controller.refresh_unlocked(seg_idx)
        if refreshed == 0:
            QMessageBox.information(self, "提示", "当前分段没有未锁定的截图。")
        else:
            self.selected_indices.clear()
            self._update_select_all_state()

    async def reset_all(self):
        seg_idx = self.controller.current_seg_index
        await self.controller.reset_segment(seg_idx)
        self.selected_indices.clear()
        self._update_select_all_state()

    # ============================================================
    # 导出操作（支持自定义目录）
    # ============================================================

    def export_selected(self):
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选中要导出的截图。")
            return

        # 弹出文件夹选择对话框
        export_dir = QFileDialog.getExistingDirectory(
            self,
            "选择导出目录",
            os.path.expanduser("~"),  # 默认用户目录
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if not export_dir:  # 用户取消选择
            return

        seg_label, _, _ = self.controller.get_current_segment()
        positions = [pos for (seg_idx, pos) in self.selected_indices
                     if seg_idx == self.controller.current_seg_index]

        exported, exported_list = self.controller.export_selected(seg_label, positions, export_dir)

        if exported == 0:
            QMessageBox.warning(self, "警告", "导出失败或选中的文件不存在。")
            return

        self.selected_indices.clear()
        self._update_select_all_state()
        QMessageBox.information(self, "导出完成", f"成功导出 {exported} 张截图到:\n{export_dir}")

    # ============================================================
    # 撤销/重做
    # ============================================================

    def _update_undo_redo_buttons(self):
        self.undo_btn.setEnabled(self.controller.can_undo())
        self.redo_btn.setEnabled(self.controller.can_redo())

    def undo_action(self):
        self.controller.undo()
        self._update_undo_redo_buttons()

    def redo_action(self):
        self.controller.redo()
        self._update_undo_redo_buttons()

    # ============================================================
    # 清理缓存（手动）
    # ============================================================

    def clear_cache(self):
        count = self.controller.clear_cache()
        self._update_cache_info()
        QMessageBox.information(self, "清理完成", f"已清理 {count} 个缓存文件。")

    # ============================================================
    # Zoom 精修
    # ============================================================

    def zoom_selected(self):
        if len(self.selected_indices) > 1:
            QMessageBox.information(self, "提示", "细选只能针对单张截图，请只选中一张截图。")
            return
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选中一张截图，然后点击'细选'。")
            return

        seg_idx, pos = next(iter(self.selected_indices))
        seg_label, _, _ = self.controller.get_current_segment()
        items = self.controller.get_segment_items(seg_label)

        if pos >= len(items):
            QMessageBox.warning(self, "警告", "截图数据不存在")
            return

        item = items[pos]
        if not item.get('path') or not os.path.exists(item['path']):
            QMessageBox.warning(self, "警告", "图片文件不存在。")
            return

        dlg = ZoomDialog(
            controller=self.controller,
            seg_label=seg_label,
            seg_idx=seg_idx,
            pos=pos,
            center_time=item['time'],
            level=1,
            parent=self,
            source="main",
            original_fav_item=None,
        )
        dlg.exec()
        self._refresh_grid()

    # ============================================================
    # 密度切换
    # ============================================================

    def on_density_changed(self, val: int):
        self.controller.density = val
        for btn in self.density_buttons:
            btn.setChecked(int(btn.text()) == val)

        if self.controller.get_video_path():
            asyncio.create_task(
                self.controller.load_segment(
                    self.controller.current_seg_index,
                    restore_locks=True,
                    randomize=False
                )
            )

    # ============================================================
    # 关闭事件
    # ============================================================

    def closeEvent(self, event):
        if self.preview_dialog and self.preview_dialog.isVisible():
            self.preview_dialog.close()
        self.controller.cleanup()
        event.accept()