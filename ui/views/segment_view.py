# ui/views/segment_view.py
# 完整版 —— 支持跨设备同步（file_id）
import os, asyncio, logging, traceback
from typing import List, Set, Tuple
from functools import partial
from datetime import timedelta
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, QTimer, QPoint, QRect, QSize, QFileSystemWatcher
from PySide6.QtGui import QPixmap, QFont, QColor, QAction, QKeyEvent, QPainter, QPen
from src.video_scanner import scan_videos_in_directory, get_video_duration
from src.controllers.segment_controller import SegmentController
from src.config_manager import ConfigManager
from ui.views.zoom_dialog import ZoomDialog
from ui.views.zoom_preview import ZoomPreviewDialog
from ui.views.preview_dialog import PreviewDialog
from ui.views.exclude_dialog import ExcludeDialog
from ui.widgets import ClickableLabel
from ui.dialogs.favorites_dialog import FavoritesDialog
logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
class QFlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, h_spacing=3, v_spacing=3):
        super().__init__(parent); self._items = []; self._h_spacing = h_spacing; self._v_spacing = v_spacing
        if parent: self.setContentsMargins(margin, margin, margin, margin)
    def addItem(self, item): self._items.append(item)
    def count(self): return len(self._items)
    def itemAt(self, index): return self._items[index] if 0 <= index < len(self._items) else None
    def takeAt(self, index): return self._items.pop(index) if 0 <= index < len(self._items) else None
    def expandingDirections(self): return Qt.Orientation(0)
    def hasHeightForWidth(self): return True
    def heightForWidth(self, width): return self._do_layout(QRect(0,0,width,0), True)
    def setGeometry(self, rect): super().setGeometry(rect); self._do_layout(rect, False)
    def sizeHint(self): return self.minimumSize()
    def minimumSize(self):
        size = QSize()
        for item in self._items: size = size.expandedTo(item.minimumSize())
        margin = self.contentsMargins(); size += QSize(margin.left()+margin.right(), margin.top()+margin.bottom())
        return size
    def _do_layout(self, rect, test_only):
        x=rect.x(); y=rect.y(); line_height=0; spacing=self._h_spacing
        for item in self._items:
            widget = item.widget()
            if widget and not widget.isVisible(): continue
            next_x = x + item.sizeHint().width() + spacing
            if next_x - spacing > rect.right() and line_height > 0:
                x = rect.x(); y = y + line_height + self._v_spacing; next_x = x + item.sizeHint().width() + spacing; line_height = 0
            if not test_only: item.setGeometry(QRect(QPoint(x,y), item.sizeHint()))
            x = next_x; line_height = max(line_height, item.sizeHint().height())
        return y + line_height - rect.y()
class SegmentView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        print("[DEBUG] SegmentView __init__ 开始")
        self.controller = SegmentController()
        self.controller.set_data_changed_callback(self._on_data_changed)
        self.controller.set_progress_callback(self._on_progress_update)
        self.config = ConfigManager()
        self.selected_indices: Set[tuple] = set()
        self.all_videos: List[str] = []
        self.filtered_videos: List[str] = []
        self.seg_buttons_layout = QHBoxLayout()
        self.seg_buttons: List[QPushButton] = []
        self.preview_dialog = None
        db_videos = self.controller.db.get_all_videos()
        self.all_videos = [v['file_path'] for v in db_videos]
        self.filtered_videos = self.all_videos.copy()
        self.setup_ui()
        self.setFocusPolicy(Qt.StrongFocus)
        self.video_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.video_list.customContextMenuRequested.connect(self._show_context_menu)
        self.video_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._update_cache_info()
        self._update_backup_status_label()
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(self._on_directory_changed)
        self._setup_watch_dirs()
        print("[DEBUG] SegmentView __init__ 完成")
    def setup_ui(self):
        main_layout = QHBoxLayout(self); main_layout.setContentsMargins(0,0,0,0); main_layout.setSpacing(0)
        left_panel = QWidget(); left_panel.setFixedWidth(220)
        left_layout = QVBoxLayout(left_panel); left_layout.setContentsMargins(8,8,8,8); left_layout.setSpacing(4)
        title_layout = QHBoxLayout()
        title = QLabel("📹 视频库"); title.setFont(QFont("Arial",13,QFont.Bold)); title_layout.addWidget(title); title_layout.addStretch()
        self.batch_delete_btn = QPushButton("🗑️"); self.batch_delete_btn.setFixedSize(30,30); self.batch_delete_btn.setToolTip("批量删除选中的视频（不删除文件）"); self.batch_delete_btn.setEnabled(False)
        self.batch_delete_btn.setStyleSheet("QPushButton{border:1px solid #888;border-radius:4px;background:transparent;font-size:16px;}QPushButton:hover{background:#e74c3c;color:white;}QPushButton:disabled{color:#666;}")
        self.batch_delete_btn.clicked.connect(self.batch_remove_videos); title_layout.addWidget(self.batch_delete_btn)
        self.import_btn = QPushButton("+"); self.import_btn.setFixedSize(30,30); self.import_btn.setToolTip("导入视频")
        self.import_btn.setStyleSheet("QPushButton{border:1px solid #888;border-radius:4px;background:transparent;font-size:16px;font-weight:bold;}QPushButton:hover{background:#3a3a3a;color:#2196F3;}")
        self.import_btn.clicked.connect(self._show_import_menu); title_layout.addWidget(self.import_btn)
        self.preview_toggle_btn = QPushButton("🎬"); self.preview_toggle_btn.setFixedSize(30,30); self.preview_toggle_btn.setToolTip("打开/关闭预览窗口"); self.preview_toggle_btn.setCheckable(True); self.preview_toggle_btn.setChecked(False)
        self.preview_toggle_btn.setStyleSheet("QPushButton{border:1px solid #888;border-radius:4px;background:transparent;font-size:14px;}QPushButton:checked{background:#2196F3;border-color:#2196F3;color:white;}QPushButton:hover{background:#3a3a3a;}QPushButton:checked:hover{background:#1a7ac4;}")
        self.preview_toggle_btn.clicked.connect(self.toggle_preview_dialog); title_layout.addWidget(self.preview_toggle_btn)
        left_layout.addLayout(title_layout)
        search_layout = QHBoxLayout(); search_layout.setSpacing(2)
        self.search_input = QLineEdit(); self.search_input.setPlaceholderText("🔍 搜索视频..."); self.search_input.setStyleSheet("QLineEdit{padding:4px 8px;border:1px solid #555;border-radius:4px;background:#2a2a2a;color:#eee;font-size:11px;}QLineEdit:focus{border-color:#2196F3;}")
        self.search_input.textChanged.connect(self._on_search_text_changed); search_layout.addWidget(self.search_input)
        self.clear_search_btn = QPushButton("✕"); self.clear_search_btn.setFixedSize(24,24); self.clear_search_btn.setToolTip("清空搜索"); self.clear_search_btn.setVisible(False)
        self.clear_search_btn.setStyleSheet("QPushButton{border:none;border-radius:12px;background:#555;color:white;font-size:11px;}QPushButton:hover{background:#e74c3c;}")
        self.clear_search_btn.clicked.connect(self._clear_search); search_layout.addWidget(self.clear_search_btn); left_layout.addLayout(search_layout)
        self.video_list = QListWidget(); self.video_list.setFont(QFont("Arial",10))
        self.video_list.setStyleSheet("QListWidget::item{padding:3px 5px;border-radius:2px;}QListWidget::item:selected{background:#2196F3;color:white;}QListWidget::item:hover{background:#3a3a3a;}")
        self.video_list.itemDoubleClicked.connect(self.on_video_selected); self.video_list.itemSelectionChanged.connect(self._update_batch_delete_btn_state)
        self._refresh_video_list(); left_layout.addWidget(self.video_list)
        info_group = QFrame(); info_group.setFrameShape(QFrame.StyledPanel); info_group.setStyleSheet("background:#f8f8f8;border-radius:4px;")
        info_layout = QVBoxLayout(info_group); info_layout.setSpacing(1)
        self.info_name = QLabel("未选择"); self.info_name.setObjectName("info_name"); font_name=self.info_name.font(); font_name.setPointSize(12); self.info_name.setFont(font_name)
        self.info_duration = QLabel("时长: --"); self.info_size = QLabel("大小: --"); self.info_path = QLabel("路径: --"); self.info_path.setWordWrap(True); self.info_path.setStyleSheet("font-size:11px;color:#666;")
        f=self.info_duration.font(); f.setPointSize(11); self.info_duration.setFont(f); self.info_size.setFont(f)
        info_layout.addWidget(self.info_name); info_layout.addWidget(self.info_duration); info_layout.addWidget(self.info_size); info_layout.addWidget(self.info_path); info_layout.addStretch()
        left_layout.addWidget(info_group)
        self.cache_label = QLabel("缓存: --"); self.cache_label.setObjectName("cache_label"); self.cache_label.setStyleSheet("font-size:12px;color:#888;"); left_layout.addWidget(self.cache_label)
        self.backup_status_label = QLabel("备份: 未设置"); self.backup_status_label.setObjectName("backup_status_label"); self.backup_status_label.setStyleSheet("font-size:12px;color:#888;"); left_layout.addWidget(self.backup_status_label)
        self.progress_label_left = QLabel(""); self.progress_label_left.setStyleSheet("color:#666;font-size:13px;font-weight:bold;padding:4px;"); self.progress_label_left.setWordWrap(True); left_layout.addWidget(self.progress_label_left)
        stat_layout = QHBoxLayout(); self.stat_locked = QLabel("锁定: 0"); self.stat_fav = QLabel("收藏: 0"); stat_layout.addWidget(self.stat_locked); stat_layout.addWidget(self.stat_fav); left_layout.addLayout(stat_layout); left_layout.addStretch()
        right_panel = QWidget(); right_layout = QVBoxLayout(right_panel); right_layout.setContentsMargins(8,8,8,8); right_layout.setSpacing(4)
        top_bar = QHBoxLayout(); self.video_name_label = QLabel("请选择视频"); self.video_name_label.setFont(QFont("Arial",13,QFont.Bold)); top_bar.addWidget(self.video_name_label); top_bar.addStretch(); self.time_display = QLabel("00:00:00"); self.time_display.setStyleSheet("font-family:monospace;font-size:13px;color:#333;"); top_bar.addWidget(self.time_display); right_layout.addLayout(top_bar)
        control_bar = QHBoxLayout(); control_bar.setSpacing(6)
        seg_group = QHBoxLayout(); seg_group.setSpacing(2); seg_group.setContentsMargins(0,0,0,0); self.seg_buttons_layout = seg_group; control_bar.addLayout(seg_group,1)
        seg_count_label = QLabel("分区:"); seg_count_label.setFont(QFont("Arial",9)); control_bar.addWidget(seg_count_label)
        self.seg_count_combo = QComboBox(); self.seg_count_combo.setFixedWidth(44); self.seg_count_combo.setFont(QFont("Arial",9))
        for i in range(3,8): self.seg_count_combo.addItem(str(i), i)
        self.seg_count_combo.setCurrentIndex(self.seg_count_combo.findData(5))
        self.seg_count_combo.currentIndexChanged.connect(self.on_seg_count_changed); control_bar.addWidget(self.seg_count_combo)
        control_bar.addStretch()
        dens_label = QLabel("密度:"); dens_label.setFont(QFont("Arial",9)); control_bar.addWidget(dens_label)
        self.density_buttons = []
        for d in [9,12,16,25]:
            btn = QPushButton(str(d)); btn.setCheckable(True); btn.setFixedSize(30,24); btn.setFont(QFont("Arial",8))
            if d == 9: btn.setChecked(True)
            btn.clicked.connect(lambda checked, val=d: self.on_density_changed(val)); control_bar.addWidget(btn); self.density_buttons.append(btn)
        self.exclude_btn = QPushButton("⛔ 排除区间"); self.exclude_btn.setToolTip("设置要排除的时间段（如片头片尾）"); self.exclude_btn.setStyleSheet("QPushButton{background:#666;color:white;font-weight:bold;padding:2px 8px;border-radius:4px;font-size:11px;}QPushButton:hover{background:#888;}"); self.exclude_btn.clicked.connect(self.show_exclude_dialog); control_bar.addWidget(self.exclude_btn)
        right_layout.addLayout(control_bar)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.NoFrame)
        self.grid_widget = QWidget(); self.grid_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.grid_layout = QGridLayout(self.grid_widget); self.grid_layout.setSpacing(2); self.grid_layout.setContentsMargins(2,2,2,2)
        self.scroll.setWidget(self.grid_widget); right_layout.addWidget(self.scroll,1)
        bottom_bar = QFlowLayout(); bottom_bar.setContentsMargins(10,6,10,6)
        self.selected_label = QLabel("已选: 0 张"); bottom_bar.addWidget(self.selected_label)
        self.select_all_btn = QPushButton("☑ 全选"); self.select_all_btn.setCheckable(True); self.select_all_btn.setEnabled(False); self.select_all_btn.clicked.connect(self.toggle_select_all); bottom_bar.addWidget(self.select_all_btn)
        view_fav_btn = QPushButton("⭐ 查看收藏"); view_fav_btn.clicked.connect(self.show_favorites); bottom_bar.addWidget(view_fav_btn)
        zoom_btn = QPushButton("🔍 细选"); zoom_btn.clicked.connect(self.zoom_selected); zoom_btn.setStyleSheet("background:#2196F3;color:white;font-weight:bold;"); bottom_bar.addWidget(zoom_btn)
        fav_btn = QPushButton("⭐ 收藏"); fav_btn.clicked.connect(self.favorite_selected); bottom_bar.addWidget(fav_btn)
        unfav_btn = QPushButton("☆ 取消收藏"); unfav_btn.clicked.connect(self.unfavorite_selected); bottom_bar.addWidget(unfav_btn)
        lock_btn = QPushButton("🔒 锁定"); lock_btn.clicked.connect(self.lock_selected); bottom_bar.addWidget(lock_btn)
        unlock_btn = QPushButton("🔓 解锁"); unlock_btn.clicked.connect(self.unlock_selected); bottom_bar.addWidget(unlock_btn)
        refresh_btn = QPushButton("🔄 刷新"); refresh_btn.clicked.connect(lambda: asyncio.create_task(self.refresh_unlocked())); bottom_bar.addWidget(refresh_btn)
        reset_btn = QPushButton("♻️ 重抽"); reset_btn.clicked.connect(lambda: asyncio.create_task(self.reset_all())); bottom_bar.addWidget(reset_btn)
        export_btn = QPushButton("📥 导出"); export_btn.clicked.connect(self.export_selected); bottom_bar.addWidget(export_btn)
        self.undo_btn = QPushButton("↩ 撤销"); self.undo_btn.setEnabled(False); self.undo_btn.clicked.connect(self.undo_action); bottom_bar.addWidget(self.undo_btn)
        self.redo_btn = QPushButton("↪ 重做"); self.redo_btn.setEnabled(False); self.redo_btn.clicked.connect(self.redo_action); bottom_bar.addWidget(self.redo_btn)
        clear_cache_btn = QPushButton("🗑️ 清缓存"); clear_cache_btn.clicked.connect(self.clear_cache); bottom_bar.addWidget(clear_cache_btn)
        self.backup_btn = QPushButton("💾 备份"); self.backup_btn.clicked.connect(self._backup_state); self.backup_btn.setToolTip("备份当前状态到云同步目录"); bottom_bar.addWidget(self.backup_btn)
        self.restore_btn = QPushButton("📂 恢复"); self.restore_btn.clicked.connect(self._restore_state); self.restore_btn.setToolTip("从备份文件恢复状态"); bottom_bar.addWidget(self.restore_btn)
        self.set_backup_dir_btn = QPushButton("📁 设置备份"); self.set_backup_dir_btn.setToolTip("设置备份文件的存储目录"); self.set_backup_dir_btn.clicked.connect(self._set_backup_dir); bottom_bar.addWidget(self.set_backup_dir_btn)
        self.watch_btn = QPushButton("📂 监控"); self.watch_btn.setToolTip("添加/删除监控目录（自动导入新视频）"); self.watch_btn.clicked.connect(self._manage_watch_dirs); bottom_bar.addWidget(self.watch_btn)
        right_layout.addLayout(bottom_bar)
        main_layout.addWidget(left_panel); main_layout.addWidget(right_panel)
        for btn in self.seg_buttons: btn.setEnabled(False)
    def _setup_watch_dirs(self):
        dirs = self.config.get_watch_dirs()
        for d in dirs:
            if os.path.exists(d) and d not in self.watcher.directories():
                self.watcher.addPath(d); logger.info(f"监控目录已添加: {d}")
    def _manage_watch_dirs(self):
        current_dirs = self.config.get_watch_dirs()
        msg = "当前监控目录:\n" + ("\n".join(current_dirs) if current_dirs else "(无)")
        reply = QMessageBox.question(self, "监控目录管理", msg + "\n\n是否添加新目录？\n（选择“No”则清空所有监控）", QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if reply == QMessageBox.Cancel: return
        elif reply == QMessageBox.Yes:
            dir_path = QFileDialog.getExistingDirectory(self, "选择要监控的目录", "", QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
            if not dir_path: return
            if dir_path not in current_dirs:
                current_dirs.append(dir_path); self.config.set_watch_dirs(current_dirs)
                if os.path.exists(dir_path): self.watcher.addPath(dir_path)
                self._scan_and_import_directory(dir_path)
            else: QMessageBox.information(self, "提示", "该目录已在监控列表中。")
        else:
            for d in current_dirs:
                if d in self.watcher.directories(): self.watcher.removePath(d)
            self.config.set_watch_dirs([]); QMessageBox.information(self, "完成", "已清空所有监控目录。")
    def _on_directory_changed(self, path: str):
        logger.info(f"监控目录发生变化: {path}"); self._scan_and_import_directory(path)
    def _scan_and_import_directory(self, dir_path: str):
        if not os.path.exists(dir_path): return
        video_files = scan_videos_in_directory(dir_path)
        if not video_files: return
        existing_names = {os.path.basename(p).lower() for p in self.all_videos}
        new_files = []
        for f in video_files:
            base = os.path.basename(f).lower()
            if base not in existing_names:
                new_files.append(f); existing_names.add(base)
        if new_files:
            logger.info(f"自动导入 {len(new_files)} 个新视频"); self._add_videos(new_files)
    def _update_backup_status_label(self):
        backup_dir = self.config.get_backup_dir()
        if backup_dir and os.path.exists(backup_dir):
            self.backup_status_label.setText(f"备份: {backup_dir}"); self.backup_status_label.setStyleSheet("font-size:12px;color:#4CAF50;")
        elif backup_dir:
            self.backup_status_label.setText(f"备份: 目录不存在"); self.backup_status_label.setStyleSheet("font-size:12px;color:#FF9800;")
        else:
            self.backup_status_label.setText("备份: 未设置"); self.backup_status_label.setStyleSheet("font-size:12px;color:#888;")
    def _set_backup_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择备份目录", os.path.expanduser("~"), QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if not dir_path: return
        test_file = os.path.join(dir_path, ".coverpicker_test")
        try:
            with open(test_file, 'w') as f: f.write("test")
            os.remove(test_file)
        except Exception as e:
            QMessageBox.warning(self, "目录不可写", f"无法写入该目录:\n{str(e)}"); return
        self.config.set_backup_dir(dir_path); self._update_backup_status_label()
        QMessageBox.information(self, "设置成功", f"备份目录已设置为:\n{dir_path}")
    def _backup_state(self):
        backup_dir = self.config.get_backup_dir()
        if not backup_dir:
            if QMessageBox.question(self, "未设置备份目录", "是否现在设置？", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes: self._set_backup_dir()
            return
        if not os.path.exists(backup_dir): QMessageBox.warning(self, "目录不存在", "请重新设置备份目录。"); self._set_backup_dir(); return
        self.backup_btn.setEnabled(False); self.backup_btn.setText("⏳ 备份中...")
        success, result = self.controller.db.backup(backup_dir)
        self.backup_btn.setEnabled(True); self.backup_btn.setText("💾 备份")
        if success:
            QMessageBox.information(self, "备份成功", f"状态已备份到:\n{result}"); self._show_recent_backups()
        else: QMessageBox.warning(self, "备份失败", f"错误: {result}")
    def _restore_state(self):
        backup_dir = self.config.get_backup_dir()
        if not backup_dir or not os.path.exists(backup_dir): QMessageBox.warning(self, "备份目录不存在", "请先设置有效的备份目录。"); self._set_backup_dir(); return
        backups = self.controller.db.get_backup_history(backup_dir)
        if not backups: QMessageBox.information(self, "无备份文件", f"在备份目录中未找到备份文件:\n{backup_dir}"); return
        items = []
        for b in backups:
            size_mb = b['size']/(1024*1024); items.append(f"{b['name']}  ({b['time']})  {size_mb:.1f}MB")
        selected, ok = QInputDialog.getItem(self, "选择备份文件", "请选择要恢复的备份文件:", items, 0, False)
        if not ok or not selected: return
        idx = items.index(selected); backup_path = backups[idx]['path']
        if QMessageBox.question(self, "确认恢复", f"将从 {backup_path} 恢复，当前进度将丢失！继续？", QMessageBox.Yes|QMessageBox.No) != QMessageBox.Yes: return
        success, result = self.controller.db.restore(backup_path)
        if success: QMessageBox.information(self, "恢复成功", "程序将关闭，请手动重启。"); QApplication.quit()
        else: QMessageBox.warning(self, "恢复失败", f"错误: {result}")
    def _show_recent_backups(self):
        backup_dir = self.config.get_backup_dir()
        if not backup_dir or not os.path.exists(backup_dir): return
        backups = self.controller.db.get_backup_history(backup_dir, limit=5)
        if not backups: return
        msg = "最近备份:\n\n"
        for b in backups[:5]:
            size_mb = b['size']/(1024*1024); msg += f"  • {b['name']}\n    时间: {b['time']}  ({size_mb:.1f}MB)\n\n"
        QMessageBox.information(self, "最近备份", msg.strip())
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key(); mod = event.modifiers()
        if key == Qt.Key_A and mod == Qt.ControlModifier: self.select_all(); return
        if key == Qt.Key_D and mod == Qt.ControlModifier: self.deselect_all(); return
        if key == Qt.Key_Delete: self._delete_selected_screenshots(); return
        if key == Qt.Key_Space and not event.isAutoRepeat(): self._preview_selected_screenshot(); return
        if key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            if self.grid_widget.hasFocus() or not self.scroll.hasFocus(): self._move_selection(key)
        super().keyPressEvent(event)
    def _move_selection(self, key):
        seg_label, _, _ = self.controller.get_current_segment()
        if seg_label is None: return
        items = self.controller.get_segment_items(seg_label); count = len(items)
        if count == 0: return
        cols = {9:3,12:3,16:4,25:5}.get(self.controller.density,4)
        if self.selected_indices: current_pos = next(iter(self.selected_indices))[1]
        else: current_pos = 0
        if key == Qt.Key_Left: new_pos = max(0, current_pos-1)
        elif key == Qt.Key_Right: new_pos = min(count-1, current_pos+1)
        elif key == Qt.Key_Up: new_pos = max(0, current_pos-cols)
        else: new_pos = min(count-1, current_pos+cols)
        self.selected_indices.clear(); self.selected_indices.add((self.controller.current_seg_index, new_pos)); self._refresh_grid()
    def _delete_selected_screenshots(self):
        if not self.selected_indices: return
        if QMessageBox.question(self, "确认删除", f"删除 {len(self.selected_indices)} 张截图？", QMessageBox.Yes|QMessageBox.No) != QMessageBox.Yes: return
        seg_label, _, _ = self.controller.get_current_segment()
        items = self.controller.get_segment_items(seg_label)
        positions = sorted([pos for (seg_idx, pos) in self.selected_indices], reverse=True)
        for pos in positions:
            if pos < len(items):
                item = items[pos]
                if item.get('favorite', False): self.controller.unfavorite_selected(seg_label, [pos])
                if item.get('locked', False): self.controller.unlock_selected(seg_label, [pos])
                if item.get('path') and os.path.exists(item['path']):
                    try: os.remove(item['path'])
                    except: pass
                items.pop(pos)
        self.selected_indices.clear(); self._refresh_grid(); self._update_select_all_state()
    def _preview_selected_screenshot(self):
        if len(self.selected_indices) != 1: return
        seg_idx, pos = next(iter(self.selected_indices))
        seg_label, _, _ = self.controller.get_current_segment()
        items = self.controller.get_segment_items(seg_label)
        if pos >= len(items): return
        item = items[pos]
        if not item.get('path') or not os.path.exists(item['path']): QMessageBox.warning(self, "警告", "图片文件不存在。"); return
        pixmap = QPixmap(item['path'])
        if pixmap.isNull(): return
        from ui.views.zoom_preview import ZoomPreviewDialog
        dlg = ZoomPreviewDialog(pixmap, item['time'], self); dlg.exec()
    def _update_cache_info(self):
        if hasattr(self, 'cache_label'):
            size_mb = self.controller.get_cache_size_mb(); file_count = self.controller.get_cache_file_count()
            if size_mb > 1024: self.cache_label.setText(f"缓存: {size_mb/1024:.2f} GB ({file_count} 个文件)")
            else: self.cache_label.setText(f"缓存: {size_mb:.1f} MB ({file_count} 个文件)")
    def show_exclude_dialog(self):
        dlg = ExcludeDialog(self.controller.excluded_ranges, self.controller.duration, self)
        if dlg.exec():
            self.controller.excluded_ranges = dlg.get_ranges()
            if self.controller.get_video_path():
                asyncio.create_task(self.controller.load_segment(self.controller.current_seg_index, restore_locks=True, randomize=False))
            QMessageBox.information(self, "提示", "排除区间已更新，当前分区将重新生成。")
    def _update_batch_delete_btn_state(self): self.batch_delete_btn.setEnabled(len(self.video_list.selectedItems()) > 0)
    def batch_remove_videos(self):
        items = self.video_list.selectedItems()
        if not items: return
        video_paths = [item.data(Qt.UserRole) for item in items if item.data(Qt.UserRole)]
        if not video_paths: return
        if QMessageBox.question(self, "确认批量删除", f"删除 {len(video_paths)} 个视频（不删除文件）？", QMessageBox.Yes|QMessageBox.No) != QMessageBox.Yes: return
        removed=0; failed=[]
        current_path = self.controller.get_video_path()
        for v in video_paths:
            if self.controller.remove_video(v):
                removed+=1
                if v in self.all_videos: self.all_videos.remove(v)
                if v in self.filtered_videos: self.filtered_videos.remove(v)
            else: failed.append(os.path.basename(v))
        if current_path and current_path not in self.all_videos:
            self.video_name_label.setText("请选择视频"); self.info_name.setText("未选择")
            self.info_duration.setText("时长: --"); self.info_size.setText("大小: --"); self.info_path.setText("路径: --")
            self._refresh_grid()
            for btn in self.seg_buttons: btn.setEnabled(False)
            if self.preview_dialog and self.preview_dialog.isVisible(): self.preview_dialog.close()
        self._refresh_video_list(); self._update_batch_delete_btn_state()
        if failed: QMessageBox.warning(self, "批量删除完成", f"成功 {removed} 个，失败 {len(failed)} 个:\n"+"\n".join(failed))
        else: QMessageBox.information(self, "批量删除完成", f"成功删除 {removed} 个视频。")
    def toggle_preview_dialog(self):
        if self.preview_dialog is None:
            self.preview_dialog = PreviewDialog(self)
            self.preview_dialog.set_main_controller(self.controller)
            self.preview_dialog.export_clip_requested.connect(self._on_clip_exported)
            self.preview_dialog.finished.connect(lambda: self.preview_toggle_btn.setChecked(False))
            if self.controller.get_video_path():
                self.preview_dialog.set_video(self.controller.get_video_path(), self.controller.get_duration(), self.controller.get_temp_dir())
        if self.preview_dialog.isVisible():
            self.preview_dialog.hide(); self.preview_toggle_btn.setChecked(False)
        else:
            self.preview_dialog.show(); self.preview_toggle_btn.setChecked(True)
            if self.controller.get_video_path():
                self.preview_dialog.set_video(self.controller.get_video_path(), self.controller.get_duration(), self.controller.get_temp_dir())
    def _on_clip_exported(self, output_path): pass
    def _show_import_menu(self):
        menu = QMenu(self)
        act_files = QAction("📄 导入视频文件", self); act_files.triggered.connect(self._import_video_files); menu.addAction(act_files)
        act_folder = QAction("📁 导入文件夹", self); act_folder.triggered.connect(self._import_folder); menu.addAction(act_folder)
        menu.exec(self.import_btn.mapToGlobal(self.import_btn.rect().bottomLeft()))
    def _import_video_files(self):
        fd = QFileDialog(self); fd.setWindowTitle("选择视频文件")
        fd.setNameFilter("视频文件 (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.mpg *.mpeg *.ts *.m2ts *.3gp *.asf *.vob *.ogv *.ogg *.divx *.xvid *.mts *.m2v *.m4p *.m4b *.m4r *.mpv *.mpe *.mxf *.rm *.rmvb *.swf *.f4v)")
        fd.setFileMode(QFileDialog.ExistingFiles)
        if fd.exec(): files = fd.selectedFiles(); self._add_videos(files)
    def _import_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹", "", QFileDialog.ShowDirsOnly)
        if folder:
            from src.video_scanner import scan_videos
            video_files = scan_videos(folder)
            if video_files: self._add_videos(video_files); QMessageBox.information(self, "导入完成", f"导入 {len(video_files)} 个视频")
            else: QMessageBox.information(self, "提示", "未找到视频文件。")
    def _add_videos(self, video_paths: List[str]):
        existing_names = {os.path.basename(p).lower() for p in self.all_videos}
        added=0; skipped=0; cached=0
        for path in video_paths:
            try:
                size = int(os.path.getsize(path)); mtime = int(os.path.getmtime(path))
                name = os.path.basename(path)
                existing = self.controller.db.get_video_by_path(path)
                if existing:
                    if existing.get('file_size') == size and existing.get('modified_time') == mtime:
                        cached += 1
                        if path not in self.all_videos: self.all_videos.append(path); self.filtered_videos.append(path)
                        continue
                    else:
                        self.controller.db.get_or_create_video(path, name, 0, "", size, mtime)
                        if path not in self.all_videos: self.all_videos.append(path); self.filtered_videos.append(path)
                        added += 1
                        continue
                file_id = self.controller.db._compute_file_id(path, size, mtime)
                existing_by_id = self.controller.db.get_video_by_file_id(file_id)
                if existing_by_id:
                    cursor = self.controller.db._get_conn().cursor()
                    cursor.execute("UPDATE videos SET file_path = ? WHERE id = ?", (path, existing_by_id['id']))
                    self.controller.db._get_conn().commit()
                    if path not in self.all_videos: self.all_videos.append(path); self.filtered_videos.append(path)
                    cached += 1
                    continue
                duration = get_video_duration(path)
                if duration is None: duration = 0
                self.controller.db.get_or_create_video(path, name, int(duration), "", size, mtime)
                self.all_videos.append(path); self.filtered_videos.append(path); added += 1
            except Exception as e:
                logger.error(f"添加视频失败 {path}: {e}")
                if path in self.all_videos: self.all_videos.remove(path); self.filtered_videos.remove(path)
                continue
        self._refresh_video_list()
        if self.search_input.text().strip(): self._on_search_text_changed(self.search_input.text())
        QMessageBox.information(self, "导入完成", f"成功导入 {added} 个视频。\n从缓存读取 {cached} 个视频（文件未变化或已通过 file_id 识别）。\n跳过已存在（同名）: {skipped} 个。")
    def _on_search_text_changed(self, text):
        self.clear_search_btn.setVisible(len(text)>0)
        if not text.strip(): self.filtered_videos = self.all_videos.copy()
        else:
            t = text.strip().lower(); self.filtered_videos = [p for p in self.all_videos if t in os.path.basename(p).lower()]
        self._refresh_video_list()
        if self.controller.get_video_path() and self.controller.get_video_path() not in self.filtered_videos: self.video_list.clearSelection()
    def _clear_search(self):
        self.search_input.clear(); self.clear_search_btn.setVisible(False)
        self.filtered_videos = self.all_videos.copy(); self._refresh_video_list()
    def _refresh_video_list(self):
        self.video_list.clear()
        for path in self.filtered_videos:
            name = os.path.basename(path); item = QListWidgetItem(name); item.setData(Qt.UserRole, path)
            icon = self.controller.get_video_state_icon(path)
            if icon: item.setText(f"{icon} {name}")
            self.video_list.addItem(item)
    def _update_video_list_icon(self, video_path):
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            if item.data(Qt.UserRole) == video_path:
                name = os.path.basename(video_path); icon = self.controller.get_video_state_icon(video_path)
                item.setText(f"{icon} {name}" if icon else name); break
    def _refresh_all_video_icons(self):
        for i in range(self.video_list.count()):
            item = self.video_list.item(i); path = item.data(Qt.UserRole)
            if path:
                name = os.path.basename(path); icon = self.controller.get_video_state_icon(path)
                item.setText(f"{icon} {name}" if icon else name)
    def _show_context_menu(self, pos):
        item = self.video_list.itemAt(pos)
        if not item: return
        video_path = item.data(Qt.UserRole)
        if not video_path: return
        menu = QMenu(self)
        act = QAction("❌ 从库中移除", self); act.triggered.connect(lambda: self._remove_video_from_library(video_path)); menu.addAction(act)
        if len(self.video_list.selectedItems()) > 1:
            act2 = QAction("🗑️ 批量删除", self); act2.triggered.connect(self.batch_remove_videos); menu.addAction(act2)
        menu.exec(self.video_list.mapToGlobal(pos))
    def _remove_video_from_library(self, video_path):
        if QMessageBox.question(self, "确认移除", f"移除 {os.path.basename(video_path)}？", QMessageBox.Yes|QMessageBox.No) != QMessageBox.Yes: return
        if not self.controller.remove_video(video_path): QMessageBox.warning(self, "错误", "移除失败。"); return
        if video_path in self.all_videos: self.all_videos.remove(video_path)
        if video_path in self.filtered_videos: self.filtered_videos.remove(video_path)
        self._refresh_video_list()
        if self.controller.get_video_path() is None:
            self.video_name_label.setText("请选择视频"); self.info_name.setText("未选择")
            self.info_duration.setText("时长: --"); self.info_size.setText("大小: --"); self.info_path.setText("路径: --")
            self._refresh_grid()
            for btn in self.seg_buttons: btn.setEnabled(False)
            if self.preview_dialog and self.preview_dialog.isVisible(): self.preview_dialog.close()
        QMessageBox.information(self, "完成", "已移除。")
    def on_video_selected(self, item):
        path = item.data(Qt.UserRole)
        if path: asyncio.create_task(self._load_video(path))
    async def _load_video(self, video_path):
        self.progress_label_left.setText("加载中...")
        if not await self.controller.load_video(video_path):
            QMessageBox.critical(self, "错误", f"无法加载视频: {video_path}")
            self.progress_label_left.setText("加载失败"); return
        self.video_name_label.setText(self.controller.get_video_name())
        self.info_name.setText(self.controller.get_video_name())
        self.info_path.setText(f"路径: {video_path}")
        dur = self.controller.get_duration()
        self.info_duration.setText(f"时长: {str(timedelta(seconds=int(dur)))}")
        size_mb = os.path.getsize(video_path)/(1024*1024)
        self.info_size.setText(f"大小: {size_mb:.2f} MB")
        self.selected_indices.clear()
        self._rebuild_seg_buttons(); self._refresh_grid(); self._update_fav_count()
        self._refresh_all_video_icons(); self.progress_label_left.setText("加载完成")
        if self.preview_dialog and self.preview_dialog.isVisible():
            self.preview_dialog.set_video(video_path, dur, self.controller.get_temp_dir())
        for btn in self.seg_buttons: btn.setEnabled(True)
        self._update_undo_redo_buttons(); self._update_select_all_state()
    def _rebuild_seg_buttons(self):
        from functools import partial
        for btn in self.seg_buttons:
            self.seg_buttons_layout.removeWidget(btn); btn.deleteLater()
        self.seg_buttons.clear()
        segments = self.controller.get_segments()
        if not segments: return
        current_idx = self.controller.current_seg_index
        for i,(label,start,end) in enumerate(segments):
            time_range = f"{self._format_time(start)} - {self._format_time(end)}"
            btn = QPushButton(f"{label} {time_range}")
            btn.setCheckable(True); btn.setMinimumWidth(90); btn.setMaximumWidth(180)
            btn.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed); btn.setFixedHeight(34)
            btn.setFont(QFont("Arial",9,QFont.Bold)); btn.setChecked(i == current_idx)
            btn.clicked.connect(partial(self.on_seg_clicked, i))
            self.seg_buttons_layout.addWidget(btn); self.seg_buttons.append(btn)
    def _update_seg_buttons_state(self):
        current_idx = self.controller.current_seg_index
        for i, btn in enumerate(self.seg_buttons): btn.setChecked(i == current_idx)
    def _format_time(self, seconds):
        h = int(seconds//3600); m = int((seconds%3600)//60); s = int(seconds%60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    def on_seg_clicked(self, idx: int):
        print(f"[DEBUG] on_seg_clicked 被调用: idx={idx}, 当前索引={self.controller.current_seg_index}")
        if idx < 0 or idx >= len(self.controller.segments):
            print(f"[DEBUG] on_seg_clicked 无效索引: idx={idx}, segments数量={len(self.controller.segments)}"); return
        if idx == self.controller.current_seg_index:
            print(f"[DEBUG] 点击的是当前分区 {idx}，不执行加载"); return
        if self.controller._load_task and not self.controller._load_task.done():
            print(f"[DEBUG] 取消之前的加载任务")
            self.controller._load_task.cancel(); self.controller._load_task = None
        self.controller.current_seg_index = idx
        self._update_seg_buttons_state()
        print(f"[DEBUG] 索引已更新为 {idx}，准备加载")
        self.controller._load_task = asyncio.create_task(self.controller._load_segment(idx, restore_locks=True, randomize=False))
        print(f"[DEBUG] 加载任务已创建")
    def on_seg_count_changed(self, index):
        if index < 0: return
        new_count = self.seg_count_combo.itemData(index)
        if new_count is None: return
        cur = self.controller.get_num_segments()
        if new_count == cur: return
        if self.controller.get_video_path():
            if QMessageBox.question(self, "确认", f"分区数改为 {new_count}，截图将重置。继续？", QMessageBox.Yes|QMessageBox.No) != QMessageBox.Yes:
                self.seg_count_combo.setCurrentIndex(self.seg_count_combo.findData(cur)); return
        self.controller.set_num_segments(new_count)
        self._rebuild_seg_buttons(); self.selected_indices.clear(); self._update_select_all_state()
        if self.controller.get_video_path():
            asyncio.create_task(self.controller.load_segment(0, restore_locks=True, randomize=False))
    def _on_progress_update(self, msg): self.progress_label_left.setText(msg)
    def _on_data_changed(self):
        self._rebuild_seg_buttons(); self._refresh_grid(); self._update_fav_count()
        self._refresh_all_video_icons(); self._update_undo_redo_buttons()
        self._update_cache_info(); self._update_select_all_state()
    def _update_select_all_state(self):
        seg_label, _, _ = self.controller.get_current_segment()
        if seg_label is None: self.select_all_btn.setEnabled(False); self.select_all_btn.setChecked(False); return
        items = self.controller.get_segment_items(seg_label); count = len(items)
        if count == 0: self.select_all_btn.setEnabled(False); self.select_all_btn.setChecked(False); return
        self.select_all_btn.setEnabled(True)
        all_selected = len(self.selected_indices) == count
        self.select_all_btn.setChecked(all_selected)
    def toggle_select_all(self):
        seg_label, _, _ = self.controller.get_current_segment()
        items = self.controller.get_segment_items(seg_label); count = len(items)
        if count == 0: return
        if self.select_all_btn.isChecked():
            for pos in range(count): self.selected_indices.add((self.controller.current_seg_index, pos))
        else: self.selected_indices.clear()
        self._refresh_grid(); self._update_select_all_state()
    def _refresh_grid(self):
        try:
            segments = self.controller.get_segments()
            if not segments or self.controller.current_seg_index >= len(segments): self._update_select_all_state(); return
            seg_label, _, _ = segments[self.controller.current_seg_index]
            items = self.controller.get_segment_items(seg_label); count = len(items)
            while self.grid_layout.count():
                child = self.grid_layout.takeAt(0)
                if child.widget(): child.widget().deleteLater()
            if count == 0: self._update_select_all_state(); return
            density = self.controller.density
            cols = {9:3,12:3,16:4,25:5}.get(density,4)
            for c in range(cols): self.grid_layout.setColumnStretch(c,1)
            locked_count = sum(1 for it in items if it.get('locked', False))
            self.stat_locked.setText(f"锁定: {locked_count}")
            for pos, item in enumerate(items):
                row = pos // cols; col = pos % cols
                img_path = item.get('path')
                pixmap = QPixmap(200,150); pixmap.fill(QColor(60,60,60))
                if img_path and os.path.exists(img_path):
                    loaded = QPixmap(img_path)
                    if not loaded.isNull(): pixmap = loaded
                    else:
                        painter = QPainter(pixmap); painter.setPen(QPen(QColor(255,0,0),3)); painter.drawText(pixmap.rect(), Qt.AlignCenter, "✕"); painter.end()
                else:
                    painter = QPainter(pixmap); painter.setPen(QPen(QColor(200,200,200),2)); painter.setFont(QFont("Arial",12,QFont.Bold)); painter.drawText(pixmap.rect(), Qt.AlignCenter, "⏳ 加载中..."); painter.end()
                index_num = pos + 1
                label = ClickableLabel(pixmap, item['time'], index_num)
                label.setObjectName(f"{self.controller.current_seg_index}_{pos}")
                label.set_locked(item.get('locked', False)); label.set_favorite(item.get('favorite', False)); label.set_exported(item.get('exported', False))
                label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                if (self.controller.current_seg_index, pos) in self.selected_indices: label.set_selected(True)
                label.clicked.connect(partial(self.on_image_click, pos))
                label.double_clicked.connect(partial(self.preview_image, pos))
                self.grid_layout.addWidget(label, row, col)
            row_count = self.grid_layout.rowCount()
            for r in range(row_count): self.grid_layout.setRowStretch(r,1)
            self._update_selected_count(); self._update_select_all_state()
            self.grid_widget.updateGeometry(); self.grid_widget.update(); self.scroll.update(); QApplication.processEvents()
        except Exception as e: logger.error(f"刷新网格出错: {e}\n{traceback.format_exc()}")
    def _update_fav_count(self):
        count = self.controller.get_favorites_count(); self.stat_fav.setText(f"收藏: {count}")
    def _update_selected_count(self):
        count = len(self.selected_indices); self.selected_label.setText(f"已选: {count} 张")
    def on_image_click(self, pos: int):
        key = (self.controller.current_seg_index, pos)
        if key in self.selected_indices: self.selected_indices.remove(key)
        else: self.selected_indices.add(key)
        self._refresh_grid()
    def preview_image(self, pos: int):
        seg_label, _, _ = self.controller.get_current_segment()
        items = self.controller.get_segment_items(seg_label)
        if pos >= len(items): return
        item = items[pos]
        if not item.get('path') or not os.path.exists(item['path']): QMessageBox.warning(self, "警告", "图片文件不存在。"); return
        pixmap = QPixmap(item['path'])
        if pixmap.isNull(): return
        dlg = ZoomPreviewDialog(pixmap, item['time'], self); dlg.exec()
    def select_all(self):
        seg_label, _, _ = self.controller.get_current_segment()
        items = self.controller.get_segment_items(seg_label)
        for pos in range(len(items)): self.selected_indices.add((self.controller.current_seg_index, pos))
        self._refresh_grid(); self._update_select_all_state()
    def deselect_all(self):
        self.selected_indices.clear(); self._refresh_grid(); self._update_select_all_state()
    def show_favorites(self):
        if not self.controller.get_video_path(): QMessageBox.information(self, "提示", "请先加载视频。"); return
        current_favs = self.controller.get_current_favorites()
        if not current_favs: QMessageBox.information(self, "提示", "当前视频没有收藏截图。"); return
        dlg = FavoritesDialog(current_favs, self.controller.get_video_name(), self.controller.get_export_base(), self.controller.get_video_path(), self)
        dlg.exec(); self._refresh_grid()
    def favorite_selected(self):
        if not self.selected_indices: QMessageBox.information(self, "提示", "请先选中要收藏的截图。"); return
        seg_label, _, _ = self.controller.get_current_segment()
        positions = [pos for (seg_idx, pos) in self.selected_indices if seg_idx == self.controller.current_seg_index]
        added, skipped = self.controller.favorite_selected(seg_label, positions)
        if added > 0:
            self.selected_indices.clear(); self._update_select_all_state()
            QMessageBox.information(self, "完成", f"成功收藏 {added} 张截图。")
        else: QMessageBox.information(self, "提示", "选中的截图已经收藏过了。")
    def unfavorite_selected(self):
        if not self.selected_indices: QMessageBox.information(self, "提示", "请先选中要取消收藏的截图。"); return
        seg_label, _, _ = self.controller.get_current_segment()
        positions = [pos for (seg_idx, pos) in self.selected_indices if seg_idx == self.controller.current_seg_index]
        removed = self.controller.unfavorite_selected(seg_label, positions)
        if removed > 0:
            self.selected_indices.clear(); self._update_select_all_state()
            QMessageBox.information(self, "完成", f"成功取消收藏 {removed} 张截图。")
    def lock_selected(self):
        if not self.selected_indices: QMessageBox.information(self, "提示", "请先选中要锁定的截图。"); return
        seg_label, _, _ = self.controller.get_current_segment()
        positions = [pos for (seg_idx, pos) in self.selected_indices if seg_idx == self.controller.current_seg_index]
        self.controller.lock_selected(seg_label, positions)
        self.selected_indices.clear(); self._update_select_all_state()
    def unlock_selected(self):
        if not self.selected_indices: QMessageBox.information(self, "提示", "请先选中要解锁的截图。"); return
        seg_label, _, _ = self.controller.get_current_segment()
        positions = [pos for (seg_idx, pos) in self.selected_indices if seg_idx == self.controller.current_seg_index]
        self.controller.unlock_selected(seg_label, positions)
        self.selected_indices.clear(); self._update_select_all_state()
    async def refresh_unlocked(self):
        seg_idx = self.controller.current_seg_index
        refreshed = await self.controller.refresh_unlocked(seg_idx)
        if refreshed == 0: QMessageBox.information(self, "提示", "当前分段没有未锁定的截图。")
        else: self.selected_indices.clear(); self._update_select_all_state()
    async def reset_all(self):
        seg_idx = self.controller.current_seg_index
        await self.controller.reset_segment(seg_idx)
        self.selected_indices.clear(); self._update_select_all_state()
    def export_selected(self):
        if not self.selected_indices: QMessageBox.information(self, "提示", "请先选中要导出的截图。"); return
        export_dir = QFileDialog.getExistingDirectory(self, "选择导出目录", os.path.expanduser("~"), QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if not export_dir: return
        seg_label, _, _ = self.controller.get_current_segment()
        positions = [pos for (seg_idx, pos) in self.selected_indices if seg_idx == self.controller.current_seg_index]
        exported, _ = self.controller.export_selected(seg_label, positions, export_dir)
        if exported == 0: QMessageBox.warning(self, "警告", "导出失败或选中的文件不存在。"); return
        self.selected_indices.clear(); self._update_select_all_state()
        QMessageBox.information(self, "导出完成", f"成功导出 {exported} 张截图到:\n{export_dir}")
    def _update_undo_redo_buttons(self):
        self.undo_btn.setEnabled(self.controller.can_undo()); self.redo_btn.setEnabled(self.controller.can_redo())
    def undo_action(self): self.controller.undo(); self._update_undo_redo_buttons()
    def redo_action(self): self.controller.redo(); self._update_undo_redo_buttons()
    def clear_cache(self):
        count = self.controller.clear_cache(); self._update_cache_info()
        QMessageBox.information(self, "清理完成", f"已清理 {count} 个缓存文件。")
    def zoom_selected(self):
        if len(self.selected_indices) > 1: QMessageBox.information(self, "提示", "细选只能针对单张截图，请只选中一张截图。"); return
        if not self.selected_indices: QMessageBox.information(self, "提示", "请先选中一张截图，然后点击'细选'。"); return
        seg_idx, pos = next(iter(self.selected_indices))
        seg_label, _, _ = self.controller.get_current_segment()
        items = self.controller.get_segment_items(seg_label)
        if pos >= len(items): QMessageBox.warning(self, "警告", "截图数据不存在"); return
        item = items[pos]
        if not item.get('path') or not os.path.exists(item['path']): QMessageBox.warning(self, "警告", "图片文件不存在。"); return
        dlg = ZoomDialog(controller=self.controller, seg_label=seg_label, seg_idx=seg_idx, pos=pos, center_time=item['time'], level=1, parent=self, source="main", original_fav_item=None)
        dlg.exec(); self._refresh_grid()
    def on_density_changed(self, val: int):
        self.controller.density = val
        for btn in self.density_buttons: btn.setChecked(int(btn.text()) == val)
        if self.controller.get_video_path():
            asyncio.create_task(self.controller.load_segment(self.controller.current_seg_index, restore_locks=True, randomize=False))
    def closeEvent(self, event):
        if self.preview_dialog and self.preview_dialog.isVisible(): self.preview_dialog.close()
        self.controller.cleanup(); event.accept()