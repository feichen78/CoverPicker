RuntimeError 排查日志 (miniPROGRESS.md)
目的：定位 main 分支快速切换视频时出现的 RuntimeError: Cannot enter into task... 问题

当前状态：⏳ 已定位到 segment_view.py + segment_controller.py 组合

排查过程
步骤	操作	结果	结论
1	完全恢复 v2.5.2	✅ 无报错	v2.5.2 是稳定基准
2	逐文件恢复 v3.0.1 改动	见下	见下
2a	恢复 favorites_dialog.py	❌ 报错仍在	收藏夹不是原因
2b	恢复 main.py	❌ 报错仍在	main.py 不是原因
2c	恢复 image_labels.py	❌ 报错仍在	image_labels.py 不是原因
2d	恢复 segment_controller.py	❌ 报错仍在，但出现新错误 get_video_resolution 不存在	依赖 segment_view.py
2e	恢复 segment_view.py + segment_controller.py 一起	✅ RuntimeError 消失	问题在这两个文件中
当前结论
问题范围：ui/views/segment_view.py + src/controllers/segment_controller.py 的 v3.0.1 改动

具体改动：

segment_controller.py：新增 video_resolution 属性、get_video_resolution() 方法

segment_view.py：信息区从 4 行改为 5 行，info_path 从 QLabel 改为 QTextEdit，行间距 2→6px，视频列表拉伸因子 2→3

待定位的精确原因
需要进一步细分 segment_view.py 的改动，逐个恢复以下部分来定位：

信息区行数（4→5 行）

info_path 类型（QLabel → QTextEdit）

行间距（2→6px）

拉伸因子（2→3）

分辨率相关调用

下一步计划
□ 在 v3.0.1 代码基础上，逐个还原 segment_view.py 信息区的改动
□ 每还原一个改动，测试一次快速切换视频
□ 精确定位是哪一行/哪个改动触发了 RuntimeError
□ 修复后验证
备注
v2.5.2 是完全稳定的基准版本

所有 v3.0.1 功能（版本号、信息区5行、分辨率、自适应缩放）均已实现

RuntimeError 不影响程序运行（不崩溃，截图正常），但控制台有报错

最后更新：2026-07-26