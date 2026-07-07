# CoverPicker v3.1 Stage6 GUI入口完整main.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication
from config import *
from core.persist_manager import PersistManager
from core.state_manager import StateManager
from core.orchestrator import EngineOrchestrator
from core.cache_manager import CacheManager
from core.clip_engine import ClipEngine
from core.ffmpeg_engine import FFmpegEngine
from gui.main_window import MainWindow

def init_core_system():
    print("=== CoverPicker v3.1 Stage6 Full System Initializing ===")
    # 持久化数据库
    persist = PersistManager(DB_PATH)
    persist.init_db()
    print("[OK] Persist SQLite DB ready")

    # 缓存管理器
    cache_mgr = CacheManager(persist=persist)
    if CACHE_CLEAN_ON_START:
        cache_mgr.auto_clean_expired()
    print("[OK] Cache Manager loaded & cleaned")

    # 全局状态
    state_mgr = StateManager(persist=persist, cache_mgr=cache_mgr)
    state_mgr.load_global_config()
    print("[OK] Global StateManager restored config")

    # 全局调度器（内置全部引擎）
    orchestrator = EngineOrchestrator(state_mgr=state_mgr)
    print("[OK] Engine Orchestrator all engines bound")

    # 初始化Clip导出引擎
    ffmpeg = FFmpegEngine()
    _clip_engine = ClipEngine(ffmpeg=ffmpeg)
    print("[OK] Clip Export Engine ready")

    return persist, cache_mgr, state_mgr, orchestrator

if __name__ == "__main__":
    persist, cache_mgr, state_mgr, orchestrator = init_core_system()
    print("\n=== Core System Initialize Complete, Launch GUI ===")

    # 启动图形界面
    app = QApplication(sys.argv)
    win = MainWindow(orchestrator=orchestrator)
    win.show()
    sys.exit(app.exec())