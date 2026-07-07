🧱 一、整体架构图（系统级）

这是项目的“总脑图”：

                    ┌────────────────────┐
                    │      main.py       │
                    └─────────┬──────────┘
                              │
                              ↓
        ┌────────────────────────────────────┐
        │         UI LAYER (PySide6)        │
        │----------------------------------│
        │ MainWindow                       │
        │ ├── SegmentPanel (A/B/C/D/E)     │
        │ ├── GridPanel (9/16/25)          │
        │ ├── ZoomPanel (timeline refine)  │
        │ ├── ClipPanel (export)           │
        │ └── StatusBar (Best / state)     │
        └──────────────┬────────────────────┘
                       │ signals/slots
                       ↓
        ┌────────────────────────────────────┐
        │     STATE CONTROLLER LAYER        │
        │----------------------------------│
        │ AppStateManager                   │
        │ ├── SegmentState                  │
        │ ├── SlotState                     │
        │ ├── SelectionState                │
        │ ├── ZoomState                     │
        │ └── CacheState                    │
        └──────────────┬────────────────────┘
                       │ calls
                       ↓
        ┌────────────────────────────────────┐
        │       CORE ENGINE LAYER           │
        │----------------------------------│
        │ SamplingEngine                   │
        │ SlotEngine                       │
        │ ZoomEngine                       │
        │ OptimizeEngine                   │
        │ BestEngine                       │
        │ ClipEngine                       │
        └──────────────┬────────────────────┘
                       │ ffmpeg / decode
                       ↓
        ┌────────────────────────────────────┐
        │   VIDEO PROCESSING LAYER          │
        │----------------------------------│
        │ FFmpegEngine                     │
        │ FrameSampler                     │
        │ SegmentBuilder                   │
        │ CacheManager                     │
        └────────────────────────────────────┘
🧠 二、模块拆分（文件级结构）

这是现在项目应该稳定的目录结构：

CoverPicker/
│
├── main.py
├── config.py
├── requirements.txt
│
├── core/
│   ├── ffmpeg_engine.py
│   ├── frame_sampler.py
│   ├── segment_engine.py
│   ├── sampling_engine.py        ← ⭐核心新增
│   ├── slot_engine.py            ← ⭐核心新增
│   ├── zoom_engine.py            ← ⭐核心新增
│   ├── optimize_engine.py        ← ⭐核心新增
│   ├── best_engine.py            ← ⭐核心新增
│   ├── clip_engine.py            ← ⭐新增
│   ├── cache_manager.py
│   └── state_manager.py
│
├── gui/
│   ├── main_window.py
│   ├── segment_widget.py
│   ├── thumbnail_grid.py
│   ├── thumbnail_view.py
│   ├── zoom_widget.py
│   ├── timeline_widget.py
│   └── status_widget.py
│
├── data/
│   ├── cache/
│   ├── thumbnails/
│   └── clips/
│
└── docs/
    ├── PRODUCT.md
    ├── ROADMAP.md