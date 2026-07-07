# CoverPicker GUI 修复版 - 确保点击视频能触发后台任务并弹窗报错
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox, QComboBox
)
from PySide6.QtCore import Qt, QThread, Signal, QObject

from config import DEFAULT_GRID_SIZE, SUPPORT_GRID_SIZES
from core.orchestrator import EngineOrchestrator
from core.state_manager import StateManager
from gui.file_tree import VideoTree
from gui.segment_widget import SegmentBar
from gui.zoom_widget import ZoomPanel
from gui.status_widget import BestPreviewBar
from gui.thumbnail_grid import ThumbGrid

class BackendWorker(QObject):
    task_done = Signal(dict)
    task_error = Signal(str)
    def __init__(self, orchestrator, action, payload):
        super().__init__()
        self.orch = orchestrator
        self.action = action
        self.payload = payload
    def run(self):
        try:
            task = self.orch.submit_task(self.action, self.payload)
            res = self.orch.wait_task(task, timeout=20)
            self.task_done.emit(res)
        except Exception as e:
            self.task_error.emit(str(e))

class MainWindow(QMainWindow):
    def __init__(self, orchestrator: EngineOrchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self.state = orchestrator.state_mgr
        self.current_gen_id = 2
        self._active_threads = []
        self.setWindowTitle("CoverPicker v3.2 日志修复版")
        self.resize(1440, 820)
        self._build_ui()
        self._bind_signal()

    def closeEvent(self, event):
        for t in self._active_threads:
            if t.isRunning():
                t.quit()
                t.wait(2000)
        event.accept()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_h = QHBoxLayout(central)
        self.tree = VideoTree()
        self.tree.setFixedWidth(260)
        main_h.addWidget(self.tree)

        right_v = QVBoxLayout()
        main_h.addLayout(right_v)
        top_bar = QHBoxLayout()
        self.btn_scan_nas = QPushButton("扫描NAS/本地文件夹")
        self.cbx_grid = QComboBox()
        for s in SUPPORT_GRID_SIZES:
            self.cbx_grid.addItem(f"{s}格网格", s)
        self.cbx_grid.setCurrentText(f"{DEFAULT_GRID_SIZE}格网格")
        self.btn_opt = QPushButton("Optimize全局刷新")
        self.btn_export_all = QPushButton("批量导出收藏剧照")
        top_bar.addWidget(self.btn_scan_nas)
        top_bar.addWidget(QLabel("网格密度:"))
        top_bar.addWidget(self.cbx_grid)
        top_bar.addWidget(self.btn_opt)
        top_bar.addWidget(self.btn_export_all)
        right_v.addLayout(top_bar)

        self.seg_bar = SegmentBar()
        right_v.addWidget(self.seg_bar)
        self.zoom_panel = ZoomPanel()
        right_v.addWidget(self.zoom_panel)

        mid_h = QHBoxLayout()
        self.grid = ThumbGrid()
        mid_h.addWidget(self.grid)
        self.best_view = BestPreviewBar()
        self.best_view.setFixedWidth(240)
        mid_h.addWidget(self.best_view)
        right_v.addLayout(mid_h)

        bottom_bar = QHBoxLayout()
        self.btn_clip = QPushButton("导出当前帧15秒片段")
        bottom_bar.addWidget(self.btn_clip)
        right_v.addLayout(bottom_bar)

    def _bind_signal(self):
        # 核心绑定：视频树点击信号绑定加载函数
        self.tree.video_click.connect(self.on_video_selected)
        self.btn_scan_nas.clicked.connect(self.on_choose_dir)
        self.seg_bar.seg_clicked.connect(self.on_switch_segment)
        self.grid.slot_click.connect(self.on_click_slot)
        self.zoom_panel.zoom_level_change.connect(self.on_set_zoom)
        self.btn_opt.clicked.connect(self.run_optimize)
        self.cbx_grid.currentIndexChanged.connect(lambda: self.refresh_grid())

    def _start_background_task(self, action, payload):
        thread = QThread()
        worker = BackendWorker(self.orchestrator, action, payload)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        # 出错直接弹窗提示
        worker.task_error.connect(lambda err: self.show_err(f"任务失败：{err}"))
        worker.task_done.connect(lambda res: self._task_success(res))
        worker.task_done.connect(thread.quit)
        worker.task_error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        self._active_threads.append(thread)
        thread.start()

    def _task_success(self, result):
        QMessageBox.information(self, "执行成功", str(result))
        self.refresh_grid()

    def on_video_selected(self, vid_path: str):
        print(f"[GUI] 点击视频文件：{vid_path}")
        self._start_background_task("load_video", {"video_path": vid_path})

    def refresh_grid(self):
        grid_size = self.cbx_grid.currentData()
        self.state.state.global_grid_size = grid_size
        self.state.save_global_config()
        slots = self.state.state.grid_slots
        self.grid.render_slots(slots, grid_size)
        best_id = self.state.state.best_slot_id
        if best_id:
            best_slot = self.state.get_slot_by_id(best_id)
            self.best_view.set_preview(best_slot.frame.cache_path)
        else:
            self.best_view.label_img.setText("暂无有效截图（抽帧失败/全黑过滤）")

    def on_choose_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "选择NAS/本地视频目录")
        if folder:
            self.tree.scan_folder(folder)

    def on_switch_segment(self, seg_id: str):
        self.seg_bar.set_active(seg_id)
        if not self.state.state.current_video:
            return
        seg = next(s for s in self.state.state.current_video.segments if s.id == seg_id)
        payload = {
            "video": self.state.state.current_video,
            "target_seg": seg,
            "gen_id": self.current_gen_id
        }
        self.current_gen_id += 1
        self._start_background_task("optimize_resample", payload)

    def on_click_slot(self, slot_id: int):
        self._start_background_task("toggle_favorite", {"slot_id":slot_id})

    def on_set_zoom(self, level: int):
        if not self.state.state.best_slot_id:
            QMessageBox.warning(self,"提示","请先选中一张截图再Zoom")
            return
        base_slot = self.state.get_slot_by_id(self.state.state.best_slot_id)
        seg = next(s for s in self.state.state.current_video.segments if s.id == base_slot.source_segment)
        payload = {
            "video": self.state.state.current_video,
            "base_ts": base_slot.frame.timestamp,
            "base_seg": seg,
            "zoom_level": level,
            "gen_id": self.current_gen_id
        }
        self.current_gen_id += 1
        self._start_background_task("zoom_sample", payload)

    def run_optimize(self):
        if not self.state.state.current_video or not self.state.state.current_seg_id:
            QMessageBox.warning(self,"提示","请先加载视频并选择分区")
            return
        seg_id = self.state.state.current_seg_id
        seg = next(s for s in self.state.state.current_video.segments if s.id == seg_id)
        payload = {
            "video": self.state.state.current_video,
            "target_seg": seg,
            "gen_id": self.current_gen_id
        }
        self.current_gen_id += 1
        self._start_background_task("optimize_resample", payload)

    def show_err(self, msg: str):
        QMessageBox.critical(self, "错误", msg)