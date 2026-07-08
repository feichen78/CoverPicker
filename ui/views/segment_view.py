# region --- 分区视图 v5.2 (修复属性冲突) ---
import os
import asyncio
import random
import shutil
import traceback
import flet as ft
from src.video_scanner import VideoScanner

class SegmentView(ft.Container):
    def __init__(self, page: ft.Page, video_path: str, on_back_click, video_list=None):
        super().__init__(expand=True, padding=0, bgcolor=ft.Colors.SURFACE)
        
        # 使用 main_page 避免与父类属性冲突
        self.main_page = page
        self.video_path = video_path
        self.on_back_click = on_back_click
        self.video_list = video_list or []
        self.video_name = os.path.basename(video_path)
        
        self.is_loading = False
        self.selected_index = None
        self.current_seg_idx = 0
        self.density = 9
        self.segments = []
        self.current_images = []
        self.current_timestamps = []
        self.locked_indices = set()
        self.cancelled = False
        
        self._build_ui()
        self.main_page.run_task(self._initialize_segments)

    def _build_ui(self):
        # ========== 顶部行 ==========
        self.back_btn = ft.TextButton("← 返回", on_click=self.on_back_click, style=ft.ButtonStyle(text_style=ft.TextStyle(size=14)))
        self.video_title = ft.Text(self.video_name, size=14, weight="bold", max_lines=1, expand=True)
        
        # 密度按钮
        self.density_btns = []
        density_row = ft.Row(spacing=2, alignment=ft.MainAxisAlignment.END)
        density_row.controls.append(ft.Text("网格:", size=11, color="grey"))
        for d in [9, 12, 16, 25]:
            btn = ft.TextButton(
                content=ft.Text(str(d), size=10, weight="bold"),
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.BLUE if d == self.density else ft.Colors.SURFACE,
                    color="white" if d == self.density else ft.Colors.ON_SURFACE,
                    padding=(8, 2, 8, 2),
                ),
                on_click=lambda e, val=d: self._on_density_click(val),
                height=26,
            )
            self.density_btns.append(btn)
            density_row.controls.append(btn)
        
        header_row = ft.Row([
            self.back_btn,
            self.video_title,
            density_row,
        ], alignment=ft.MainAxisAlignment.START, spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        
        # ========== 分段标签 ==========
        self.segment_chips = []
        self.segment_row = ft.Row(spacing=6, alignment=ft.MainAxisAlignment.CENTER)
        for name in ["A", "B", "C", "D", "E"]:
            chip = ft.Chip(
                label=ft.Text(name, size=12, weight="bold"),
                selected=(name == "A"),
                selected_color="#2196F3",
                on_click=lambda e, n=name: self._on_segment_click(n),
                elevation=0,
                height=28,
            )
            self.segment_chips.append(chip)
            self.segment_row.controls.append(chip)
        
        # ========== GridView ==========
        self.grid = ft.GridView(
            expand=True,
            runs_count=3,
            max_extent=250,
            child_aspect_ratio=16/9,
            spacing=8,
            run_spacing=8,
            padding=12,
        )
        self.grid_container = ft.Container(
            content=self.grid,
            expand=True,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            border_radius=8,
        )
        
        # ========== 状态栏 ==========
        self.status_text = ft.Text("加载中...", size=11, color="grey")
        self.progress = ft.ProgressRing(width=16, height=16, stroke_width=2)
        
        status_row = ft.Row([
            self.status_text,
            self.progress,
        ], spacing=8, alignment=ft.MainAxisAlignment.CENTER)
        
        # ========== 底部操作栏 ==========
        self.select_info = ft.Text("", size=11, color="grey")
        
        self.lock_btn = ft.IconButton(
            ft.Icons.LOCK_OUTLINE, icon_size=20, 
            on_click=self._toggle_lock, disabled=True,
        )
        self.refresh_btn = ft.IconButton(
            ft.Icons.REFRESH, icon_size=20,
            on_click=self._refresh_unlocked,
        )
        self.redraw_btn = ft.IconButton(
            ft.Icons.REFRESH, icon_size=20,
            on_click=self._refresh_all,
            style=ft.ButtonStyle(color=ft.Colors.AMBER_400),
        )
        self.export_btn = ft.IconButton(
            ft.Icons.FILE_DOWNLOAD, icon_size=20,
            on_click=self._on_export,
            style=ft.ButtonStyle(color=ft.Colors.BLUE),
        )
        
        bottom_row = ft.Row([
            self.select_info,
            ft.Container(expand=True),
            self.lock_btn,
            self.refresh_btn,
            self.redraw_btn,
            self.export_btn,
        ], alignment=ft.MainAxisAlignment.START, spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        
        # ========== 组装 ==========
        self.content = ft.Column([
            ft.Container(content=header_row, padding=(8, 4, 8, 4), height=40),
            ft.Divider(height=1),
            ft.Container(content=self.segment_row, padding=(4, 4, 4, 4), height=38),
            ft.Divider(height=1),
            self.grid_container,
            ft.Container(content=status_row, padding=(4, 2, 4, 2), height=28),
            ft.Divider(height=1),
            ft.Container(content=bottom_row, padding=(8, 2, 8, 4), height=40),
        ], expand=True, spacing=0)

    def _get_cols(self):
        if self.density == 9:
            return 3
        elif self.density == 12:
            return 3
        elif self.density == 16:
            return 4
        elif self.density == 25:
            return 5
        return 3

    # ========== 核心功能 ==========

    async def _initialize_segments(self):
        if self.cancelled:
            return
        self.status_text.value = "读取视频信息..."
        self.progress.visible = True
        self.main_page.update()
        
        try:
            duration = await self._get_video_duration()
            if duration <= 0:
                self.status_text.value = "无法获取视频时长"
                self.progress.visible = False
                self.main_page.update()
                return
            
            self.segments = VideoScanner.calculate_segments(duration)
            if not self.segments:
                self.status_text.value = "无效时长"
                self.progress.visible = False
                self.main_page.update()
                return
            
            self._update_segment_chips()
            await self._load_current_segment()
            
        except Exception as e:
            print(f"[初始化异常]: {traceback.format_exc()}")
            self.status_text.value = "加载失败"
            self.progress.visible = False
            self.main_page.update()

    async def _get_video_duration(self):
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", self.video_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode != 0:
                return -1
            return float(stdout.decode().strip())
        except:
            return -1

    def _update_segment_chips(self):
        for i, chip in enumerate(self.segment_chips):
            if i < len(self.segments):
                chip.label = ft.Text(self.segments[i]["name"], size=12, weight="bold")
                chip.selected = (i == self.current_seg_idx)
                chip.visible = True
            else:
                chip.visible = False
        self.main_page.update()

    async def _load_current_segment(self, randomize=True):
        if self.is_loading or self.cancelled:
            return
        
        self.is_loading = True
        self.selected_index = None
        self.locked_indices.clear()
        self.lock_btn.disabled = True
        
        seg_name = self.segments[self.current_seg_idx]['name']
        self.status_text.value = f"{seg_name} {self.density}张 生成中..."
        self.progress.visible = True
        self.main_page.update()
        
        try:
            seg = self.segments[self.current_seg_idx]
            start = seg["start"]
            end = seg["end"]
            duration = end - start
            
            if duration <= 0:
                self.status_text.value = "时长为0"
                self.progress.visible = False
                self.is_loading = False
                self.main_page.update()
                return
            
            count = self.density
            if count == 1:
                timestamps = [start + duration / 2]
            else:
                step = duration / (count + 1)
                base = [start + step * (i + 1) for i in range(count)]
                if randomize:
                    offset_range = step * 0.4
                    timestamps = []
                    for t in base:
                        offset = random.uniform(-offset_range, offset_range)
                        new_t = t + offset
                        new_t = max(start + 0.1, min(end - 0.1, new_t))
                        timestamps.append(new_t)
                else:
                    timestamps = base
            
            self.current_timestamps = timestamps
            
            tasks = [self._extract_frame(ts, idx) for idx, ts in enumerate(timestamps)]
            self.current_images = await asyncio.gather(*tasks)
            
            if self.cancelled:
                return
            
            self._refresh_grid()
            
            success = sum(1 for img in self.current_images if img is not None)
            self.status_text.value = f"{seg_name} {success}/{self.density} ✓"
            self.progress.visible = False
            
        except Exception as e:
            print(f"[加载异常]: {traceback.format_exc()}")
            self.status_text.value = "加载失败"
            self.progress.visible = False
        finally:
            self.is_loading = False
            self.main_page.update()

    async def _extract_frame(self, timestamp, index):
        if self.cancelled:
            return None
        temp_dir = os.environ.get("TEMP", ".")
        output_path = os.path.join(temp_dir, f"cover_{self.current_seg_idx}_{index}_{timestamp:.2f}.jpg")
        try:
            cmd = [
                "ffmpeg",
                "-ss", str(timestamp),
                "-i", self.video_path,
                "-vframes", "1",
                "-q:v", "2",
                "-y",
                output_path
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(proc.communicate(), timeout=90)
            if proc.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path
            return None
        except:
            return None

    def _refresh_grid(self):
        self.grid.controls.clear()
        
        cols = self._get_cols()
        self.grid.runs_count = cols
        
        for idx, img_path in enumerate(self.current_images):
            ts = self.current_timestamps[idx]
            is_locked = idx in self.locked_indices
            card = self._create_card(idx, img_path, ts, is_locked)
            self.grid.controls.append(card)
        
        self.main_page.update()

    def _create_card(self, index, img_path, timestamp, is_locked):
        if is_locked:
            border = ft.BorderSide(3, ft.Colors.AMBER)
        elif index == self.selected_index:
            border = ft.BorderSide(3, ft.Colors.BLUE)
        else:
            border = None
        
        if img_path and os.path.exists(img_path):
            try:
                abs_path = os.path.abspath(img_path).replace("\\", "/")
                image = ft.Image(src=abs_path, fit="cover", expand=True)
            except:
                image = ft.Container(bgcolor="grey", expand=True, alignment=ft.Alignment(0,0), 
                                     content=ft.Text("✗", color="white"))
        else:
            image = ft.Container(bgcolor="grey", expand=True, alignment=ft.Alignment(0,0),
                                 content=ft.Text("✗", color="white"))
        
        idx_badge = ft.Container(
            content=ft.Text(f"#{index+1}", size=9, color="white", weight="bold"),
            bgcolor=ft.Colors.with_opacity(0.6, ft.Colors.BLACK),
            border_radius=3,
            padding=(4, 1, 4, 1),
            alignment=ft.Alignment(-1, -1),
        )
        
        lock_icon = ft.Icon(ft.Icons.LOCK, color=ft.Colors.AMBER, size=14) if is_locked else ft.Container()
        lock_container = ft.Container(content=lock_icon, alignment=ft.Alignment(1, -1))
        
        time_text = self._format_time(timestamp)
        time_badge = ft.Container(
            content=ft.Text(time_text, size=8, color="white"),
            bgcolor=ft.Colors.with_opacity(0.5, ft.Colors.BLACK),
            border_radius=2,
            padding=(4, 1, 4, 1),
            alignment=ft.Alignment(0, 1),
        )
        
        return ft.GestureDetector(
            content=ft.Stack([
                ft.Container(
                    content=image,
                    expand=True,
                    border_radius=6,
                    border=border,
                ),
                idx_badge,
                lock_container,
                time_badge,
            ], expand=True),
            on_tap=lambda e, i=index: self._on_card_click(i),
        )

    def _format_time(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _on_card_click(self, index):
        if self.is_loading:
            return
        if self.selected_index == index:
            self.selected_index = None
            self.lock_btn.disabled = True
        else:
            self.selected_index = index
            self.lock_btn.disabled = False
        
        if self.selected_index is not None:
            ts = self.current_timestamps[self.selected_index]
            self.select_info.value = f"选择: #{self.selected_index+1} {self._format_time(ts)}"
        else:
            self.select_info.value = ""
        
        self._refresh_grid()

    def _toggle_lock(self, e):
        if self.selected_index is None:
            return
        idx = self.selected_index
        if idx in self.locked_indices:
            self.locked_indices.remove(idx)
        else:
            self.locked_indices.add(idx)
        self.selected_index = None
        self.lock_btn.disabled = True
        self._refresh_grid()
        self.main_page.update()

    async def _refresh_unlocked(self, e):
        if self.is_loading:
            return
        await self._load_current_segment(randomize=True)

    async def _refresh_all(self, e):
        if self.is_loading:
            return
        self.locked_indices.clear()
        await self._load_current_segment(randomize=True)

    async def _on_export(self, e):
        if self.selected_index is None:
            self.status_text.value = "请先选择一张图片"
            self.main_page.update()
            return
        img_path = self.current_images[self.selected_index]
        if not img_path or not os.path.exists(img_path):
            self.status_text.value = "文件不存在"
            self.main_page.update()
            return
        
        try:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            still_pic_dir = os.path.join(project_root, "StillPic")
            video_folder = os.path.join(still_pic_dir, os.path.splitext(self.video_name)[0])
            os.makedirs(video_folder, exist_ok=True)
            ts = self.current_timestamps[self.selected_index]
            target = os.path.join(video_folder, f"cover_{ts:.1f}s.jpg")
            shutil.copy2(img_path, target)
            self.status_text.value = f"导出: cover_{ts:.1f}s.jpg"
            self.main_page.update()
        except Exception as ex:
            print(f"[导出失败]: {ex}")
            self.status_text.value = "导出失败"
            self.main_page.update()

    def _on_segment_click(self, name):
        if self.is_loading:
            return
        for i, seg in enumerate(self.segments):
            if seg["name"] == name:
                self.current_seg_idx = i
                break
        self._update_segment_chips()
        self.main_page.run_task(self._load_current_segment, True)

    def _on_density_click(self, val):
        if self.is_loading or val == self.density:
            return
        self.density = val
        for btn in self.density_btns:
            if int(btn.content.value) == val:
                btn.style.bgcolor = ft.Colors.BLUE
                btn.style.color = "white"
            else:
                btn.style.bgcolor = ft.Colors.SURFACE
                btn.style.color = ft.Colors.ON_SURFACE
        self.main_page.update()
        self.main_page.run_task(self._load_current_segment, True)
# endregion