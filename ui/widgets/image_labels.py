# ui/widgets/image_labels.py

import logging
from PySide6.QtWidgets import QLabel, QSizePolicy
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QColor, QPainter, QBrush, QFont, QPen

logger = logging.getLogger(__name__)


class ClickableLabel(QLabel):
    """可点击的截图标签 - 固定尺寸，图片居中保持宽高比"""
    clicked = Signal()
    double_clicked = Signal()

    def __init__(self, pixmap: QPixmap, time_sec: float, index: int = 0, parent=None):
        super().__init__(parent)
        self.time_sec = time_sec
        self.index = index
        self.is_selected = False
        self.is_locked = False
        self.is_favorite = False
        self.is_exported = False

        self.original_pixmap = pixmap
        self.display_pixmap = QPixmap()
        self.time_text = f"{time_sec:.1f}s"

        self.setMinimumSize(160, 120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("border: 1px solid #ccc; background: #2a2a2a;")

        self._update_display_pixmap()

    def _update_display_pixmap(self):
        if self.original_pixmap.isNull():
            self.display_pixmap = QPixmap(200, 150)
            self.display_pixmap.fill(QColor(60, 60, 60))
            self.update()
            return

        w = self.width() - 2
        h = self.height() - 2
        if w < 10 or h < 10:
            w, h = 200, 150

        scaled = self.original_pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        self.display_pixmap = QPixmap(w, h)
        self.display_pixmap.fill(QColor(30, 30, 30))

        painter = QPainter(self.display_pixmap)
        x = (w - scaled.width()) // 2
        y = (h - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.end()

        self.update()

    def set_original_pixmap(self, pixmap: QPixmap):
        self.original_pixmap = pixmap
        self._update_display_pixmap()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_display_pixmap()

    def paintEvent(self, event):
        if self.display_pixmap.isNull():
            self._update_display_pixmap()
            if self.display_pixmap.isNull():
                painter = QPainter(self)
                painter.fillRect(self.rect(), QColor(60, 60, 60))
                painter.end()
                return

        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.display_pixmap)

        painter.setRenderHint(QPainter.Antialiasing)

        if self.is_selected:
            painter.setBrush(QBrush(QColor(33, 150, 243)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(6, 6, 14, 14)

        # 收藏标记（黄色星星）
        if self.is_favorite:
            painter.setFont(QFont("Segoe UI Emoji", 16))
            painter.setPen(QColor(255, 215, 0))
            painter.drawText(self.width() - 28, 24, "⭐")

        painter.setPen(Qt.white)
        painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
        seq_rect_x = 6
        seq_rect_y = 24 if self.is_selected else 6
        seq_rect_w = 24
        seq_rect_h = 18
        painter.drawRoundedRect(seq_rect_x, seq_rect_y, seq_rect_w, seq_rect_h, 3, 3)
        painter.setPen(Qt.white)
        painter.setFont(QFont("Arial", 9, QFont.Bold))
        painter.drawText(seq_rect_x + 4, seq_rect_y + 13, f"{self.index}")

        painter.setPen(Qt.white)
        painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
        painter.drawRoundedRect(4, self.height() - 22, 60, 18, 3, 3)
        painter.setPen(Qt.white)
        painter.setFont(QFont("Arial", 8))
        painter.drawText(6, self.height() - 7, self.time_text)

        if self.is_locked:
            painter.setFont(QFont("Segoe UI Emoji", 13))
            painter.setPen(QColor(255, 200, 0))
            painter.drawText(self.width() - 28, 24, "🔒")

        if self.is_exported:
            painter.setBrush(QBrush(QColor(0, 200, 0)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(self.width() - 14, self.height() - 14, 10, 10)

        painter.end()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit()

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.update()

    def set_locked(self, locked: bool):
        self.is_locked = locked
        self.update()

    def set_favorite(self, fav: bool):
        self.is_favorite = fav
        self.update()

    def set_exported(self, exp: bool):
        self.is_exported = exp
        self.update()


class FavImageLabel(QLabel):
    """收藏弹窗中的图片标签 - 固定尺寸，图片居中保持宽高比"""
    clicked = Signal()
    double_clicked = Signal()

    def __init__(self, pixmap: QPixmap, time_sec: float, parent=None):
        super().__init__(parent)
        self.time_sec = time_sec
        self.is_selected = False
        self.is_favorite = True  # 收藏弹窗中所有图片都是收藏
        self.is_exported = False
        self.time_text = f"{time_sec:.1f}s"

        self.original_pixmap = pixmap
        self.display_pixmap = QPixmap()
        self.current_img_w = 160
        self.current_img_h = 120

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setStyleSheet("border: 1px solid #ccc; background: #2a2a2a;")

        self._update_display_pixmap()

    def set_image_size(self, w: int, h: int):
        if w != self.current_img_w or h != self.current_img_h:
            self.current_img_w = w
            self.current_img_h = h
            self.setFixedSize(w + 2, h + 2)
            self._update_display_pixmap()

    def _update_display_pixmap(self):
        if self.original_pixmap.isNull():
            self.display_pixmap = QPixmap(self.current_img_w, self.current_img_h)
            self.display_pixmap.fill(QColor(60, 60, 60))
            self.update()
            return

        w = max(10, self.current_img_w)
        h = max(10, self.current_img_h)

        scaled = self.original_pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        self.display_pixmap = QPixmap(w, h)
        self.display_pixmap.fill(QColor(30, 30, 30))

        painter = QPainter(self.display_pixmap)
        x = (w - scaled.width()) // 2
        y = (h - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.end()

        self.update()

    def set_original_pixmap(self, pixmap: QPixmap):
        self.original_pixmap = pixmap
        self._update_display_pixmap()

    def paintEvent(self, event):
        if self.display_pixmap.isNull():
            self._update_display_pixmap()
            if self.display_pixmap.isNull():
                painter = QPainter(self)
                painter.fillRect(self.rect(), QColor(60, 60, 60))
                painter.end()
                return

        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.display_pixmap)

        painter.setRenderHint(QPainter.Antialiasing)

        # 选中标记（蓝色圆点）
        if self.is_selected:
            painter.setBrush(QBrush(QColor(33, 150, 243)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(6, 6, 14, 14)

        # 收藏标记（黄色星星） - 收藏弹窗所有图片都显示星星
        painter.setFont(QFont("Segoe UI Emoji", 16))
        painter.setPen(QColor(255, 215, 0))
        painter.drawText(self.width() - 28, 24, "⭐")

        # 时间戳
        painter.setPen(Qt.white)
        painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
        painter.drawRoundedRect(4, self.height() - 22, 60, 18, 3, 3)
        painter.setPen(Qt.white)
        painter.setFont(QFont("Arial", 8))
        painter.drawText(6, self.height() - 7, self.time_text)

        # 导出标记（绿色圆点）
        if self.is_exported:
            painter.setBrush(QBrush(QColor(0, 200, 0)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(self.width() - 16, self.height() - 16, 10, 10)

        painter.end()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit()

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.update()

    def set_exported(self, exp: bool):
        self.is_exported = exp
        self.update()