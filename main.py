# main.py

import sys
import asyncio
import logging
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QMessageBox
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPalette, QColor
from qasync import QEventLoop

from ui.views.segment_view import SegmentView

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def apply_theme(app: QApplication, is_dark: bool):
    """应用深色/浅色主题"""
    if is_dark:
        app.setStyle("Fusion")
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(45, 45, 45))
        dark_palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.Text, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
        dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
        dark_palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(120, 120, 120))
        dark_palette.setColor(QPalette.Disabled, QPalette.Text, QColor(120, 120, 120))
        dark_palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(120, 120, 120))
        app.setPalette(dark_palette)

        app.setStyleSheet("""
            QWidget { background-color: #2d2d2d; color: #ffffff; }
            QFrame { background-color: #2d2d2d; }
            QLabel { color: #ffffff; }
            QPushButton {
                background-color: #3a3a3a; color: #ffffff;
                border: 1px solid #555555; border-radius: 4px; padding: 4px 10px;
            }
            QPushButton:hover { background-color: #4a4a4a; }
            QPushButton:pressed { background-color: #2a2a2a; }
            QPushButton:disabled { color: #666666; background-color: #2a2a2a; }
            QPushButton:checked { background-color: #2196F3; border-color: #2196F3; color: white; }
            QListWidget {
                background-color: #1e1e1e; color: #ffffff;
                border: 1px solid #3a3a3a; border-radius: 4px;
            }
            QListWidget::item { padding: 3px 5px; border-radius: 2px; }
            QListWidget::item:selected { background-color: #2196F3; color: white; }
            QListWidget::item:hover { background-color: #3a3a3a; }
            QScrollArea { border: none; background-color: #2d2d2d; }
            QScrollBar:vertical {
                background-color: #2d2d2d; width: 12px; border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #555555; border-radius: 6px; min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background-color: #777777; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar:horizontal {
                background-color: #2d2d2d; height: 12px; border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background-color: #555555; border-radius: 6px; min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover { background-color: #777777; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
            QComboBox {
                background-color: #3a3a3a; color: #ffffff;
                border: 1px solid #555555; border-radius: 4px; padding: 2px 8px;
            }
            QComboBox:hover { background-color: #4a4a4a; }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox QAbstractItemView {
                background-color: #3a3a3a; color: #ffffff;
                selection-background-color: #2196F3;
            }
            QLineEdit {
                background-color: #2a2a2a; color: #ffffff;
                border: 1px solid #555555; border-radius: 4px; padding: 4px 8px;
            }
            QLineEdit:focus { border-color: #2196F3; }
            QMenu {
                background-color: #2d2d2d; color: #ffffff;
                border: 1px solid #555555;
            }
            QMenu::item:selected { background-color: #2196F3; }
            QMenuBar { background-color: #2d2d2d; color: #ffffff; }
            QMenuBar::item:selected { background-color: #3a3a3a; }
            QSlider::groove:horizontal {
                height: 6px; background: #3a3a3a; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #2196F3; width: 16px; height: 16px;
                margin: -5px 0; border-radius: 8px;
            }
            QSlider::sub-page:horizontal { background: #2196F3; border-radius: 3px; }
            QDialog { background-color: #2d2d2d; }
            QGroupBox {
                color: #ffffff; border: 1px solid #555555;
                border-radius: 4px; margin-top: 10px; padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 10px; padding: 0 5px 0 5px;
            }
            QMessageBox { background-color: #2d2d2d; }
            QMessageBox QPushButton { min-width: 80px; }
            QSplitter::handle { background-color: #3a3a3a; }
            QSplitter::handle:hover { background-color: #555555; }
            QLabel#info_name { color: #2196F3; }
            QLabel#cache_label { color: #888; }
        """)
        logger.info("应用深色主题")
    else:
        app.setStyle("Fusion")
        light_palette = QPalette()
        light_palette.setColor(QPalette.Window, QColor(240, 240, 240))
        light_palette.setColor(QPalette.WindowText, QColor(0, 0, 0))
        light_palette.setColor(QPalette.Base, QColor(255, 255, 255))
        light_palette.setColor(QPalette.AlternateBase, QColor(233, 233, 233))
        light_palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
        light_palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
        light_palette.setColor(QPalette.Text, QColor(0, 0, 0))
        light_palette.setColor(QPalette.Button, QColor(240, 240, 240))
        light_palette.setColor(QPalette.ButtonText, QColor(0, 0, 0))
        light_palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
        light_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        light_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        light_palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        light_palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(140, 140, 140))
        light_palette.setColor(QPalette.Disabled, QPalette.Text, QColor(140, 140, 140))
        light_palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(140, 140, 140))
        app.setPalette(light_palette)

        app.setStyleSheet("""
            QWidget { background-color: #f0f0f0; color: #000000; }
            QFrame { background-color: #f0f0f0; }
            QLabel { color: #000000; }
            QPushButton {
                background-color: #e0e0e0; color: #000000;
                border: 1px solid #cccccc; border-radius: 4px; padding: 4px 10px;
            }
            QPushButton:hover { background-color: #d0d0d0; }
            QPushButton:pressed { background-color: #c0c0c0; }
            QPushButton:disabled { color: #999999; background-color: #e8e8e8; }
            QPushButton:checked { background-color: #2196F3; border-color: #2196F3; color: white; }
            QListWidget {
                background-color: #ffffff; color: #000000;
                border: 1px solid #cccccc; border-radius: 4px;
            }
            QListWidget::item { padding: 3px 5px; border-radius: 2px; }
            QListWidget::item:selected { background-color: #2196F3; color: white; }
            QListWidget::item:hover { background-color: #e0e0e0; }
            QScrollArea { border: none; background-color: #f0f0f0; }
            QScrollBar:vertical {
                background-color: #f0f0f0; width: 12px; border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #cccccc; border-radius: 6px; min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background-color: #aaaaaa; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar:horizontal {
                background-color: #f0f0f0; height: 12px; border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background-color: #cccccc; border-radius: 6px; min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover { background-color: #aaaaaa; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
            QComboBox {
                background-color: #ffffff; color: #000000;
                border: 1px solid #cccccc; border-radius: 4px; padding: 2px 8px;
            }
            QComboBox:hover { background-color: #f0f0f0; }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox QAbstractItemView {
                background-color: #ffffff; color: #000000;
                selection-background-color: #2196F3; selection-color: white;
            }
            QLineEdit {
                background-color: #ffffff; color: #000000;
                border: 1px solid #cccccc; border-radius: 4px; padding: 4px 8px;
            }
            QLineEdit:focus { border-color: #2196F3; }
            QMenu {
                background-color: #ffffff; color: #000000;
                border: 1px solid #cccccc;
            }
            QMenu::item:selected { background-color: #2196F3; color: white; }
            QMenuBar { background-color: #f0f0f0; color: #000000; }
            QMenuBar::item:selected { background-color: #e0e0e0; }
            QSlider::groove:horizontal {
                height: 6px; background: #cccccc; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #2196F3; width: 16px; height: 16px;
                margin: -5px 0; border-radius: 8px;
            }
            QSlider::sub-page:horizontal { background: #2196F3; border-radius: 3px; }
            QDialog { background-color: #f0f0f0; }
            QGroupBox {
                color: #000000; border: 1px solid #cccccc;
                border-radius: 4px; margin-top: 10px; padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 10px; padding: 0 5px 0 5px;
            }
            QSplitter::handle { background-color: #cccccc; }
            QSplitter::handle:hover { background-color: #aaaaaa; }
            QLabel#info_name { color: #2196F3; }
            QLabel#cache_label { color: #666; }
        """)
        logger.info("应用浅色主题")


def detect_system_theme() -> bool:
    """检测 Windows 系统主题是否为深色模式"""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return value == 0
    except Exception:
        return False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CoverPicker")
        self.resize(1280, 720)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.segment_view = SegmentView()
        layout.addWidget(self.segment_view)

    def showEvent(self, event):
        """窗口显示后检查缓存"""
        super().showEvent(event)
        QTimer.singleShot(500, self._check_cache)

    def _check_cache(self):
        """检查缓存大小，如果超过阈值则提示清理"""
        try:
            controller = self.segment_view.controller
            cache_size_gb = controller.get_cache_size_gb()
            threshold = 5.0

            if cache_size_gb > threshold:
                reply = QMessageBox.question(
                    self,
                    "缓存清理提醒",
                    f"缓存目录当前占用 {cache_size_gb:.2f} GB，已超过 {threshold} GB 阈值。\n\n"
                    "是否自动清理最旧的缓存文件？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.segment_view.progress_label_left.setText("正在清理缓存...")
                    deleted, freed_mb = controller.auto_clean_cache(threshold)
                    self.segment_view.progress_label_left.setText(
                        f"缓存清理完成：删除 {deleted} 个文件，释放 {freed_mb:.1f} MB"
                    )
                    # 更新缓存标签
                    if hasattr(self.segment_view, '_update_cache_info'):
                        self.segment_view._update_cache_info()
        except Exception as e:
            logger.error(f"检查缓存失败: {e}")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CoverPicker")

    is_dark = detect_system_theme()
    apply_theme(app, is_dark)

    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()