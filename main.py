import sys
import asyncio
import traceback
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtCore import QTimer
from qasync import QEventLoop
from ui.views.segment_view import SegmentView

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        print("MainWindow init start")
        self.setWindowTitle("CoverPicker - 视频封面选择器")
        self.resize(1400, 900)
        try:
            self.segment_view = SegmentView()
            self.setCentralWidget(self.segment_view)
            print("SegmentView created successfully")
        except Exception as e:
            print("Error creating SegmentView:")
            traceback.print_exc()
            # 即使出错也继续，避免窗口不显示
            import sys
            sys.exit(1)
        # 延迟加载第一个视频（确保事件循环已运行）
        QTimer.singleShot(200, self.segment_view.load_first_video)

def main():
    print("main start")
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    window = MainWindow()
    window.show()
    print("Window shown")
    with loop:
        sys.exit(loop.run_forever())

if __name__ == "__main__":
    main()