# region --- Flet App 路由控制器 (诊断模式) ---
import flet as ft

class CoverPickerApp:
    """
    管理整个 Flet 应用的路由和全局状态。
    """
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "CoverPicker - 诊断模式"
        self.page.window_width = 1000
        self.page.window_height = 700
        self.page.padding = 20
        
        # 【诊断核心】：强制设置背景色为浅蓝色，看窗口是否有颜色
        self.page.bgcolor = ft.Colors.LIGHT_BLUE_50 
        
        # 绑定路由变化事件
        self.page.on_route_change = self._route_change
        
        # 【诊断核心】：手动触发一次初始路由
        self.page.go("/")  

    def _route_change(self, e):
        """路由变化时的处理函数"""
        print(f"[路由日志] 当前路由变更为: {self.page.route}")
        
        # 清空现有视图
        self.page.views.clear()
        
        # 【诊断核心】：不再调用 HomeView，直接放一个最基础的红色方块
        self.page.views.append(
            ft.View(
                route="/",
                bgcolor=ft.Colors.SURFACE,
                controls=[
                    ft.Text("如果你能看到这行红字，说明路由系统已打通！", size=30, color="red", weight="bold"),
                    ft.ElevatedButton("测试按钮", bgcolor="green", color="white", on_click=lambda e: print("按钮被点击了"))
                ]
            )
        )
        
        # 强制刷新页面
        self.page.update()

# endregion