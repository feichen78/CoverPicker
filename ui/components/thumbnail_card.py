# region --- 缩略图卡片组件 ---
import flet as ft

class ThumbnailCard(ft.Container):
    """
    可复用的缩略图卡片，支持点击、收藏、锁定状态展示。
    """
    def __init__(self, img_path, video_path, timestamp, on_click=None, **kwargs):
        super().__init__(**kwargs)
        self.img_path = img_path
        self.video_path = video_path
        self.timestamp = timestamp
        self._on_click = on_click
        
        # 基础 UI 样式
        self.border_radius = 8
        self.ink = True
        self.padding = 0
        self.on_click = self._handle_click
        
        # 内部布局
        self.content = ft.Column(
            controls=[
                ft.Image(src=img_path, fit="cover", width=300, height=180),
                ft.Container(
                    content=ft.Text(f"{timestamp:.1f}s", size=12, color="white"),
                    padding=5,
                    bgcolor="black54",
                    alignment=ft.alignment.bottom_center
                )
            ],
            spacing=0
        )

    def _handle_click(self, e):
        """处理卡片点击事件"""
        if self._on_click:
            self._on_click(self.img_path, self.video_path, self.timestamp)

# endregion