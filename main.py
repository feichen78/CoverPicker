# region --- 程序绝对主入口 ---
import flet as ft
from src.video_scanner import VideoScanner
from ui.views.home_view import HomeView
from ui.views.segment_view import SegmentView

def main(page: ft.Page):
    page.title = "CoverPicker - 视频封面挑选工具"
    page.window_width = 1300
    page.window_height = 900
    page.bgcolor = ft.Colors.SURFACE
    page.padding = 0
    page.spacing = 0
    
    print("[main] 初始化...")
    
    scanner = VideoScanner({
        "supported_extensions": [
            ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".ts", ".flv", ".webm", ".m4v", ".mpg", ".mpeg"
        ], 
        "nas_video_path": "Z:\\"
    })
    
    video_list = []
    
    def go_to_segment(video_path):
        print(f"[main] 切换到 SegmentView: {video_path}")
        segment_view = SegmentView(
            page=page,
            video_path=video_path,
            on_back_click=go_back,
            video_list=video_list,
        )
        page.views.append(segment_view)
        page.update()
        print(f"[main] 已添加 SegmentView，当前 views 数量: {len(page.views)}")

    def go_back(e=None):
        print("[main] 返回首页")
        if len(page.views) > 1:
            page.views.pop()
            page.update()
        else:
            # 如果只有首页，清空并重建
            page.views.clear()
            home_view = HomeView(page, scanner, go_to_segment)
            page.views.append(ft.View(route="/home", controls=[home_view], padding=0))
            page.update()

    # 启动时显示首页
    home_view = HomeView(page, scanner, go_to_segment)
    page.views.append(ft.View(route="/home", controls=[home_view], padding=0))
    page.update()
    print("[main] 首页已显示")

if __name__ == "__main__":
    ft.app(target=main)
# endregion