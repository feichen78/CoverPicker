# ui/dialogs/favorites_dialog.py

import os
import shutil
import logging
from typing import List, Dict, Optional, Tuple
from functools import partial
from collections import defaultdict

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGridLayout, QScrollArea, QFrame, QMessageBox, QSizePolicy,
    QWidget, QTabWidget, QFileDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QFont, QColor

from ui.widgets import FavImageLabel
from ui.views.zoom_dialog import ZoomDialog
from ui.views.zoom_preview import ZoomPreviewDialog

logger = logging.getLogger(__name__)


class FavoritesDialog(QDialog):
    """收藏弹窗 - 按分区分组显示所有收藏截图"""

    def __init__(
        self,
        favorites: List[dict],
        video_name: str,
        export_base: str,
        video_path: str,
        parent=None
    ):
        super().__init__(parent)
        self.favorites = favorites
        self.video_name = video_name
        self.export_base = export_base
        self.video_path = video_path

        self.selected_indices: set = set()
        self.image_labels: List[FavImageLabel] = []
        self.fav_items: List[dict] = []  # 扁平化的收藏列表

        self.parent_view = parent

        self.setWindowTitle(f"⭐ 收藏 - {video_name}")
        self.setMinimumSize(700, 500)
        self.resize(900, 650)

        self.setup_ui()
        self.load_favorites()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # 标题栏
        title_layout = QHBoxLayout()
        title = QLabel(f"⭐ 收藏截图 - {self.video_name}")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        title_layout.addWidget(title)
        title_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setStyleSheet("""
            QPushButton { border: none; font-size: 16px; border-radius: 4px; }
            QPushButton:hover { background: #e74c3c; color: white; }
        """)
        close_btn.clicked.connect(self.reject)
        title_layout.addWidget(close_btn)

        main_layout.addLayout(title_layout)

        # 标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #ccc; border-radius: 4px; }
            QTabBar::tab { padding: 6px 12px; }
            QTabBar::tab:selected { background: #2196F3; color: white; }
        """)
        main_layout.addWidget(self.tab_widget)

        # 底部操作栏
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        self.selected_label = QLabel("已选: 0 张")
        bottom_bar.addWidget(self.selected_label)

        # 全选按钮（切换模式）
        self.select_all_btn = QPushButton("☑ 全选")
        self.select_all_btn.setCheckable(True)
        self.select_all_btn.setEnabled(False)
        self.select_all_btn.clicked.connect(self.toggle_select_all)
        bottom_bar.addWidget(self.select_all_btn)

        bottom_bar.addStretch()

        self.export_btn = QPushButton("📥 导出选中")
        self.export_btn.setEnabled(False)
        self.export_btn.setStyleSheet("background: #2196F3; color: white; font-weight: bold;")
        self.export_btn.clicked.connect(self.export_selected)
        bottom_bar.addWidget(self.export_btn)

        self.zoom_btn = QPushButton("🔍 细选")
        self.zoom_btn.setEnabled(False)
        self.zoom_btn.setStyleSheet("background: #FF9800; color: white; font-weight: bold;")
        self.zoom_btn.clicked.connect(self.zoom_selected)
        bottom_bar.addWidget(self.zoom_btn)

        main_layout.addLayout(bottom_bar)

        # 进度标签
        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: #888; font-size: 11px; padding: 4px;")
        main_layout.addWidget(self.progress_label)

    def load_favorites(self):
        """按分区分组加载收藏"""
        self.tab_widget.clear()
        self.fav_items = []
        self.selected_indices.clear()
        self.image_labels.clear()

        if not self.favorites:
            empty_label = QLabel("当前视频没有收藏截图")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #666; font-size: 16px; padding: 40px;")
            tab = QWidget()
            layout = QVBoxLayout(tab)
            layout.addWidget(empty_label)
            self.tab_widget.addTab(tab, "无收藏")
            self._update_buttons()
            return

        # 按分区分组
        groups = defaultdict(list)
        for fav in self.favorites:
            groups[fav.get('segment', '未知')].append(fav)

        # 为每个分区创建标签页
        for seg_label in sorted(groups.keys()):
            items = groups[seg_label]
            tab = QWidget()
            layout = QVBoxLayout(tab)
            layout.setContentsMargins(8, 8, 8, 8)

            # 网格区域
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)

            grid_widget = QWidget()
            grid_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            grid_layout = QGridLayout(grid_widget)
            grid_layout.setSpacing(6)
            grid_layout.setContentsMargins(4, 4, 4, 4)

            # 计算列数
            cols = 4
            for col in range(cols):
                grid_layout.setColumnStretch(col, 1)

            # 添加截图
            start_idx = len(self.fav_items)
            for pos, fav in enumerate(items):
                self.fav_items.append(fav)
                idx = start_idx + pos

                pixmap = QPixmap(200, 150)
                pixmap.fill(QColor(60, 60, 60))
                if fav.get('path') and os.path.exists(fav['path']):
                    loaded = QPixmap(fav['path'])
                    if not loaded.isNull():
                        pixmap = loaded

                label = FavImageLabel(pixmap, fav.get('time', 0))
                label.setObjectName(f"fav_{idx}")
                label.set_favorite(True)
                label.set_exported(fav.get('exported', False))
                label.set_selected(False)

                label.clicked.connect(partial(self.on_label_click, idx))
                label.double_clicked.connect(partial(self.preview_single, idx))

                row = pos // cols
                col = pos % cols
                grid_layout.addWidget(label, row, col)
                self.image_labels.append(label)

            scroll.setWidget(grid_widget)
            layout.addWidget(scroll)

            # 分区统计
            stat_label = QLabel(f"分区 {seg_label}: {len(items)} 张收藏")
            stat_label.setStyleSheet("color: #888; font-size: 11px; padding: 4px;")
            layout.addWidget(stat_label)

            self.tab_widget.addTab(tab, f"{seg_label} ({len(items)})")

        self._update_buttons()
        self._update_select_all_state()

    def on_label_click(self, idx: int):
        if idx in self.selected_indices:
            self.selected_indices.remove(idx)
        else:
            self.selected_indices.add(idx)
        self._refresh_selection()

    def preview_single(self, idx: int):
        if idx >= len(self.fav_items):
            return
        item = self.fav_items[idx]
        if not item.get('path') or not os.path.exists(item['path']):
            QMessageBox.warning(self, "警告", "图片文件不存在。")
            return
        pixmap = QPixmap(item['path'])
        if pixmap.isNull():
            return
        dlg = ZoomPreviewDialog(pixmap, item.get('time', 0), self)
        dlg.exec()

    def _refresh_selection(self):
        """刷新所有标签的选中状态"""
        for idx, label in enumerate(self.image_labels):
            label.set_selected(idx in self.selected_indices)
        self._update_buttons()
        self._update_select_all_state()

    def _update_buttons(self):
        has_selected = len(self.selected_indices) > 0
        self.export_btn.setEnabled(has_selected)
        self.zoom_btn.setEnabled(len(self.selected_indices) == 1)
        self.select_all_btn.setEnabled(len(self.fav_items) > 0)

    def _update_select_all_state(self):
        count = len(self.fav_items)
        if count == 0:
            self.select_all_btn.setEnabled(False)
            self.select_all_btn.setChecked(False)
            return
        self.select_all_btn.setEnabled(True)
        all_selected = len(self.selected_indices) == count
        self.select_all_btn.setChecked(all_selected)
        self.selected_label.setText(f"已选: {len(self.selected_indices)} 张")

    def toggle_select_all(self):
        count = len(self.fav_items)
        if count == 0:
            return
        if self.select_all_btn.isChecked():
            self.selected_indices = set(range(count))
        else:
            self.selected_indices.clear()
        self._refresh_selection()

    def export_selected(self):
        """导出收藏截图，支持自定义保存位置"""
        if not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选中要导出的收藏截图。")
            return

        # 弹出文件夹选择对话框
        export_dir = QFileDialog.getExistingDirectory(
            self,
            "选择导出目录",
            os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if not export_dir:
            return

        selected = [self.fav_items[i] for i in self.selected_indices]
        # 在用户选择的目录下创建视频名子目录
        export_dir = os.path.join(export_dir, self.video_name)
        os.makedirs(export_dir, exist_ok=True)

        exported = 0
        for item in selected:
            if not item.get('path') or not os.path.exists(item['path']):
                continue
            time_sec = item.get('time', 0)
            dest_name = f"cover_{time_sec:.2f}s.jpg"
            dest_path = os.path.join(export_dir, dest_name)
            try:
                shutil.copy2(item['path'], dest_path)
                item['exported'] = True
                exported += 1
            except Exception as e:
                logger.error(f"导出收藏失败: {e}")

        if exported > 0:
            # 更新标签显示
            for idx, label in enumerate(self.image_labels):
                if idx in self.selected_indices:
                    label.set_exported(True)
            # 保存状态到数据库
            if self.parent_view and hasattr(self.parent_view, 'controller'):
                controller = self.parent_view.controller
                controller._save_state_to_db()
                # 更新视频列表图标
                if hasattr(self.parent_view, '_update_video_list_icon'):
                    self.parent_view._update_video_list_icon(self.video_path)
            self.selected_indices.clear()
            self._refresh_selection()
            QMessageBox.information(self, "导出完成", f"成功导出 {exported} 张收藏截图到:\n{export_dir}")
        else:
            QMessageBox.warning(self, "警告", "导出失败，请检查文件是否存在。")

    def zoom_selected(self):
        if len(self.selected_indices) != 1:
            QMessageBox.information(self, "提示", "请只选中一张截图进入细选。")
            return

        idx = next(iter(self.selected_indices))
        item = self.fav_items[idx]
        if not item.get('path') or not os.path.exists(item['path']):
            QMessageBox.warning(self, "警告", "图片文件不存在。")
            return

        # 获取主控制器
        controller = None
        if self.parent_view and hasattr(self.parent_view, 'controller'):
            controller = self.parent_view.controller

        if not controller:
            QMessageBox.warning(self, "警告", "无法获取主控制器。")
            return

        # 查找对应的 seg_label 和 pos
        seg_label = item.get('segment', 'A')
        time_sec = item.get('time', 0)

        # 在 controller 的 screenshots 中查找匹配的截图
        items = controller.get_segment_items(seg_label)
        pos = -1
        for i, img in enumerate(items):
            if abs(img.get('time', 0) - time_sec) < 0.1:
                pos = i
                break

        if pos == -1:
            pos = 0

        dlg = ZoomDialog(
            controller=controller,
            seg_label=seg_label,
            seg_idx=0,
            pos=pos,
            center_time=time_sec,
            level=1,
            parent=self,
            source="favorites",
            original_fav_item=item,
        )
        dlg.exec()
        # 刷新收藏列表
        self.load_favorites()