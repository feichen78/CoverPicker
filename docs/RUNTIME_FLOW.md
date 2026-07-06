🧠 CoverPicker v3.1 Runtime Flow

本文档描述 CoverPicker 从用户操作到帧生成的完整运行时执行流程
用于统一所有 UI / Engine / State 行为，防止状态混乱

🧱 1. 系统启动流程（Startup Flow）
main.py
  ↓
MainWindow.__init__()
  ↓
StateManager.init()
  ↓
EngineOrchestrator.init()
  ↓
SlotEngine.init()
  ↓
SamplingEngine.init()
  ↓
Video list load (NAS scan)
  ↓
UI render video list
🎬 2. 打开视频流程（Video Load Flow）
User selects video
  ↓
StateManager.load_video(video_path)
  ↓
Video metadata parse (FFmpegEngine)
  ↓
SegmentEngine.build_segments()

    Example:
    A | B | C | D | E

  ↓
SamplingEngine.generate_initial_frames()
  ↓
SlotEngine.create_slots(frames)
  ↓
BestEngine.compute_initial_best()
  ↓
UI.render_grid(slots)
🧩 3. Segment 点击流程（A/B/C/D/E）
User clicks segment
  ↓
StateManager.set_current_segment(segment_id)
  ↓
EngineOrchestrator.plan(GENERATE_GRID)
  ↓
SamplingEngine.sample_segment(segment)

    - cross-check time distribution
    - avoid duplication
    - ensure diversity

  ↓
SlotEngine.replace_non_locked_slots(frames)
  ↓
BestEngine.recompute()
  ↓
UI.update_grid()
🖼️ 4. Slot 点击（收藏 / 取消收藏）
User clicks slot
  ↓
StateManager.update_slot_state(slot_id)
  ↓
SlotEngine.toggle_favorite(slot)

    if favorite:
        mark SELECTED
    else:
        mark UNSELECTED

  ↓
BestEngine.recompute()
  ↓
UI.update_slot_visual()
⭐ 5. Best 更新流程（核心显示逻辑）
Any slot state change
  ↓
StateManager.trigger_recompute_best()
  ↓
BestEngine.compute(slots)

Priority:

    LOCKED    > 1
    FAVORITE  > 2
    SCORE     > 3

  ↓
StateManager.update_best_slot()
  ↓
UI.update_best_display()
🔍 6. Zoom 流程（多尺度重采样）
User clicks Zoom
  ↓
StateManager.zoom_request(slot_id, level)
  ↓
EngineOrchestrator.plan(ZOOM)
  ↓
ZoomEngine.sample():

    Step 1: base frame time
    Step 2: expand time window
    Step 3: cross-segment sampling
    Step 4: diversity filter

  ↓
SlotEngine.replace_partial_slots(new_frames)

    ONLY replace:
        locked == False

  ↓
BestEngine.recompute()
  ↓
UI.partial_refresh()
⚙️ 7. Optimize 流程（全局重构）
User clicks Optimize
  ↓
StateManager.request_optimize()
  ↓
EngineOrchestrator.plan(OPTIMIZE)
  ↓
SamplingEngine.resample_global():

    - full video distribution sampling
    - segment-balanced selection
    - uniqueness enforcement

  ↓
SlotEngine.replace_non_locked_slots()
  ↓
BestEngine.recompute()
  ↓
UI.refresh_grid()
❤️ 8. 收藏 / 保存流程（Favorite System）
User toggles favorite
  ↓
SlotEngine.update_state(FAVORITE)
  ↓
CacheManager.persist_state()
  ↓
StateManager.sync()
  ↓
UI.update_icon(♥ / ☆)
🎞️ 9. 视频片段导出流程（Clip Engine）
User selects "Save Clip"
  ↓
StateManager.clip_request(start_time, duration)
  ↓
EngineOrchestrator.plan(CLIP)
  ↓
ClipEngine.ffmpeg_extract():

    ffmpeg -ss start -t duration -i input.mp4

  ↓
Save to:

    StillClip/<video_name>/<index>.mp4

  ↓
StateManager.confirm_export()
  ↓
UI.show_success()
🧠 10. Engine 调度统一入口（关键）

所有操作必须经过：

UI Action
  ↓
StateManager
  ↓
EngineOrchestrator
  ↓
Engine Execution
  ↓
SlotEngine update
  ↓
StateManager commit
  ↓
UI refresh
🚫 11. 禁止规则（稳定性核心）
❌ 禁止1：Engine直接操作UI
WRONG:
ZoomEngine → UI update
❌ 禁止2：Slot绕过StateManager
WRONG:
SlotEngine modifies UI state directly
❌ 禁止3：局部状态更新
WRONG:
only update best without slot sync
🧱 12. 状态一致性原则（SSOT）

StateManager 是唯一事实源

Slot / Frame / Best / Zoom / Optimize
        ↓
     MUST sync
        ↓
   StateManager
📊 13. 系统运行总结
CoverPicker运行本质：

一个“基于视频分区 + 多尺度采样 + 人类筛选决策”的系统

核心循环：
Sample → View → Select → Refine → Lock → Export
🚀 14. v3.1设计目标确认

✔ NAS级视频批处理
✔ 多分区浏览（A/B/C/D/E）
✔ 多尺度Zoom采样
✔ Slot锁定机制
✔ 收藏/导出体系
✔ 全状态一致性

📌 文档结束