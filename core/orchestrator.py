# EngineOrchestrator: unified request scheduler & transaction lock
import threading
import queue
import time
from typing import Optional, Dict, Any
from config import OP_PRIORITY
from core.state_manager import StateManager

class OrchestratorTask:
    def __init__(self, action_type: str, payload: Dict[str, Any]):
        self.action_type = action_type
        self.payload = payload
        self.priority = OP_PRIORITY.get(action_type, 5)
        self.completed = False
        self.result = None
        self.error = None

    def __lt__(self, other):
        return self.priority > other.priority

class EngineOrchestrator:
    def __init__(self, state_mgr: StateManager):
        self.state_mgr = state_mgr
        self.task_queue = queue.PriorityQueue()
        self._lock = threading.Lock()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def submit_task(self, action_type: str, payload: Dict[str, Any]) -> OrchestratorTask:
        task = OrchestratorTask(action_type, payload)
        self.task_queue.put(task)
        return task

    def _worker_loop(self):
        while True:
            task = self.task_queue.get()
            self._execute_task(task)
            self.task_queue.task_done()

    def _execute_task(self, task: OrchestratorTask):
        with self._lock:
            try:
                task.result = self._route_action(task.action_type, task.payload)
                task.completed = True
            except Exception as e:
                task.error = str(e)
                task.completed = False

    def _route_action(self, action: str, payload: Dict):
        # Stage1 only route base events, engine logic will be called later
        if action == "set_segment":
            seg_id = payload["seg_id"]
            self.state_mgr.set_segment(seg_id)
            return {"status": "ok", "seg_id": seg_id}
        elif action == "toggle_favorite":
            sid = payload["slot_id"]
            self.state_mgr.update_slot_favorite(sid)
            return {"status": "ok", "slot_id": sid}
        elif action == "toggle_lock":
            sid = payload["slot_id"]
            self.state_mgr.update_slot_lock(sid)
            return {"status": "ok", "slot_id": sid}
        elif action == "set_zoom_level":
            lv = payload["level"]
            self.state_mgr.set_zoom_level(lv)
            return {"status": "ok", "zoom_level": lv}
        return {"status": "unhandled_action", "action": action}

    def wait_task(self, task: OrchestratorTask, timeout: float = 10.0):
        start = time.time()
        while not task.completed:
            if time.time() - start > timeout:
                raise TimeoutError(f"Task {task.action_type} execute timeout")
            time.sleep(0.05)
        return task.result