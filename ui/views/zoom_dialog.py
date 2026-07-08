# region --- Zoom 精修弹窗 v12 (修复 Flet 0.85.3 兼容性) ---
import os
import shutil
import asyncio
import flet as ft

class ZoomDialog:
    def __init__(self, page: ft.Page, video_path: str, timestamp: float, extract_func):
        self.page = page
        self.video_path = video_path
        self.original_timestamp = timestamp
        self.extract_func = extract_func
        self.level = 1
        self.images = []
        self.timestamps = []
        self.selected_index = None
        self.overlay_container = None
        self.grid = None
        self.status_text = None
        self.level_text = None
        self.upgrade_btn = None
        self.export_btn = None
        self.dialog_card = None

    async def show(self):
        print("[ZoomDialog] show() 被调用")
        
        # 构建全屏遮罩 - 使用 ft.Alignment(0, 0) 代替 ft.alignment.center
        self.overlay_container = ft.Container(
            content=self._build_dialog_card(),
            expand=True,
            bgcolor=ft.Colors.with_opacity(0.5, ft.Colors.BLACK),
            alignment=ft.Alignment(0, 0),  # 居中
            visible=True,
        )
        
        self.page.overlay.append(self.overlay_container)
        self.page.update()
        print("[ZoomDialog] 全屏遮罩已添加到页面")
        
        asyncio.create_task(self._load_level(1))

    def _build_dialog_card(self):
        """构建对话框卡片"""
        self.level_text = ft.Text("层级 L1 (±2s)", size=16, weight="bold")
        self.status_text = ft.Text("正在加载...", size=12, color="grey")
        self.grid = ft.GridView(
            expand=True,
            runs_count=3,
            max_extent=180,
            child_aspect_ratio=16/9,
            spacing=5,
            run_spacing=5,
            padding=5,
        )
        self.upgrade_btn = ft.ElevatedButton("🔄 更精细 (L2)", on_click=self._upgrade_level_click)
        self.export_btn = ft.ElevatedButton("✅ 导出选中", on_click=self._export_click)
        
        btn_row = ft.Row([
            self.upgrade_btn,
            self.export_btn,
            ft.TextButton("关闭", on_click=self._close),
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=10)
        
        self.dialog_card = ft.Container(
            content=ft.Column([
                self.level_text,
                self.status_text,
                ft.Container(self.grid, expand=True, height=350),
                btn_row,
            ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=750,
            height=520,
            bgcolor=ft.Colors.WHITE,
            border_radius=12,
            padding=20,
            shadow=ft.BoxShadow(
                spread_radius=10,
                blur_radius=30,
                color=ft.Colors.with_opacity(0.3, ft.Colors.BLACK),
            ),
        )
        return self.dialog_card

    def _upgrade_level_click(self, e):
        if self.level == 1:
            asyncio.create_task(self._load_level(2))
        else:
            self.status_text.value = "⚠️ 已达到最大层级 (L2)"
            self.page.update()

    def _export_click(self, e):
        asyncio.create_task(self._export_selected())

    async def _load_level(self, level):
        print(f"[ZoomDialog] 加载层级 L{level}")
        self.level = level
        self.selected_index = None
        self.level_text.value = f"层级 L{level} ({'±2s' if level==1 else '±8s'})"
        self.status_text.value = f"正在生成 {9 if level==1 else 12} 张缩略图..."
        self.grid.controls.clear()
        self.page.update()

        offset = 2 if level == 1 else 8
        center = self.original_timestamp
        count = 9 if level == 1 else 12
        start = center - offset
        end = center + offset
        duration = end - start
        if duration <= 0:
            self.status_text.value = "⚠️ 时间窗口无效，请重试。"
            self.page.update()
            return

        if count == 1:
            ts_list = [center]
        else:
            step = duration / (count + 1)
            ts_list = [start + step * (i + 1) for i in range(count)]
        self.timestamps = ts_list

        tasks = []
        for idx, ts in enumerate(ts_list):
            tasks.append(self.extract_func(ts, idx, -1))
        self.images = await asyncio.gather(*tasks)

        self._refresh_grid()
        success = sum(1 for img in self.images if img is not None)
        self.status_text.value = f"已生成 {success}/{count} 张，点击选择或升级层级。"
        self.page.update()

    def _refresh_grid(self):
        self.grid.controls.clear()
        count = len(self.timestamps)
        cols = 3 if count <= 9 else 4
        self.grid.runs_count = cols

        for idx, img_path in enumerate(self.images):
            timestamp = self.timestamps[idx]
            is_sel = (idx == self.selected_index)
            card = self._create_card(idx, img_path, timestamp, is_sel)
            self.grid.controls.append(card)
        self.page.update()

    def _create_card(self, index, img_path, timestamp, selected):
        border = ft.BorderSide(3, ft.Colors.BLUE) if selected else None
        if img_path and os.path.exists(img_path):
            try:
                abs_path = os.path.abspath(img_path).replace("\\", "/")
                image_content = ft.Image(src=abs_path, fit="cover", expand=True)
            except:
                image_content = ft.Container(
                    bgcolor="grey", 
                    expand=True,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Text("读取失败", color="white")
                )
        else:
            image_content = ft.Container(
                bgcolor="grey", 
                expand=True,
                alignment=ft.Alignment(0, 0),
                content=ft.Text("截取失败", color="white")
            )
        return ft.GestureDetector(
            content=ft.Column([
                ft.Container(
                    content=image_content,
                    expand=True,
                    border_radius=8,
                    border=border,
                ),
                ft.Text(f"{timestamp:.1f}s", size=10, color="grey", text_align=ft.TextAlign.CENTER),
            ], spacing=1, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            on_tap=lambda e, idx=index: self._select(idx),
        )

    def _select(self, index):
        self.selected_index = index
        self._refresh_grid()
        self.status_text.value = f"已选中 {self.timestamps[index]:.1f}s"
        self.page.update()

    async def _export_selected(self):
        if self.selected_index is None:
            self.status_text.value = "⚠️ 请先点击选择一张图片。"
            self.page.update()
            return
        img_path = self.images[self.selected_index]
        if not img_path or not os.path.exists(img_path):
            self.status_text.value = "⚠️ 选中的截图文件不存在！"
            self.page.update()
            return
        try:
            video_name = os.path.basename(self.video_path)
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            still_pic_dir = os.path.join(project_root, "StillPic")
            video_folder_name = os.path.splitext(video_name)[0]
            target_folder = os.path.join(still_pic_dir, video_folder_name)
            os.makedirs(target_folder, exist_ok=True)
            timestamp = self.timestamps[self.selected_index]
            target_filename = f"zoom_{timestamp:.1f}s.jpg"
            target_path = os.path.join(target_folder, target_filename)
            shutil.copy2(img_path, target_path)
            self.status_text.value = f"✅ 导出成功: {target_filename}"
            self.status_text.color = "green"
            self.page.update()
        except Exception as ex:
            self.status_text.value = f"❌ 导出失败: {str(ex)}"
            self.page.update()

    def _close(self, e):
        """关闭：直接移除遮罩"""
        print("[ZoomDialog] _close() 被调用，移除遮罩")
        if self.overlay_container is None:
            print("[ZoomDialog] overlay_container 为空")
            return
        
        if self.overlay_container in self.page.overlay:
            self.page.overlay.remove(self.overlay_container)
            self.page.update()
            print("[ZoomDialog] 遮罩已移除")
        else:
            print("[ZoomDialog] 警告：遮罩不在 overlay 中")
            self.page.overlay.clear()
            self.page.update()
            print("[ZoomDialog] 已强制清空 overlay")
# endregion