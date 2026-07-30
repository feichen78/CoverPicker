# ui/views/zoom_preview.py
# v3.2: 上下左右键切换截图（上下按列数切换）+ 空格键关闭预览
#       键盘不参与平移，平移仅由鼠标拖拽实现
#       移除调试日志

from PySide6.QtWidgets import QDialog, QVBoxLayout, QScrollArea, QLabel, QApplication
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QPixmap, QMouseEvent, QWheelEvent, QKeyEvent, QShowEvent
from typing import List, Optional, Tuple


class ZoomPreviewDialog(QDialog):
    def __init__(self, pixmap: QPixmap, time_sec: float, parent=None,
                 image_list: Optional[List[Tuple[QPixmap, float]]] = None,
                 current_index: int = 0,
                 cols: int = 3):
        super().__init__(parent)
        self.setWindowTitle(f"预览 - {time_sec:.1f}s")
        self.setModal(True)

        screen = QApplication.primaryScreen()
        if screen:
            screen_rect = screen.availableGeometry()
            screen_w = screen_rect.width()
            screen_h = screen_rect.height()
        else:
            screen_w = 1920
            screen_h = 1080

        target_w = int(screen_w * 0.8)
        target_h = int(screen_h * 0.8)
        target_w = max(1000, min(1600, target_w))
        target_h = max(750, min(1200, target_h))

        self.resize(target_w, target_h)
        self.setMinimumSize(800, 600)

        self.original_pixmap = pixmap
        self.scale_factor = 1.0
        self.zoom_increment = 0.1
        self.min_scale = 0.1
        self.max_scale = 5.0
        self.pan_start = QPoint()
        self._initialized = False

        self.image_list: List[Tuple[QPixmap, float]] = image_list if image_list else []
        self.current_index: int = current_index
        self.cols: int = cols if cols > 0 else 3

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

        self.status_label = QLabel("滚轮缩放 | 拖动平移 | ← ↑ ↓ → 切换 | 空格关闭")
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

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        self.setFocus()

        if not self._initialized and not self.original_pixmap.isNull():
            QTimer.singleShot(50, self._apply_initial_scale_and_update)
            self._initialized = True

    def _apply_initial_scale_and_update(self):
        if self.original_pixmap.isNull():
            return

        viewport_size = self.scroll_area.viewport().size()
        vw = viewport_size.width()
        vh = viewport_size.height()

        if vw <= 10 or vh <= 10:
            vw = self.width() - 20
            vh = self.height() - 80

        img_w = self.original_pixmap.width()
        img_h = self.original_pixmap.height()

        if img_w <= 0 or img_h <= 0:
            return

        fit_scale = min(vw / img_w, vh / img_h)
        fit_scale = max(fit_scale, self.min_scale)

        self.scale_factor = fit_scale
        self.update_image()

    def _center_scroll(self):
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
        total = len(self.image_list)
        if total > 1:
            self.status_label.setText(
                f"缩放: {self.scale_factor:.1f}x | 拖动平移 | ← ↑ ↓ → 切换 ({self.current_index + 1}/{total}) | 空格关闭"
            )
        else:
            self.status_label.setText(f"缩放: {self.scale_factor:.1f}x | 拖动平移 | 空格关闭")
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

    def switch_to(self, delta: int):
        if not self.image_list or len(self.image_list) <= 1:
            return
        new_index = self.current_index + delta
        if 0 <= new_index < len(self.image_list):
            self.current_index = new_index
            new_pixmap, new_time = self.image_list[new_index]
            self.original_pixmap = new_pixmap
            self.setWindowTitle(f"预览 - {new_time:.1f}s")
            self.update_image()
            self._apply_initial_scale_and_update()

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()

        if key == Qt.Key_Escape or key == Qt.Key_Space:
            self.close()
            event.accept()
            return

        if key == Qt.Key_Left:
            self.switch_to(-1)
            event.accept()
            return

        if key == Qt.Key_Right:
            self.switch_to(1)
            event.accept()
            return

        if key == Qt.Key_Up:
            self.switch_to(-self.cols)
            event.accept()
            return

        if key == Qt.Key_Down:
            self.switch_to(self.cols)
            event.accept()
            return

        super().keyPressEvent(event)