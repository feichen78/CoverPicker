# gui/segment_widget.py

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton


class SegmentWidget(QWidget):
    """
    A–E 分区选择栏
    """

    def __init__(self, on_click):
        super().__init__()

        self.on_click = on_click
        self.buttons = {}

        layout = QHBoxLayout()
        self.setLayout(layout)

        for i in range(5):
            name = chr(ord("A") + i)
            btn = QPushButton(name)

            btn.clicked.connect(lambda _, n=name: self._clicked(n))

            self.buttons[name] = btn
            layout.addWidget(btn)

    def _clicked(self, name):
        self.on_click(name)

    def set_active(self, name):
        for k, btn in self.buttons.items():
            btn.setStyleSheet("")
        if name in self.buttons:
            self.buttons[name].setStyleSheet(
                "background-color: #448aff; color: white;"
            )