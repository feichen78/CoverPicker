import sys
import asyncio
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PySide6.QtCore import QTimer
from qasync import QEventLoop
from ui.views.segment_view import SegmentView


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


def main():
    app = QApplication(sys.argv)
    # 创建与 Qt 集成的 asyncio 事件循环
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.show()

    # 启动事件循环（阻塞直到应用程序退出）
    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()