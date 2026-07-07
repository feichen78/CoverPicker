🧱 CoverPicker v3.1 整体架构图（系统级）
统一分层规范，补充缺失 Orchestrator 文件、独立持久化存储层
plaintext
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
        │ ├── GridPanel (9/16/25切换)      │
        │ ├── ZoomPanel (timeline refine)  │
        │ ├── ClipPanel (export)           │
        │ └── StatusBar (Best / state标记) │
        └──────────────┬────────────────────┘
                       │ signals/slots
                       ↓
        ┌────────────────────────────────────┐
        │     STATE CONTROLLER LAYER        │
        │----------------------------------│
        │ AppStateManager（全局唯一状态源） │
        │ ├── SegmentState                 │
        │ ├── SlotState                    │
        │ ├── SelectionState               │
        │ ├── ZoomState                    │
        │ └── CacheState                   │
        └──────────────┬────────────────────┘
                       │ calls
                       ↓
        ┌────────────────────────────────────┐
        │ ENGINE ORCHESTRATOR LAYER         │
        │----------------------------------│
        │ EngineOrchestrator 统一调度入口   │
        │ 统一处理请求、冲突、事务锁、回滚  │
        └──────────────┬────────────────────┘
                       │ 分发执行
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
        └──────────────┬────────────────────┘
                       │ 缓存读写
                       ↓
        ┌────────────────────────────────────┐
        │     STORAGE LAYER（新增分层）     │
        │----------------------------------│
        │ CacheManager 缓存生命周期管理    │
        │ PersistManager SQLite持久化读写   │
        └────────────────────────────────────┘
🧠 二、模块拆分（文件级稳定目录结构）
CoverPicker/
│
├── main.py # 程序入口
├── config.py # 全局量化参数配置（阈值、缓存上限、分段规则）
├── requirements.txt # 完整依赖清单
│
├── core/
│ ├── orchestrator.py # EngineOrchestrator（新增，调度核心）
│ ├── state_manager.py # 全局唯一状态管理器
│ ├── persist_manager.py # SQLite 持久化读写
│ ├── ffmpeg_engine.py
│ ├── frame_sampler.py
│ ├── segment_engine.py
│ ├── sampling_engine.py
│ ├── slot_engine.py
│ ├── zoom_engine.py
│ ├── optimize_engine.py
│ ├── best_engine.py
│ ├── clip_engine.py
│ └── cache_manager.py
│
├── gui/
│ ├── main_window.py
│ ├── segment_widget.py
│ ├── thumbnail_grid.py
│ ├── thumbnail_view.py
│ ├── zoom_widget.py
│ ├── timeline_widget.py
│ └── status_widget.py
│
├── data/
│ ├── cache/ # 临时缩略图缓存，按视频 hash 隔离
│ ├── thumbnails/ # 用户手动收藏导出剧照临时存放
│ ├── clips/ # 导出视频片段临时目录
│ └── app_state.db # SQLite 持久化数据库
│
└── docs/
├── PRODUCT.md
├── ARCHITECTURE.md
├── DESIGN_PHILOSOPHY.md
├── ENGINE_SPEC.md
├── DEVELOPMENT_ROADMAP.md
├── ROADMAP.md
├── RUNTIME_FLOW.md
├── SYSTEM_SPEC.md
└── IDEAS.md
三、UI 层通信强制规范
UI 组件仅负责：渲染界面、捕获鼠标点击、发送标准化事件信号
UI 禁止直接修改状态、禁止直接调用引擎接口
所有用户操作信号统一发送至 StateManager，再经由 Orchestrator 调度引擎执行