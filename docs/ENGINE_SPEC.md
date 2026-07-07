🧠 CoverPicker v3.1 Engine Specification
本文档定义所有核心 Engine 的行为、输入输出、约束与执行规则
所有实现必须严格遵守 StateManager + EngineOrchestrator 分层架构
🚨 0. 全局总约束（不可修改）
❗原则 1：单一状态源（SSOT）
ONLY StateManager 持有全部全局状态，任何引擎不得独立存储状态
❗原则 2：Engine 禁止直接操作 UI
Engine 修改状态 → StateManager 统一推送更新 → UI 刷新
禁止链路：Engine → UI
❗原则 3：所有用户操作必须经过 Orchestrator 统一调度
UI 事件 → StateManager → EngineOrchestrator → 对应 Engine 执行
❗原则 4：Slot 是唯一可操作单元
全部筛选、替换、收藏逻辑基于 Slot，不直接操作原始 Frame
🧱 1. SlotEngine（筛选单元核心）
🎯 职责
管理 Slot 完整生命周期；控制收藏 / 锁定标记；安全替换候选帧；保障 UI 状态全局一致
📦 Slot 标准数据结构
python
运行
class Slot:
    id: int                  # 全局唯一自增ID
    frame: Frame             # 绑定不可变帧对象
    state: SlotState
    locked: bool             # True=任何采样不替换
    favorite: bool           # True=标记收藏，Best优先级提升
    source_segment: str      # 归属Segment ID
    generation_id: int       # 采样批次ID，区分新旧候选
🔄 SlotState 完整流转（含回退逻辑，补充解除收藏 / 解锁分支）
EMPTY → GENERATED → VIEWED → SELECTED (收藏) → LOCKED
反向回退：LOCKED→SELECTED→VIEWED→GENERATED→EMPTY
⚙️ 核心 API
create_slots：批量初始化 Slot 对象
def create_slots (frames: List [Frame]) -> List [Slot]:
return [Slot (frame=f, state=GENERATED) for f in frames]
update_state：修改收藏 / 浏览状态，锁定帧拒绝变更
def update_state (slot, action):
if slot.locked:
return
if action == "favorite":
slot.favorite = not slot.favorite
slot.state = SELECTED if slot.favorite else VIEWED
replace_slots：批量替换未锁定 Slot 绑定帧
def replace_slots (slots, new_frames):
for slot in slots:
if slot.locked:
continue
slot.frame = new_frames.pop ()
slot.state = GENERATED
🎯 2. SamplingEngine（初始 Grid 生成器）
🎯 职责
生成分区均匀分布候选帧；过滤近似重复帧、黑屏无效帧；保障多批次采样结果差异化
📦 输入
video 对象、segments 列表、grid 尺寸、目标时间区间
📤 输出
List [Frame] 不重复、无黑屏、分布均匀的帧集合
⚙️ 核心算法步骤
Step1：Segment 权重分配
weight (segment) = 基础权重 1.0 + 未浏览加分 0.3 + 用户收藏兴趣加分 0.5
Step2：区间随机采样时间点
t = random (segment.start, segment.end)
Step3：全局去重过滤规则
任意两帧时间差＜0.8s 判定近似帧，直接丢弃
Step4：黑屏帧过滤
帧平均亮度＜35 判定无效，丢弃，重新采样替补
Step5：分区数量均衡控制
单 Segment 最大候选帧数量 = grid_size / 3
🔍 3. ZoomEngine（多尺度分层精修）
统一标准化层级（消除文档冲突）
L1: ±2s 仅限当前 Segment
L2: ±8s 当前 Segment + 相邻分区
L3: 跨全部 Segment 拓展采样
L4: 全局无差别全新重采样
🎯 职责
基于用户选中 Slot 内 Frame 做精细化拓展采样；默认仅当前分区，全局探索模式允许跨分区
📦 输入
基准 Frame、zoom_level 层级、video 对象、全部分段列表
📤 输出
List [Frame] 差异化新候选帧
⚙️ 核心流程
Step1：基于基准帧时间生成拓展时间窗口
Step2：按层级加载对应 Segment 范围
Step3：帧相似度过滤，和基准帧过于近似直接剔除
Step4：补充足量差异化帧填满替换数量
⚙️ 4. OptimizeEngine（全局分区重采样）
🎯 职责
刷新当前 Segment 全部候选 Grid；保留锁定、收藏帧，仅替换普通 Slot
⚙️ 输入
当前全部 Slot 集合、video 对象
⚙️ 输出
全新 Frame 列表，用于替换可修改 Slot
🔄 强制规则
DO NOT replace: locked slots；默认不替换 favorite slots（提供强制刷新开关）
算法流程：调用 SamplingEngine 全局均衡采样 → 多样性过滤 → 返回可用新帧
⭐ 5. BestEngine（最优帧推荐系统）
🎯 职责
计算当前 Grid 优先级最高帧，供 UI 高亮展示
⚙️ 优先级权重（固定）
LOCKED (权重 10) > FAVORITE (权重 5) > 画质 score (0~5)
画质 score 计算维度：画面清晰度、对比度（预留人脸检测拓展接口，v3.2 暂不实现）
def compute_best (slots):
return max (slots, key=lambda s: priority_score (s))
🎬 6. ClipEngine（无损视频片段导出）
🎯 职责
调用 FFmpeg 截取指定时间区间片段，无二次编码
⚙️ 输入
起始时间、持续时长、视频原始路径、输出目录
⚙️ FFmpeg 固定命令（stream copy 无损模式）
ffmpeg -ss start_time -t duration -i input.mp4 -c copy output.mp4
🧠 7. EngineOrchestrator（统一调度核心）
🎯 职责
管控所有 Engine 执行顺序、操作冲突、事务锁、失败回滚
⚙️ 标准执行模型流程
REQUEST（UI 操作传入） → PLAN（生成执行计划） → EXECUTE（调用对应引擎） → COMMIT（状态统一提交 / 失败回滚）
⚙️ 操作优先级队列（固定）
ZOOM > SELECT 收藏 / 锁定 > OPTIMIZE 全局重采样 > SAMPLING 初始采样 > 后台缓存任务
🧠 8. StateManager（唯一状态源）
🎯 职责
全软件状态持有者；状态变更统一分发；持久化同步入口；UI 更新事件推送
📦 标准 AppState 结构
class AppState:
current_video: Video
all_segments: List [Segment]
current_grid_slots: List [Slot]
current_zoom_level: int
best_slot_id: int
cache_config: CacheState
global_grid_size: int
⚙️ 标准对外 API
load_video ()、set_segment ()、update_slot ()、recompute_best ()、zoom_request ()、optimize_request ()
🧱 9. 系统执行铁律（永久约束）
禁止任何 Engine 直接修改 UI 界面
所有状态变更必须经过 StateManager 统一提交
全部引擎调用强制走 Orchestrator 调度入口
所有筛选、替换操作最小单元为 Slot，不直接操作 Frame
🧠 10. 系统本质总结
CoverPicker v3.1 底层本质：
多尺度视频帧人工决策系统链路：
均匀采样 → 分区浏览筛选 → 分层精细探索 → 人工标记取舍 → 素材导出
🚀 11. 开发稳定边界
v3.1 架构定型后，不再修改分层、对象、调度规则；后续迭代仅拓展引擎内部算法，不推翻整体架构。