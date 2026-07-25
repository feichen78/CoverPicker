# ui/dialogs/favorites_dialog.py
# 修复：添加高度上限，防止布局计算溢出导致崩溃
# 添加防重复刷新标志

import os, logging
from typing import List, Set
from functools import partial
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QPixmap, QFont, QColor
from ui.widgets import FavImageLabel
from ui.views.zoom_preview import ZoomPreviewDialog
from src.config_manager import ConfigManager

logger = logging.getLogger(__name__)

class FavoritesDialog(QDialog):
    def __init__(self, favorites: List[dict], video_name: str, export_base: str, video_path: str, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.favorites = favorites
        self.video_name = video_name
        self.export_base = export_base
        self.video_path = video_path
        self.selected_indices: Set[int] = set()
        self.controller = parent.controller if parent else None
        self.config = ConfigManager()
        self._is_refreshing = False

        print(f"[DEBUG] FavoritesDialog __init__: 收到 {len(favorites)} 条收藏")

        self.setWindowTitle(f"⭐ 收藏夹 - {video_name}")
        self.setModal(False)
        self.setMinimumSize(600, 400)
        self.resize(900, 600)

        main_layout = QVBoxLayout(self)

        # 顶部信息栏
        top_layout = QHBoxLayout()
        info_label = QLabel(f"📸 {len(favorites)} 张收藏截图")
        info_label.setFont(QFont("Arial", 11, QFont.Bold))
        top_layout.addWidget(info_label)
        top_layout.addStretch()

        self.export_btn = QPushButton("📥 导出选中")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_selected)
        top_layout.addWidget(self.export_btn)

        self.select_all_btn = QPushButton("☑ 全选")
        self.select_all_btn.setCheckable(True)
        self.select_all_btn.clicked.connect(self.toggle_select_all)
        top_layout.addWidget(self.select_all_btn)

        self.open_folder_btn = QPushButton("📂 打开导出夹")
        self.open_folder_btn.clicked.connect(self.open_export_folder)
        top_layout.addWidget(self.open_folder_btn)

        main_layout.addLayout(top_layout)

        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.container)
        main_layout.addWidget(self.scroll_area)

        self._refresh_favorites()
        self.setFocus()

    def _refresh_favorites(self):
        """刷新收藏列表显示"""
        if self._is_refreshing:
            print("[DEBUG] _refresh_favorites: 正在刷新中，跳过")
            return
        self._is_refreshing = True

        try:
            print("[DEBUG] _refresh_favorites called")
            # 清空容器
            while self.container_layout.count():
                child = self.container_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            if not self.favorites:
                empty_label = QLabel("暂无收藏截图")
                empty_label.setAlignment(Qt.AlignCenter)
                empty_label.setFont(QFont("Arial", 12))
                self.container_layout.addWidget(empty_label)
                self._is_refreshing = False
                return

            # 按分区分组
            groups = {}
            for fav in self.favorites:
                seg = fav.get('segment', 'Unknown')
                if seg not in groups:
                    groups[seg] = []
                groups[seg].append(fav)

            # 计算列数
            avail_width = self.scroll_area.viewport().width() - 20
            if avail_width <= 0:
                avail_width = 860

            # 根据窗口宽度动态计算列数
            if avail_width >= 1200:
                cols = 6
                thumb_size = 180
            elif avail_width >= 900:
                cols = 5
                thumb_size = 170
            elif avail_width >= 600:
                cols = 4
                thumb_size = 140
            else:
                cols = 3
                thumb_size = 120

            max_count_per_row = cols
            print(f"[DEBUG] max_count={max_count_per_row}, cols={cols}")
            print(f"[DEBUG] avail_width={avail_width}")
            print(f"[DEBUG] thumb_size={thumb_size}x{int(thumb_size*0.56)}")

            # 按分区显示
            total_height = 0
            for seg_label, favs in sorted(groups.items()):
                # 分区标签
                seg_title = QLabel(f"📁 分区 {seg_label} ({len(favs)} 张)")
                seg_title.setFont(QFont("Arial", 10, QFont.Bold))
                seg_title.setStyleSheet("color:#2196F3;padding:4px 0;")
                self.container_layout.addWidget(seg_title)
                total_height += 30

                # 网格布局
                grid = QGridLayout()
                grid.setSpacing(4)
                grid.setContentsMargins(4, 4, 4, 4)

                for idx, fav in enumerate(favs):
                    row = idx // max_count_per_row
                    col = idx % max_count_per_row

                    img_path = fav.get('path', '')
                    timestamp = fav.get('time', 0)
                    exported = fav.get('exported', False)

                    print(f"[DEBUG] fav idx={idx}, seg={seg_label}, exported_raw={exported}, exported_bool={bool(exported)}")

                    if img_path and os.path.exists(img_path):
                        pixmap = QPixmap(img_path)
                        if pixmap.isNull():
                            pixmap = QPixmap(thumb_size, int(thumb_size * 0.56))
                            pixmap.fill(QColor(60, 60, 60))
                    else:
                        pixmap = QPixmap(thumb_size, int(thumb_size * 0.56))
                        pixmap.fill(QColor(60, 60, 60))

                    label = FavImageLabel(pixmap, timestamp, idx + 1)
                    label.setFixedSize(thumb_size, int(thumb_size * 0.56))
                    label.set_exported(exported)
                    label.setObjectName(f"{seg_label}_{idx}")

                    # 选中状态
                    if idx in self.selected_indices:
                        label.set_selected(True)

                    label.clicked.connect(partial(self.on_fav_click, idx))
                    label.double_clicked.connect(partial(self.preview_fav, idx))

                    grid.addWidget(label, row, col)

                # 添加网格到容器
                grid_widget = QWidget()
                grid_widget.setLayout(grid)
                self.container_layout.addWidget(grid_widget)

                # 计算高度：每个标签高度+间距
                rows = (len(favs) + max_count_per_row - 1) // max_count_per_row
                row_height = int(thumb_size * 0.56) + 4
                grid_height = rows * row_height + 20
                total_height += grid_height + 40  # +标签和间距

            # 设置容器最小高度，防止无限增长
            max_height = min(total_height, self.scroll_area.viewport().height() * 3)
            self.container.setMinimumHeight(max_height)
            print(f"[DEBUG] _refresh_favorites finished, fixed height={max_height}")

            # 恢复选中状态
            print(f"[DEBUG] Restored selected_indices: {self.selected_indices}")

        finally:
            self._is_refreshing = False

    def resizeEvent(self, event):
        """窗口大小变化时刷新布局"""
        super().resizeEvent(event)
        # 延迟刷新，避免频繁触发
        if not self._is_refreshing:
            QTimer.singleShot(200, self._refresh_favorites)

    def on_fav_click(self, idx):
        if idx in self.selected_indices:
            self.selected_indices.remove(idx)
        else:
            self.selected_indices.add(idx)
        self._refresh_favorites()
        self.export_btn.setEnabled(len(self.selected_indices) > 0)

    def preview_fav(self, idx):
        if idx >= len(self.favorites):
            return
        fav = self.favorites[idx]
        img_path = fav.get('path', '')
        if not img_path or not os.path.exists(img_path):
            QMessageBox.warning(self, "警告", "图片文件不存在。")
            return
        pixmap = QPixmap(img_path)
        if pixmap.isNull():
            return
        dlg = ZoomPreviewDialog(pixmap, fav.get('time', 0), self)
        dlg.exec()

    def toggle_select_all(self):
        if self.select_all_btn.isChecked():
            for idx in range(len(self.favorites)):
                self.selected_indices.add(idx)
        else:
            self.selected_indices.clear()
        self._refresh_favorites()
        self.export_btn.setEnabled(len(self.selected_indices) > 0)

    def export_selected(self):
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选中要导出的截图。")
            return

        default_dir = self.config.get_last_export_dir() or os.path.expanduser("~")
        export_dir = QFileDialog.getExistingDirectory(
            self,
            "选择导出目录",
            default_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if not export_dir:
            return
        self.config.set_last_export_dir(export_dir)

        # 创建视频子目录
        video_name = os.path.splitext(self.video_name)[0]
        full_export_dir = os.path.join(export_dir, video_name)
        os.makedirs(full_export_dir, exist_ok=True)

        exported_count = 0
        for idx in list(self.selected_indices):
            if idx >= len(self.favorites):
                continue
            fav = self.favorites[idx]
            img_path = fav.get('path', '')
            if not img_path or not os.path.exists(img_path):
                continue
            timestamp = fav.get('time', 0)
            dest_name = f"cover_{timestamp:.2f}s.jpg"
            dest_path = os.path.join(full_export_dir, dest_name)
            try:
                import shutil
                shutil.copy2(img_path, dest_path)
                fav['exported'] = True
                exported_count += 1
                # 更新数据库
                if self.controller and self.controller.video_id:
                    seg_label = fav.get('segment', 'A')
                    timestamp_ms = int(timestamp * 1000)
                    self.controller.db.update_favorite_exported(
                        self.controller.video_id, seg_label, timestamp_ms
                    )
            except Exception as e:
                logger.error(f"导出失败: {e}")

        if exported_count > 0:
            self.selected_indices.clear()
            self.export_btn.setEnabled(False)
            self._refresh_favorites()
            if self.controller:
                self.controller._notify_data_changed()
            QMessageBox.information(self, "导出完成", f"成功导出 {exported_count} 张截图到:\n{full_export_dir}")
        else:
            QMessageBox.warning(self, "警告", "导出失败。")

    def open_export_folder(self):
        """打开导出文件夹"""
        default_dir = self.config.get_last_export_dir() or os.path.expanduser("~")
        video_name = os.path.splitext(self.video_name)[0]
        full_dir = os.path.join(default_dir, video_name)

        if not os.path.exists(full_dir):
            # 如果目录不存在，创建它
            try:
                os.makedirs(full_dir, exist_ok=True)
            except Exception as e:
                QMessageBox.warning(self, "警告", f"无法创建目录: {e}")
                return

        # 打开文件夹
        import subprocess
        try:
            if os.name == 'nt':
                os.startfile(full_dir)
            else:
                subprocess.Popen(['xdg-open', full_dir])
        except Exception as e:
            QMessageBox.warning(self, "警告", f"无法打开文件夹: {e}")