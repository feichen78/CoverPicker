🧠 CoverPicker v3.1 Runtime Flow
完整运行时流程，补充软件关闭流程、文件失效同步流程、异步多线程规范
所有链路严格遵循 UI→State→Orchestrator→Engine→State 提交→UI 刷新标准链路
🧱 1. 软件启动流程（Startup Flow）
main.py 入口
↓
MainWindow.init 初始化界面
↓
PersistManager 加载本地 app_state.db 恢复全局配置
↓
StateManager.init () 初始化空全局状态
↓
EngineOrchestrator.init () 初始化调度队列、事务锁
↓
CacheManager.init () 自动清理 7 天过期缓存、校验单视频缓存不超 2GB 上限
↓
Video 扫描器加载本地 / NAS 视频目录列表
↓
UI 渲染视频列表界面
🎬 2. 打开视频完整流程
用户点击视频文件
↓
StateManager.load_video (video_path)
↓
FFmpegEngine 解析视频元数据（时长、编码）
↓
SegmentBuilder 自动均分生成 A/B/C/D/E 分段
↓
SamplingEngine 生成初始 Grid 帧集合（过滤黑屏、重复帧）
↓
SlotEngine 批量创建 Slot 对象绑定候选帧
↓
BestEngine 计算初始最优推荐帧
↓
StateManager 批量提交状态变更
↓
UI 刷新分区栏、Grid 缩略图面板
🧩 3. Segment 分区点击切换流程
用户点击 A/B/C/D/E 分区标签
↓
StateManager.set_current_segment (segment_id)
↓
EngineOrchestrator 接收 GENERATE_GRID 执行计划
↓
SamplingEngine 针对当前分区均匀采样
↓
SlotEngine 替换全部未锁定 Slot 新帧
↓
BestEngine 重新计算最优帧
↓
State 提交，UI 局部刷新网格
🖼️ 4. Slot 收藏 / 锁定点击流程
用户点击 Slot 收藏 / 锁定按钮
↓
StateManager.update_slot_state (slot_id, action)
↓
SlotEngine 切换 favorite/locked 标记，锁定帧拒绝变更
↓
BestEngine 重新计算全局最优帧
↓
State 统一提交
↓
UI 更新 Slot 角标、Best 高亮面板
⭐ 5. Best 推荐帧更新统一流程
任意 Slot 收藏、锁定、替换操作触发
↓
StateManager 触发 recompute_best
↓
BestEngine 按优先级计算当前最优 Slot
↓
State 更新 best_slot_id
↓
UI 刷新顶部 Best 预览窗口
🔍 6. Zoom 分层精修完整流程
用户选中 Slot 点击 Zoom 层级按钮
↓
StateManager.zoom_request (slot_id, zoom_level)
↓
Orchestrator 规划 ZOOM 优先级执行计划
↓
ZoomEngine 按层级规则生成拓展候选帧
↓
SlotEngine 仅替换未锁定 Slot 新帧（partial 替换）
↓
BestEngine 重算推荐帧
↓
局部提交状态，UI 仅刷新变更缩略图
⚙️ 7. Optimize 全局重采样流程
用户点击全局刷新按钮
↓
StateManager.request_optimize ()
↓
Orchestrator 执行 OPTIMIZE 队列任务
↓
SamplingEngine 全局均衡重采样
↓
SlotEngine 替换全部非锁定 Slot
↓
BestEngine 重算
↓
完整刷新 Grid 界面
❤️ 8. 收藏持久化同步流程
切换收藏 / 锁定状态
↓
SlotEngine 更新标记
↓
PersistManager 同步写入 SQLite 数据库
↓
State 本地内存同步
↓
UI 更新视觉标记
🎞️ 9. 视频片段无损导出流程
用户设置起止时间、点击导出 Clip
↓
StateManager.clip_request (start, duration)
↓
Orchestrator 分发 CLIP 任务
↓
ClipEngine 调用 FFmpeg stream copy 截取
↓
自动按视频 hash 分目录存储，文件名自增防覆盖
↓
持久化记录导出标记
↓
UI 弹出导出成功提示
🛑 10. 软件关闭新增流程（补充缺失链路）
用户关闭主窗口
↓
PersistManager 批量写入全部当前状态、网格尺寸配置
↓
CacheManager 标记缓存，7 天过期自动清理
↓
全部引擎、调度器安全销毁线程锁
↓
程序退出
📂 11. NAS 视频文件失效同步流程（补充 NAS 场景）
加载视频检测文件不存在 / 网络断开
↓
StateManager 标记视频失效状态
↓
UI 视频列表灰色标记失效文件
↓
所有对应 Slot、缓存保留，下次文件恢复自动重载
🧠 12. 全局调度统一入口（所有操作强制链路）
UI 用户交互事件
↓
StateManager 接收请求
↓
EngineOrchestrator 统一规划、上锁排队执行
↓
对应 Core Engine 完成计算生成新帧 / 修改标记
↓
SlotEngine 更新 Slot 数据
↓
StateManager 批量提交全部变更
↓
UI 主线程局部刷新界面
🚫 13. 全局禁止行为
❌ Engine 直接调用 UI 刷新接口
❌ Slot 绕过 StateManager 直接修改内存数据
❌ 局部更新 Best 而不同步全部 Slot 状态
📊 14. SSOT 单一状态源强制约束
Video/Segment/Slot/Zoom/Best/ 缓存配置全部状态唯一归属 StateManager，任何模块数据变更必须同步至 State
🧩 15. 多线程异步规范（补充缺失并发规则）
FFmpeg 抽帧、采样、导出全部放入后台子线程
StateManager 读写加互斥锁，禁止多线程并发修改
所有 UI 渲染、刷新操作强制切回 Qt 主线程执行，避免界面卡死、崩溃
🧠 16. 系统运行核心循环总结
均匀采样 → 分区浏览 → 人工筛选标记 → 分层 Zoom 精修 → 锁定满意帧 → 导出素材
🚀 17. v3.1 设计目标确认
✔ NAS 千级视频库稳定运行
✔ A/B/C/D/E 多分区导航
✔ L1~L4 标准化 Zoom 分层采样
✔ Slot 锁定防替换机制
✔ 收藏 / 导出完整持久化体系
✔ 全链路状态一致性、无错乱