# region --- 首页视图 ---
import os
import flet as ft
from src.video_scanner import VideoScanner

class HomeView(ft.Container):
    def __init__(self, page: ft.Page, scanner: VideoScanner, go_to_segment_callback):
        super().__init__(expand=True, padding=10, bgcolor=ft.Colors.SURFACE)
        
        self.main_page = page
        self.scanner = scanner
        self.go_to_segment = go_to_segment_callback
        self.video_list = []
        self.scanning = False
        
        # ----- UI 组件 -----
        self.title = ft.Text("CoverPicker", size=28, weight="bold")
        self.subtitle = ft.Text("视频封面选择工具", size=14, color="grey")
        
        self.scan_btn = ft.ElevatedButton(
            "扫描视频",
            icon=ft.Icons.FOLDER_OPEN,
            on_click=self._start_scan,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE,
                color="white",
            )
        )
        
        self.status_text = ft.Text("请点击「扫描视频」开始", size=13, color="grey")
        
        self.video_grid = ft.GridView(
            expand=True,
            runs_count=1,
            max_extent=400,
            spacing=8,
            run_spacing=8,
            padding=8,
        )
        
        self.video_container = ft.Container(
            content=self.video_grid,
            expand=True,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8,
            padding=4,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
        )
        
        self.footer = ft.Row([
            ft.Text("共 0 个视频", size=12, color="grey"),
            ft.Text("|", size=12, color="grey"),
            ft.Text("Z:\\", size=12, color="grey"),
            ft.Text("|", size=12, color="grey"),
            ft.Text("就绪", size=12, color="green"),
        ], spacing=8)
        
        self.content = ft.Column([
            ft.Row([
                ft.Column([
                    self.title,
                    self.subtitle,
                ], spacing=0),
                ft.Row([
                    self.scan_btn,
                ], alignment=ft.MainAxisAlignment.END),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(height=1),
            self.status_text,
            self.video_container,
            self.footer,
        ], expand=True, spacing=8)

    async def _start_scan(self, e):
        if self.scanning:
            return
        
        self.scanning = True
        self.scan_btn.disabled = True
        self.status_text.value = "正在扫描视频，请稍候..."
        self.status_text.color = "blue"
        self.main_page.update()
        
        try:
            self.video_list = await self.scanner.scan_videos("Z:\\")
            
            self.status_text.value = f"扫描完成，共找到 {len(self.video_list)} 个视频"
            self.status_text.color = "green"
            
            self.footer.controls[0] = ft.Text(f"共 {len(self.video_list)} 个视频", size=12, color="grey")
            self.footer.controls[4] = ft.Text("就绪", size=12, color="green")
            
            self._build_video_grid()
            
        except Exception as ex:
            self.status_text.value = f"扫描失败: {str(ex)}"
            self.status_text.color = "red"
            print(f"[扫描异常]: {ex}")
        finally:
            self.scanning = False
            self.scan_btn.disabled = False
            self.main_page.update()

    def _build_video_grid(self):
        self.video_grid.controls.clear()
        
        for video_path in self.video_list:
            name = os.path.basename(video_path)
            try:
                size = os.path.getsize(video_path)
                size_str = f"{size / (1024**3):.1f} GB" if size > 1024**3 else f"{size / (1024**2):.1f} MB"
            except:
                size_str = "未知"
            
            card = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.VIDEO_FILE, size=32, color=ft.Colors.BLUE),
                    ft.Column([
                        ft.Text(name, size=14, weight="bold", max_lines=1),
                        ft.Text(f"文件大小: {size_str}", size=11, color="grey"),
                    ], spacing=0, expand=True),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, size=20, color="grey"),
                ], alignment=ft.MainAxisAlignment.START, spacing=8),
                padding=12,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=8,
                on_click=lambda e, path=video_path: self.go_to_segment(path),
            )
            self.video_grid.controls.append(card)
        self.main_page.update()
# endregion