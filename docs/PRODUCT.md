📘 CoverPicker 产品说明书（v3.1）
1. 产品定位

CoverPicker 是一款用于 NAS视频库剧照筛选与封面选择的工具。

它的目标是：

将用户从“长视频中手动找帧”的时间，从几十分钟降低到几分钟。

❌ 非目标

CoverPicker 不做：

视频播放器
视频剪辑软件
自动AI选封面工具
✅ 核心目标

只做一件事：

在大量视频帧中，帮助用户快速找到最满意的剧照或封面

2. 核心系统结构（非常重要）

CoverPicker 是一个 四层筛选系统

VIDEO
  ↓
SEGMENT（分区）
  ↓
GRID（帧候选集合）
  ↓
ZOOM（时间精细化）
  ↓
CLIP（视频导出）
3. 数据模型定义（工程核心）
3.1 Frame（帧）
Frame:
    time: float
    image: QImage
3.2 Slot（UI单元）

Grid中的每一个位置：

Slot:
    frame: Frame
    locked: bool
    favorite: bool
    visible: bool
3.3 Segment（视频分区）
Segment:
    name: str   # A/B/C/D/E
    start_time: float
    end_time: float
    slots: List[Slot]
    visited: bool
3.4 Clip（导出片段）
Clip:
    start_time: float
    end_time: float
    file_path: str
4. 第一层：视频分区（Segment Navigation）

视频按时间自动分为多个区：

A | B | C | D | E

规则：

默认跳过前10%
Segment 可扩展（F/G/H…）
支持状态：
A ✓ 已浏览
B
C ★ 推荐
D ✓
E
Segment状态定义
未浏览 → 已浏览 → 推荐 → 已导出
时间范围筛选（重要新增）

用户可限制采样区间：

00:14:12 ~ 00:35:20

Segment只在该区间内生成。

5. 第二层：Grid（帧筛选系统）

进入Segment后生成 Grid：

默认：

3x3 = 9帧

可切换：

9 / 12 / 16 / 25
用户操作
点击帧：
favorite = toggle
lock：
locked = true
补充机制（核心功能）

触发：

“补充当前Segment”

规则：

只替换 Slot where locked == false
保留 locked / favorite slot
示例：
原始：
①✔ ② ③✔ ④ ⑤ ⑥ ⑦✔ ⑧ ⑨

补充后：
①✔ ②新 ③✔ ④新 ⑤新 ⑥新 ⑦✔ ⑧新 ⑨新
6. 第三层：Zoom（时间轴精细化）
定义（非常重要）

Zoom =

基于当前 Frame 时间点，重新进行时间采样

采样规则

初级：

±4秒

中级：

±1秒

高级：

±0.2秒
Zoom行为规则（关键）
❌ 不改变 Segment
❌ 不重置 Grid
❌ 不重新进入 A/B/C
✅ 仅更新当前 Slot内容
7. 第四层：收藏系统（Favorites）
收藏规则

用户点击：

❤ 或 ☆

状态：

favorite = true
收藏管理
可取消收藏
可批量导出
可跨 Segment 存在
8. Best Frame（推荐帧）
定义

Best Frame = 当前 Grid 中的推荐展示帧

计算规则（简单稳定版）

优先级：

1. locked
2. favorite
3. score（基础清晰度）
9. Optimize（重采样）
定义

对当前 Segment重新采样Frame

规则
只替换 unlocked slots
不改变 favorite / locked
时间分布随机扰动
10. 视频片段导出（Clip）
功能

导出用户选定时间片段

UI行为

用户选择：

00:35:22

选择：

10 / 15 / 20 秒
输出
StillClip/影片名/0001.mp4
实现方式
FFmpeg
无需重新编码（fast copy模式）
11. UI状态系统（非常重要）
Segment状态
gray   = 未浏览
blue   = 已浏览
green  = 收藏帧
orange = 导出Clip
Slot状态
locked
favorite
normal
12. 用户完整流程（闭环）
选择视频
→ Segment浏览（A/B/C）
→ Grid生成（9/16/25）
→ 收藏帧
→ 补充未选帧
→ Zoom精细化
→ Lock最终帧
→ Save/Export
13. 成功标准

CoverPicker 成功定义：

将视频封面筛选时间从 30分钟降低到 3分钟以内

14. 设计原则（强约束）
所有操作必须“可逆”
所有状态必须“可保存”
所有采样必须“可重复”
UI不做决策，只做表达
## NAS级设计原则

CoverPicker 面向 NAS 视频库（1000+ 视频），因此：

### 1. 禁止局部重复采样
任何重采样必须跨时间区间分布，而不是邻近帧。

### 2. 视频是“全局资源”
采样必须跨 Segment，而不是局限单 Segment。

### 3. 系统目标是“筛选效率”，不是“单视频优化”
单视频优化只是子问题。
🧠 CoverPicker v3.1 工程规格化（System Specification）

这一步的目标只有一个：

✅ 把 PRODUCT.md 变成“可以直接写代码的系统说明书”

📐 一、系统总架构（核心）

CoverPicker 不再是 UI 程序，而是一个四层引擎系统

┌──────────────────────────────┐
│        UI Layer (PySide6)    │
└─────────────┬────────────────┘
              ↓
┌──────────────────────────────┐
│      State Controller        │  ← 核心调度
└─────────────┬────────────────┘
              ↓
┌──────────────────────────────┐
│     Sampling Engine          │  ← 帧生成核心（关键）
└─────────────┬────────────────┘
              ↓
┌──────────────────────────────┐
│   Video Processing Engine    │  ← ffmpeg / 解码
└──────────────────────────────┘
🧠 二、核心数据流（非常重要）

所有操作必须遵循这个链路：

VIDEO LOAD
   ↓
SEGMENT BUILD
   ↓
FRAME SAMPLING
   ↓
SLOT CREATION
   ↓
GRID RENDER
   ↓
USER ACTION
   ↓
STATE UPDATE
🧩 三、核心对象规格（必须严格实现）
3.1 Frame（不可变）
class Frame:
    time: float
    image_path: str
    source_segment: str

👉 Frame = 只读对象（禁止修改）

3.2 Slot（核心UI单元）
class Slot:
    frame: Frame
    locked: bool
    favorite: bool
    score: float
Slot规则
状态	含义
locked	永久保留
favorite	用户喜欢
score	系统评分
3.3 Segment（时间分区）
class Segment:
    id: str   # A/B/C/D/E...
    start: float
    end: float
    visited: bool
3.4 Video（新增关键）
class Video:
    path: str
    duration: float
    segments: List[Segment]
🧠 四、核心引擎规格
4.1 Sampling Engine（最重要）
🎯 职责

生成 Frame（核心）

❌ 禁止行为（非常关键）

Sampling Engine 禁止：

❌ 只在 ±几秒内采样
❌ 只在单Segment采样
❌ 重复旧frame
✅ 正确行为（NAS级采样）
规则1：全局分布采样
time ∈ [video_start, video_end]
规则2：Segment加权随机
P(segment) = uniform OR weighted
规则3：去重机制
if abs(time - existing_frame_time) < threshold:
    reject
规则4：多样性约束（关键）

必须保证：

时间分散
Segment分散
视觉差异最大化（未来扩展）
4.2 Slot Engine
职责

维护 Grid 状态

更新规则
if locked == True:
    NEVER overwrite
if favorite == True:
    preserve during optimize
补充机制（核心）
replace only where locked == False
4.3 Zoom Engine（重大修正）
❗Zoom真实定义

Zoom = 跨Segment局部重采样

❌ 禁止旧实现
❌ ±4秒邻近采样
❌ 单帧时间窗口放大
✅ 正确实现
input: frame
output: new frame set

rule:
    sample from:
        same segment ± adjacent segments
        OR global weighted pool
Zoom层级（不是时间，而是“密度”）
Level 1: coarse (segment-wide)
Level 2: medium (multi-segment)
Level 3: fine (local + cross segment)
Level 4: ultra (very high density sampling)
4.4 Optimize Engine
职责

重生成 Grid，但不破坏用户选择

规则
preserve locked slots
preserve favorite slots
replace others with new samples
与 Zoom 区别（必须严格）
功能	本质
Optimize	Grid重建
Zoom	Frame重采样
4.5 Best Engine
定义
Best = max(score + user_preference)
优先级
locked > favorite > score
🧠 五、状态机（核心）
Slot状态流转
empty → sampled → favorite → locked
Segment状态
unvisited → visited → preferred
🧠 六、关键系统约束（NAS级）
❗1. 禁止局部采样
NO sampling within ±seconds only
❗2. 必须跨Segment
every batch must include multiple segments
❗3. 每次补充必须“明显变化”
new frames must differ visually & temporally
🧠 七、UI行为绑定规则
Grid UI
click → favorite toggle
long press → lock
optimize → regenerate slots
Zoom UI
click frame → zoom engine
zoom level change → resample density
Segment UI
click → load grid
revisit → preserve state
🧠 八、系统边界（非常重要）
CoverPicker 不做：
❌ 自动选封面
❌ AI评分主导
❌ 视频编辑
❌ 播放控制
CoverPicker 只做：

✔ 人类视觉筛选加速器

🧠 九、最终工程目标
Reduce:
    manual frame browsing time

From:
    30 minutes

To:
    2–5 minutes per video

AND

Scale to:
    1000–10000 NAS videos
🚀 十、这一版规格化的意义

现在这个系统已经变成：

🧠 一个“视频视觉检索 + 人类决策辅助系统”

而不是：

❌ 截图工具 / 视频工具