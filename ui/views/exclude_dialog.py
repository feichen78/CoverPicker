from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLineEdit, QLabel, QMessageBox
)
from PySide6.QtCore import Qt
from typing import List, Tuple

class ExcludeRangeDialog(QDialog):
    def __init__(self, ranges: List[Tuple[float, float]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("排除区间设置")
        self.setMinimumWidth(400)
        self.setModal(True)
        self.ranges = ranges.copy()

        layout = QVBoxLayout(self)

        # 说明
        layout.addWidget(QLabel("排除这些时间段内的截图（秒）："))

        # 列表显示已有区间
        self.list_widget = QListWidget()
        self.update_list()
        layout.addWidget(self.list_widget)

        # 添加新区间
        add_layout = QHBoxLayout()
        self.start_input = QLineEdit()
        self.start_input.setPlaceholderText("起始秒")
        self.end_input = QLineEdit()
        self.end_input.setPlaceholderText("结束秒")
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self.add_range)
        add_layout.addWidget(QLabel("新增:"))
        add_layout.addWidget(self.start_input)
        add_layout.addWidget(self.end_input)
        add_layout.addWidget(add_btn)
        layout.addLayout(add_layout)

        # 删除选中
        del_btn = QPushButton("删除选中")
        del_btn.clicked.connect(self.delete_selected)
        layout.addWidget(del_btn)

        # 按钮
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确认")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def update_list(self):
        self.list_widget.clear()
        for low, high in self.ranges:
            item = QListWidgetItem(f"{low:.1f}s  ~  {high:.1f}s")
            item.setData(Qt.UserRole, (low, high))
            self.list_widget.addItem(item)

    def add_range(self):
        try:
            low = float(self.start_input.text())
            high = float(self.end_input.text())
            if low >= high:
                QMessageBox.warning(self, "错误", "起始时间必须小于结束时间。")
                return
            self.ranges.append((low, high))
            self.ranges.sort(key=lambda x: x[0])
            self.update_list()
            self.start_input.clear()
            self.end_input.clear()
        except ValueError:
            QMessageBox.warning(self, "错误", "请输入有效的数字（秒）。")

    def delete_selected(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.ranges.pop(row)
            self.update_list()

    def get_ranges(self) -> List[Tuple[float, float]]:
        return self.ranges