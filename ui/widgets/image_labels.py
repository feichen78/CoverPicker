# ui/widgets/image_labels.py
# 提供 ClickableLabel 和 FavImageLabel（拉伸填满）

from PySide6.QtWidgets import QLabel, QSizePolicy
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QPainter, QPen, QFont, QColor


class ClickableLabel(QLabel):
    """主界面截图标签（保持原有逻辑）"""
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
        self._loading = False
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(False)
        self.setMinimumSize(80, 60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.update_pixmap()

    def set_loading(self, loading: bool):
        self._loading = loading
        self.update_pixmap()

    def update_pixmap(self):
        if self._loading:
            scaled = QPixmap(self.width() - 4, self.height() - 4)
            scaled.fill(QColor(50, 50, 50))
            painter = QPainter(scaled)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(QColor(200, 200, 200)))
            painter.setFont(QFont("Arial", 14, QFont.Bold))
            painter.drawText(scaled.rect(), Qt.AlignCenter, "⏳ 加载中...")
            painter.end()
            self.setPixmap(scaled)
            return

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
    """收藏弹窗专用图片标签 —— 图片拉伸填满，保留标记绘制"""
    clicked = Signal()
    double_clicked = Signal()

    def __init__(self, pixmap: QPixmap, timestamp: float, parent=None):
        super().__init__(parent)
        self.original_pixmap = pixmap
        self.timestamp = timestamp
        self._selected = False
        self._favorite = True   # 收藏弹窗中所有图片都是收藏状态
        self._exported = False
        self._loading = False

        # 关键：设置拉伸填满
        self.setScaledContents(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(60, 45)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setPixmap(self.original_pixmap)  # 直接设置原图，由 setScaledContents 拉伸

    def set_loading(self, loading: bool):
        self._loading = loading
        self.update()

    def set_exported(self, exported: bool):
        self._exported = exported
        self.update()

    def set_selected(self, selected: bool):
        self._selected = selected
        self.update()

    def set_favorite(self, favorite: bool):
        self._favorite = favorite
        self.update()

    def paintEvent(self, event):
        # 先让 QLabel 绘制拉伸后的图片
        super().paintEvent(event)

        # 然后在图片之上绘制时间戳、标记等
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 时间戳
        hours = int(self.timestamp // 3600)
        minutes = int((self.timestamp % 3600) // 60)
        secs = int(self.timestamp % 60)
        time_str = f"{hours:02d}:{minutes:02d}:{secs:02d}"
        painter.setPen(QPen(QColor(255, 165, 0, 230)))
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(time_str)
        painter.drawText(self.width() - tw - 6, self.height() - 6, time_str)

        # 选中标记（蓝点）
        if self._selected:
            painter.setPen(QPen(QColor(33, 150, 243), 2))
            painter.setBrush(QColor(33, 150, 243))
            painter.drawEllipse(6, 6, 10, 10)

        # 收藏星标（右上角）
        if self._favorite:
            painter.setPen(QPen(QColor(255, 215, 0), 2))
            painter.setBrush(QColor(255, 215, 0))
            painter.setFont(QFont("Arial", 12, QFont.Bold))
            painter.drawText(self.width() - 24, 18, "⭐")

        # 导出标记（右下角绿点）
        if self._exported:
            painter.setPen(QPen(QColor(76, 175, 80), 2))
            painter.setBrush(QColor(76, 175, 80))
            painter.drawEllipse(self.width() - 16, self.height() - 16, 10, 10)

        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 不需要额外操作，因为 setScaledContents 自动拉伸

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()