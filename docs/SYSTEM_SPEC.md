📘 CoverPicker 系统规格说明书（SYSTEM SPECIFICATION）
Version: 3.1
1. 文档目的
定义 v3.1 完整系统硬性规格，规范所有 Engine、UI、状态、数据对象、存储规则，所有开发代码严格对齐本文档。
2. 系统固定工作流
plaintext
Video加载
    ↓
Segment自动均分划分
    ↓
均匀Sampling生成Grid候选
    ↓
Slot人工浏览筛选、标记收藏/锁定
    ↓
分层Zoom精细拓展采样
    ↓
Optimize全局刷新候选
    ↓
剧照/视频片段导出
3. 完整五层系统分层（新增独立 Storage 层）
UI 层 → StateManager 状态层 → Orchestrator 调度层 → Core 引擎层 → 视频处理层 → Storage 持久缓存层
4. 五大核心不可变对象定义
4.1 Video
python
运行
Video
    path: str               # 本地/NAS完整路径
    duration: float         # 总时长秒
    file_hash: str          # 唯一哈希标识，用于隔离缓存、数据库关联
    segments: List[Segment]
4.2 Segment（导航单位）
python
运行
Segment
    id: str                 # A/B/C/D/E标识
    start_time: float
    end_time: float
    visited: bool           # 用户浏览标记
分段规则：视频总时长均分 5 段；总时长＜300s 合并为单一 Segment
4.3 Frame（不可变对象，禁止修改）
python
运行
Frame
    timestamp: float        # 精确截取时间点
    cache_path: str         # 缓存图片本地路径
仅可生成新 Frame，不允许修改已有 Frame 属性
4.4 Slot（唯一操作单元）
python
运行
Slot
    frame: Frame
    favorite: bool
    locked: bool
    quality_score: float
Grid = Slot 集合，而非 Frame 集合
4.5 Clip（导出片段对象）
python
运行
Clip
    start_time: float
    end_time: float
    output_path: str
5. 全局状态管理强制规则
StateManager 全软件唯一事实源；
变更链路标准：Engine 计算结果 → StateManager 更新 → UI 统一刷新；
禁止逆向链路 Engine→UI、UI 直接修改数据。
6. Grid 网格系统规范
支持尺寸：3×3 (9)、3×4 (12)、4×4 (16 默认)、5×5 (25)
网格尺寸选择状态存入数据库持久保存，重启软件自动沿用上次选择。
7. Segment 导航系统规范
仅负责时间区间定位、浏览状态标记；不参与收藏、Zoom、画质评分逻辑。
8. Sampling 采样系统硬性规则
默认仅当前 Segment 内均匀采样，覆盖完整时间区间；
两次采样结果必须存在明显差异化，禁止仅在上一轮帧附近随机；
全局探索模式允许跨 Segment 采样（Zoom L3/L4、Optimize）；
内置 0.8s 近似帧过滤、亮度 35 黑屏帧过滤。
9. Slot 操作约束
locked=True 时，任何采样、刷新操作均不可替换当前 Slot 绑定 Frame；
favorite 仅为优先级标记，默认不锁定（Optimize 提供强制刷新开关）。
10. Zoom 分层统一规范（v3.1 全局统一）
L1 ±2s 同分区精细采样
L2 ±8s 当前 + 相邻分区
L3 跨全部分区拓展
L4 全局无差别全新重采样
Zoom 仅修改当前 Grid 候选，不切换 Segment、不重置全部界面上下文。
11. Optimize 全局重采样区分定义
Optimize：整段分区全部重新生成候选；Zoom：基于单张满意帧精细化拓展，二者逻辑完全隔离。
12. Best 推荐系统优先级固定
locked 帧 > 收藏 favorite 帧 > 画质评分帧；仅 UI 高亮参考，不自动保存、不修改用户标记。
13. 收藏持久化规则
收藏、锁定、浏览状态全部写入 SQLite 数据库；跨软件重启、关闭视频后完整保留；收藏标记跨 Segment 永久生效。
14. Clip 导出硬性约束
全部片段采用 FFmpeg -c copy 无损流复制，禁止默认转码；支持自定义时长 10/15/20s，支持自定义起止时间。
15. Orchestrator 调度事务规范
所有操作封装事务；引擎执行失败自动回滚状态，不残留脏数据；多操作并发按固定优先级排队执行。
16. UI 层职责边界
UI 仅做界面渲染、捕获点击事件、发送标准化操作信号；所有业务计算、数据修改全部交由 Core 引擎处理。
17. 全局系统刚性原则
① 单一全局状态源；② 全部操作支持可逆撤销；③ 用户状态持久可恢复；④ 功能模块化可扩展；⑤ 用户拥有全部最终决策权限。
18. 长期兼容目标
支持 1000~10000 规模 NAS 视频库长期维护；支持 Windows/macOS 双平台；远期拓展 AI 辅助评分（v3.2 不实现）；新增功能不得破坏 Segment→Grid→Zoom 核心工作流。