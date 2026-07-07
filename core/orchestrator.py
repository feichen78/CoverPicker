# EngineOrchestrator 路径兼容修复完整版
import threading
import queue
import time
from pathlib import Path
from typing import Optional, Dict, Any
from config import OP_PRIORITY, LOCAL_SMB_MAX_WORKERS, WEBDAV_MAX_WORKERS
from core.state_manager import StateManager
from core.ffmpeg_engine import FFmpegEngine, is_network_path
from core.sampling_engine import SamplingEngine
from core.zoom_engine import ZoomEngine
from core.optimize_engine import OptimizeEngine
from core.segment_engine import SegmentEngine
from core.slot_engine import SlotEngine

class OrchestratorTask:
    def __init__(self, action_type: str, payload: Dict[str, Any]):
        self.action_type = action_type
        self.payload = payload
        self.priority = OP_PRIORITY.get(action_type, 5)
        self.completed = False
        self.result = None
        self.error = None
        self.transaction_lock = threading.Lock()

    def __lt__(self, other):
        return self.priority > other.priority

class EngineOrchestrator:
    def __init__(self, state_mgr: StateManager):
        self.state_mgr = state_mgr
        self.task_queue = queue.PriorityQueue()
        self._global_lock = threading.Lock()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

        # 绑定所有引擎实例
        self.ffmpeg = FFmpegEngine()
        self.cache_mgr = state_mgr.cache_mgr
        self.sampling = SamplingEngine(ffmpeg=self.ffmpeg, cache_mgr=self.cache_mgr)
        self.zoom = ZoomEngine(ffmpeg=self.ffmpeg, cache_mgr=self.cache_mgr)
        self.optimize = OptimizeEngine(sampling_engine=self.sampling)
        self.segment = SegmentEngine()
        self.slot = SlotEngine()

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
        with self._global_lock:
            try:
                task.transaction_lock.acquire()
                print(f"\n[ORCH START] 执行任务: {task.action_type}, payload={task.payload}")
                task.result = self._route_action(task.action_type, task.payload)
                task.completed = True
                print(f"[ORCH SUCCESS] {task.action_type} 执行完成, result={task.result}")
                self.state_mgr.commit_video_state()
            except Exception as e:
                import traceback
                err_stack = traceback.format_exc()
                task.error = str(e)
                task.completed = False
                print(f"\n[ORCH FATAL ERROR] 任务 {task.action_type} 崩溃！")
                print(f"错误信息: {str(e)}")
                print(f"完整堆栈:\n{err_stack}")
            finally:
                task.transaction_lock.release()

    def _get_worker_limit(self, video_path: str) -> int:
        if is_network_path(video_path):
            return WEBDAV_MAX_WORKERS
        return LOCAL_SMB_MAX_WORKERS

    def _route_action(self, action: str, payload: Dict):
        if action == "set_segment":
            seg_id = payload["seg_id"]
            self.state_mgr.set_segment(seg_id)
            return {"status": "ok", "seg_id": seg_id}

        elif action == "toggle_favorite":
            sid = payload["slot_id"]
            self.state_mgr.update_slot_favorite(sid)
            return {"status": "ok", "slot_id": sid, "new_best": self.state_mgr.state.best_slot_id}

        elif action == "toggle_lock":
            sid = payload["slot_id"]
            self.state_mgr.update_slot_lock(sid)
            return {"status": "ok", "slot_id": sid, "new_best": self.state_mgr.state.best_slot_id}

        elif action == "set_zoom_level":
            lv = payload["level"]
            self.state_mgr.set_zoom_level(lv)
            return {"status": "ok", "zoom_level": lv}

        elif action == "set_quality_score":
            sid = payload["slot_id"]
            score = payload["score"]
            self.state_mgr.set_slot_quality(sid)
            return {"status": "ok", "slot_id": sid, "score": score, "new_best": self.state_mgr.state.best_slot_id}

        elif action == "load_video":
            vid_path = payload["video_path"]
            # 统一标准化路径，解决正反斜杠+中文路径报错
            vid_path_fix = str(Path(vid_path).resolve())
            print(f"[LOAD_VIDEO] 原始路径: {vid_path}")
            print(f"[LOAD_VIDEO] 标准化后路径: {vid_path_fix}")
            print(f"[LOAD_VIDEO] 开始读取视频时长")
            duration = self.ffmpeg.get_video_duration(vid_path_fix)
            print(f"[LOAD_VIDEO] 获取时长成功: {duration}s")
            video = self.state_mgr.load_video(vid_path_fix, duration)
            segs = self.segment.build_segments(duration)
            video.segments = segs
            self.state_mgr.set_segment(segs[0].id)
            grid_size = self.state_mgr.state.global_grid_size
            print(f"[LOAD_VIDEO] 开始采样首分区，网格数量 {grid_size}")
            frames = self.sampling.sample_segment(video, segs[0], grid_size, gen_id=1)
            print(f"[LOAD_VIDEO] 采样完成，有效帧数量: {len(frames)}")
            self.state_mgr.clear_all_slots()
            start_id = self.state_mgr._slot_id_auto_inc
            slots, new_id = self.slot.create_slots(frames, segs[0].id, gen_id=1, start_slot_id=start_id)
            self.state_mgr._slot_id_auto_inc = new_id
            self.state_mgr.state.grid_slots = slots
            self.state_mgr.recompute_best()
            return {"status": "video_loaded", "hash": video.file_hash, "segments": [s.id for s in segs]}

        elif action == "zoom_sample":
            vid = payload["video"]
            base_ts = payload["base_ts"]
            base_seg = payload["base_seg"]
            lv = payload["zoom_level"]
            grid_size = self.state_mgr.state.global_grid_size
            gen_id = payload["gen_id"]
            new_frames = self.zoom.sample_zoom_frames(vid, base_ts, base_seg, grid_size, lv, gen_id)
            self.state_mgr.replace_unlocked_slots(new_frames, base_seg.id, gen_id)
            return {"status": "zoom_done", "frame_count": len(new_frames), "new_best": self.state_mgr.state.best_slot_id}

        elif action == "optimize_resample":
            vid = payload["video"]
            target_seg = payload["target_seg"]
            force_fav = payload.get("force_favorite_refresh", False)
            grid_size = self.state_mgr.state.global_grid_size
            gen_id = payload["gen_id"]
            new_frames = self.optimize.global_resample_current_segment(vid, target_seg, grid_size, gen_id, force_fav)
            self.state_mgr.replace_unlocked_slots(new_frames, target_seg.id, gen_id)
            return {"status": "optimize_done", "frame_count": len(new_frames), "new_best": self.state_mgr.state.best_slot_id}

        return {"status": "unhandled_action", "action": action}

    def wait_task(self, task: OrchestratorTask, timeout: float = 15.0):
        start = time.time()
        while not task.completed:
            if time.time() - start > timeout:
                raise TimeoutError(f"Task {task.action_type} execute timeout")
            time.sleep(0.05)
        if task.error:
            raise RuntimeError(f"任务执行失败: {task.error}")
        return task.result