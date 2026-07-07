# 📘 CoverPicker 系统规格说明书（SYSTEM SPECIFICATION）

Version: 1.0

---

# 1. 文档目的

SYSTEM_SPEC.md 定义 CoverPicker 的系统规格。

它回答的问题不是：

> 产品是什么？

而是：

> 系统应该如何组织。

所有 Engine、UI、State、数据结构，都必须遵守本规格。

---

# 2. 系统定位

CoverPicker 是一个面向 NAS 视频库的人机协作式剧照筛选系统。

系统职责：

```
Video
    ↓
Segment
    ↓
Sampling
    ↓
Grid
    ↓
Selection
    ↓
Zoom
    ↓
Export
```

整个系统围绕这一流程设计。

---

# 3. 系统组成

整个系统由六个层级组成。

```
┌──────────────────────────────┐
│ UI Layer                     │
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│ StateManager                 │
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│ Engine Orchestrator          │
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│ Core Engines                 │
│ Sampling / Zoom / Optimize   │
│ Best / Clip / Slot           │
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│ Video Processing             │
│ FFmpeg / Cache               │
└──────────────────────────────┘
```

---

# 4. 核心对象

整个系统只有五个核心对象。

## 4.1 Video

表示一个视频。

```python
Video
    path
    duration
    segments
```

一个 Video 可以包含多个 Segment。

---

## 4.2 Segment

Segment 是视频导航单位。

```python
Segment
    id
    start_time
    end_time
    visited
```

Segment 不保存图片。

Segment 只负责描述时间范围。

---

## 4.3 Frame

Frame 表示一个视频帧。

```python
Frame
    timestamp
    image_path
```

Frame 是不可变对象。

任何 Engine 不允许修改 Frame。

只能生成新的 Frame。

---

## 4.4 Slot

Slot 是用户操作单位。

```python
Slot
    frame
    favorite
    locked
    score
```

Grid 实际上是 Slot 的集合。

不是 Frame 的集合。

---

## 4.5 Clip

Clip 表示导出的视频片段。

```python
Clip
    start_time
    end_time
    output_path
```

---

# 5. 状态管理

整个系统只有一个状态源：

StateManager。

任何状态都必须经过 StateManager。

禁止：

```
Engine → UI
```

正确流程：

```
Engine

↓

StateManager

↓

UI
```

---

# 6. Grid 系统

Grid 是当前 Segment 的候选集合。

支持：

```
3×3 = 9

3×4 = 12

4×4 = 16

5×5 = 25
```

Grid 内部保存 Slot。

不是 Frame。

---

# 7. Segment 系统

Segment 是导航单位。

职责：

- 浏览区域
- 保存浏览状态
- 保存完成状态

不负责：

- 收藏
- Zoom
- 推荐

---

# 8. Sampling 系统

Sampling 的职责：

生成新的 Frame。

默认规则：

- 仅在当前 Segment 内采样。
- 覆盖整个 Segment。
- 避免重复时间点。
- 尽量保证时间分布均匀。

重新采样必须明显区别于上一轮结果。

禁止只在上一轮截图附近随机。

未来：

支持 Global Explore 模式。

该模式允许跨 Segment。

---

# 9. Slot 系统

Slot 保存：

```
favorite

locked

score
```

Slot 支持：

收藏

取消收藏

锁定

替换

补充截图时：

```
locked == true

↓

禁止替换
```

其余 Slot 可以更新。

---

# 10. Zoom 系统

Zoom 是精修系统。

职责：

围绕当前 Frame，

逐步提高时间精度。

默认层级：

```
Level1

±4 秒

Level2

±1 秒

Level3

±0.2 秒
```

Zoom 不改变：

Segment

Grid

用户上下文。

Zoom 只改变：

当前 Slot 的候选内容。

---

# 11. Optimize 系统

Optimize 是重新探索。

职责：

重新生成当前 Segment 的候选截图。

规则：

保留：

favorite

locked

重新生成：

其它 Slot。

Optimize 与 Zoom 完全不同。

Optimize：

重新开始。

Zoom：

继续精修。

---

# 12. Best 系统

Best 用于推荐当前 Grid 中最值得关注的一张图。

优先级：

```
locked

↓

favorite

↓

score
```

Best 只是推荐。

不会自动保存。

不会自动修改收藏。

---

# 13. 收藏系统

用户可以：

收藏

取消收藏

批量保存

收藏跨 Segment 保存。

支持恢复。

---

# 14. Clip 系统

支持：

10 秒

15 秒

20 秒

视频片段导出。

实现方式：

FFmpeg Stream Copy。

禁止重新编码。

---

# 15. Engine 调度

所有 Engine 必须经过：

```
Engine Orchestrator
```

统一执行。

禁止：

多个 Engine 同时修改状态。

统一流程：

```
Request

↓

Plan

↓

Execute

↓

Commit
```

---

# 16. StateManager

StateManager 是唯一状态源。

负责：

Video

Segment

Grid

Slot

Best

Zoom

所有 UI 更新。

任何模块不得绕过 StateManager。

---

# 17. UI 原则

UI 不做业务逻辑。

UI 只负责：

显示

响应点击

发送事件

真正的数据修改：

全部由 Engine 完成。

---

# 18. 系统原则

整个系统必须遵守：

① 状态唯一。

② 操作可逆。

③ 数据可恢复。

④ 功能可扩展。

⑤ 用户始终拥有最终决定权。

---

# 19. 长期目标

CoverPicker 最终应支持：

- 1000～10000 视频管理
- 长期持续维护
- AI 辅助筛选
- 多平台运行（Windows / macOS / Linux）

但任何未来功能，

都不能破坏：

Segment → Grid → Zoom

这一核心工作流。