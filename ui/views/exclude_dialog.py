# ui/views/exclude_dialog.py
# 排除区间设置对话框 —— 时间格式改为 hh:mm:ss

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QGroupBox, QFormLayout,
    QMessageBox, QTimeEdit
)
from PySide6.QtCore import Qt, QTime
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


class ExcludeDialog(QDialog):
    """排除区间设置对话框（时间格式 hh:mm:ss）"""

    def __init__(self, ranges: List[Tuple[float, float]], duration: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("排除区间设置")
        self.setMinimumWidth(450)
        self.setMinimumHeight(350)

        self.ranges = ranges.copy()
        self.duration = duration
        self.parent_view = parent

        self.setup_ui()

    def _seconds_to_time(self, seconds: float) -> QTime:
        """将秒数转换为 QTime"""
        seconds = max(0, min(seconds, self.duration))
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return QTime(hours, minutes, secs)

    def _time_to_seconds(self, time: QTime) -> float:
        """将 QTime 转换为秒数"""
        return time.hour() * 3600 + time.minute() * 60 + time.second()

    def _format_time(self, seconds: float) -> str:
        """格式化时间为 hh:mm:ss"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def setup_ui(self):
        layout = QVBoxLayout(self)

        info_label = QLabel("设置要排除的时间段（如片头片尾、版权声明），生成截图时自动跳过这些区间。")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(info_label)

        persist_label = QLabel("💡 排除区间将自动保存到数据库，并通过云同步在不同设备间共享。")
        persist_label.setWordWrap(True)
        persist_label.setStyleSheet("color: #2196F3; font-size: 10px;")
        layout.addWidget(persist_label)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("QListWidget::item { padding: 4px; }")
        self._refresh_list()
        layout.addWidget(self.list_widget)

        add_group = QGroupBox("添加新区间")
        add_layout = QFormLayout(add_group)

        # 起始时间（使用 QTimeEdit）
        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setDisplayFormat("HH:mm:ss")
        self.start_time_edit.setWrapping(True)
        self.start_time_edit.setTime(self._seconds_to_time(0))
        add_layout.addRow("起始时间:", self.start_time_edit)

        # 结束时间（使用 QTimeEdit）
        self.end_time_edit = QTimeEdit()
        self.end_time_edit.setDisplayFormat("HH:mm:ss")
        self.end_time_edit.setWrapping(True)
        self.end_time_edit.setTime(self._seconds_to_time(min(60, self.duration)))
        add_layout.addRow("结束时间:", self.end_time_edit)

        add_btn = QPushButton("添加区间")
        add_btn.clicked.connect(self._add_range)
        add_layout.addRow(add_btn)

        layout.addWidget(add_group)

        btn_layout = QHBoxLayout()
        remove_btn = QPushButton("删除选中")
        remove_btn.clicked.connect(self._remove_selected)
        btn_layout.addWidget(remove_btn)

        clear_btn = QPushButton("清空所有")
        clear_btn.clicked.connect(self._clear_all)
        btn_layout.addWidget(clear_btn)

        btn_layout.addStretch()

        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _refresh_list(self):
        """刷新排除区间列表"""
        self.list_widget.clear()
        for start, end in self.ranges:
            item = QListWidgetItem(
                f"{self._format_time(start)} - {self._format_time(end)}  (时长: {end - start:.1f}s)"
            )
            item.setData(Qt.UserRole, (start, end))
            self.list_widget.addItem(item)

    def _add_range(self):
        """添加新区间"""
        start = self._time_to_seconds(self.start_time_edit.time())
        end = self._time_to_seconds(self.end_time_edit.time())

        if start >= end:
            QMessageBox.warning(self, "错误", "起始时间必须小于结束时间。")
            return

        # 检查是否超出视频时长
        if end > self.duration:
            QMessageBox.warning(self, "错误", f"结束时间不能超过视频时长 ({self._format_time(self.duration)})。")
            return

        # 检查是否与其他区间重叠
        for s, e in self.ranges:
            if not (end <= s or start >= e):
                QMessageBox.warning(
                    self,
                    "错误",
                    f"区间与 {self._format_time(s)}-{self._format_time(e)} 重叠，请调整。"
                )
                return

        self.ranges.append((start, end))
        self.ranges.sort(key=lambda x: x[0])
        self._refresh_list()

    def _remove_selected(self):
        """删除选中的区间"""
        item = self.list_widget.currentItem()
        if item:
            idx = self.list_widget.row(item)
            del self.ranges[idx]
            self._refresh_list()

    def _clear_all(self):
        """清空所有区间"""
        if self.ranges:
            reply = QMessageBox.question(
                self,
                "确认",
                "确定要清空所有排除区间吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.ranges.clear()
                self._refresh_list()

    def get_ranges(self) -> List[Tuple[float, float]]:
        """获取排除区间列表（秒数格式）"""
        return self.ranges

    def accept(self):
        """确定时保存排除区间到数据库"""
        super().accept()
        if self.parent_view and hasattr(self.parent_view, 'controller'):
            controller = self.parent_view.controller
            controller.set_excluded_ranges(self.ranges, save=True)
            logger.info(f"排除区间已保存: {self.ranges}")