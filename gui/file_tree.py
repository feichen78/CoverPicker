# 视频目录树，支持本地/SMB/WebDAV网络路径递归扫描
import os
from pathlib import Path
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PySide6.QtCore import Qt, Signal

VIDEO_SUFFIX = (".mp4", ".mkv", ".mov", ".avi", ".flv", ".m4v")

class VideoTree(QTreeWidget):
    video_click = Signal(str)
    def __init__(self):
        super().__init__()
        self.setHeaderLabel("视频目录")
        self.itemClicked.connect(self._on_click_item)
        self.video_path_map = {}

    def scan_folder(self, root_path: str):
        self.clear()
        self.video_path_map.clear()
        root_item = QTreeWidgetItem([Path(root_path).name])
        root_item.setData(0, Qt.UserRole, root_path)
        self.addTopLevelItem(root_item)
        self._scan_recursive(root_path, root_item)
        self.expandAll()

    def _scan_recursive(self, dir_path: str, parent_item: QTreeWidgetItem):
        try:
            entries = os.listdir(dir_path)
        except OSError:
            return
        video_items = []
        dir_items = []
        for name in entries:
            full = os.path.join(dir_path, name)
            p = Path(full)
            if p.is_dir():
                item = QTreeWidgetItem([name])
                item.setData(0, Qt.UserRole, full)
                dir_items.append((name, item, full))
            elif p.suffix.lower() in VIDEO_SUFFIX:
                item = QTreeWidgetItem([name])
                item.setData(0, Qt.UserRole, full)
                self.video_path_map[id(item)] = full
                video_items.append(item)
        # 先添加子文件夹
        for _, d_item, d_path in dir_items:
            parent_item.addChild(d_item)
            self._scan_recursive(d_path, d_item)
        # 再添加视频文件
        for v_item in video_items:
            parent_item.addChild(v_item)

    def _on_click_item(self, item: QTreeWidgetItem):
        vid_path = self.video_path_map.get(id(item))
        if vid_path:
            self.video_click.emit(vid_path)