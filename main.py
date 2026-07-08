# region --- 程序绝对主入口 (独立桌面软件版，严格适配 Flet 0.85.3) ---
import flet as ft
from src.video_scanner import VideoScanner
from ui.views.home_view import HomeView
from ui.views.segment_view import SegmentView

def main(page: ft.Page):
    # 1. 全局基础设置
    page.title = "CoverPicker - 视频封面挑选工具"
    page.window_width = 1000
    page.window_height = 700
    page.bgcolor = ft.Colors.SURFACE
    
    # 2. 初始化核心引擎
    scanner = VideoScanner({
        "supported_extensions": [
            ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".ts", ".flv", ".webm", ".m4v", ".mpg", ".mpeg"
        ], 
        "nas_video_path": "Z:\\"
    })
    
    # 【核心修复】：彻底放弃 page.go() 路由，改用纯视图栈 (View Stack) 管理，这是 Flet 最稳定的做法
    def show_home():
        page.views.clear()
        page.views.append(
            ft.View(
                route="/home",
                controls=[HomeView(page, scanner, go_to_segment)]
            )
        )
        page.update()

    def go_to_segment(video_path):
        """进入分区挑选页：直接追加视图，不触发路由"""
        page.views.append(
            ft.View(
                route=f"/segment/{video_path}",
                controls=[SegmentView(page, video_path, go_back)]
            )
        )
        page.update()

    def go_back(e=None):
        """返回上一页：安全弹出视图栈"""
        if len(page.views) > 1:
            page.views.pop()
            page.update()
        else:
            show_home()

    # 3. 启动时直接显示首页
    show_home()

if __name__ == "__main__":
    ft.app(target=main) 
# endregion