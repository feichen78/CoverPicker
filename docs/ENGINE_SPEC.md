🧠 CoverPicker v3.1 Engine Specification

本文档定义所有核心 Engine 的行为、输入输出、约束与执行规则
所有实现必须严格遵守 StateManager + Orchestrator 架构

🚨 0. 总原则（绝对约束）
❗原则1：单一状态源（SSOT）
ONLY StateManager owns state
❗原则2：Engine不可直接影响UI
Engine → StateManager → UI
NOT Engine → UI
❗原则3：所有操作必须经过 Orchestrator
UI → StateManager → EngineOrchestrator → Engines
❗原则4：Slot是唯一操作单位
Everything operates on Slot, NOT Frame
🧱 1. SlotEngine（状态核心）
🎯 职责
管理 Slot 生命周期
控制 favorite / locked
执行安全替换
维护 UI 状态一致性
📦 Slot结构
class Slot:
    id: int
    frame: Frame

    state: SlotState

    locked: bool
    favorite: bool

    source_segment: str
    generation_id: int
🔄 SlotState
EMPTY → GENERATED → VIEWED → SELECTED → LOCKED
⚙️ 核心API
1. create_slots
def create_slots(frames: List[Frame]) -> List[Slot]:
    return [Slot(frame=f, state=GENERATED) for f in frames]
2. update_state
def update_state(slot, action):

    if slot.locked:
        return

    if action == "favorite":
        slot.favorite = not slot.favorite
        slot.state = SELECTED if slot.favorite else VIEWED
3. replace_slots
def replace_slots(slots, new_frames):

    for slot in slots:
        if slot.locked:
            continue

        slot.frame = new_frames.pop()
        slot.state = GENERATED
🎯 2. SamplingEngine（初始生成器）
🎯 职责
生成初始 Grid
保证空间分布
防止重复帧
支持 Segment 权重
📦 输入
video
segments
grid_size
time_range
📤 输出
List[Frame]
⚙️ 核心算法
Step1：Segment权重选择
weight(segment) =
    base_weight
    + unvisited_bonus
    + user_interest_bonus
Step2：时间采样
t = random(segment.start, segment.end)
Step3：全局去重
if abs(t - existing_frame_time) < threshold:
    reject
Step4：空间均匀性控制
max_per_segment = grid_size / 3
🔍 3. ZoomEngine（多尺度探索）
🎯 职责
基于选中 Frame 做细化探索
SamplingEngine

默认：

仅在当前 Segment 内随机采样。

要求：

每次重新采样都必须覆盖整个 Segment，

不能局限于上一轮截图附近。

只有"全片探索（Global Explore）"模式，

才允许跨 Segment。
提供多层 Zoom
📦 输入
base_frame
zoom_level
video
segments
📤 输出
List[Frame]
🔄 Zoom Levels
L1: ±2s 同segment
L2: ±8s + adjacent
L3: cross-segment
L4: global re-sample
⚙️ 核心流程
Step1：时间扩展
candidates = [
    base_time ± random_range,
    segment_range,
    adjacent_segments
]
Step2：跨Segment补充
segments = current + neighbors + weighted_global
Step3：去相似过滤
if similarity(frame, base_frame) > threshold:
    reject
⚙️ 4. OptimizeEngine（全局重构）
🎯 职责
重建Grid
保留 locked / favorite
提高整体质量
⚙️ 输入
slots
video
⚙️ 输出
new_frames
🔄 规则
DO NOT replace:
    locked slots
    favorite slots (unless forced)
⚙️ 算法
frames = SamplingEngine.resample_global()
frames = diversity_filter(frames)
⭐ 5. BestEngine（推荐系统）
🎯 职责
计算最佳帧
提供UI展示
⚙️ 优先级
LOCKED > FAVORITE > SCORE
⚙️ 计算方式
best = max(slots, key=lambda s:
    priority(s.state) + quality_score(s.frame)
)
🎬 6. ClipEngine（视频导出）
🎯 职责
FFmpeg剪辑导出
⚙️ 输入
start_time
duration
video_path
⚙️ 输出
mp4 file
⚙️ FFmpeg命令
ffmpeg -ss start_time -t duration -i input.mp4 -c copy output.mp4
🧠 7. EngineOrchestrator（统一调度）
🎯 职责
控制所有 Engine 执行顺序
解决冲突
保证一致性
⚙️ 核心流程
REQUEST → PLAN → EXECUTE → COMMIT
⚙️ 优先级
ZOOM > SELECT > OPTIMIZE > SAMPLING > BACKGROUND
⚙️ 执行模型
def execute(action):

    plan = self.plan(action)

    lock()

    result = run_engines(plan)

    commit(result)

    unlock()
🧠 8. StateManager（唯一状态源）
🎯 职责
保存全局状态
分发事件
统一更新UI
⚙️ 状态结构
class AppState:
    video
    segments
    slots
    zoom_level
    best_slot
⚙️ API
load_video()
set_segment()
update_slot()
recompute_best()
zoom_request()
optimize_request()
🧱 9. 系统执行原则（最终约束）
❗规则1
NO engine directly modifies UI
❗规则2
ALL changes go through StateManager
❗规则3
ALL engine calls go through Orchestrator
❗规则4
Slot is the only mutable UI unit
🧠 10. 系统本质总结
CoverPicker v3.1 本质是：
A multi-scale video frame decision system:

Sampling → Exploration → Refinement → Selection → Export
🚀 11. 开发稳定边界（非常重要）

从 v3.1 开始：

❌ 不再改架构
❌ 不再推翻模块
✔ 只实现 engine 内部逻辑

📌 文档结束