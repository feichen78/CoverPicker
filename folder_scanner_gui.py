#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NAS 空文件夹/无视频文件夹扫描工具
独立于 CoverPicker 运行，用于清理 NAS 上不包含视频文件的空文件夹或无效文件夹。
"""

import os
import sys
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QTextEdit,
    QFileDialog, QMessageBox, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QLineEdit, QDialog, QScrollArea
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QEvent
from PySide6.QtGui import QFont, QColor, QKeyEvent, QPixmap


# ============================================================
# 图片预览对话框
# ============================================================

class ImagePreviewDialog(QDialog):
    """简单的图片预览对话框，支持按空格/ESC关闭"""
    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🖼️ 图片预览 - 按空格或 ESC 关闭")
        self.setModal(True)
        self.setMinimumSize(400, 300)

        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # 滚动区域（适配大图）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: #1a1a1a;")

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background: #1a1a1a; padding: 10px;")

        # 加载图片
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            # 限制最大尺寸为屏幕的 80%，保持比例
            screen = QApplication.primaryScreen().size()
            max_width = int(screen.width() * 0.8)
            max_height = int(screen.height() * 0.8)
            scaled = pixmap.scaled(max_width, max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled)
            # 调整窗口大小以适应图片（但不超过屏幕）
            self.resize(scaled.width() + 40, scaled.height() + 80)
        else:
            self.image_label.setText("无法加载图片")
            self.resize(400, 300)

        scroll.setWidget(self.image_label)
        layout.addWidget(scroll)

        # 底部提示
        hint = QLabel("按 空格键 或 ESC 关闭预览")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: #888; font-size: 12px; padding: 4px;")
        layout.addWidget(hint)

        # 设置焦点，确保键盘事件被捕获
        self.setFocusPolicy(Qt.StrongFocus)

    def keyPressEvent(self, event: QKeyEvent):
        """按空格或 ESC 关闭对话框"""
        if event.key() in (Qt.Key_Space, Qt.Key_Escape):
            self.accept()
        else:
            super().keyPressEvent(event)


# ============================================================
# 配置
# ============================================================

VIDEO_EXTENSIONS = {
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm',
    '.m4v', '.mpg', '.mpeg', '.ts', '.m2ts', '.3gp', '.asf',
    '.vob', '.ogv', '.ogg', '.divx', '.xvid', '.mts', '.m2v',
    '.m4p', '.m4b', '.m4r', '.mpv', '.mpe', '.mxf', '.rm',
    '.rmvb', '.swf', '.f4v'
}

EXCLUDE_DIRS = {
    '@Recycle', 'System Volume Information', '.Trashes',
    '.Spotlight-V100', '$RECYCLE.BIN', 'Thumbs.db', '.DS_Store',
    'Lost+Found', '@eaDir', '@tmp', 'Network Trash Folder',
    'Temporary Items', '.fseventsd', '.TemporaryItems'
}

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.svg', '.ico'}
DOC_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.md', '.rtf'}
ARCHIVE_EXTENSIONS = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.iso'}


# ============================================================
# 扫描线程
# ============================================================

class ScanWorker(QThread):
    progress = Signal(int, int)
    found = Signal(str, dict)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, root_path: str):
        super().__init__()
        self.root_path = root_path
        self._is_running = True

    def stop(self):
        self._is_running = False

    def _has_video_in_subtree(self, folder: Path, children_cache: Dict[str, List[str]]) -> bool:
        """
        递归检查文件夹及其所有子文件夹是否包含视频文件。
        使用缓存避免重复遍历。
        """
        folder_str = str(folder)

        # 直接检查当前文件夹中的视频文件
        try:
            for f in folder.iterdir():
                if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
                    return True
        except (PermissionError, OSError):
            pass

        # 检查所有子文件夹
        for sub in children_cache.get(folder_str, []):
            if self._has_video_in_subtree(Path(sub), children_cache):
                return True

        return False

    def run(self):
        root = Path(self.root_path)
        if not root.is_dir():
            self.error.emit(f"路径不存在或不是目录: {self.root_path}")
            return

        # ---- 第1步：收集所有目录路径 ----
        all_folders = []
        children_cache = {}  # {父目录路径: [子目录路径列表]}

        for dirpath, dirnames, filenames in os.walk(root):
            if not self._is_running:
                return

            # 过滤排除目录
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]

            all_folders.append(dirpath)

            # 记录子目录关系
            parent = dirpath
            for sub in dirnames:
                sub_path = os.path.join(parent, sub)
                children_cache.setdefault(parent, []).append(sub_path)

        total = len(all_folders)
        suspicious = []

        # ---- 第2步：从下往上检查 ----
        all_folders_sorted = sorted(all_folders, key=lambda p: p.count(os.sep), reverse=True)

        for idx, folder in enumerate(all_folders_sorted):
            if not self._is_running:
                break

            self.progress.emit(idx + 1, total)

            has_video_in_subtree = self._has_video_in_subtree(Path(folder), children_cache)

            if not has_video_in_subtree:
                # 统计文件信息
                file_count = 0
                total_size = 0
                video_count = 0
                image_count = 0
                doc_count = 0
                archive_count = 0
                other_count = 0

                try:
                    for f in Path(folder).iterdir():
                        if f.is_file():
                            file_count += 1
                            total_size += f.stat().st_size
                            ext = f.suffix.lower()
                            if ext in VIDEO_EXTENSIONS:
                                video_count += 1
                            elif ext in IMAGE_EXTENSIONS:
                                image_count += 1
                            elif ext in DOC_EXTENSIONS:
                                doc_count += 1
                            elif ext in ARCHIVE_EXTENSIONS:
                                archive_count += 1
                            else:
                                other_count += 1
                except (PermissionError, OSError):
                    continue

                info = {
                    'path': folder,
                    'file_count': file_count,
                    'total_size': total_size,
                    'video_count': video_count,
                    'image_count': image_count,
                    'doc_count': doc_count,
                    'archive_count': archive_count,
                    'other_count': other_count
                }
                suspicious.append(info)
                self.found.emit(folder, info)

        self.finished.emit(suspicious)


# ============================================================
# 主窗口
# ============================================================

class FolderScannerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📁 NAS 空文件夹/无视频文件夹扫描工具")
        self.setMinimumSize(1100, 700)

        self.suspicious_folders: List[dict] = []
        self.selected_folder_path: Optional[str] = None
        self.scan_worker: Optional[ScanWorker] = None

        self._setup_ui()
        self._connect_signals()
        self._update_status("就绪")

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 顶部工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self.root_path_edit = QLineEdit()
        self.root_path_edit.setPlaceholderText("选择 NAS 上的根目录...")
        self.root_path_edit.setReadOnly(True)
        toolbar.addWidget(self.root_path_edit, 3)

        self.browse_btn = QPushButton("📂 浏览")
        self.browse_btn.setFixedWidth(80)
        toolbar.addWidget(self.browse_btn)

        self.scan_btn = QPushButton("🔍 开始扫描")
        self.scan_btn.setFixedWidth(120)
        self.scan_btn.setStyleSheet("background: #2196F3; color: white; font-weight: bold;")
        toolbar.addWidget(self.scan_btn)

        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setFixedWidth(80)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background: #f44336; color: white; font-weight: bold;")
        toolbar.addWidget(self.stop_btn)

        self.status_label = QLabel("就绪")
        self.status_label.setFont(QFont("Arial", 10))
        toolbar.addWidget(self.status_label, 1)

        main_layout.addLayout(toolbar)

        self.progress_label = QLabel("")
        self.progress_label.setFont(QFont("Arial", 9))
        self.progress_label.setStyleSheet("color: #666;")
        main_layout.addWidget(self.progress_label)

        # 主区域
        splitter = QSplitter(Qt.Horizontal)

        # 左侧
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_title = QLabel("📋 可疑文件夹列表")
        left_title.setFont(QFont("Arial", 11, QFont.Bold))
        left_layout.addWidget(left_title)

        self.folder_list = QListWidget()
        self.folder_list.setFont(QFont("Consolas", 10))
        self.folder_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        left_layout.addWidget(self.folder_list)

        self.folder_count_label = QLabel("共 0 个可疑文件夹")
        self.folder_count_label.setFont(QFont("Arial", 9))
        left_layout.addWidget(self.folder_count_label)

        splitter.addWidget(left_widget)

        # 右侧预览
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_title = QLabel("📄 文件夹详情")
        right_title.setFont(QFont("Arial", 11, QFont.Bold))
        right_layout.addWidget(right_title)

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setFont(QFont("Consolas", 10))
        self.info_text.setMaximumHeight(120)
        self.info_text.setStyleSheet("background: #f5f5f5; border: 1px solid #ddd;")
        right_layout.addWidget(self.info_text)

        self.file_table = QTableWidget()
        self.file_table.setColumnCount(3)
        self.file_table.setHorizontalHeaderLabels(["文件名", "大小", "类型"])
        self.file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.file_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.file_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.file_table.setAlternatingRowColors(True)
        self.file_table.setFocusPolicy(Qt.StrongFocus)
        self.file_table.installEventFilter(self)
        right_layout.addWidget(self.file_table)

        splitter.addWidget(right_widget)

        splitter.setSizes([400, 700])
        main_layout.addWidget(splitter, 1)

        # 底部操作栏
        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)

        self.delete_btn = QPushButton("🗑️ 删除选中")
        self.delete_btn.setEnabled(False)
        self.delete_btn.setStyleSheet("background: #e74c3c; color: white; font-weight: bold;")
        action_bar.addWidget(self.delete_btn)

        self.move_btn = QPushButton("📂 移动选中")
        self.move_btn.setEnabled(False)
        self.move_btn.setStyleSheet("background: #FF9800; color: white; font-weight: bold;")
        action_bar.addWidget(self.move_btn)

        self.select_all_btn = QPushButton("☑ 全选")
        self.select_all_btn.setEnabled(False)
        action_bar.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("☐ 取消全选")
        self.deselect_all_btn.setEnabled(False)
        action_bar.addWidget(self.deselect_all_btn)

        action_bar.addStretch()

        self.export_btn = QPushButton("📤 导出列表")
        self.export_btn.setEnabled(False)
        action_bar.addWidget(self.export_btn)

        self.clear_btn = QPushButton("🗑️ 清空列表")
        self.clear_btn.setEnabled(False)
        action_bar.addWidget(self.clear_btn)

        main_layout.addLayout(action_bar)

        self.bottom_status = QLabel("💡 提示：单击选中文件夹，然后点击删除/移动；在文件列表中按空格键预览图片")
        self.bottom_status.setFont(QFont("Arial", 9))
        self.bottom_status.setStyleSheet("color: #888;")
        main_layout.addWidget(self.bottom_status)

    def _connect_signals(self):
        self.browse_btn.clicked.connect(self._browse_root)
        self.scan_btn.clicked.connect(self._start_scan)
        self.stop_btn.clicked.connect(self._stop_scan)
        self.folder_list.itemSelectionChanged.connect(self._on_folder_selected)
        self.folder_list.itemDoubleClicked.connect(self._on_folder_double_clicked)
        self.delete_btn.clicked.connect(self._delete_selected)
        self.move_btn.clicked.connect(self._move_selected)
        self.select_all_btn.clicked.connect(self._select_all)
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        self.export_btn.clicked.connect(self._export_list)
        self.clear_btn.clicked.connect(self._clear_list)

    def _update_status(self, text: str, is_busy: bool = False):
        self.status_label.setText(text)
        self.scan_btn.setEnabled(not is_busy)
        self.stop_btn.setEnabled(is_busy)
        self.browse_btn.setEnabled(not is_busy)

    def _browse_root(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择 NAS 根目录",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if folder:
            self.root_path_edit.setText(folder)
            self._update_status(f"已选择: {folder}")

    def _start_scan(self):
        root_path = self.root_path_edit.text().strip()
        if not root_path or not Path(root_path).is_dir():
            QMessageBox.warning(self, "提示", "请先选择一个有效的目录。")
            return

        self.suspicious_folders.clear()
        self.folder_list.clear()
        self.file_table.setRowCount(0)
        self.info_text.clear()
        self.folder_count_label.setText("共 0 个可疑文件夹")
        self._update_buttons()

        self._update_status("正在扫描...", is_busy=True)
        self.progress_label.setText("正在扫描，请稍候...")

        self.scan_worker = ScanWorker(root_path)
        self.scan_worker.progress.connect(self._on_scan_progress)
        self.scan_worker.found.connect(self._on_folder_found)
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.error.connect(self._on_scan_error)
        self.scan_worker.start()

    def _stop_scan(self):
        if self.scan_worker and self.scan_worker.isRunning():
            self.scan_worker.stop()
            self.scan_worker.wait()
            self._update_status("扫描已停止")
            self.progress_label.setText("")

    def _on_scan_progress(self, current: int, total: int):
        self.progress_label.setText(f"已检查 {current} / {total} 个文件夹")

    def _on_folder_found(self, path: str, info: dict):
        self.suspicious_folders.append(info)
        item = QListWidgetItem()
        item.setData(Qt.UserRole, path)
        if info['file_count'] == 0:
            item.setText(f"📭 {path}  (空文件夹)")
            item.setForeground(QColor(150, 150, 150))
        else:
            item.setText(f"📁 {path}  (无视频: {info['file_count']} 个文件)")
            item.setForeground(QColor(200, 120, 50))
        self.folder_list.addItem(item)
        self.folder_count_label.setText(f"共 {len(self.suspicious_folders)} 个可疑文件夹")
        self._update_buttons()

    def _on_scan_finished(self, results: list):
        self._update_status(f"扫描完成，发现 {len(results)} 个可疑文件夹")
        self.progress_label.setText(f"扫描完成！共检查 {len(self.suspicious_folders)} 个文件夹")
        self._update_buttons()

        if len(results) == 0:
            QMessageBox.information(self, "扫描完成", "未发现空文件夹或不含视频的文件夹。")

    def _on_scan_error(self, msg: str):
        self._update_status(f"扫描出错: {msg}")
        self.progress_label.setText("")
        QMessageBox.critical(self, "扫描错误", msg)

    def _on_folder_selected(self):
        selected = self.folder_list.selectedItems()
        if not selected:
            self.info_text.clear()
            self.file_table.setRowCount(0)
            return

        item = selected[0]
        path = item.data(Qt.UserRole)
        if not path:
            return

        info = None
        for f in self.suspicious_folders:
            if f['path'] == path:
                info = f
                break

        if not info:
            return

        self.selected_folder_path = path
        self._show_folder_info(info)
        self._update_buttons()

    def _on_folder_double_clicked(self, item: QListWidgetItem):
        path = item.data(Qt.UserRole)
        if not path:
            return
        if os.path.exists(path):
            try:
                os.startfile(path)
            except Exception as e:
                QMessageBox.warning(self, "无法打开", f"无法打开文件夹:\n{str(e)}")

    def _show_folder_info(self, info: dict):
        path = info['path']
        size_mb = info['total_size'] / (1024 * 1024)
        size_str = f"{size_mb:.2f} MB" if size_mb < 1024 else f"{size_mb/1024:.2f} GB"

        stats = f"""
📂 路径: {path}
📊 文件总数: {info['file_count']}
💾 总大小: {size_str}
{'─' * 40}
🎬 视频文件: {info['video_count']}
🖼️ 图片文件: {info['image_count']}
📄 文档文件: {info['doc_count']}
📦 压缩包: {info['archive_count']}
📎 其他: {info['other_count']}
"""
        self.info_text.setText(stats)

        self.file_table.setRowCount(0)
        try:
            files = []
            for f in Path(path).iterdir():
                if f.is_file():
                    ext = f.suffix.lower()
                    if ext in VIDEO_EXTENSIONS:
                        ftype = "🎬 视频"
                    elif ext in IMAGE_EXTENSIONS:
                        ftype = "🖼️ 图片"
                    elif ext in DOC_EXTENSIONS:
                        ftype = "📄 文档"
                    elif ext in ARCHIVE_EXTENSIONS:
                        ftype = "📦 压缩包"
                    else:
                        ftype = "📎 其他"
                    files.append((f.name, f.stat().st_size, ftype))

            files.sort(key=lambda x: x[0].lower())
            self.file_table.setRowCount(len(files))

            for row, (name, size, ftype) in enumerate(files):
                size_str = f"{size / 1024:.1f} KB" if size < 1024*1024 else f"{size / (1024*1024):.2f} MB"
                self.file_table.setItem(row, 0, QTableWidgetItem(name))
                self.file_table.setItem(row, 1, QTableWidgetItem(size_str))
                self.file_table.setItem(row, 2, QTableWidgetItem(ftype))
        except (PermissionError, OSError):
            pass

    def _get_selected_paths(self) -> List[str]:
        paths = []
        for item in self.folder_list.selectedItems():
            path = item.data(Qt.UserRole)
            if path:
                paths.append(path)
        return paths

    def _show_confirmation_dialog(self, title: str, msg: str) -> int:
        """显示置顶确认对话框"""
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(msg)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        box.setWindowModality(Qt.ApplicationModal)
        return box.exec()

    def _delete_selected(self):
        paths = self._get_selected_paths()
        if not paths:
            QMessageBox.information(self, "提示", "请先选中要删除的文件夹。")
            return

        msg = f"确定要删除选中的 {len(paths)} 个文件夹吗？\n\n此操作不可恢复！"
        if len(paths) <= 5:
            msg += "\n\n" + "\n".join(paths)

        self.bottom_status.setText("⏳ 等待确认...")
        reply = self._show_confirmation_dialog("确认删除", msg)

        if reply != QMessageBox.Yes:
            self.bottom_status.setText("已取消删除")
            QTimer.singleShot(2000, lambda: self.bottom_status.setText(""))
            return

        deleted = []
        failed = []
        self.bottom_status.setText("⏳ 正在删除...")

        for path in paths:
            try:
                shutil.rmtree(path)
                deleted.append(path)
            except Exception as e:
                failed.append(f"{path}: {str(e)}")

        self._remove_from_list(deleted)
        self._update_buttons()

        if failed:
            QMessageBox.warning(self, "删除完成", f"成功删除 {len(deleted)} 个，失败 {len(failed)} 个:\n" + "\n".join(failed[:5]))
        else:
            QMessageBox.information(self, "删除完成", f"成功删除 {len(deleted)} 个文件夹。")
        self.bottom_status.setText("")

    def _move_selected(self):
        paths = self._get_selected_paths()
        if not paths:
            QMessageBox.information(self, "提示", "请先选中要移动的文件夹。")
            return

        target_dir = QFileDialog.getExistingDirectory(
            self,
            "选择目标目录",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if not target_dir:
            return

        msg = f"确定要将选中的 {len(paths)} 个文件夹移动到:\n{target_dir}？"
        self.bottom_status.setText("⏳ 等待确认...")
        reply = self._show_confirmation_dialog("确认移动", msg)

        if reply != QMessageBox.Yes:
            self.bottom_status.setText("已取消移动")
            QTimer.singleShot(2000, lambda: self.bottom_status.setText(""))
            return

        moved = []
        failed = []
        self.bottom_status.setText("⏳ 正在移动...")

        for path in paths:
            try:
                dest = os.path.join(target_dir, os.path.basename(path))
                counter = 1
                while os.path.exists(dest):
                    base, ext = os.path.splitext(os.path.basename(path))
                    dest = os.path.join(target_dir, f"{base}_{counter}{ext}")
                    counter += 1
                shutil.move(path, dest)
                moved.append(path)
            except Exception as e:
                failed.append(f"{path}: {str(e)}")

        self._remove_from_list(moved)
        self._update_buttons()

        if failed:
            QMessageBox.warning(self, "移动完成", f"成功移动 {len(moved)} 个，失败 {len(failed)} 个:\n" + "\n".join(failed[:5]))
        else:
            QMessageBox.information(self, "移动完成", f"成功移动 {len(moved)} 个文件夹到:\n{target_dir}")
        self.bottom_status.setText("")

    def _remove_from_list(self, paths: List[str]):
        to_remove = set(paths)
        items_to_remove = []
        for i in range(self.folder_list.count()):
            item = self.folder_list.item(i)
            path = item.data(Qt.UserRole)
            if path in to_remove:
                items_to_remove.append((i, item))

        for i, item in reversed(items_to_remove):
            self.folder_list.takeItem(i)

        self.suspicious_folders = [f for f in self.suspicious_folders if f['path'] not in to_remove]
        self.folder_count_label.setText(f"共 {len(self.suspicious_folders)} 个可疑文件夹")

        if self.folder_list.count() == 0:
            self.info_text.clear()
            self.file_table.setRowCount(0)

    def _select_all(self):
        self.folder_list.selectAll()

    def _deselect_all(self):
        self.folder_list.clearSelection()

    def _export_list(self):
        if not self.suspicious_folders:
            QMessageBox.information(self, "提示", "没有数据可导出。")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出列表",
            f"empty_folders_{datetime.now().strftime('%Y%m%d')}.txt",
            "文本文件 (*.txt);;CSV文件 (*.csv)"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("# NAS 空文件夹/无视频文件夹列表\n")
                f.write(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 总计: {len(self.suspicious_folders)} 个文件夹\n")
                f.write("\n")
                for info in self.suspicious_folders:
                    f.write(f"{info['path']}\n")
            QMessageBox.information(self, "导出完成", f"已导出到:\n{file_path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def _clear_list(self):
        if self.folder_list.count() == 0:
            return
        reply = self._show_confirmation_dialog("确认清空", "确定要清空列表吗？")
        if reply == QMessageBox.Yes:
            self.suspicious_folders.clear()
            self.folder_list.clear()
            self.file_table.setRowCount(0)
            self.info_text.clear()
            self.folder_count_label.setText("共 0 个可疑文件夹")
            self._update_buttons()

    def _update_buttons(self):
        has_items = self.folder_list.count() > 0
        has_selection = len(self.folder_list.selectedItems()) > 0

        self.delete_btn.setEnabled(has_selection)
        self.move_btn.setEnabled(has_selection)
        self.select_all_btn.setEnabled(has_items)
        self.deselect_all_btn.setEnabled(has_items)
        self.export_btn.setEnabled(has_items)
        self.clear_btn.setEnabled(has_items)

    # ============================================================
    # 空格键预览图片（自定义对话框）
    # ============================================================
    def eventFilter(self, obj, event):
        if obj == self.file_table and event.type() == QEvent.KeyPress:
            key_event = event
            if key_event.key() == Qt.Key_Space:
                current_row = self.file_table.currentRow()
                if current_row < 0:
                    return True
                name_item = self.file_table.item(current_row, 0)
                if not name_item:
                    return True
                file_name = name_item.text()
                ext = os.path.splitext(file_name)[1].lower()
                if ext in IMAGE_EXTENSIONS:
                    if not self.selected_folder_path:
                        return True
                    full_path = os.path.join(self.selected_folder_path, file_name)
                    if os.path.isfile(full_path):
                        # 弹出自定义预览对话框，按空格或ESC关闭
                        preview_dlg = ImagePreviewDialog(full_path, self)
                        preview_dlg.exec()
                return True
        return super().eventFilter(obj, event)


# ============================================================
# 主入口
# ============================================================

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("NAS文件夹扫描工具")
    app.setOrganizationName("CoverPicker")

    window = FolderScannerGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()