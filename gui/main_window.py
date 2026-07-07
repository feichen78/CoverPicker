# CoverPicker GUI 基础脚手架 v3.1 Stage6
import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QScrollArea, QGridLayout, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QThread
from config import THUMBNAIL_DIR, DEFAULT_GRID_SIZE
from core.orchestrator import EngineOrchestrator
from core.state_manager import StateManager

class BackendWorkThread(QThread):
    """后台异步线程，防止UI阻塞"""
    task_done = Signal(dict)
    task_error = Signal(str)

    def __init__(self, orchestrator: EngineOrchestrator, action: str, payload: dict):
        super().__init__()
        self.orch = orchestrator
        self.action = action
        self.payload = payload

    def run(self):
        try:
            task = self.orch.submit_task(self.action, self.payload)
            res = self.orch.wait_task(task)
            self.task_done.emit(res)
        except Exception as e:
            self.task_error.emit(str(e))

class MainWindow(QMainWindow):
    def __init__(self, orchestrator: EngineOrchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self.state = orchestrator.state_mgr
        self.setWindowTitle("CoverPicker v3.1 Stage6")
        self.resize(1280, 720)
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # 顶部操作栏
        top_bar = QHBoxLayout()
        self.btn_load_video = QPushButton("选择视频(NAS/本地)")
        self.btn_load_video.clicked.connect(self.on_select_video)
        self.label_current_video = QLabel("未加载视频")
        top_bar.addWidget(self.btn_load_video)
        top_bar.addWidget(self.label_current_video)
        main_layout.addLayout(top_bar)

        # 网格预览占位区
        self.grid_container = QFrame()
        grid_layout = QGridLayout(self.grid_container)
        placeholder = QLabel("加载视频后显示截图网格")
        placeholder.setAlignment(Qt.AlignCenter)
        grid_layout.addWidget(placeholder)
        main_layout.addWidget(self.grid_container)

        # 底部操作按钮栏
        bottom_bar = QHBoxLayout()
        self.btn_zoom = QPushButton("Zoom L1 精细采样")
        self.btn_optimize = QPushButton("Optimize 全局重采样")
        self.btn_export = QPushButton("导出选中剧照")
        self.btn_clip = QPushButton("导出视频片段")
        bottom_bar.addWidget(self.btn_zoom)
        bottom_bar.addWidget(self.btn_optimize)
        bottom_bar.addWidget(self.btn_export)
        bottom_bar.addWidget(self.btn_clip)
        main_layout.addLayout(bottom_bar)

    def on_select_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择视频文件", "",
            "Video Files (*.mp4 *.mkv *.mov *.avi *.flv)"
        )
        if not file_path:
            return
        self.label_current_video.setText(file_path)
        # 后台加载视频
        worker = BackendWorkThread(self.orchestrator, "load_video", {"video_path": file_path})
        worker.task_done.connect(self.on_video_loaded)
        worker.task_error.connect(self.show_err)
        worker.start()

    def on_video_loaded(self, result: dict):
        QMessageBox.information(self, "完成", f"视频加载成功\n分区列表：{result['segments']}")

    def show_err(self, err_msg: str):
        QMessageBox.critical(self, "操作失败", err_msg)