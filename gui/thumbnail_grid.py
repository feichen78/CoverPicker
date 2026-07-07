# 多密度网格缩略图、收藏/锁定角标
from PySide6.QtWidgets import QWidget, QGridLayout, QLabel, QFrame
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtCore import Qt, Signal

class ThumbItem(QLabel):
    clicked_slot = Signal(int)
    def __init__(self, slot_id: int):
        super().__init__()
        self.slot_id = slot_id
        self.setFixedSize(130, 90)
        self.setFrameShape(QFrame.Box)
        self.favorite = False
        self.locked = False
        self.update_mark()

    def update_mark(self):
        tip = ""
        if self.locked:
            tip += "🔒"
        if self.favorite:
            tip += "♥"
        self.setText(tip)
        font = QFont()
        font.setPointSize(16)
        self.setFont(font)
        self.setAlignment(Qt.AlignBottom | Qt.AlignRight)

    def mouseReleaseEvent(self, evt):
        self.clicked_slot.emit(self.slot_id)

class ThumbGrid(QWidget):
    slot_click = Signal(int)
    grid_size_change = Signal(int)
    def __init__(self):
        super().__init__()
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(6)
        self.setLayout(self.grid_layout)
        self.items = {}

    def clear_all(self):
        self.items.clear()
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def render_slots(self, slots, grid_count: int):
        self.clear_all()
        row_max = {9:3,12:3,16:4,25:5}[grid_count]
        idx = 0
        for slot in slots:
            item = ThumbItem(slot.id)
            item.favorite = slot.favorite
            item.locked = slot.locked
            item.update_mark()
            pix = QPixmap(slot.frame.cache_path)
            item.setPixmap(pix.scaled(130,90,Qt.KeepAspectRatio))
            item.clicked_slot.connect(self.slot_click.emit)
            self.items[slot.id] = item
            r = idx // row_max
            c = idx % row_max
            self.grid_layout.addWidget(item, r, c)
            idx += 1