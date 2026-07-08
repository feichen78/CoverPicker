# region --- 首页视图：视频列表 (修复 page 属性冲突) ---
import os
import flet as ft
from src.video_scanner import VideoScanner

class HomeView(ft.Container):
    """
    首页：展示扫描到的视频列表。
    """
    def __init__(self, page: ft.Page, scanner: VideoScanner, on_video_click):
        super().__init__(expand=True, padding=20)
        
        # 【修复核心】：将 self.page 改为 self.main_page，避免与 Flet 内置属性冲突
        self.main_page = page
        self.scanner = scanner
        self.on_video_click = on_video_click
        
        # 状态文本
        self.status_text = ft.Text("点击按钮扫描视频目录...", size=16, weight="bold")
        
        # 视频列表
        self.video_list = ft.ListView(expand=True, spacing=10, padding=10)
        
        # 扫描按钮
        self.scan_btn = ft.ElevatedButton(
            "🔍 扫描视频目录", 
            icon=ft.Icons.SEARCH, 
            on_click=self._scan_videos,
            style=ft.ButtonStyle(color="white", bgcolor="blue", padding=20)
        )
        
        # 组装页面内容
        self.content = ft.Column([
            ft.Row([
                ft.Text("CoverPicker", size=24, weight="bold"),
                self.scan_btn
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(),
            self.status_text,
            self.video_list
        ], expand=True)

    def _scan_videos(self, e):
        """扫描视频目录"""
        self.status_text.value = "正在扫描，请稍候..."
        # 【修复核心】：这里也同步改为 self.main_page.update()
        self.main_page.update()
        
        self.video_list.controls.clear()
        videos = self.scanner.scan()
        
        if not videos:
            self.status_text.value = "未找到视频文件，请检查路径配置。"
            self.main_page.update()
            return
            
        for path in videos:
            file_name = os.path.basename(path)
            
            list_tile = ft.ListTile(
                leading=ft.Icon(ft.Icons.VIDEO_FILE, size=30, color="blue"),
                title=ft.Text(file_name, weight="bold"),
                subtitle=ft.Text(path, size=12, max_lines=1),
                trailing=ft.Icon(ft.Icons.CHEVRON_RIGHT),
                on_click=lambda e, p=path: self.on_video_click(p)
            )
            self.video_list.controls.append(list_tile)
            
        self.status_text.value = f"扫描完成，共找到 {len(videos)} 个视频。"
        self.main_page.update()

# endregion