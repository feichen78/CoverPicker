import os  # <-- 添加这一行
from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont


class HomeView(QWidget):
    """首页：展示视频列表，点击跳转"""
    video_selected = Signal(str)  # 发送视频路径

    def __init__(self, videos: list, parent=None):
        super().__init__(parent)
        self.videos = videos
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("📹 视频列表")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.setFont(QFont("Arial", 12))
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)

        for path in self.videos:
            name = os.path.basename(path)
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, path)  # 存储完整路径
            self.list_widget.addItem(item)

        layout.addWidget(self.list_widget)

    def on_item_double_clicked(self, item: QListWidgetItem):
        path = item.data(Qt.UserRole)
        if path:
            self.video_selected.emit(path)