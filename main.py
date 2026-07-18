# main.py
import sys, asyncio, logging, os
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QMessageBox, QMenuBar, QMenu
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPalette, QColor, QAction
from qasync import QEventLoop
from ui.views.segment_view import SegmentView
from src.config_manager import ConfigManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def apply_theme(app: QApplication, is_dark: bool):
    if is_dark:
        app.setStyle("Fusion")
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(45,45,45))
        dark_palette.setColor(QPalette.WindowText, QColor(255,255,255))
        dark_palette.setColor(QPalette.Base, QColor(25,25,25))
        dark_palette.setColor(QPalette.AlternateBase, QColor(53,53,53))
        dark_palette.setColor(QPalette.ToolTipBase, QColor(255,255,255))
        dark_palette.setColor(QPalette.ToolTipText, QColor(255,255,255))
        dark_palette.setColor(QPalette.Text, QColor(255,255,255))
        dark_palette.setColor(QPalette.Button, QColor(53,53,53))
        dark_palette.setColor(QPalette.ButtonText, QColor(255,255,255))
        dark_palette.setColor(QPalette.BrightText, QColor(255,0,0))
        dark_palette.setColor(QPalette.Link, QColor(42,130,218))
        dark_palette.setColor(QPalette.Highlight, QColor(42,130,218))
        dark_palette.setColor(QPalette.HighlightedText, QColor(0,0,0))
        dark_palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(120,120,120))
        dark_palette.setColor(QPalette.Disabled, QPalette.Text, QColor(120,120,120))
        dark_palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(120,120,120))
        app.setPalette(dark_palette)
        app.setStyleSheet("""QWidget{background-color:#2d2d2d;color:#ffffff;}QFrame{background-color:#2d2d2d;}QLabel{color:#ffffff;}QPushButton{background-color:#3a3a3a;color:#ffffff;border:1px solid #555;border-radius:4px;padding:4px 10px;}QPushButton:hover{background-color:#4a4a4a;}QPushButton:pressed{background-color:#2a2a2a;}QPushButton:disabled{color:#666;background-color:#2a2a2a;}QPushButton:checked{background-color:#2196F3;border-color:#2196F3;color:white;}QListWidget{background-color:#1e1e1e;color:#ffffff;border:1px solid #3a3a3a;border-radius:4px;}QListWidget::item{padding:3px 5px;border-radius:2px;}QListWidget::item:selected{background-color:#2196F3;color:white;}QListWidget::item:hover{background-color:#3a3a3a;}QScrollArea{border:none;background-color:#2d2d2d;}QScrollBar:vertical{background-color:#2d2d2d;width:12px;border-radius:6px;}QScrollBar::handle:vertical{background-color:#555;border-radius:6px;min-height:20px;}QScrollBar::handle:vertical:hover{background-color:#777;}QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0px;}QScrollBar:horizontal{background-color:#2d2d2d;height:12px;border-radius:6px;}QScrollBar::handle:horizontal{background-color:#555;border-radius:6px;min-width:20px;}QScrollBar::handle:horizontal:hover{background-color:#777;}QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{width:0px;}QComboBox{background-color:#3a3a3a;color:#fff;border:1px solid #555;border-radius:4px;padding:2px 8px;}QComboBox:hover{background-color:#4a4a4a;}QComboBox::drop-down{border:none;width:20px;}QComboBox QAbstractItemView{background-color:#3a3a3a;color:#fff;selection-background-color:#2196F3;}QLineEdit{background-color:#2a2a2a;color:#fff;border:1px solid #555;border-radius:4px;padding:4px 8px;}QLineEdit:focus{border-color:#2196F3;}QMenu{background-color:#2d2d2d;color:#fff;border:1px solid #555;}QMenu::item:selected{background-color:#2196F3;}QMenuBar{background-color:#2d2d2d;color:#fff;}QMenuBar::item:selected{background-color:#3a3a3a;}QSlider::groove:horizontal{height:6px;background:#3a3a3a;border-radius:3px;}QSlider::handle:horizontal{background:#2196F3;width:16px;height:16px;margin:-5px 0;border-radius:8px;}QSlider::sub-page:horizontal{background:#2196F3;border-radius:3px;}QDialog{background-color:#2d2d2d;}QGroupBox{color:#fff;border:1px solid #555;border-radius:4px;margin-top:10px;padding-top:10px;}QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 5px 0 5px;}QMessageBox{background-color:#2d2d2d;}QMessageBox QPushButton{min-width:80px;}QSplitter::handle{background-color:#3a3a3a;}QSplitter::handle:hover{background-color:#555;}QLabel#info_name{color:#2196F3;}QLabel#cache_label{color:#888;}""")
        logger.info("应用深色主题")
    else:
        app.setStyle("Fusion")
        light_palette = QPalette()
        light_palette.setColor(QPalette.Window, QColor(240,240,240))
        light_palette.setColor(QPalette.WindowText, QColor(0,0,0))
        light_palette.setColor(QPalette.Base, QColor(255,255,255))
        light_palette.setColor(QPalette.AlternateBase, QColor(233,233,233))
        light_palette.setColor(QPalette.ToolTipBase, QColor(255,255,255))
        light_palette.setColor(QPalette.ToolTipText, QColor(0,0,0))
        light_palette.setColor(QPalette.Text, QColor(0,0,0))
        light_palette.setColor(QPalette.Button, QColor(240,240,240))
        light_palette.setColor(QPalette.ButtonText, QColor(0,0,0))
        light_palette.setColor(QPalette.BrightText, QColor(255,0,0))
        light_palette.setColor(QPalette.Link, QColor(42,130,218))
        light_palette.setColor(QPalette.Highlight, QColor(42,130,218))
        light_palette.setColor(QPalette.HighlightedText, QColor(255,255,255))
        light_palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(140,140,140))
        light_palette.setColor(QPalette.Disabled, QPalette.Text, QColor(140,140,140))
        light_palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(140,140,140))
        app.setPalette(light_palette)
        app.setStyleSheet("""QWidget{background-color:#f0f0f0;color:#000;}QFrame{background-color:#f0f0f0;}QLabel{color:#000;}QPushButton{background-color:#e0e0e0;color:#000;border:1px solid #ccc;border-radius:4px;padding:4px 10px;}QPushButton:hover{background-color:#d0d0d0;}QPushButton:pressed{background-color:#c0c0c0;}QPushButton:disabled{color:#999;background-color:#e8e8e8;}QPushButton:checked{background-color:#2196F3;border-color:#2196F3;color:white;}QListWidget{background-color:#fff;color:#000;border:1px solid #ccc;border-radius:4px;}QListWidget::item{padding:3px 5px;border-radius:2px;}QListWidget::item:selected{background-color:#2196F3;color:white;}QListWidget::item:hover{background-color:#e0e0e0;}QScrollArea{border:none;background-color:#f0f0f0;}QScrollBar:vertical{background-color:#f0f0f0;width:12px;border-radius:6px;}QScrollBar::handle:vertical{background-color:#ccc;border-radius:6px;min-height:20px;}QScrollBar::handle:vertical:hover{background-color:#aaa;}QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0px;}QScrollBar:horizontal{background-color:#f0f0f0;height:12px;border-radius:6px;}QScrollBar::handle:horizontal{background-color:#ccc;border-radius:6px;min-width:20px;}QScrollBar::handle:horizontal:hover{background-color:#aaa;}QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{width:0px;}QComboBox{background-color:#fff;color:#000;border:1px solid #ccc;border-radius:4px;padding:2px 8px;}QComboBox:hover{background-color:#f0f0f0;}QComboBox::drop-down{border:none;width:20px;}QComboBox QAbstractItemView{background-color:#fff;color:#000;selection-background-color:#2196F3;selection-color:white;}QLineEdit{background-color:#fff;color:#000;border:1px solid #ccc;border-radius:4px;padding:4px 8px;}QLineEdit:focus{border-color:#2196F3;}QMenu{background-color:#fff;color:#000;border:1px solid #ccc;}QMenu::item:selected{background-color:#2196F3;color:white;}QMenuBar{background-color:#f0f0f0;color:#000;}QMenuBar::item:selected{background-color:#e0e0e0;}QSlider::groove:horizontal{height:6px;background:#ccc;border-radius:3px;}QSlider::handle:horizontal{background:#2196F3;width:16px;height:16px;margin:-5px 0;border-radius:8px;}QSlider::sub-page:horizontal{background:#2196F3;border-radius:3px;}QDialog{background-color:#f0f0f0;}QGroupBox{color:#000;border:1px solid #ccc;border-radius:4px;margin-top:10px;padding-top:10px;}QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 5px 0 5px;}QSplitter::handle{background-color:#ccc;}QSplitter::handle:hover{background-color:#aaa;}QLabel#info_name{color:#2196F3;}QLabel#cache_label{color:#666;}""")
        logger.info("应用浅色主题")

def detect_system_theme() -> bool:
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return value == 0
    except:
        return False

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CoverPicker")
        self.resize(1280, 720)
        self.config = ConfigManager()
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0,0,0,0)
        self.segment_view = SegmentView()
        layout.addWidget(self.segment_view)
        
        # 添加菜单栏
        self.setup_menu()
        
        # 应用保存的主题
        self.apply_saved_theme()
    
    def setup_menu(self):
        menubar = self.menuBar()
        view_menu = menubar.addMenu("视图")
        theme_menu = QMenu("主题切换", self)
        self.theme_action_system = QAction("跟随系统", self, checkable=True)
        self.theme_action_light = QAction("浅色", self, checkable=True)
        self.theme_action_dark = QAction("深色", self, checkable=True)
        theme_menu.addAction(self.theme_action_system)
        theme_menu.addAction(self.theme_action_light)
        theme_menu.addAction(self.theme_action_dark)
        view_menu.addMenu(theme_menu)
        # 连接信号
        self.theme_action_system.triggered.connect(lambda: self.set_theme('system'))
        self.theme_action_light.triggered.connect(lambda: self.set_theme('light'))
        self.theme_action_dark.triggered.connect(lambda: self.set_theme('dark'))
        # 更新勾选状态
        self.update_theme_actions()
    
    def update_theme_actions(self):
        current = self.config.get_theme()
        self.theme_action_system.setChecked(current == 'system')
        self.theme_action_light.setChecked(current == 'light')
        self.theme_action_dark.setChecked(current == 'dark')
    
    def set_theme(self, theme: str):
        self.config.set_theme(theme)
        self.apply_saved_theme()
        self.update_theme_actions()
    
    def apply_saved_theme(self):
        theme = self.config.get_theme()
        if theme == 'system':
            is_dark = detect_system_theme()
        elif theme == 'dark':
            is_dark = True
        else:
            is_dark = False
        apply_theme(QApplication.instance(), is_dark)
    
    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(500, self._check_cache)
    
    def _check_cache(self):
        try:
            controller = self.segment_view.controller
            cache_size_gb = controller.get_cache_size_gb()
            if cache_size_gb > 5.0:
                reply = QMessageBox.question(self, "缓存清理提醒", f"缓存目录当前占用 {cache_size_gb:.2f} GB，超过 5 GB。是否自动清理？", QMessageBox.Yes|QMessageBox.No)
                if reply == QMessageBox.Yes:
                    deleted, freed_mb = controller.auto_clean_cache(5.0)
                    self.segment_view.progress_label_left.setText(f"缓存清理完成：删除 {deleted} 个文件，释放 {freed_mb:.1f} MB")
                    self.segment_view._update_cache_info()
        except:
            pass

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CoverPicker")
    window = MainWindow()
    window.show()
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    with loop:
        loop.run_forever()

if __name__ == "__main__":
    main()