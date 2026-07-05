from PySide6.QtWidgets import QWidget, QGridLayout, QLabel
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt


class ClickLabel(QLabel):

    def __init__(self, idx, callback):
        super().__init__()
        self.idx = idx
        self.callback = callback

    def mousePressEvent(self, event):
        self.callback(self.idx)


class ThumbnailGrid(QWidget):

    def __init__(self, on_select):
        super().__init__()

        self.on_select = on_select
        self.labels = []
        self.current_index = None

        layout = QGridLayout()
        self.setLayout(layout)

        for i in range(9):

            label = ClickLabel(i, self._clicked)

            label.setFixedSize(200, 120)
            label.setAlignment(Qt.AlignCenter)

            self.labels.append(label)
            layout.addWidget(label, i // 3, i % 3)

    def _clicked(self, idx):
        self.current_index = idx
        self._update_style()
        self.on_select(idx)

    def set_images(self, images):

        for i, label in enumerate(self.labels):

            if i < len(images):
                pix = QPixmap(images[i]).scaled(
                    200, 120, Qt.KeepAspectRatio
                )
                label.setPixmap(pix)
            else:
                label.clear()

    def _update_style(self):

        for i, label in enumerate(self.labels):

            if i == self.current_index:
                label.setStyleSheet("border:3px solid #2196f3;")
            else:
                label.setStyleSheet("border:1px solid #ccc;")