from PySide6.QtWidgets import QWidget, QGridLayout, QLabel
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, Signal


class ClickableLabel(QLabel):
    clicked = Signal(int)

    def __init__(self, index):
        super().__init__()
        self.index = index

    def mousePressEvent(self, event):
        self.clicked.emit(self.index)


class ThumbnailView(QWidget):
    def __init__(self):
        super().__init__()

        self.layout = QGridLayout()
        self.setLayout(self.layout)

        self.labels = []
        self.selected_index = None   # ⭐ 改：不再默认选中
        self.image_paths = []

    def clear(self):
        for i in reversed(range(self.layout.count())):
            self.layout.itemAt(i).widget().deleteLater()

        self.labels = []
        self.selected_index = None
        self.image_paths = []

    def show_images(self, image_paths):
        self.clear()
        self.image_paths = image_paths

        cols = 3

        for index, path in enumerate(image_paths):
            label = ClickableLabel(index)

            pixmap = QPixmap(str(path))
            pixmap = pixmap.scaled(320, 180, Qt.KeepAspectRatio)

            label.setPixmap(pixmap)
            label.clicked.connect(self.on_clicked)

            row = index // cols
            col = index % cols

            self.layout.addWidget(label, row, col)
            self.labels.append(label)

        # ❌ 删除自动选中逻辑

    def on_clicked(self, index):
        self.highlight(index)

    def highlight(self, index):
        self.selected_index = index

        for i, label in enumerate(self.labels):
            if i == index:
                label.setStyleSheet("border: 3px solid #00ff00;")
            else:
                label.setStyleSheet("border: none;")

    def get_selected_image(self):
        if self.selected_index is None:
            return None

        if not self.image_paths:
            return None

        return self.image_paths[self.selected_index]