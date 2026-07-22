# ui/widgets/image_labels.py
# 修复：添加 QRect 导入，解决 NameError 崩溃

import os
import logging
from PySide6.QtWidgets import QLabel, QApplication, QSizePolicy
from PySide6.QtCore import Qt, Signal, QTimer, QRect
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QPen, QBrush

logger = logging.getLogger(__name__)


class ClickableLabel(QLabel):
    clicked = Signal(int)
    double_clicked = Signal(int)

    def __init__(self, pixmap, timestamp, index_num, parent=None):
        super().__init__(parent)
        self.original_pixmap = pixmap
        self.timestamp = timestamp
        self.index_num = index_num
        self.is_selected = False
        self.is_locked = False
        self.is_favorite = False
        self.is_exported = False
        self.is_loading = False
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
        self.is_exported = exported
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
            painter.fillRect(rect, QColor(50, 50, 50))
            scaled = self.original_pixmap.scaled(
                img_rect.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            x = img_rect.x() + (img_rect.width() - scaled.width()) // 2
            y = img_rect.y() + (img_rect.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)

        # 选中边框
        if self.is_selected:
            painter.setPen(QPen(QColor(41, 128, 185), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)

        # 状态标记
        font = QFont("Arial", 8)
        painter.setFont(font)

        # 序号（左上角）
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(rect.left() + 4, rect.top() + 14, str(self.index_num))

        # ===== 时间戳（右上角，黑底白字矩形块，格式 h:mm:ss） =====
        hours = int(self.timestamp // 3600)
        minutes = int((self.timestamp % 3600) // 60)
        seconds = int(self.timestamp % 60)
        time_str = f"{hours}:{minutes:02d}:{seconds:02d}"  # 小时不补零

        painter.setFont(QFont("Arial", 9, QFont.Bold))
        fm = painter.fontMetrics()
        text_rect = fm.boundingRect(time_str)

        # 矩形块边距
        padding = 3
        bg_rect = QRect(
            rect.right() - text_rect.width() - 6 - padding,
            rect.top() + 2,
            text_rect.width() + 2 * padding,
            text_rect.height() + 2 * padding
        )
        # 绘制黑色背景
        painter.fillRect(bg_rect, QColor(0, 0, 0))
        # 绘制白色文字
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(
            rect.right() - text_rect.width() - 6,
            rect.top() + 4 + text_rect.height(),
            time_str
        )

        # 锁定（左上角）
        if self.is_locked:
            painter.setPen(QColor(255, 255, 0))
            painter.setFont(QFont("Arial", 8))
            painter.drawText(rect.left() + 4, rect.top() + 30, "🔒")

        # 收藏（左上角，红色桃心）
        if self.is_favorite:
            painter.setPen(QColor(255, 0, 0))
            painter.setFont(QFont("Arial", 10))
            y_offset = 46 if self.is_locked else 30
            painter.drawText(rect.left() + 4, rect.top() + y_offset, "❤️")

        # 已导出（右下角绿点）
        if self.is_exported:
            painter.setBrush(QColor(0, 200, 0))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(rect.right() - 16, rect.bottom() - 16, 10, 10)

        # 选中圆点（左上角）
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
    def __init__(self, pixmap, timestamp, index_num, parent=None):
        super().__init__(pixmap, timestamp, index_num, parent)