# Best最优帧预览状态栏
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

class BestPreviewBar(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.label_title = QLabel("当前推荐最佳帧(Best)")
        self.label_img = QLabel("暂无候选截图")
        self.label_img.setFixedSize(220, 140)
        self.label_img.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label_title)
        layout.addWidget(self.label_img)
        self.setLayout(layout)

    def set_preview(self, img_path: str):
        pix = QPixmap(img_path)
        if pix.isNull():
            self.label_img.setText("图片加载失败")
            return
        self.label_img.setPixmap(pix.scaled(220, 140, Qt.KeepAspectRatio))