from PySide6.QtWidgets import QDialog, QVBoxLayout, QScrollArea, QLabel
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QPixmap, QMouseEvent, QWheelEvent, QKeyEvent

class ZoomPreviewDialog(QDialog):
    def __init__(self, pixmap: QPixmap, time_sec: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"预览 - {time_sec:.1f}s")
        self.setModal(True)
        self.resize(800, 600)
        self.setMinimumSize(400, 300)

        self.original_pixmap = pixmap
        self.scale_factor = 1.0
        self.zoom_increment = 0.1
        self.min_scale = 0.1
        self.max_scale = 5.0
        self.pan_start = QPoint()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("border: none;")
        self.scroll_area.setWidget(self.image_label)

        layout.addWidget(self.scroll_area)

        self.status_label = QLabel(f"缩放: {self.scale_factor:.1f}x  |  滚轮缩放  |  拖动平移")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("padding: 4px; background: #f0f0f0;")
        layout.addWidget(self.status_label)

        self.scroll_area.setMouseTracking(True)
        self.scroll_area.mousePressEvent = self.image_mouse_press
        self.scroll_area.mouseMoveEvent = self.image_mouse_move
        self.scroll_area.mouseReleaseEvent = self.image_mouse_release
        self.scroll_area.wheelEvent = self.image_wheel

        self.setFocusPolicy(Qt.StrongFocus)
        self.update_image()
        # 延迟居中滚动，确保布局完成
        QTimer.singleShot(50, self._center_scroll)

    def _center_scroll(self):
        """将滚动条设置为中间位置，使图片居中显示"""
        h_bar = self.scroll_area.horizontalScrollBar()
        v_bar = self.scroll_area.verticalScrollBar()
        if h_bar and h_bar.maximum() > h_bar.minimum():
            h_bar.setValue((h_bar.maximum() - h_bar.minimum()) // 2)
        if v_bar and v_bar.maximum() > v_bar.minimum():
            v_bar.setValue((v_bar.maximum() - v_bar.minimum()) // 2)

    def update_image(self):
        if self.original_pixmap.isNull():
            return
        orig_w = self.original_pixmap.width()
        orig_h = self.original_pixmap.height()
        new_w = int(orig_w * self.scale_factor)
        new_h = int(orig_h * self.scale_factor)
        # 增大最大尺寸限制，避免过早截断
        max_dim = 10000
        if new_w > max_dim or new_h > max_dim:
            ratio = min(max_dim / new_w, max_dim / new_h)
            new_w = int(new_w * ratio)
            new_h = int(new_h * ratio)
        if new_w < 1:
            new_w = 1
        if new_h < 1:
            new_h = 1
        scaled = self.original_pixmap.scaled(new_w, new_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled)
        self.image_label.resize(scaled.size())
        self.status_label.setText(f"缩放: {self.scale_factor:.1f}x  |  滚轮缩放  |  拖动平移")
        # 更新后延迟居中
        QTimer.singleShot(20, self._center_scroll)

    def image_wheel(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta > 0:
            self.scale_factor = min(self.scale_factor + self.zoom_increment, self.max_scale)
        else:
            self.scale_factor = max(self.scale_factor - self.zoom_increment, self.min_scale)
        self.update_image()
        event.accept()

    def image_mouse_press(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.pan_start = event.pos()
            self.scroll_area.setCursor(Qt.ClosedHandCursor)

    def image_mouse_move(self, event: QMouseEvent):
        if event.buttons() & Qt.LeftButton:
            delta = event.pos() - self.pan_start
            self.pan_start = event.pos()
            h_bar = self.scroll_area.horizontalScrollBar()
            v_bar = self.scroll_area.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())

    def image_mouse_release(self, event: QMouseEvent):
        self.scroll_area.setCursor(Qt.ArrowCursor)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)