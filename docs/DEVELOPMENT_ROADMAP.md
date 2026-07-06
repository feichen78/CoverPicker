# 📄 CoverPicker v3.1 → v3.2 Development Roadmap

> 本文档定义 CoverPicker 从 v3.1 架构设计到 v3.2 可运行系统的**实际开发顺序**
> 用于避免模块混乱、循环返工和功能崩坏

---

# 🧠 0. 开发原则（必须遵守）

## ❗原则1：必须按顺序开发

不能跳过阶段：

> ❌ 不允许先写 Zoom 再补 Slot  
> ❌ 不允许 UI 先跑再补 StateManager  

---

## ❗原则2：每一步必须可运行

```text
每个阶段 = 可以启动 + 可以点击 + 不崩
原则3：优先保证系统稳定，不追求功能完整
🚀 1. 第一阶段：核心骨架（必须先完成）
🎯 目标：

建立“不会崩的最小系统”

📦 开发顺序：
1. StateManager（必须第一）
- AppState结构
- load_video()
- set_segment()

✔ 目标：能加载视频 + 保存状态

2. SlotEngine（第二）
- Slot结构
- create_slots()
- toggle_favorite()

✔ 目标：能显示9宫格

3. SamplingEngine（第三）
- generate_initial_frames()

✔ 目标：能生成第一批截图

✔ 第一阶段完成标准：
能打开视频
能生成9张图
UI不崩
state可追踪
🔵 2. 第二阶段：基础交互（核心体验）
🎯 目标：

实现“可选图系统”

📦 开发顺序：
4. BestEngine
- compute_best()
- priority rules

✔ 目标：best能正确变化

5. 收藏系统（SlotEngine增强）
- favorite toggle
- state update

✔ 目标：可收藏 / 可取消

6. EngineOrchestrator（基础版）
- handle(action)
- simple routing

✔ 目标：所有操作经过统一入口

✔ 第二阶段完成标准：
收藏正常
best正常变化
操作不会乱
🟡 3. 第三阶段：Zoom系统（关键难点）
🎯 目标：

恢复并稳定 Zoom

📦 开发顺序：
7. ZoomEngine（L1 → L2）
- ±2s
- ±8s
8. SlotEngine replace_partial()
9. StateManager.zoom_request()
✔ 第三阶段完成标准：
zoom不会回退9宫格
zoom不会空白
zoom至少稳定2次连续使用
🔴 4. 第四阶段：Optimize系统
🎯 目标：

全局重采样

10. OptimizeEngine
- global resample
- non-locked replace only
✔ 完成标准：
optimize不会破坏收藏
slot稳定更新
🟣 5. 第五阶段：系统稳定层（最关键）
🎯 目标：

防崩溃架构完成

11. EngineOrchestrator升级
- plan()
- priority system
- conflict resolution
12. StateManager统一commit
- best recompute
- UI sync
✔ 完成标准：
zoom + optimize 不冲突
UI不闪烁
state一致
🟢 6. 第六阶段：Clip系统（增强功能）
13. ClipEngine
- ffmpeg export
- segment clip
🧠 7. 最终稳定版本标准（v3.2）
✔ 系统必须满足：
Zoom稳定
Optimize稳定
收藏可控
Best稳定
UI无状态错乱
NAS级视频支持
📌 8. 开发节奏总结
Phase 1 → 能跑
Phase 2 → 能选
Phase 3 → 能zoom
Phase 4 → 能优化
Phase 5 → 不会崩
Phase 6 → 可导出
🚀 9. 核心原则总结

❗先稳定，再功能
❗先State，再Engine
❗先流程，再UI

📄 文档结束