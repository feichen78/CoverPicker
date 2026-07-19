# ui/views/exclude_dialog.py
# 排除区间设置对话框 —— 支持编辑已有区间（v2.1.5）

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QGroupBox, QFormLayout,
    QMessageBox, QTimeEdit, QWidget
)
from PySide6.QtCore import Qt, QTime
from typing import List, Tuple, Optional
from functools import partial
import logging

logger = logging.getLogger(__name__)


class ExcludeDialog(QDialog):
    """排除区间设置对话框（时间格式 hh:mm:ss），支持编辑已有区间"""

    def __init__(self, ranges: List[Tuple[float, float]], duration: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("排除区间设置")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self.ranges = ranges.copy()
        self.duration = duration
        self.parent_view = parent

        self._editing_index: Optional[int] = None

        self.list_widget = None
        self.start_time_edit = None
        self.end_time_edit = None
        self.add_btn = None
        self.update_btn = None
        self.cancel_edit_btn = None

        self.setup_ui()

    def _seconds_to_time(self, seconds: float) -> QTime:
        seconds = max(0, min(seconds, self.duration))
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return QTime(hours, minutes, secs)

    def _time_to_seconds(self, time: QTime) -> float:
        return time.hour() * 3600 + time.minute() * 60 + time.second()

    def _format_time(self, seconds: float) -> str:
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
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.list_widget)

        add_group = QGroupBox("添加/编辑区间")
        add_layout = QFormLayout(add_group)

        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setDisplayFormat("HH:mm:ss")
        self.start_time_edit.setWrapping(True)
        self.start_time_edit.setTime(self._seconds_to_time(0))
        add_layout.addRow("起始时间:", self.start_time_edit)

        self.end_time_edit = QTimeEdit()
        self.end_time_edit.setDisplayFormat("HH:mm:ss")
        self.end_time_edit.setWrapping(True)
        self.end_time_edit.setTime(self._seconds_to_time(min(60, self.duration)))
        add_layout.addRow("结束时间:", self.end_time_edit)

        btn_row = QHBoxLayout()

        self.add_btn = QPushButton("添加区间")
        self.add_btn.clicked.connect(self._add_range)
        btn_row.addWidget(self.add_btn)

        self.update_btn = QPushButton("更新区间")
        self.update_btn.setEnabled(False)
        self.update_btn.clicked.connect(self._update_range)
        btn_row.addWidget(self.update_btn)

        self.cancel_edit_btn = QPushButton("取消编辑")
        self.cancel_edit_btn.setEnabled(False)
        self.cancel_edit_btn.clicked.connect(self._cancel_edit)
        btn_row.addWidget(self.cancel_edit_btn)

        btn_row.addStretch()
        add_layout.addRow(btn_row)

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

        self._refresh_list()

    def _refresh_list(self):
        self.list_widget.clear()
        for idx, (start, end) in enumerate(self.ranges):
            item = QListWidgetItem()
            widget = QWidget()
            widget_layout = QHBoxLayout(widget)
            widget_layout.setContentsMargins(0, 0, 0, 0)
            widget_layout.setSpacing(4)

            label = QLabel(
                f"{self._format_time(start)} - {self._format_time(end)}  (时长: {end - start:.1f}s)"
            )
            label.setStyleSheet("padding-left: 4px;")
            widget_layout.addWidget(label)

            widget_layout.addStretch()

            edit_btn = QPushButton("✏️ 编辑")
            edit_btn.setFixedWidth(60)
            edit_btn.setStyleSheet("font-size: 10px; padding: 2px 4px;")
            edit_btn.clicked.connect(partial(self._start_edit, idx))
            widget_layout.addWidget(edit_btn)

            widget.setLayout(widget_layout)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

        if self._editing_index is not None and self._editing_index < len(self.ranges):
            item = self.list_widget.item(self._editing_index)
            if item:
                item.setBackground(Qt.GlobalColor.lightGray)
                self.list_widget.setCurrentRow(self._editing_index)

        self._update_button_states()

    def _update_button_states(self):
        is_editing = self._editing_index is not None
        self.add_btn.setEnabled(not is_editing)
        self.update_btn.setEnabled(is_editing)
        self.cancel_edit_btn.setEnabled(is_editing)

    def _start_edit(self, index: int):
        if index < 0 or index >= len(self.ranges):
            return
        self._editing_index = index
        start, end = self.ranges[index]
        self.start_time_edit.setTime(self._seconds_to_time(start))
        self.end_time_edit.setTime(self._seconds_to_time(end))
        self._clear_highlight()
        item = self.list_widget.item(index)
        if item:
            item.setBackground(Qt.GlobalColor.lightGray)
            self.list_widget.setCurrentRow(index)
        self._update_button_states()

    def _cancel_edit(self):
        self._editing_index = None
        self._clear_highlight()
        self._update_button_states()

    def _clear_highlight(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item:
                item.setBackground(Qt.GlobalColor.transparent)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        index = self.list_widget.row(item)
        if index is not None and index < len(self.ranges):
            self._start_edit(index)

    def _add_range(self):
        if self._editing_index is not None:
            self._cancel_edit()

        start = self._time_to_seconds(self.start_time_edit.time())
        end = self._time_to_seconds(self.end_time_edit.time())

        if start >= end:
            QMessageBox.warning(self, "错误", "起始时间必须小于结束时间。")
            return

        if end > self.duration:
            QMessageBox.warning(self, "错误", f"结束时间不能超过视频时长 ({self._format_time(self.duration)})。")
            return

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

    def _update_range(self):
        if self._editing_index is None:
            return

        start = self._time_to_seconds(self.start_time_edit.time())
        end = self._time_to_seconds(self.end_time_edit.time())

        if start >= end:
            QMessageBox.warning(self, "错误", "起始时间必须小于结束时间。")
            return

        if end > self.duration:
            QMessageBox.warning(self, "错误", f"结束时间不能超过视频时长 ({self._format_time(self.duration)})。")
            return

        for idx, (s, e) in enumerate(self.ranges):
            if idx == self._editing_index:
                continue
            if not (end <= s or start >= e):
                QMessageBox.warning(
                    self,
                    "错误",
                    f"区间与 {self._format_time(s)}-{self._format_time(e)} 重叠，请调整。"
                )
                return

        self.ranges[self._editing_index] = (start, end)
        self.ranges.sort(key=lambda x: x[0])

        found_index = None
        for idx, (s, e) in enumerate(self.ranges):
            if abs(s - start) < 0.001 and abs(e - end) < 0.001:
                found_index = idx
                break

        if found_index is not None:
            self._editing_index = found_index
        else:
            self._editing_index = None

        self._refresh_list()
        self._update_button_states()

    def _remove_selected(self):
        if self._editing_index is not None:
            QMessageBox.information(self, "提示", "请先取消编辑再删除区间。")
            return

        item = self.list_widget.currentItem()
        if item is None:
            return

        idx = self.list_widget.row(item)
        if idx < len(self.ranges):
            del self.ranges[idx]
            self._refresh_list()

    def _clear_all(self):
        if self._editing_index is not None:
            QMessageBox.information(self, "提示", "请先取消编辑再清空区间。")
            return

        if not self.ranges:
            return

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
        return self.ranges

    def accept(self):
        super().accept()
        if self.parent_view and hasattr(self.parent_view, 'controller'):
            controller = self.parent_view.controller
            controller.set_excluded_ranges(self.ranges, save=True)
            logger.info(f"排除区间已保存: {self.ranges}")