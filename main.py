# CoverPicker v3.1 Main Scaffold Stage1
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from config import *
from core.persist_manager import PersistManager
from core.state_manager import StateManager
from core.orchestrator import EngineOrchestrator
from core.cache_manager import CacheManager

def init_core_system():
    print("=== CoverPicker v3.1 Stage1 Core Initializing ===")
    # 1 Persist DB
    persist = PersistManager(DB_PATH)
    persist.init_db()
    print("[OK] Persist Manager & SQLite DB initialized")

    # 2 Cache Manager
    cache_mgr = CacheManager()
    if CACHE_CLEAN_ON_START:
        cache_mgr.auto_clean_expired()
    print("[OK] Cache Manager ready, auto clean executed")

    # 3 Global State Manager
    state_mgr = StateManager(persist=persist, cache_mgr=cache_mgr)
    state_mgr.load_global_config()
    print("[OK] Global StateManager loaded saved config")

    # 4 Orchestrator Scheduler
    orchestrator = EngineOrchestrator(state_mgr=state_mgr)
    print("[OK] Engine Orchestrator ready")

    return persist, cache_mgr, state_mgr, orchestrator

if __name__ == "__main__":
    persist, cache_mgr, state_mgr, orchestrator = init_core_system()
    print("\n=== Core System Load Complete ===")
    print("You can import core modules for unit test now.")
    input("\nPress Enter to exit...")