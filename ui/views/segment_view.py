# region --- 分区视图：v0.10.25 修复截图超时 + Zoom 弹窗异步加载 ---
import os
import shutil
import asyncio
import math
import random
import traceback
import flet as ft
from src.video_scanner import VideoScanner
from ui.views.zoom_dialog import ZoomDialog

class SegmentView(ft.Container):
    def __init__(self, page: ft.Page, video_path: str, on_back_click):
        super().__init__(expand=True, padding=8)
        
        self.main_page = page
        self.video_path = video_path
        self.on_back_click = on_back_click
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
        self.running_tasks = []
        self.running_procs = []
        
        # ---------- UI 组件 ----------
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
            runs_count=3,
            max_extent=200,
            child_aspect_ratio=16/9,
            spacing=5,
            run_spacing=5,
            padding=5,
        )
        self.grid_container = ft.Container(
            content=self.grid,
            expand=True,
        )
        
        self.lock_btn = ft.ElevatedButton(
            "🔒 锁定/解锁",
            icon=ft.Icons.LOCK_OUTLINE,
            on_click=self._toggle_lock,
            disabled=True,
        )
        self.refresh_unlocked_btn = ft.ElevatedButton(
            "🔄 刷新未锁定",
            icon=ft.Icons.REFRESH,
            on_click=self._refresh_unlocked,
        )
        self.refresh_all_btn = ft.ElevatedButton(
            "🔄 全部重抽",
            icon=ft.Icons.REFRESH,
            on_click=self._refresh_all,
            style=ft.ButtonStyle(bgcolor=ft.Colors.AMBER_400),
        )
        
        self.bottom_bar = ft.Container(
            content=ft.Row([
                ft.TextButton("取消", on_click=self.on_back_click),
                ft.Row([
                    self.lock_btn,
                    self.refresh_unlocked_btn,
                    self.refresh_all_btn,
                ], spacing=10),
                ft.ElevatedButton(
                    "✅ 确认并导出封面", 
                    on_click=self._on_export_click, 
                    style=ft.ButtonStyle(color="white", bgcolor="blue")
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=6,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border=ft.Border(top=ft.BorderSide(1, "outline_variant"))
        )
        
        self.content = ft.Column([
            ft.Container(content=self.header, padding=4),
            ft.Divider(height=1),
            self.segment_row,
            ft.Divider(height=2, color="transparent"),
            self.density_row,
            ft.Divider(height=2, color="transparent"),
            self.status_text,
            self.grid_container,
            self.bottom_bar,
        ], expand=True, spacing=0)
        
        self.main_page.on_close = self._on_page_close
        self.main_page.run_task(self._initialize_segments)

    def _on_page_close(self):
        self.cancelled = True
        for task in self.running_tasks:
            if not task.done():
                task.cancel()
        for proc in self.running_procs:
            if proc.returncode is None:
                try:
                    proc.terminate()
                except:
                    pass
        self.running_tasks.clear()
        self.running_procs.clear()

    async def _initialize_segments(self):
        if self.cancelled:
            return
        self.status_text.value = "正在读取视频信息..."
        self.main_page.update()
        
        try:
            duration = await self._get_video_duration()
            if duration <= 0:
                self.status_text.value = "❌ 无法获取视频时长，请确保 FFmpeg 已安装并加入系统 PATH。"
                self.main_page.update()
                return
            
            self.segments = VideoScanner.calculate_segments(duration)
            if not self.segments:
                self.status_text.value = "❌ 视频时长无效。"
                self.main_page.update()
                return
            
            self._build_segment_chips()
            self._build_density_buttons()
            
            self.current_seg_idx = 0
            await self._load_current_segment(randomize=True)
            
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[初始化异常]: {traceback.format_exc()}")
            if not self.cancelled:
                try:
                    self.status_text.value = f"❌ 加载失败：{str(e)}"
                    self.main_page.update()
                except RuntimeError:
                    pass

    async def _get_video_duration(self):
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", self.video_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode != 0:
                print(f"[ffprobe 错误] {stderr.decode()}")
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

    async def _load_current_segment(self, randomize=True):
        if self.is_loading or self.cancelled:
            return
        
        self.is_loading = True
        self.selected_index = None
        self.locked_indices.clear()
        self.lock_btn.disabled = True
        
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
                base_timestamps = [start_time + step * (i + 1) for i in range(count)]
                
                if randomize:
                    offset_range = step * 0.4
                    timestamps = []
                    for t in base_timestamps:
                        offset = random.uniform(-offset_range, offset_range)
                        new_t = t + offset
                        new_t = max(start_time + 0.1, min(end_time - 0.1, new_t))
                        timestamps.append(new_t)
                else:
                    timestamps = base_timestamps
            
            self.current_timestamps = timestamps
            
            # 移除复杂参数，统一使用 -ss 前置（快速定位）
            tasks = []
            for idx, ts in enumerate(timestamps):
                tasks.append(self._extract_frame(ts, idx, self.current_seg_idx))
            
            self.status_text.value = f"正在生成 {self.density} 张截图 (大文件可能较慢)..."
            self.main_page.update()
            
            gather_task = asyncio.gather(*tasks)
            self.running_tasks.append(gather_task)
            self.current_images = await gather_task
            
            if self.cancelled:
                return
                
            success_count = sum(1 for img in self.current_images if img is not None)
            self._refresh_grid()
            if success_count == self.density:
                self.status_text.value = f"✅ 分段 {seg_name} 已生成 {success_count}/{self.density} 张截图，请点击选择或锁定。"
            else:
                self.status_text.value = f"⚠️ 分段 {seg_name} 仅生成 {success_count}/{self.density} 张截图（部分超时或失败），请尝试刷新未锁定。"
            
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if not self.cancelled:
                print(f"[加载分段异常]: {traceback.format_exc()}")
                try:
                    self.status_text.value = f"❌ 加载失败：{str(e)}"
                    self.main_page.update()
                except RuntimeError:
                    pass
        finally:
            self.is_loading = False
            self.running_tasks = [t for t in self.running_tasks if not t.done()]
            if not self.cancelled:
                try:
                    self.main_page.update()
                except RuntimeError:
                    pass

    async def _refresh_unlocked(self, e=None):
        if self.is_loading or self.cancelled:
            return
        
        if not self.locked_indices:
            await self._load_current_segment(randomize=True)
            return
        
        self.is_loading = True
        self.selected_index = None
        self.status_text.value = "正在刷新未锁定截图..."
        self.main_page.update()
        
        try:
            seg = self.segments[self.current_seg_idx]
            start_time = seg["start"]
            end_time = seg["end"]
            duration = end_time - start_time
            count = self.density
            
            new_timestamps = []
            locked_times = [self.current_timestamps[i] for i in self.locked_indices]
            
            for idx in range(count):
                if idx in self.locked_indices:
                    new_timestamps.append(self.current_timestamps[idx])
                else:
                    for _ in range(30):
                        t = start_time + random.random() * duration
                        too_close = any(abs(t - lt) < 1.0 for lt in locked_times)
                        if not too_close:
                            break
                    new_timestamps.append(t)
            
            self.current_timestamps = new_timestamps
            
            tasks = []
            for idx, ts in enumerate(new_timestamps):
                if idx in self.locked_indices:
                    tasks.append(asyncio.sleep(0, result=self.current_images[idx]))
                else:
                    tasks.append(self._extract_frame(ts, idx, self.current_seg_idx))
            
            gather_task = asyncio.gather(*tasks)
            self.running_tasks.append(gather_task)
            self.current_images = await gather_task
            
            if self.cancelled:
                return
                
            success_count = sum(1 for img in self.current_images if img is not None)
            self._refresh_grid()
            self.status_text.value = f"✅ 已刷新未锁定截图，{len(self.locked_indices)} 张保持锁定，成功 {success_count}/{self.density} 张。"
            
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if not self.cancelled:
                print(f"[刷新异常]: {traceback.format_exc()}")
                try:
                    self.status_text.value = f"❌ 刷新失败：{str(e)}"
                    self.main_page.update()
                except RuntimeError:
                    pass
        finally:
            self.is_loading = False
            self.running_tasks = [t for t in self.running_tasks if not t.done()]
            if not self.cancelled:
                try:
                    self.main_page.update()
                except RuntimeError:
                    pass

    async def _refresh_all(self, e=None):
        if self.is_loading or self.cancelled:
            return
        await self._load_current_segment(randomize=True)

    def _toggle_lock(self, e=None):
        if self.is_loading or self.cancelled:
            return
        if self.selected_index is None:
            self.status_text.value = "⚠️ 请先点击选择一张图片。"
            self.status_text.color = "orange"
            self.main_page.update()
            return
        
        idx = self.selected_index
        if idx in self.locked_indices:
            self.locked_indices.remove(idx)
            self.status_text.value = f"已解锁图片 {idx+1}。"
        else:
            self.locked_indices.add(idx)
            self.status_text.value = f"已锁定图片 {idx+1}。"
        
        self.selected_index = None
        self.lock_btn.disabled = True
        self._refresh_grid()
        self.main_page.update()

    def _refresh_grid(self):
        if self.cancelled:
            return
        self.grid.controls.clear()
        if self.density == 9:
            cols = 3
        elif self.density == 12:
            cols = 3
        elif self.density == 16:
            cols = 4
        elif self.density == 25:
            cols = 5
        else:
            cols = 3
        self.grid.runs_count = cols
        
        for idx, img_path in enumerate(self.current_images):
            timestamp = self.current_timestamps[idx]
            is_locked = idx in self.locked_indices
            card = self._create_cover_card(idx, img_path, timestamp, is_locked)
            self.grid.controls.append(card)
        try:
            self.main_page.update()
        except RuntimeError:
            pass

    # =========================================================
    # 创建卡片（双击事件已修复，移除无效参数）
    # =========================================================
    def _create_cover_card(self, index, img_path, timestamp, is_locked=False):
        if is_locked:
            border = ft.BorderSide(3, ft.Colors.AMBER)
        elif index == self.selected_index:
            border = ft.BorderSide(3, ft.Colors.BLUE)
        else:
            border = None
        
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
        
        if is_locked:
            lock_icon = ft.Icon(ft.Icons.LOCK, color=ft.Colors.AMBER, size=20)
            icon_container = ft.Container(
                content=lock_icon,
                alignment=ft.Alignment(1, -1),
            )
        else:
            icon_container = ft.Container()
        
        card_content = ft.Stack([
            ft.Container(
                content=image_content,
                expand=True,
                border_radius=8,
                border=border,
            ),
            icon_container,
        ], expand=True)
        
        return ft.GestureDetector(
            content=ft.Column([
                card_content,
                ft.Text(f"{timestamp:.1f}s", size=10, color="grey", text_align=ft.TextAlign.CENTER),
            ], spacing=1, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            on_tap=lambda e, idx=index: self._on_cover_selected(idx),
            on_double_tap=lambda e, idx=index: self._open_zoom(idx),
        )

    def _on_cover_selected(self, index):
        if self.is_loading or self.cancelled:
            return
        if self.selected_index == index:
            self.selected_index = None
            self.lock_btn.disabled = True
        else:
            self.selected_index = index
            self.lock_btn.disabled = False
        self._refresh_grid()

    # =========================================================
    # Zoom 精修入口（增加健壮性和日志）
    # =========================================================
    def _open_zoom(self, index):
        print(f"[Zoom] 双击触发，index={index}")
        if self.is_loading or self.cancelled:
            print("[Zoom] 被阻止（loading 或 cancelled）")
            return
        if index >= len(self.current_timestamps):
            print(f"[Zoom] 索引越界")
            return
        timestamp = self.current_timestamps[index]
        print(f"[Zoom] 时间戳: {timestamp}")
        try:
            zoom = ZoomDialog(
                page=self.main_page,
                video_path=self.video_path,
                timestamp=timestamp,
                extract_func=self._extract_frame
            )
            # 使用 run_task 启动异步显示，但内部已使用 create_task 不阻塞
            self.main_page.run_task(zoom.show)
            print("[Zoom] ZoomDialog.show() 已启动")
        except Exception as e:
            print(f"[Zoom] 异常: {e}")
            traceback.print_exc()

    def _on_segment_click(self, idx):
        if self.is_loading or self.cancelled:
            return
        if idx == self.current_seg_idx:
            return
        
        self.current_seg_idx = idx
        for i, chip in enumerate(self.segment_chips):
            chip.selected = (i == idx)
            chip.leading = ft.Icon(ft.Icons.FOLDER_OPEN if i == idx else ft.Icons.FOLDER)
        self.main_page.update()
        self.main_page.run_task(self._load_current_segment, randomize=True)

    def _on_density_click(self, val):
        if self.is_loading or self.cancelled:
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
        self.main_page.run_task(self._load_current_segment, randomize=True)

    # =========================================================
    # 底层工具函数（简化 FFmpeg 命令，增加超时至 90 秒）
    # =========================================================
    async def _extract_frame(self, timestamp, index, seg_idx):
        """
        提取单帧，统一使用 -ss 前置（快速定位），无额外分析参数。
        超时 90 秒，适应网络存储。
        """
        if self.cancelled:
            return None
        temp_dir = os.environ.get("TEMP", ".")
        output_path = os.path.join(temp_dir, f"cover_seg{seg_idx}_{index}_{timestamp:.2f}.jpg")
        try:
            # 统一使用 -ss 前置，去掉 -analyzeduration 和 -probesize
            cmd = [
                "ffmpeg",
                "-ss", str(timestamp),
                "-i", self.video_path,
                "-vframes", "1",
                "-q:v", "2",
                "-y",  # 覆盖已存在的文件
                output_path
            ]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            self.running_procs.append(proc)
            
            # 超时设为 90 秒
            timeout = 90
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            
            self.running_procs = [p for p in self.running_procs if p.returncode is None]
            
            if proc.returncode != 0:
                err_msg = stderr.decode()[:300]
                print(f"[ffmpeg 错误] 返回码 {proc.returncode}, stderr: {err_msg}")
                return None
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path
            else:
                print(f"[ffmpeg 警告] 输出文件不存在或大小为0: {output_path}")
                return None
        except asyncio.TimeoutError:
            print(f"[ffmpeg 超时] 时间戳 {timestamp}s (已等待{timeout}秒)")
            return None
        except asyncio.CancelledError:
            if proc in self.running_procs:
                try:
                    proc.terminate()
                except:
                    pass
            return None
        except Exception as e:
            print(f"[ffmpeg 异常] {e}")
            return None

    # =========================================================
    # 导出功能（不变）
    # =========================================================
    async def _on_export_click(self, e):
        if self.is_loading or self.cancelled:
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
            self.lock_btn.disabled = True
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