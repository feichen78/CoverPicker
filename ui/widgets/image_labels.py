# ui/widgets/image_labels.py

from PySide6.QtWidgets import QLabel, QSizePolicy
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QPainter, QPen, QFont, QColor


class ClickableLabel(QLabel):
    """可点击的截图标签，包含缩略图、序号、时间戳、状态标识"""

    clicked = Signal()
    double_clicked = Signal()

    def __init__(self, pixmap: QPixmap, timestamp: float, index: int, parent=None):
        super().__init__(parent)
        self.original_pixmap = pixmap
        self.timestamp = timestamp
        self.index = index
        self._selected = False
        self._locked = False
        self._favorite = False
        self._exported = False

        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(False)
        self.setMinimumSize(100, 80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.update_pixmap()

    def update_pixmap(self):
        if self.original_pixmap.isNull():
            self.clear()
            return

        scaled = self.original_pixmap.scaled(
            self.width() - 4,
            self.height() - 4,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        result = scaled.copy()
        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.setPen(QPen(QColor(255, 255, 255, 200)))
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(4, 18, f"{self.index}")

        hours = int(self.timestamp // 3600)
        minutes = int((self.timestamp % 3600) // 60)
        secs = int(self.timestamp % 60)
        time_str = f"{hours:02d}:{minutes:02d}:{secs:02d}"
        painter.setPen(QPen(QColor(255, 165, 0, 230)))
        painter.setFont(QFont("Arial", 9, QFont.Bold))
        painter.drawText(4, result.height() - 6, time_str)

        if self._selected:
            painter.setPen(QPen(QColor(33, 150, 243), 2))
            painter.setBrush(QColor(33, 150, 243))
            painter.drawEllipse(4, 22, 8, 8)

        if self._locked:
            painter.setPen(QPen(QColor(255, 215, 0), 2))
            painter.setBrush(QColor(255, 215, 0))
            painter.drawText(4, 36, "🔒")

        if self._favorite:
            painter.setPen(QPen(QColor(255, 215, 0), 2))
            painter.setBrush(QColor(255, 215, 0))
            painter.drawText(result.width() - 20, 18, "⭐")

        if self._exported:
            painter.setPen(QPen(QColor(76, 175, 80), 2))
            painter.setBrush(QColor(76, 175, 80))
            painter.drawEllipse(result.width() - 16, result.height() - 16, 8, 8)

        painter.end()
        self.setPixmap(result)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_pixmap()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()

    def set_selected(self, selected: bool):
        self._selected = selected
        self.update_pixmap()

    def set_locked(self, locked: bool):
        self._locked = locked
        self.update_pixmap()

    def set_favorite(self, favorite: bool):
        self._favorite = favorite
        self.update_pixmap()

    def set_exported(self, exported: bool):
        self._exported = exported
        self.update_pixmap()


class FavImageLabel(QLabel):
    """
    用于收藏弹窗的图片标签，不显示序号。
    支持单击选中、双击放大预览。
    """

    clicked = Signal()
    double_clicked = Signal()

    def __init__(self, pixmap: QPixmap, timestamp: float, parent=None):
        super().__init__(parent)
        self.original_pixmap = pixmap
        self.timestamp = timestamp
        self._selected = False
        self._favorite = False
        self._exported = False

        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(False)
        self.setMinimumSize(80, 60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.update_pixmap()

    def set_image_size(self, width: int, height: int):
        self.setFixedSize(width, height)
        self.update_pixmap()

    def update_pixmap(self):
        if self.original_pixmap.isNull():
            self.clear()
            return

        scaled = self.original_pixmap.scaled(
            self.width() - 4,
            self.height() - 4,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        result = scaled.copy()
        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)

        hours = int(self.timestamp // 3600)
        minutes = int((self.timestamp % 3600) // 60)
        secs = int(self.timestamp % 60)
        time_str = f"{hours:02d}:{minutes:02d}:{secs:02d}"
        painter.setPen(QPen(QColor(255, 165, 0, 230)))
        painter.setFont(QFont("Arial", 9, QFont.Bold))
        painter.drawText(4, result.height() - 6, time_str)

        if self._selected:
            painter.setPen(QPen(QColor(33, 150, 243), 2))
            painter.setBrush(QColor(33, 150, 243))
            painter.drawEllipse(4, 22, 8, 8)

        if self._favorite:
            painter.setPen(QPen(QColor(255, 215, 0), 2))
            painter.setBrush(QColor(255, 215, 0))
            painter.drawText(result.width() - 20, 18, "⭐")

        if self._exported:
            painter.setPen(QPen(QColor(76, 175, 80), 2))
            painter.setBrush(QColor(76, 175, 80))
            painter.drawEllipse(result.width() - 16, result.height() - 16, 8, 8)

        painter.end()
        self.setPixmap(result)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_pixmap()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()

    def set_selected(self, selected: bool):
        self._selected = selected
        self.update_pixmap()

    def set_favorite(self, favorite: bool):
        self._favorite = favorite
        self.update_pixmap()

    def set_exported(self, exported: bool):
        self._exported = exported
        self.update_pixmap()