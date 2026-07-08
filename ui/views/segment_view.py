# region --- 分区视图：5分段导航 + 网格密度切换 (增强错误处理版) ---
import os
import shutil
import asyncio
import math
import traceback
import flet as ft
from src.video_scanner import VideoScanner

class SegmentView(ft.Container):
    def __init__(self, page: ft.Page, video_path: str, on_back_click):
        super().__init__(expand=True, padding=20)
        
        self.main_page = page
        self.video_path = video_path
        self.on_back_click = on_back_click
        self.video_name = os.path.basename(video_path)
        
        self.is_loading = False
        self.selected_index = None
        self.current_seg_idx = 0
        self.density = 16
        self.segments = []
        self.current_images = []
        self.current_timestamps = []
        
        # UI 组件（与之前相同）
        self.header = ft.Row([
            ft.TextButton("⬅️ 返回视频列表", on_click=self.on_back_click),
            ft.Text(self.video_name, size=20, weight="bold", max_lines=1, expand=True),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        
        self.segment_chips = []
        self.segment_row = ft.Row(spacing=10, alignment=ft.MainAxisAlignment.CENTER)
        
        self.density_buttons = []
        self.density_row = ft.Row(spacing=5, alignment=ft.MainAxisAlignment.CENTER)
        
        self.status_text = ft.Text("请稍候，正在加载视频分区...", size=14, color="grey")
        
        self.grid = ft.GridView(
            expand=True,
            runs_count=4,
            max_extent=200,
            child_aspect_ratio=16/9,
            spacing=10,
            run_spacing=10,
            padding=10
        )
        
        self.bottom_bar = ft.Container(
            content=ft.Row([
                ft.TextButton("取消", on_click=self.on_back_click),
                ft.ElevatedButton(
                    "✅ 确认并导出封面", 
                    on_click=self._on_export_click, 
                    style=ft.ButtonStyle(color="white", bgcolor="blue")
                ),
            ], alignment=ft.MainAxisAlignment.END),
            padding=10,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border=ft.Border(top=ft.BorderSide(1, "outline_variant"))
        )
        
        self.content = ft.Column([
            ft.Container(content=self.header, padding=10),
            ft.Divider(),
            self.segment_row,
            ft.Divider(height=5, color="transparent"),
            self.density_row,
            ft.Divider(height=5, color="transparent"),
            self.status_text,
            self.grid,
            ft.Container(expand=True),
            self.bottom_bar
        ], expand=True)
        
        # 启动加载
        self.main_page.run_task(self._initialize_segments)

    # =========================================================
    # 1. 初始化分段（增强异常捕获）
    # =========================================================
    async def _initialize_segments(self):
        self.is_loading = True
        self.status_text.value = "正在读取视频信息..."
        self.main_page.update()
        
        try:
            duration = await self._get_video_duration()
            if duration <= 0:
                self.status_text.value = "❌ 无法获取视频时长，请确保 FFmpeg 已安装并加入系统 PATH。"
                self.is_loading = False
                self.main_page.update()
                return
            
            self.segments = VideoScanner.calculate_segments(duration)
            if not self.segments:
                self.status_text.value = "❌ 视频时长无效。"
                self.is_loading = False
                self.main_page.update()
                return
            
            # 构建按钮
            self._build_segment_chips()
            self._build_density_buttons()
            
            # 加载默认分段 A
            self.current_seg_idx = 0
            await self._load_current_segment()
            
        except Exception as e:
            print(f"[初始化异常]: {traceback.format_exc()}")
            self.status_text.value = f"❌ 加载失败：{str(e)}"
            self.is_loading = False
            self.main_page.update()
        finally:
            # 确保无论如何都解锁
            self.is_loading = False
            self.main_page.update()

    # =========================================================
    # 2. 构建 UI 按钮
    # =========================================================
    def _build_segment_chips(self):
        self.segment_row.controls.clear()
        self.segment_chips.clear()
        colors = ["blue", "green", "orange", "purple", "red"]
        for idx, seg in enumerate(self.segments):
            chip = ft.Chip(
                label=ft.Text(seg["name"], weight="bold"),
                selected=(idx == self.current_seg_idx),
                selected_color=colors[idx % len(colors)],
                on_click=lambda e, i=idx: self._on_segment_click(i),
                leading=ft.Icon(ft.Icons.FOLDER_OPEN if idx == self.current_seg_idx else ft.Icons.FOLDER),
            )
            self.segment_chips.append(chip)
            self.segment_row.controls.append(chip)
        self.main_page.update()

    def _build_density_buttons(self):
        self.density_row.controls.clear()
        self.density_buttons.clear()
        densities = [9, 12, 16, 25]
        for d in densities:
            btn = ft.TextButton(
                content=ft.Text(str(d), weight="bold"),
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.BLUE if d == self.density else ft.Colors.SURFACE,
                    color="white" if d == self.density else ft.Colors.ON_SURFACE,
                ),
                on_click=lambda e, val=d: self._on_density_click(val)
            )
            self.density_buttons.append(btn)
            self.density_row.controls.append(btn)
        self.main_page.update()

    # =========================================================
    # 3. 核心加载逻辑（增强异常捕获）
    # =========================================================
    async def _load_current_segment(self):
        if self.is_loading:
            return
        
        self.is_loading = True
        self.selected_index = None
        seg_name = self.segments[self.current_seg_idx]['name']
        self.status_text.value = f"正在生成 {self.density} 张候选截图 (分段 {seg_name})..."
        self.main_page.update()
        
        self.grid.controls.clear()
        self.main_page.update()
        
        try:
            seg = self.segments[self.current_seg_idx]
            start_time = seg["start"]
            end_time = seg["end"]
            duration = end_time - start_time
            
            if duration <= 0:
                self.status_text.value = f"❌ 分段 {seg_name} 时长为 0，无法截图。"
                self.is_loading = False
                self.main_page.update()
                return
            
            count = self.density
            if count == 1:
                timestamps = [start_time + duration / 2]
            else:
                step = duration / (count + 1)
                timestamps = [start_time + step * (i + 1) for i in range(count)]
            
            self.current_timestamps = timestamps
            
            # 并行截图
            tasks = [self._extract_frame(ts, idx, self.current_seg_idx) for idx, ts in enumerate(timestamps)]
            self.current_images = await asyncio.gather(*tasks)
            
            # 刷新网格
            self._refresh_grid()
            
            self.status_text.value = f"✅ 分段 {seg_name} 已加载 {self.density} 张候选，请点击选择。"
            
        except Exception as e:
            print(f"[加载分段异常]: {traceback.format_exc()}")
            self.status_text.value = f"❌ 加载失败：{str(e)}"
        finally:
            self.is_loading = False
            self.main_page.update()

    def _refresh_grid(self):
        self.grid.controls.clear()
        cols = int(math.sqrt(self.density))
        if self.density == 12:
            cols = 3
        self.grid.runs_count = cols
        
        for idx, img_path in enumerate(self.current_images):
            card = self._create_cover_card(idx, img_path, self.current_timestamps[idx])
            self.grid.controls.append(card)
        self.main_page.update()

    # =========================================================
    # 4. 事件回调
    # =========================================================
    def _on_segment_click(self, idx):
        if self.is_loading:
            return
        if idx == self.current_seg_idx:
            return
        
        self.current_seg_idx = idx
        for i, chip in enumerate(self.segment_chips):
            chip.selected = (i == idx)
            chip.leading = ft.Icon(ft.Icons.FOLDER_OPEN if i == idx else ft.Icons.FOLDER)
        self.main_page.update()
        self.main_page.run_task(self._load_current_segment)

    def _on_density_click(self, val):
        if self.is_loading:
            return
        if val == self.density:
            return
        
        self.density = val
        for btn in self.density_buttons:
            if int(btn.content.value) == val:
                btn.style.bgcolor = ft.Colors.BLUE
                btn.style.color = "white"
            else:
                btn.style.bgcolor = ft.Colors.SURFACE
                btn.style.color = ft.Colors.ON_SURFACE
        self.main_page.update()
        self.main_page.run_task(self._load_current_segment)

    def _on_cover_selected(self, index):
        if self.is_loading:
            return
        if self.selected_index == index:
            self.selected_index = None
        else:
            self.selected_index = index
        self._refresh_grid()

    # =========================================================
    # 5. 底层工具函数（增加超时和异常处理）
    # =========================================================
    async def _get_video_duration(self):
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", self.video_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode != 0:
                print(f"[ffprobe 错误码] {proc.returncode}, stderr: {stderr.decode()}")
                return -1
            duration_str = stdout.decode().strip()
            if not duration_str:
                return -1
            return float(duration_str)
        except asyncio.TimeoutError:
            print("[ffprobe 超时]")
            return -1
        except Exception as e:
            print(f"[ffprobe 异常] {e}")
            return -1

    async def _extract_frame(self, timestamp, index, seg_idx):
        temp_dir = os.environ.get("TEMP", ".")
        output_path = os.path.join(temp_dir, f"cover_seg{seg_idx}_{index}_{timestamp:.2f}.jpg")
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-ss", str(timestamp), "-i", self.video_path,
                "-vframes", "1", "-q:v", "2", output_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(proc.communicate(), timeout=60)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path
            else:
                return None
        except Exception as e:
            print(f"[ffmpeg 错误] {e}")
            return None

    # =========================================================
    # 6. 卡片创建（不变）
    # =========================================================
    def _create_cover_card(self, index, img_path, timestamp):
        border = ft.BorderSide(3, "blue") if index == self.selected_index else None
        if img_path and os.path.exists(img_path):
            try:
                abs_path = os.path.abspath(img_path).replace("\\", "/")
                image_content = ft.Image(src=abs_path, fit="cover", expand=True)
            except Exception as ex:
                print(f"[读取图片失败]: {ex}")
                image_content = ft.Container(
                    bgcolor="grey", expand=True,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Text("读取失败", color="white")
                )
        else:
            image_content = ft.Container(
                bgcolor="grey", expand=True,
                alignment=ft.Alignment(0, 0),
                content=ft.Text("截取失败", color="white")
            )
        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=image_content,
                    expand=True,
                    border_radius=8,
                    border=border
                ),
                ft.Text(f"{timestamp:.1f}s", size=12, color="grey", text_align=ft.TextAlign.CENTER)
            ], spacing=5),
            border_radius=10,
            padding=5,
            ink=True,
            on_click=lambda e, idx=index: self._on_cover_selected(idx)
        )

    # =========================================================
    # 7. 导出功能（不变）
    # =========================================================
    async def _on_export_click(self, e):
        if self.is_loading:
            return
        if self.selected_index is None:
            self.status_text.value = "⚠️ 请先点击选择一张封面！"
            self.status_text.color = "orange"
            self.main_page.update()
            return
        selected_img_path = self.current_images[self.selected_index]
        if not selected_img_path or not os.path.exists(selected_img_path):
            self.status_text.value = "⚠️ 选中的截图文件不存在！"
            self.status_text.color = "orange"
            self.main_page.update()
            return
        try:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            still_pic_dir = os.path.join(project_root, "StillPic")
            video_folder_name = os.path.splitext(self.video_name)[0]
            target_folder = os.path.join(still_pic_dir, video_folder_name)
            os.makedirs(target_folder, exist_ok=True)
        except Exception as ex:
            print(f"\n[创建文件夹失败]: {ex}")
            traceback.print_exc()
            self.status_text.value = f"❌ 创建文件夹失败，请查看终端日志！"
            self.status_text.color = "red"
            self.main_page.update()
            return
        timestamp = self.current_timestamps[self.selected_index]
        target_filename = f"cover_{timestamp:.1f}s.jpg"
        target_path = os.path.join(target_folder, target_filename)
        try:
            shutil.copy2(selected_img_path, target_path)
            self.status_text.value = f"✅ 成功导出: {target_filename} 到 {video_folder_name} 文件夹"
            self.status_text.color = "green"
            self.main_page.update()
            await asyncio.sleep(2)
            self.selected_index = None
            self._refresh_grid()
            self.status_text.value = f"分段 {self.segments[self.current_seg_idx]['name']} 已加载，可继续挑选。"
            self.status_text.color = "grey"
            self.main_page.update()
        except Exception as ex:
            print(f"\n[保存文件失败]: {ex}")
            traceback.print_exc()
            self.status_text.value = f"❌ 保存失败，请查看终端日志！"
            self.status_text.color = "red"
            self.main_page.update()

# endregion