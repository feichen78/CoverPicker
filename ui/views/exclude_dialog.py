# ui/views/exclude_dialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QDoubleSpinBox, QGroupBox,
    QFormLayout, QMessageBox
)
from PySide6.QtCore import Qt
from typing import List, Tuple


class ExcludeDialog(QDialog):
    """排除区间设置对话框"""

    def __init__(self, ranges: List[Tuple[float, float]], duration: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("排除区间设置")
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)

        self.ranges = ranges.copy()
        self.duration = duration

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 说明
        info_label = QLabel("设置要排除的时间段（如片头片尾、版权声明），生成截图时自动跳过这些区间。")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(info_label)

        # 区间列表
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("QListWidget::item { padding: 4px; }")
        self._refresh_list()
        layout.addWidget(self.list_widget)

        # 添加区间控件
        add_group = QGroupBox("添加新区间")
        add_layout = QFormLayout(add_group)

        self.start_spin = QDoubleSpinBox()
        self.start_spin.setRange(0, self.duration)
        self.start_spin.setSingleStep(1)
        self.start_spin.setDecimals(1)
        self.start_spin.setSuffix(" 秒")
        add_layout.addRow("起始时间:", self.start_spin)

        self.end_spin = QDoubleSpinBox()
        self.end_spin.setRange(0, self.duration)
        self.end_spin.setSingleStep(1)
        self.end_spin.setDecimals(1)
        self.end_spin.setSuffix(" 秒")
        add_layout.addRow("结束时间:", self.end_spin)

        add_btn = QPushButton("添加区间")
        add_btn.clicked.connect(self._add_range)
        add_layout.addRow(add_btn)

        layout.addWidget(add_group)

        # 操作按钮
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
        self.list_widget.clear()
        for start, end in self.ranges:
            item = QListWidgetItem(f"{start:.1f}s - {end:.1f}s  (时长: {end - start:.1f}s)")
            item.setData(Qt.UserRole, (start, end))
            self.list_widget.addItem(item)

    def _add_range(self):
        start = self.start_spin.value()
        end = self.end_spin.value()
        if start >= end:
            QMessageBox.warning(self, "错误", "起始时间必须小于结束时间。")
            return
        # 检查是否与其他区间重叠
        for s, e in self.ranges:
            if not (end <= s or start >= e):
                QMessageBox.warning(self, "错误", f"区间与 {s:.1f}-{e:.1f} 重叠，请调整。")
                return
        self.ranges.append((start, end))
        self.ranges.sort(key=lambda x: x[0])
        self._refresh_list()

    def _remove_selected(self):
        item = self.list_widget.currentItem()
        if item:
            idx = self.list_widget.row(item)
            del self.ranges[idx]
            self._refresh_list()

    def _clear_all(self):
        if self.ranges:
            reply = QMessageBox.question(self, "确认", "确定要清空所有排除区间吗？", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.ranges.clear()
                self._refresh_list()

    def get_ranges(self) -> List[Tuple[float, float]]:
        return self.ranges