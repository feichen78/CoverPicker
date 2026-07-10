import sys
import asyncio
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtCore import QTimer
from qasync import QEventLoop
from ui.views.segment_view import SegmentView

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CoverPicker - 视频封面选择器")
        self.resize(1400, 900)
        self.segment_view = SegmentView()
        self.setCentralWidget(self.segment_view)
        # 延迟加载第一个视频（如果存在）
        QTimer.singleShot(200, self.segment_view.load_first_video)

def main():
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    window = MainWindow()
    window.show()
    with loop:
        sys.exit(loop.run_forever())

if __name__ == "__main__":
    main()