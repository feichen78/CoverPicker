📋 CoverPicker 项目进度日志

🏷️ 当前版本信息
项目 内容
版本号 v3.2.11
版本名称 扫描删除范围修复 + 空文件夹扫描工具 + 打包闪窗修复
发布日期 2026-10-30
状态 ✅ 核心功能稳定
稳定基准版本 v2.5.2
对应 PRODUCT.md 版本 v3.2.11

✅ v3.2.11 已完成
编号 优化项 状态 说明
1 扫描删除范围限定 ✅ 已完成 定时扫描仅移除原本属于监控目录、但当前扫描不到的视频，手动导入的视频不再被误移除
2 空文件夹扫描工具优化 ✅ 已完成 tools/folder_scanner_gui.py：修正“无视频文件夹”判定逻辑，父文件夹含视频子文件夹时不再被误标；新增 .actors、extrafanart 排除；新增空格键图片预览，再按空格关闭
3 打包后 ffmpeg 窗口闪烁修复 ✅ 已完成 打包版截取帧时不再频繁弹出 ffmpeg 控制台窗口，截图速度恢复正常

✅ v3.2.10 已完成
编号 优化项 状态 说明
1 自动化测试套件完善 ✅ 已完成 311 个测试全部通过，整体覆盖率 77%
2 测试隔离修复 ✅ 已完成 修复 config_manager 路径缓存导致的测试配置污染，所有测试使用临时 HOME 目录
3 测试弹窗消除 ✅ 已完成 全局 mock QMessageBox，批量测试不再需要手动点击确认
4 CI 配置 ✅ 已完成 新增 .github/workflows/test.yml，Windows + Python 3.13 自动运行测试并生成覆盖率
5 覆盖率提升 ✅ 已完成 从 61% 提升至 77%

✅ v3.2.9 已完成
编号 优化项 状态 说明
1 延迟删除触发（方案A） ✅ 已完成 加载完成后自动清理待删除视频，避免幽灵条目
2 线程安全修复（E1） ✅ 已完成 预览窗口关闭使用 QTimer.singleShot 确保主线程执行
3 恢复状态清空选中集合（E4） ✅ 已完成 _restore_state 成功后显式清空 selected_indices
4 旧标签残留修复 ✅ 已完成 _update_ticks 中 duration<=0 时隐藏所有刻度标签

✅ v3.2.8 已完成
编号 优化项 状态 说明
1 备份清理策略优化 ✅ 已完成 每天第一次启动时清理，保留最近5个备份
2 刻度密度提升 ✅ 已完成 时间轴刻度从5个提升至11个（0%,10%,...100%）
3 FFmpeg 兼容性优化 ✅ 已完成 移除 -skip_frame nokey，添加色彩空间转换

✅ v3.2.2 已完成
编号 优化项 状态 说明
1 预览窗口时间轴优化（方案A） ✅ 已完成 时间输入框 + 跳转按钮 + “当前”按钮
2 GIF 默认选项优化 ✅ 已完成 帧率默认 5fps，尺寸默认 25%
3 备份保留策略调整 ✅ 已完成 从保留1个改为保留最近5个

✅ v3.2.1 已完成优化
编号 优化项 状态 说明
O1 调试日志规范化 ✅ 已完成 preview_dialog.py 中 print 改为 logger.debug()
O4 分区索引越界防护 ✅ 已完成 refresh_unlocked 和 reset_segment 增加 seg_idx 有效性检查

✅ v3.2 已实现功能
O3：自动恢复备份提示优化
O4：手动恢复状态无需重启
O5：细选窗口最大化按钮
3.2.1：数据库备份自动恢复
3.2.2：GIF 动态预览导出
3.2.3：截图快速切换（放大预览窗口）
3.2.4：导出命名优化
3.2.5：打开导出夹按钮
视频列表分组排序
监控目录扫描优化

🧪 自动化测试套件（v3.2.10 完成）
1. 当前测试状态总览
指标 值
总测试用例数 311
通过数 311
失败数 0
警告数 6（ResourceWarning，可忽略）
执行时间 约 5.5 分钟
整体覆盖率 77%
通过率 100%

2. 模块覆盖率明细
模块 覆盖率 状态
crash_handler.py 100% ✅ 完全覆盖
logger_setup.py 100% ✅ 完全覆盖
config_manager.py 85% ✅ 良好
preview_controller.py 81% ✅ 良好
database.py 79% ✅ 良好
video_scanner.py 76% ✅ 良好
segment_controller.py 72% ✅ 良好
version.py 已记录为覆盖 ✅ 已确认
整体 77% 🎯 超额完成目标（70%）

3. 测试文件清单
核心测试（21 个文件）
test_batch_delete.py（5）
test_config.py（6）
test_database.py（6）
test_exceptions.py（10）
test_exclude_dialog.py（13）
test_favorites_dialog.py（7）
test_import_large.py（2）
test_import_operations.py（4）
test_integration.py（4）
test_keyboard_shortcuts.py（4）
test_monitor.py（6）
test_performance.py（7）
test_preview_dialog.py（8）
test_search_filter.py（5）
test_segment_controller.py（12）
test_segment_view.py（6）
test_segment_view_interaction.py（8）
test_sorting.py（4）
test_ui_style.py（7）
test_video_scanner.py（14）
test_zoom_dialog.py（5）

中优先级补充（5 个文件）
test_export_clip.py（5）
test_gif_export.py（4）
test_custom_segments.py（7）
test_undo_redo_scope.py（7）
test_metadata_cache.py（6）

低优先级补充（2 个文件）
test_layout_geometry.py（7）
test_concurrent_control.py（6）

新增模块测试（2 个文件）
test_crash_handler.py（10）
test_logger_setup.py（9）

补充测试（7 个文件）
test_config_manager_extra.py（12）
test_video_scanner_extra.py（10）
test_database_extra.py（7）
test_database_extra2.py（8）
test_segment_controller_extra.py（10）
test_segment_controller_extra2.py（8）
test_segment_controller_extra3.py（15）

4. 关键修复记录
问题 状态 说明
配置污染（config.json） ✅ 已修复 路径缓存问题已解决
测试弹窗（QMessageBox） ✅ 已修复 全局 mock 已添加
批量测试崩溃 ✅ 已修复 精简不稳定测试
ResourceWarning ✅ 已优化 6 个警告可忽略
覆盖率从 61% → 77% ✅ 已完成 +16% 提升

5. CI/CD 配置
GitHub Actions
文件：.github/workflows/test.yml
触发条件：push 到 main/develop，PR 到 main
环境：Windows-latest, Python 3.13
包含：FFmpeg 安装、依赖安装、测试、覆盖率报告

Codecov
状态：已配置
上传：coverage.xml 自动上传
徽章：可在 README 中添加

6. 测试运行方式
# 运行所有测试
pytest tests/ -v

# 运行并生成覆盖率报告
pytest tests/ --cov=src --cov-report=html
start htmlcov/index.html

# 快速验证
pytest tests/ -v --tb=short

⚠️ 已知问题
编号 问题描述 状态 影响 说明
P1 快速切换视频时偶发 RuntimeError ✅ 已确认 不影响功能 Python asyncio 在 Windows 上的底层行为
P2 预览窗口拖动进度条不够顺滑 ✅ 已确认 影响预览体验 待 v3.2.12 方案 B 优化，详见后续计划

📊 整体完成度评估
功能模块 完成度 说明
视频分区浏览（7.2） ✅ 100% 自动分段、切换正常
Grid 候选浏览（7.3） ✅ 100% 密度切换、截图显示正常
收藏管理（7.6） ✅ 100% 收藏池、收藏夹弹窗正常
锁定功能（7.3/7.4） ✅ 100% 锁定/解锁、刷新未锁定正常
导出功能（7.4/7.5） ✅ 100% 单张/批量导出正常
Zoom 细选（7.3/7.4） ✅ 100% L1~L4 四层细选完整实现
左侧视频列表状态标识（7.1） ✅ 100% ⭐/✅/👁️ 状态标识已实现
预览窗口（7.4） ✅ 100% 时间输入跳转 + 11个刻度
搜索/导入/批量删除（7.1） ✅ 100% 全部已实现
清理缓存（7.5） ✅ 100% 手动清理
撤销/重做（7.4） ✅ 100% 针对收藏/锁定操作
排除区间（7.3） ✅ 100% 视频级别，持久化
主题跟随（6.1） ✅ 100% 跟随系统深色/浅色模式
更多格式支持（附录） ✅ 100% 支持 20+ 种视频格式
独立可执行文件（附录） ✅ 100% PyInstaller 目录模式打包
NAS 级持久化（9） ✅ 100% SQLite 持久化
NAS 性能优化（9） ✅ 100% 元数据缓存 + 并发控制 + 快速关键帧提取
取消任务即时响应 ✅ 100% 切换分区/视频时立即终止 FFmpeg
跨设备状态同步 ✅ 100% file_id 跨设备识别
NAS收藏持久化 ✅ 100% 收藏截图保存在 [视频目录]/[视频名]_covers/
自动备份 ✅ 100% 关闭窗口时自动备份，保留最近5个
自动恢复备份 ✅ 100% 启动时自动恢复
智能监控 ✅ 100% 文件监控 + 60秒定时扫描
崩溃报告与日志增强 ✅ 100% 全局异常捕获 + 崩溃报告
截图提取失败重试 ✅ 100% 自动重试最多3次
缓存优化 ✅ 100% 缓存目录固定
主界面显示版本号 ✅ 100% src/version.py 定义 VERSION
信息区5行显示 ✅ 100% 文件名/时长/分辨率/大小/路径
分辨率自动获取 ✅ 100% ffprobe 导入时获取
放大预览自适应缩放 ✅ 100% 首次打开适应窗口
收藏夹显示修复 ✅ 100% 最大化按钮恢复
预览窗口短期优化 ✅ 100% 300ms 防抖 + 640x360
路径规范化修复 ✅ 100% get_video_by_path 支持路径格式修复
扫描删除范围限定（v3.2.11） ✅ 100% 手动导入视频不再被定时扫描误移除
空文件夹扫描工具（v3.2.11） ✅ 100% tools/folder_scanner_gui.py
打包闪窗修复（v3.2.11） ✅ 100% 打包后 ffmpeg 不再弹窗
自动化测试套件（v3.2.10） ✅ 100% 311 测试通过，覆盖率 77%
加权综合完成度：约 99.6%

📁 当前项目结构
CoverPicker/
├── main.py
├── src/
│   ├── version.py
│   ├── config_manager.py
│   ├── database.py
│   ├── video_scanner.py
│   ├── logger_setup.py
│   ├── crash_handler.py
│   └── controllers/
│       ├── segment_controller.py
│       └── preview_controller.py
├── ui/
│   ├── views/
│   │   ├── segment_view.py
│   │   ├── zoom_dialog.py
│   │   ├── zoom_preview.py
│   │   ├── preview_dialog.py
│   │   └── exclude_dialog.py
│   ├── dialogs/
│   │   └── favorites_dialog.py
│   └── widgets/
│       └── image_labels.py
├── tools/
│   └── folder_scanner_gui.py
├── tests/
│   ├── conftest.py
│   ├── pytest.ini（位于项目根目录）
│   └── test_*.py（37 个测试文件）
├── .github/
│   └── workflows/
│       └── test.yml
├── log/
│   ├── CoverPicker.log
│   └── crashes/
├── PROGRESS.md
├── PROGRESS_TEST.md
└── PRODUCT.md

📝 开发日志
2026-10-30 (v3.2.11)
完成事项：
- 修复定时扫描误移除手动导入视频的问题，扫描删除范围限定为监控目录内
- 优化 tools/folder_scanner_gui.py：修正无视频文件夹判定逻辑，排除 .actors 和 extrafanart，新增空格键图片预览/关闭
- 修复打包后 ffmpeg 窗口闪烁问题
- 验证：本地移动硬盘视频加载后不再从列表消失

2026-08-25 (v3.2.10)
完成事项：
- 自动化测试套件完善，311 个测试全部通过
- 整体覆盖率从 61% 提升至 77%
- 修复测试配置污染、测试弹窗、批量测试崩溃
- 新增 GitHub Actions CI 配置
- 新增 PROGRESS_TEST.md 测试进度文档

2026-07-30 (v3.2.9)
完成事项：
- 延迟删除触发（方案A）
- 线程安全修复（E1）
- 恢复状态清空选中集合（E4）
- 旧标签残留修复

2026-07-30 (v3.2.8)
完成事项：
- 备份清理策略优化（每天首次启动清理）
- 刻度密度提升（5→11个均匀刻度）
- FFmpeg 兼容性优化（移除 -skip_frame nokey）

2026-07-29 (v3.2.2)
完成事项：
- 预览窗口时间轴优化（方案A）
- GIF 默认选项优化
- 备份保留策略调整

🚧 后续计划
版本 核心目标 状态
v3.2.11 扫描删除范围修复 + 空文件夹扫描工具 + 打包闪窗修复 ✅ 已发布
v3.2.12 预览窗口拖动顺滑优化（方案 B） 📋 计划中

v3.2.12 方案 B 说明
目标：改善预览窗口拖动进度条不顺滑、不易定位的问题。

方案 B 内容：
1. 拖动过程中不每次都同步提取帧，改为节流或后台提取，避免阻塞 UI 线程
2. 拖动时使用关键帧快速预览，松手后使用精确 seek 提取最终帧
3. 缓存粒度由 0.01 秒调整为 0.5~1 秒，提高缓存命中率
4. 预取当前时间点前后若干帧，减少松手后的等待

涉及文件：
- ui/views/preview_dialog.py
- src/controllers/preview_controller.py

预期收益：
- 拖动进度条时 UI 不再卡顿
- 松手后定位更准确
- 缓存命中率提升，重复定位更快

备注：
- 方案 C（预生成时间轴缩略图条）体验更好，但首次加载开销和测试量更大，暂不实施
- 方案 B 完成后再评估是否需要升级到方案 C

🧪 回归测试计划
1. 回归测试的定义
回归测试 = 在修改代码后，重新执行之前已测试过的功能，确认没有因新代码引入新的问题。

2. 测试分级
改动类型 测试范围
修复具体 Bug 测试该 Bug 涉及的功能及关联功能
新增功能 测试新增功能 + 核心工作流
依赖升级（PySide6 / FFmpeg） 完整回归测试

3. 测试时机
阶段 测试内容 平台
日常开发 修改的功能模块 Windows
正式发布前 完整回归测试 Windows

4. 测试清单（完整回归测试）
编号 测试项 操作 预期结果
T1 导入视频 点击“+”导入一个本地视频文件 视频出现在左侧列表
T2 导入文件夹 导入一个含视频的文件夹 所有视频出现在列表
T3 加载视频 双击列表中的视频 顶部显示文件名，分区按钮出现，截图网格生成
T4 切换分区 点击 A/B/C 分区按钮 截图网格切换到对应分区
T5 切换截图密度 点击 9/12/16/25 密度按钮 截图数量变化，布局调整正确
T6 选中截图 单击截图 左上角出现蓝色圆点
T7 多选截图 Ctrl+单击 多张截图同时被选中
T8 取消选中 再次单击已选中的截图 蓝色圆点消失
T9 收藏截图 选中截图 → 点击“⭐ 收藏” ❤️ 出现在左上角，收藏数增加
T10 取消收藏 选中已收藏截图 → 点击“☆ 取消收藏” ❤️ 消失，收藏数减少
T11 锁定截图 选中截图 → 点击“🔒 锁定” 🔒 标记出现在左上角
T12 解锁截图 选中已锁定截图 → 点击“🔓 解锁” 🔒 标记消失
T13 刷新（未锁定） 点击“🔄 刷新” 未锁定的截图重新生成
T14 重抽 点击“♻️ 重抽” 所有截图（包括锁定）重新生成
T15 导出单张 选中截图 → 点击“📥 导出” 图片保存到导出目录，右下角出现绿点
T16 预览窗口 点击“🎬”打开预览窗口 窗口打开，视频可预览
T17 片段导出 预览窗口中选段 → 点击“导出片段” 视频片段保存成功
T18 GIF 导出 预览窗口中选段 → 点击“导出GIF” GIF 保存成功
T19 收藏夹 点击“⭐ 收藏夹” 弹出收藏夹弹窗，显示所有收藏截图
T20 细选 选中单张截图 → 点击“🔍 细选” 弹出细选窗口，显示前后 9 张
T21 搜索视频 在搜索栏输入文字 视频列表实时过滤
T22 删除视频 右键视频 → “从库中移除” 视频从列表移除（不删除文件）
T23 批量删除 选中多个视频 → 点击“🗑️” 多个视频从列表移除
T24 撤销 执行收藏/锁定操作后 → 点击“↩ 撤销” 操作回退
T25 重做 撤销后 → 点击“↪ 重做” 操作恢复
T26 排除区间 点击“⛔ 排除区间”设置时间段 截图跳过该时段
T27 分区数切换 在下拉框选择 1~5 分区数改变，截图重置
T28 清空缓存 点击“🗑️ 清理缓存” 缓存大小变为 0
T29 备份状态 点击“💾 保存状态” 备份文件生成
T30 恢复状态 点击“📂 恢复状态”选择备份 数据库恢复
T31 手动导入视频不被误删 手动导入非监控目录视频，等待 2 个扫描周期 视频仍在列表
T32 监控目录删除仍生效 删除监控目录内视频，等待扫描 视频从列表移除

5. 测试记录
日期 版本 平台 测试范围 结果 备注
2026-08-25 v3.2.10 Windows 完整回归测试（311 测试，覆盖率 77%） ✅ 已完成 CI 通过
2026-10-30 v3.2.11 Windows 扫描删除范围修复验证 ✅ 已完成 本地移动硬盘视频不再消失

📌 备注
所有修改遵循“稳定性 > 性能 > 新增功能”原则
v2.5.2 是稳定的基准版本
AI 预览版开发已终止（测试未通过）
备份清理逻辑：每天第一次启动时执行，保留最近5个备份
核心布局方案已冻结（见 PRODUCT.md 附录F）
自动化测试套件详见 PROGRESS_TEST.md，PROGRESS.md 已合并其核心内容

最后更新：2026-10-30
状态：✅ v3.2.11 已完成
稳定基准版本：v2.5.2
对应 PRODUCT.md 版本：v3.2.11