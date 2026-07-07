# L1~L4 Zoom层级控制面板
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal

class ZoomPanel(QWidget):
    zoom_level_change = Signal(int)
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout()
        self.btns = {}
        levels = [
            (1, "L1 ±2s"),
            (2, "L2 ±8s"),
            (3, "L3 跨相邻"),
            (4, "L4 全局重采样")
        ]
        for lv, txt in levels:
            btn = QPushButton(txt)
            btn.clicked.connect(lambda chk, l=lv: self.zoom_level_change.emit(l))
            self.btns[lv] = btn
            layout.addWidget(btn)
        self.setLayout(layout)