# A/B/C/D/E 分区导航栏
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal

class SegmentBar(QWidget):
    seg_clicked = Signal(str)
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout()
        layout.setSpacing(8)
        self.btns = {}
        for label in ["A", "B", "C", "D", "E"]:
            btn = QPushButton(f"分区{label}")
            btn.clicked.connect(lambda chk, lab=label: self.seg_clicked.emit(lab))
            self.btns[label] = btn
            layout.addWidget(btn)
        self.setLayout(layout)

    def set_active(self, seg_id: str):
        for lab, btn in self.btns.items():
            if lab == seg_id:
                btn.setStyleSheet("background:#3388ff;color:white;")
            else:
                btn.setStyleSheet("")