# ui/widgets/image_labels.py
# 完整文件，可直接覆盖
# 增加 FavImageLabel.set_exported 调试，确保 exported 正确传递

import os
import logging
from PySide6.QtWidgets import QLabel, QApplication, QSizePolicy
from PySide6.QtCore import Qt, Signal, QTimer, QRect, QSize
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QPen, QBrush

logger = logging.getLogger(__name__)


class ClickableLabel(QLabel):
    clicked = Signal(int)
    double_clicked = Signal(int)

    def __init__(self, pixmap, timestamp, index_num, parent=None, allow_background: bool = True, allow_scale: bool = True):
        super().__init__(parent)
        self.original_pixmap = pixmap
        self.timestamp = timestamp
        self.index_num = index_num
        self.is_selected = False
        self.is_locked = False
        self.is_favorite = False
        self.is_exported = False
        self.is_loading = False
        self.allow_background = allow_background
        self.allow_scale = allow_scale
        self.setScaledContents(False)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(100, 80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_selected(self, selected):
        self.is_selected = selected
        self.update()

    def set_locked(self, locked):
        self.is_locked = locked
        self.update()

    def set_favorite(self, favorite):
        self.is_favorite = favorite
        self.update()

    def set_exported(self, exported):
        # 强制转换为布尔值并打印调试
        exported_bool = bool(exported)
        print(f"[DEBUG] ClickableLabel.set_exported: index={self.index_num}, exported={exported_bool}")
        self.is_exported = exported_bool
        self.update()

    def set_loading(self, loading):
        self.is_loading = loading
        self.update()

    def update_pixmap(self):
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        rect = self.rect()
        margin = 2
        img_rect = rect.adjusted(margin, margin, -margin, -margin)

        if self.is_loading or self.original_pixmap is None or self.original_pixmap.isNull():
            painter.fillRect(rect, QColor(60, 60, 60))
            painter.setPen(QColor(200, 200, 200))
            painter.drawText(rect, Qt.AlignCenter, "加载中...")
        else:
            if self.allow_background:
                painter.fillRect(rect, QColor(50, 50, 50))

            if self.allow_scale:
                scaled = self.original_pixmap.scaled(
                    img_rect.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                x = img_rect.x() + (img_rect.width() - scaled.width()) // 2
                y = img_rect.y() + (img_rect.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
            else:
                # 不缩放：直接绘制原始尺寸，居中显示
                pix = self.original_pixmap
                x = img_rect.x() + (img_rect.width() - pix.width()) // 2
                y = img_rect.y() + (img_rect.height() - pix.height()) // 2
                painter.drawPixmap(x, y, pix)

        if self.is_selected:
            painter.setPen(QPen(QColor(41, 128, 185), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)

        font = QFont("Arial", 8)
        painter.setFont(font)

        painter.setPen(QColor(255, 255, 255))
        painter.drawText(rect.left() + 4, rect.top() + 14, str(self.index_num))

        hours = int(self.timestamp // 3600)
        minutes = int((self.timestamp % 3600) // 60)
        seconds = int(self.timestamp % 60)
        time_str = f"{hours}:{minutes:02d}:{seconds:02d}"

        painter.setFont(QFont("Arial", 9, QFont.Bold))
        fm = painter.fontMetrics()
        text_rect = fm.boundingRect(time_str)

        padding = 3
        bg_rect = QRect(
            rect.right() - text_rect.width() - 6 - padding,
            rect.top() + 2,
            text_rect.width() + 2 * padding,
            text_rect.height() + 2 * padding
        )
        painter.fillRect(bg_rect, QColor(0, 0, 0))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(
            rect.right() - text_rect.width() - 6,
            rect.top() + 4 + text_rect.height(),
            time_str
        )

        if self.is_locked:
            painter.setPen(QColor(255, 255, 0))
            painter.setFont(QFont("Arial", 8))
            painter.drawText(rect.left() + 4, rect.top() + 30, "🔒")

        if self.is_favorite:
            painter.setPen(QColor(255, 0, 0))
            painter.setFont(QFont("Arial", 10))
            y_offset = 46 if self.is_locked else 30
            painter.drawText(rect.left() + 4, rect.top() + y_offset, "❤️")

        # 绿点：仅当 is_exported 为 True 时绘制
        if self.is_exported:
            painter.setBrush(QColor(0, 200, 0))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(rect.right() - 16, rect.bottom() - 16, 10, 10)

        if self.is_selected:
            painter.setBrush(QColor(41, 128, 185))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(rect.left() + 4, rect.top() + 4, 10, 10)

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.index_num - 1)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self.index_num - 1)
        super().mouseDoubleClickEvent(event)


class FavImageLabel(ClickableLabel):
    """收藏窗口专用标签 —— 无背景，不缩放，原始尺寸"""
    def __init__(self, pixmap, timestamp, index_num, parent=None):
        super().__init__(pixmap, timestamp, index_num, parent, allow_background=False, allow_scale=False)
        self._fixed_size = QSize()
        # 确保初始 exported 为 False
        self.is_exported = False

    def setFixedSize(self, w, h):
        super().setFixedSize(w, h)
        self._fixed_size = QSize(w, h)

    def sizeHint(self):
        if self._fixed_size.isValid():
            return self._fixed_size
        if self.original_pixmap and not self.original_pixmap.isNull():
            return self.original_pixmap.size()
        return QSize(100, 80)

    def set_exported(self, exported):
        # 强制转换为布尔值并打印调试
        exported_bool = bool(exported)
        print(f"[DEBUG] FavImageLabel.set_exported: index={self.index_num}, exported={exported_bool}")
        self.is_exported = exported_bool
        self.update()