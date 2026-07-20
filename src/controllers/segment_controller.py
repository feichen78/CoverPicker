# src/controllers/segment_controller.py
# 修改：收藏截图保存到视频所在目录的 [视频名]_covers 子目录
# 修改：渐进式加载（占位图），每生成一张截图后刷新界面
# 修复：提取帧失败时增加重试机制，减少占位图
# 修改：清理缓存功能改为删除所有历史 CoverPicker_* 临时目录，统计汇总所有缓存

import os, asyncio, random, tempfile, shutil, logging, json
from typing import Dict, List, Set, Tuple, Optional, Any
from datetime import timedelta
from dataclasses import dataclass
from src.database import Database
from src.video_scanner import get_video_duration, calculate_segments, extract_frame, extract_frames_batch_fast
logger = logging.getLogger(__name__)

@dataclass
class Action: type: str; video_id: int; seg_label: str; timestamp_ms: int; old_state: bool; new_state: bool

class SegmentController:
    def __init__(self):
        print("[DEBUG] SegmentController __init__ 开始")
        self.db = Database()
        self.video_path: Optional[str] = None
        self.video_id: Optional[int] = None
        self.duration: float = 0.0
        self.video_name: str = ""
        self.num_segments: int = 5
        self.segments: List[Tuple[str, float, float]] = []
        self.current_seg_index: int = 0
        self.screenshots: Dict[str, List[dict]] = {}
        self.favorites: List[dict] = []
        self.loaded_segments: Set[str] = set()
        self.density: int = 9
        self.skip_ratio: float = 0.15
        self.excluded_ranges: List[Tuple[float, float]] = []
        self.temp_dir: str = tempfile.mkdtemp(prefix="CoverPicker_")
        self.export_base: str = os.path.join(os.getcwd(), "StillPic")
        self._load_task: Optional[asyncio.Task] = None
        self.undo_stack: List[Action] = []
        self.redo_stack: List[Action] = []
        self._is_undo_or_redo: bool = False
        self._ffmpeg_semaphore = asyncio.Semaphore(3)
        self._on_data_changed: Optional[callable] = None
        self._on_progress_update: Optional[callable] = None
        print("[DEBUG] SegmentController __init__ 完成")

    def set_data_changed_callback(self, callback): self._on_data_changed = callback
    def set_progress_callback(self, callback): self._on_progress_update = callback
    def _notify_data_changed(self):
        if self._on_data_changed: self._on_data_changed()
    def _notify_progress(self, message: str):
        if self._on_progress_update: self._on_progress_update(message)

    def _get_favorites_dir(self) -> str:
        if not self.video_path:
            return self.temp_dir
        video_dir = os.path.dirname(self.video_path)
        video_name = os.path.splitext(os.path.basename(self.video_path))[0]
        favorites_dir = os.path.join(video_dir, f"{video_name}_covers")
        os.makedirs(favorites_dir, exist_ok=True)
        return favorites_dir

    def _get_favorite_path(self, seg_label: str, time_sec: float, suffix: str = "") -> str:
        favorites_dir = self._get_favorites_dir()
        if suffix:
            filename = f"fav_{seg_label}_{time_sec:.2f}_{suffix}.jpg"
        else:
            filename = f"fav_{seg_label}_{time_sec:.2f}.jpg"
        return os.path.join(favorites_dir, filename)

    def set_num_segments(self, num: int):
        if num < 3: num = 3
        elif num > 7: num = 7
        if self.num_segments != num and self.video_path and self.duration > 0:
            self.num_segments = num
            self.segments = calculate_segments(self.duration, self.num_segments)
            self.screenshots = {}
            self.loaded_segments = set()
            self.current_seg_index = 0
            self._clear_history()
            self._notify_data_changed()
    def get_num_segments(self) -> int: return self.num_segments
    def apply_custom_segments(self, segments: List[Tuple[str, float, float]]):
        if not segments or len(segments) < 2: return
        for label, start, end in segments:
            if start >= end or start < 0 or end > self.duration: return
        self.num_segments = -1
        self.segments = segments
        self.screenshots = {}
        self.loaded_segments = set()
        self.current_seg_index = 0
        self._clear_history()
        self._notify_data_changed()
        if self.video_path:
            asyncio.create_task(self.load_segment(0, restore_locks=True, randomize=False))
    def get_excluded_ranges(self) -> List[Tuple[float, float]]: return self.excluded_ranges.copy()
    def set_excluded_ranges(self, ranges: List[Tuple[float, float]], save: bool = True):
        self.excluded_ranges = ranges.copy()
        self._notify_data_changed()
        if save and self.video_id and self.video_path and self.segments:
            seg_label = self.segments[self.current_seg_index][0]
            self.db.update_segment_state(self.video_id, seg_label, excluded_ranges=ranges)
            logger.info(f"排除区间已保存到数据库: {ranges}")
    def load_excluded_ranges_from_db(self):
        if not self.video_id or not self.segments: return
        seg_label = self.segments[self.current_seg_index][0]
        seg_state = self.db.get_segment_state(self.video_id, seg_label)
        if seg_state and seg_state.get('excluded_ranges'):
            self.excluded_ranges = seg_state['excluded_ranges']
            logger.info(f"从数据库加载排除区间: {self.excluded_ranges}")
        else: self.excluded_ranges = []
    async def load_video(self, video_path: str) -> bool:
        print(f"[DEBUG] load_video 被调用: {video_path}")
        if self._load_task and not self._load_task.done(): self._load_task.cancel()
        self.video_path = video_path
        self.video_name = os.path.basename(video_path)
        duration = get_video_duration(video_path)
        if duration is None:
            print("[DEBUG] load_video 失败: 无法获取时长")
            return False
        self.duration = duration
        if self.num_segments == -1: self.num_segments = 5
        self.segments = calculate_segments(duration, self.num_segments)
        print(f"[DEBUG] load_video: 分区数={len(self.segments)}")
        file_name = os.path.basename(video_path)
        file_size = int(os.path.getsize(video_path))
        modified_time = int(os.path.getmtime(video_path))
        self.video_id = self.db.get_or_create_video(video_path, file_name, int(duration), "", file_size, modified_time)
        for label, start, end in self.segments:
            self.db.get_or_create_segment(self.video_id, label, int(start), int(end))
        self.load_excluded_ranges_from_db()
        self.favorites = []
        self._restore_favorites_from_db()
        self.screenshots = {}
        self.loaded_segments = set()
        self.current_seg_index = 0
        self._clear_history()
        self._load_task = asyncio.create_task(self._load_segment(0, restore_locks=True, randomize=False))
        await self._load_task
        self._load_task = None
        self._restore_favorites_to_screenshots()
        if self.loaded_segments: self.db.update_video_state(self.video_id, is_viewed=True)
        self._notify_data_changed()
        print("[DEBUG] load_video 完成")
        return True
    async def load_segment(self, seg_idx: int, restore_locks: bool = True, randomize: bool = False):
        print(f"[DEBUG] ========== load_segment 被调用: seg_idx={seg_idx} ==========")
        print(f"[DEBUG] self.video_path={self.video_path}")
        print(f"[DEBUG] self.segments={self.segments}")
        print(f"[DEBUG] self.current_seg_index={self.current_seg_index}")
        print(f"[DEBUG] self._load_task={self._load_task}")
        if not self.video_path or not self.segments:
            print(f"[DEBUG] load_segment 返回: video_path={self.video_path}, segments={self.segments}")
            return
        if seg_idx < 0 or seg_idx >= len(self.segments):
            print(f"[DEBUG] load_segment 无效索引: seg_idx={seg_idx}, len={len(self.segments)}")
            return
        if self._load_task and not self._load_task.done():
            print(f"[DEBUG] 取消当前加载任务")
            self._load_task.cancel()
            try:
                await self._load_task
            except asyncio.CancelledError:
                print("[DEBUG] 当前任务已取消")
            self._load_task = None
            self.screenshots = {}
            self.loaded_segments = set()
            self._notify_data_changed()
        self.current_seg_index = seg_idx
        print(f"[DEBUG] 当前分区索引已更新为: {seg_idx}")
        self.load_excluded_ranges_from_db()
        self._load_task = asyncio.create_task(self._load_segment(seg_idx, restore_locks, randomize))
        print(f"[DEBUG] 新加载任务已创建，等待完成...")
        await self._load_task
        print(f"[DEBUG] 加载任务完成")
        self._load_task = None
        self._notify_data_changed()

    def _is_time_excluded(self, t: float) -> bool:
        for low, high in self.excluded_ranges:
            if low <= t <= high:
                return True
        return False

    async def _load_segment(self, seg_idx: int, restore_locks: bool = True, randomize: bool = False):
        print(f"[DEBUG] ========== _load_segment 开始: seg_idx={seg_idx} ==========")
        if not self.video_path:
            print("[DEBUG] _load_segment 返回: video_path 为空"); return
        if not self.segments:
            print("[DEBUG] _load_segment 返回: segments 为空"); return
        if seg_idx < 0 or seg_idx >= len(self.segments):
            print(f"[DEBUG] _load_segment 返回: seg_idx={seg_idx} 超出范围"); return
        current_task = asyncio.current_task()
        if current_task and current_task.cancelled():
            print(f"[DEBUG] 分段 {seg_idx} 加载被取消"); return
        label, start, end = self.segments[seg_idx]
        print(f"[DEBUG] 加载分区 {label}: {start:.1f}s - {end:.1f}s")
        seg_key = label
        if seg_key in self.loaded_segments and not randomize:
            print(f"[DEBUG] 分区 {label} 已加载，但继续执行加载（刷新数据）")
        offset = (end - start) * self.skip_ratio
        start_cropped = start + offset; end_cropped = end - offset
        if end_cropped <= start_cropped: start_cropped = start; end_cropped = end
        count = self.density
        old_items = self.screenshots.get(seg_key, [])
        new_times = [random.uniform(start_cropped, end_cropped) for _ in range(count)]
        new_times.sort()
        valid_times = []
        attempts = 0
        max_attempts = 1000 * count
        sample_t = random.uniform(start_cropped, end_cropped)
        if self._is_time_excluded(sample_t):
            all_excluded = True
            for _ in range(10):
                t = random.uniform(start_cropped, end_cropped)
                if not self._is_time_excluded(t):
                    all_excluded = False
                    break
            if all_excluded:
                print(f"[DEBUG] 分区 {label} 全部被排除区间覆盖，不生成截图")
                self.screenshots[seg_key] = []
                self.loaded_segments.add(label)
                self._notify_progress(f"{label} 全部被排除，无截图")
                self._notify_data_changed()
                return
        for t in new_times:
            if not self._is_time_excluded(t):
                valid_times.append(t)
        while len(valid_times) < count and attempts < max_attempts:
            t = random.uniform(start_cropped, end_cropped)
            if not self._is_time_excluded(t):
                valid_times.append(t)
            attempts += 1
        if len(valid_times) > count:
            valid_times = valid_times[:count]
        valid_times.sort()
        new_times = valid_times
        count = len(new_times)
        new_items = []; reused_count = 0; total = len(new_times)
        old_items_sorted = sorted(old_items, key=lambda x: x['time'])
        old_times = [item['time'] for item in old_items_sorted]
        placeholder_items = []
        for t in new_times:
            placeholder_items.append({'time': t, 'path': None, 'locked': False, 'favorite': False, 'exported': False})
        self.screenshots[seg_key] = placeholder_items
        self._notify_data_changed()
        for idx, t in enumerate(new_times):
            if current_task and current_task.cancelled():
                print(f"[DEBUG] 分段加载被取消: idx={idx}"); return
            matched = None; best_match_idx = -1
            for i, old_t in enumerate(old_times):
                if abs(old_t - t) < 1.0:
                    best_match_idx = i; break
            if best_match_idx >= 0:
                matched = old_items_sorted[best_match_idx]
            if matched and matched.get('path') and os.path.exists(matched['path']) and os.path.getsize(matched['path']) > 0:
                new_items.append({'time': t, 'path': matched['path'], 'locked': matched.get('locked', False), 'favorite': matched.get('favorite', False), 'exported': matched.get('exported', False)})
                reused_count += 1
                if seg_key not in self.screenshots:
                    placeholder_items = []
                    for tmp_t in new_times:
                        placeholder_items.append({'time': tmp_t, 'path': None, 'locked': False, 'favorite': False, 'exported': False})
                    self.screenshots[seg_key] = placeholder_items
                self.screenshots[seg_key][idx] = new_items[-1]
                self._notify_data_changed()
                continue
            success = False
            temp_path = None
            retry_t = t
            for retry in range(3):
                temp_path = os.path.join(self.temp_dir, f"seg_{label}_{retry_t:.2f}_{retry}.jpg")
                self._notify_progress(f"正在生成 {label} 第 {idx+1}/{total} 张 @ {retry_t:.2f}s (尝试{retry+1})")
                try:
                    async with self._ffmpeg_semaphore:
                        success = await asyncio.to_thread(extract_frame, self.video_path, retry_t, temp_path, retries=1)
                    if success and os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                        break
                    else:
                        offset = random.uniform(-1.0, 1.0)
                        retry_t = t + offset
                        retry_t = max(start_cropped, min(end_cropped, retry_t))
                        while self._is_time_excluded(retry_t):
                            offset = random.uniform(-1.0, 1.0)
                            retry_t = t + offset
                            retry_t = max(start_cropped, min(end_cropped, retry_t))
                except asyncio.CancelledError:
                    if os.path.exists(temp_path):
                        try: os.remove(temp_path)
                        except: pass
                    raise
            if success:
                new_items.append({'time': retry_t, 'path': temp_path, 'locked': False, 'favorite': False, 'exported': False})
            else:
                logger.warning(f"分区 {label} 时间点 {t:.2f}s 提取失败，保留占位图")
                new_items.append({'time': t, 'path': None, 'locked': False, 'favorite': False, 'exported': False})
            if seg_key not in self.screenshots:
                placeholder_items = []
                for tmp_t in new_times:
                    placeholder_items.append({'time': tmp_t, 'path': None, 'locked': False, 'favorite': False, 'exported': False})
                self.screenshots[seg_key] = placeholder_items
            self.screenshots[seg_key][idx] = new_items[-1]
            self._notify_data_changed()
        if current_task and current_task.cancelled():
            print(f"[DEBUG] 分段加载完成后被取消"); return
        self.screenshots[seg_key] = new_items
        self.loaded_segments.add(label)
        self._restore_favorites_to_screenshots()
        self._notify_progress(f"{label} 分段加载完成 ({len(new_items)} 张, 复用 {reused_count} 张)")
        self._notify_data_changed()
        print(f"[DEBUG] ========== _load_segment 完成: {label} ==========")

    def _save_favorite_to_nas(self, seg_label: str, time_sec: float, source_path: str) -> str:
        dest_path = self._get_favorite_path(seg_label, time_sec)
        try:
            shutil.copy2(source_path, dest_path)
            logger.info(f"收藏截图已保存到NAS: {dest_path}")
            return dest_path
        except Exception as e:
            logger.error(f"保存收藏截图到NAS失败: {e}")
            fallback_path = os.path.join(self.temp_dir, os.path.basename(source_path))
            shutil.copy2(source_path, fallback_path)
            return fallback_path

    def favorite_selected(self, seg_label: str, positions: List[int]) -> Tuple[int, int]:
        if self._is_undo_or_redo: return self._favorite_selected_impl(seg_label, positions, record_history=False)
        return self._favorite_selected_impl(seg_label, positions, record_history=True)
    def _favorite_selected_impl(self, seg_label: str, positions: List[int], record_history: bool) -> Tuple[int, int]:
        items = self.screenshots.get(seg_label, []); processed_keys = set(); added_count = 0; skipped_count = 0
        for pos in positions:
            if pos >= len(items): continue
            item = items[pos]; key = (self.video_path, seg_label, item['time'])
            if key in processed_keys: skipped_count += 1; continue
            processed_keys.add(key)
            if not item.get('favorite', False):
                old_state = False; new_state = True; item['favorite'] = True
                if self.video_id:
                    timestamp_ms = int(item['time'] * 1000)
                    if not self.db.is_favorite(self.video_id, seg_label, timestamp_ms):
                        nas_path = self._save_favorite_to_nas(seg_label, item['time'], item['path'])
                        self.db.add_favorite(self.video_id, seg_label, timestamp_ms, nas_path, os.path.basename(nas_path), item.get('exported', False))
                self.favorites.append({'video_path': self.video_path, 'segment': seg_label, 'time': item['time'], 'path': nas_path if self.video_id else item['path'], 'exported': item.get('exported', False)})
                added_count += 1
                if record_history: self._push_action(Action('favorite', self.video_id, seg_label, timestamp_ms, old_state, new_state))
        if added_count > 0: self._save_state_to_db(); self._notify_data_changed()
        return added_count, skipped_count

    def unfavorite_selected(self, seg_label: str, positions: List[int]) -> int:
        if self._is_undo_or_redo: return self._unfavorite_selected_impl(seg_label, positions, record_history=False)
        return self._unfavorite_selected_impl(seg_label, positions, record_history=True)
    def _unfavorite_selected_impl(self, seg_label: str, positions: List[int], record_history: bool) -> int:
        items = self.screenshots.get(seg_label, []); removed_count = 0
        for pos in positions:
            if pos >= len(items): continue
            item = items[pos]
            if item.get('favorite', False):
                old_state = True; new_state = False; item['favorite'] = False
                if self.video_id:
                    timestamp_ms = int(item['time'] * 1000)
                    self.db.remove_favorite(self.video_id, seg_label, timestamp_ms)
                self.favorites = [f for f in self.favorites if not (f.get('video_path')==self.video_path and f.get('segment')==seg_label and abs(f.get('time',0)-item['time'])<0.01)]
                removed_count += 1
                if record_history: self._push_action(Action('unfavorite', self.video_id, seg_label, timestamp_ms, old_state, new_state))
        if removed_count > 0: self._save_state_to_db(); self._notify_data_changed()
        return removed_count

    def get_current_favorites(self) -> List[dict]: return [f for f in self.favorites if f.get('video_path') == self.video_path]

    def export_selected(self, seg_label: str, positions: List[int], export_dir: Optional[str] = None) -> Tuple[int, List[Tuple[str, str]]]:
        items = self.screenshots.get(seg_label, []); export_paths = []
        for pos in positions:
            if pos >= len(items): continue
            item = items[pos]
            if item.get('path') and os.path.exists(item['path']): export_paths.append((item['time'], item['path'], pos))
        if not export_paths: return 0, []
        if export_dir is None:
            video_name = os.path.splitext(os.path.basename(self.video_path))[0]
            export_dir = os.path.join(self.export_base, video_name)
        else:
            video_name = os.path.splitext(os.path.basename(self.video_path))[0]
            export_dir = os.path.join(export_dir, video_name)
        os.makedirs(export_dir, exist_ok=True)
        exported = 0; exported_list = []
        for time_sec, src_path, pos in export_paths:
            dest_name = f"cover_{time_sec:.2f}s.jpg"; dest_path = os.path.join(export_dir, dest_name)
            try:
                shutil.copy2(src_path, dest_path); exported += 1; exported_list.append((time_sec, dest_path))
                items[pos]['exported'] = True
                if self.video_id:
                    timestamp_ms = int(time_sec * 1000)
                    self.db.update_favorite_exported(self.video_id, seg_label, timestamp_ms)
            except: pass
        if exported > 0: self._save_state_to_db(); self._notify_data_changed()
        return exported, exported_list

    def replace_screenshot(self, seg_label: str, pos: int, new_time: float, new_path: str, old_time: float) -> bool:
        items = self.screenshots.get(seg_label, [])
        if pos >= len(items): return False
        original = items[pos]
        locked = original.get('locked', False); favorite = original.get('favorite', False); exported = original.get('exported', False)
        new_temp_path = os.path.join(self.temp_dir, f"seg_{seg_label}_{new_time:.2f}_replaced.jpg")
        try: shutil.copy2(new_path, new_temp_path)
        except: return False
        original['time'] = new_time; original['path'] = new_temp_path; original['locked'] = locked; original['favorite'] = favorite; original['exported'] = exported
        if favorite and self.video_id:
            old_timestamp_ms = int(old_time * 1000); new_timestamp_ms = int(new_time * 1000)
            self.db.remove_favorite(self.video_id, seg_label, old_timestamp_ms)
            nas_path = self._save_favorite_to_nas(seg_label, new_time, new_temp_path)
            self.db.add_favorite(self.video_id, seg_label, new_timestamp_ms, nas_path, os.path.basename(nas_path), is_exported=exported)
            for fav in self.favorites:
                if (fav.get('video_path')==self.video_path and fav.get('segment')==seg_label and abs(fav.get('time',0)-old_time)<0.01):
                    fav['time'] = new_time; fav['path'] = nas_path; fav['exported'] = exported; break
        self._notify_data_changed(); return True

    def replace_favorite_screenshot(self, seg_label: str, old_time: float, new_time: float, new_path: str) -> bool:
        print(f"[DEBUG] replace_favorite_screenshot: seg_label={seg_label}, old_time={old_time:.2f}, new_time={new_time:.2f}")
        fav_item = None; fav_index = -1
        for i, fav in enumerate(self.favorites):
            if (fav.get('segment') == seg_label and abs(fav.get('time', 0) - old_time) < 0.01):
                fav_item = fav; fav_index = i; break
        if fav_item is None:
            print(f"[DEBUG] replace_favorite_screenshot: 未找到收藏项")
            return False
        nas_path = self._save_favorite_to_nas(seg_label, new_time, new_path)
        old_timestamp_ms = int(old_time * 1000); new_timestamp_ms = int(new_time * 1000)
        exported = fav_item.get('exported', False)
        fav_item['time'] = new_time; fav_item['path'] = nas_path
        if self.video_id:
            self.db.remove_favorite(self.video_id, seg_label, old_timestamp_ms)
            self.db.add_favorite(self.video_id, seg_label, new_timestamp_ms, nas_path, os.path.basename(nas_path), is_exported=exported)
            logger.info(f"[DEBUG] 数据库已更新: 替换收藏截图")
        items = self.screenshots.get(seg_label, [])
        for item in items:
            if abs(item.get('time', 0) - old_time) < 0.01:
                item['favorite'] = True; item['path'] = nas_path; item['time'] = new_time; break
        self._notify_data_changed()
        print(f"[DEBUG] replace_favorite_screenshot: 替换成功")
        return True

    def lock_selected(self, seg_label: str, positions: List[int]) -> int:
        if self._is_undo_or_redo: return self._lock_selected_impl(seg_label, positions, record_history=False)
        return self._lock_selected_impl(seg_label, positions, record_history=True)
    def _lock_selected_impl(self, seg_label: str, positions: List[int], record_history: bool) -> int:
        items = self.screenshots.get(seg_label, []); count = 0
        for pos in positions:
            if pos < len(items):
                item = items[pos]
                if not item.get('locked', False):
                    old_state = False; new_state = True; item['locked'] = True; count += 1
                    if record_history and self.video_id:
                        timestamp_ms = int(item['time'] * 1000)
                        self._push_action(Action('lock', self.video_id, seg_label, timestamp_ms, old_state, new_state))
        if count > 0: self._notify_data_changed()
        return count
    def unlock_selected(self, seg_label: str, positions: List[int]) -> int:
        if self._is_undo_or_redo: return self._unlock_selected_impl(seg_label, positions, record_history=False)
        return self._unlock_selected_impl(seg_label, positions, record_history=True)
    def _unlock_selected_impl(self, seg_label: str, positions: List[int], record_history: bool) -> int:
        items = self.screenshots.get(seg_label, []); count = 0
        for pos in positions:
            if pos < len(items):
                item = items[pos]
                if item.get('locked', False):
                    old_state = True; new_state = False; item['locked'] = False; count += 1
                    if record_history and self.video_id:
                        timestamp_ms = int(item['time'] * 1000)
                        self._push_action(Action('unlock', self.video_id, seg_label, timestamp_ms, old_state, new_state))
        if count > 0: self._notify_data_changed()
        return count
    def _push_action(self, action: Action):
        self.undo_stack.append(action); self.redo_stack.clear()
        if len(self.undo_stack) > 100: self.undo_stack = self.undo_stack[-100:]
    def _clear_history(self): self.undo_stack.clear(); self.redo_stack.clear()
    def can_undo(self) -> bool: return len(self.undo_stack) > 0
    def can_redo(self) -> bool: return len(self.redo_stack) > 0
    def undo(self):
        if not self.can_undo(): return
        action = self.undo_stack.pop(); self._execute_action(action, reverse=True); self.redo_stack.append(action); self._save_state_to_db(); self._notify_data_changed()
    def redo(self):
        if not self.can_redo(): return
        action = self.redo_stack.pop(); self._execute_action(action, reverse=False); self.undo_stack.append(action); self._save_state_to_db(); self._notify_data_changed()
    def _execute_action(self, action: Action, reverse: bool):
        self._is_undo_or_redo = True
        try:
            if action.type == 'favorite':
                if reverse: self._apply_favorite_state(action, False)
                else: self._apply_favorite_state(action, True)
            elif action.type == 'unfavorite':
                if reverse: self._apply_favorite_state(action, True)
                else: self._apply_favorite_state(action, False)
            elif action.type == 'lock':
                if reverse: self._apply_lock_state(action, False)
                else: self._apply_lock_state(action, True)
            elif action.type == 'unlock':
                if reverse: self._apply_lock_state(action, True)
                else: self._apply_lock_state(action, False)
        finally: self._is_undo_or_redo = False
    def _apply_favorite_state(self, action: Action, set_favorite: bool):
        items = self.screenshots.get(action.seg_label, [])
        target_time = action.timestamp_ms / 1000.0
        for item in items:
            if abs(item['time'] - target_time) < 0.01:
                item['favorite'] = set_favorite; break
        if set_favorite:
            if not self.db.is_favorite(action.video_id, action.seg_label, action.timestamp_ms):
                thumb_path = ""
                for item in items:
                    if abs(item['time'] - target_time) < 0.01:
                        thumb_path = item.get('path', ''); break
                nas_path = self._save_favorite_to_nas(action.seg_label, target_time, thumb_path)
                self.db.add_favorite(action.video_id, action.seg_label, action.timestamp_ms, nas_path, os.path.basename(nas_path), is_exported=False)
                self.favorites.append({'video_path': self.video_path, 'segment': action.seg_label, 'time': target_time, 'path': nas_path, 'exported': False})
        else:
            self.db.remove_favorite(action.video_id, action.seg_label, action.timestamp_ms)
            self.favorites = [f for f in self.favorites if not (f.get('video_path')==self.video_path and f.get('segment')==action.seg_label and abs(f.get('time',0)-target_time)<0.01)]
    def _apply_lock_state(self, action: Action, set_locked: bool):
        items = self.screenshots.get(action.seg_label, [])
        target_time = action.timestamp_ms / 1000.0
        for item in items:
            if abs(item['time'] - target_time) < 0.01:
                item['locked'] = set_locked; break
    async def refresh_unlocked(self, seg_idx: int) -> int:
        if not self.video_path or not self.segments: return 0
        seg_label, start, end = self.segments[seg_idx]
        offset = (end - start) * self.skip_ratio
        start_cropped = start + offset; end_cropped = end - offset
        if end_cropped <= start_cropped: start_cropped = start; end_cropped = end
        items = self.screenshots.get(seg_label, [])
        unlocked_positions = [i for i, item in enumerate(items) if not item.get('locked', False)]
        if not unlocked_positions: return 0
        locked_times = [item['time'] for item in items if item.get('locked', False)]
        refreshed = 0; total = len(unlocked_positions)
        for idx, pos in enumerate(unlocked_positions):
            self._notify_progress(f"刷新未锁定 {idx+1}/{total}")
            for _ in range(20):
                t = random.uniform(start_cropped, end_cropped)
                if self._is_time_excluded(t):
                    continue
                if all(abs(t - lt) > 0.5 for lt in locked_times):
                    break
            temp_path = os.path.join(self.temp_dir, f"seg_{seg_label}_{t:.2f}_new.jpg")
            try:
                async with self._ffmpeg_semaphore:
                    success = await asyncio.to_thread(extract_frame, self.video_path, t, temp_path, retries=1)
                if success:
                    items[pos]['time'] = t; items[pos]['path'] = temp_path; items[pos]['locked'] = False; refreshed += 1
            except asyncio.CancelledError: raise
        if refreshed > 0: self._notify_data_changed()
        self._notify_progress(f"刷新完成: {refreshed} 张")
        return refreshed
    async def reset_segment(self, seg_idx: int):
        seg_label = self.segments[seg_idx][0]
        self.screenshots[seg_label] = []
        self._clear_history()
        await self._load_segment(seg_idx, restore_locks=False, randomize=True)
        self._notify_data_changed()
    def get_video_state_icon(self, video_path: str) -> str:
        video_data = self.db.get_video_by_path(video_path)
        if not video_data: return ""
        if video_data.get('is_starred', 0): return "⭐"
        elif video_data.get('is_exported', 0): return "✅"
        elif video_data.get('is_viewed', 0): return "👁️"
        return ""
    def get_video_state(self, video_path: str) -> dict: return self.db.get_video_by_path(video_path)
    def get_video_name(self) -> str: return self.video_name
    def get_video_path(self) -> Optional[str]: return self.video_path
    def get_video_id(self) -> Optional[int]: return self.video_id
    def get_duration(self) -> float: return self.duration
    def get_segments(self) -> List[Tuple[str, float, float]]: return self.segments
    def get_segment_count(self) -> int: return len(self.segments)
    def get_segment_items(self, seg_label: str) -> List[dict]: return self.screenshots.get(seg_label, [])
    def get_current_segment(self) -> Optional[Tuple[str, float, float]]:
        if 0 <= self.current_seg_index < len(self.segments): return self.segments[self.current_seg_index]
        return None
    def get_favorites_count(self) -> int:
        if not self.video_path: return 0
        return sum(1 for f in self.favorites if f.get('video_path') == self.video_path)
    def get_export_base(self) -> str: return self.export_base
    def get_temp_dir(self) -> str: return self.temp_dir
    def get_loaded_segments(self) -> Set[str]: return self.loaded_segments
    def is_segment_loaded(self, seg_label: str) -> bool: return seg_label in self.loaded_segments

    # ====== 缓存统计与清理（全局历史缓存） ======
    def _get_all_cache_dirs(self) -> List[str]:
        """获取 %TEMP% 下所有 CoverPicker_* 目录路径"""
        temp_root = tempfile.gettempdir()
        try:
            entries = os.listdir(temp_root)
            cache_dirs = []
            for entry in entries:
                full_path = os.path.join(temp_root, entry)
                if os.path.isdir(full_path) and entry.startswith("CoverPicker_"):
                    cache_dirs.append(full_path)
            return cache_dirs
        except Exception as e:
            logger.error(f"扫描缓存目录失败: {e}")
            return []

    def get_cache_size(self) -> int:
        """汇总所有历史缓存目录的总大小（字节）"""
        total = 0
        for d in self._get_all_cache_dirs():
            for root, dirs, files in os.walk(d):
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(root, f))
                    except:
                        pass
        return total

    def get_cache_size_mb(self) -> float:
        return self.get_cache_size() / (1024 * 1024)

    def get_cache_size_gb(self) -> float:
        return self.get_cache_size() / (1024 * 1024 * 1024)

    def get_cache_file_count(self) -> int:
        """汇总所有历史缓存目录的文件总数"""
        count = 0
        for d in self._get_all_cache_dirs():
            for root, dirs, files in os.walk(d):
                count += len(files)
        return count

    def clear_cache(self) -> int:
        """
        清理所有历史缓存目录（包括当前会话的临时目录）
        返回被删除的文件总数
        """
        total_files = 0
        current_dir = self.temp_dir
        cache_dirs = self._get_all_cache_dirs()
        for d in cache_dirs:
            try:
                # 统计文件数
                file_count = 0
                for root, dirs, files in os.walk(d):
                    file_count += len(files)
                total_files += file_count
                # 删除整个目录
                shutil.rmtree(d, ignore_errors=True)
                logger.info(f"已删除缓存目录: {d} ({file_count} 个文件)")
            except Exception as e:
                logger.error(f"删除缓存目录失败 {d}: {e}")
        # 重新创建当前会话的临时目录（如果已被删除）
        if not os.path.exists(current_dir):
            try:
                os.makedirs(current_dir, exist_ok=True)
                logger.info(f"已重新创建当前临时目录: {current_dir}")
            except Exception as e:
                logger.error(f"重新创建临时目录失败: {e}")
        return total_files

    # ====== 原有缓存统计方法保留（现已汇总） ======
    # 注意：下面的方法已被覆盖，但为了兼容旧调用，保留名称指向新实现。

    def remove_video(self, video_path: str) -> bool:
        video_data = self.db.get_video_by_path(video_path)
        if not video_data: return False
        video_id = video_data['id']
        if self.video_path == video_path:
            if self._load_task and not self._load_task.done(): self._load_task.cancel()
            self.video_path = None; self.video_id = None; self.duration = 0.0; self.video_name = ""
            self.segments = []; self.screenshots = {}; self.loaded_segments = set(); self.favorites = []
            self.current_seg_index = 0; self._clear_history(); self._notify_data_changed()
        try: self.db.delete_video(video_id); return True
        except: return False

    def auto_clean_cache(self, threshold_gb: float = 5.0) -> Tuple[int, float]:
        # 此功能暂不使用，保留空实现
        return 0, 0.0

    def _restore_favorites_from_db(self):
        if not self.video_path or not self.video_id: return
        db_favs = self.db.get_favorites(self.video_id)
        if not db_favs: self.favorites = []; return
        self.favorites = []
        favorites_dir = self._get_favorites_dir()
        video_dir = os.path.dirname(self.video_path)
        for fav in db_favs:
            exported = bool(fav.get('is_exported', 0))
            thumb_path = fav.get('thumbnail_path', '')
            thumb_name = fav.get('thumbnail_name', '')
            path = ""
            if thumb_name:
                nas_path = os.path.join(favorites_dir, thumb_name)
                if os.path.exists(nas_path):
                    path = nas_path
                    logger.debug(f"在NAS收藏目录找到: {nas_path}")
            if not path and thumb_path and os.path.exists(thumb_path):
                path = thumb_path
            if not path and thumb_name:
                video_dir_path = os.path.join(video_dir, thumb_name)
                if os.path.exists(video_dir_path):
                    path = video_dir_path
            if not path:
                path = thumb_path
                logger.warning(f"收藏截图未找到: {thumb_name}")
            self.favorites.append({
                'video_path': self.video_path,
                'segment': fav['segment_label'],
                'time': fav['timestamp_ms'] / 1000,
                'path': path,
                'exported': exported,
            })
    def _restore_favorites_to_screenshots(self):
        if not self.video_path: return
        fav_items = [f for f in self.favorites if f.get('video_path') == self.video_path]
        if not fav_items: return
        for seg_label, items in self.screenshots.items():
            for item in items:
                matched_favs = [f for f in fav_items if f.get('segment') == seg_label and abs(f.get('time', 0) - item['time']) < 0.1]
                if matched_favs:
                    matched = next((f for f in matched_favs if f.get('exported', False)), matched_favs[0])
                    item['favorite'] = True; item['exported'] = matched.get('exported', False)
    def _save_state_to_db(self):
        if not self.video_path or not self.video_id: return
        for seg_label, items in self.screenshots.items():
            has_starred = any(item.get('favorite', False) for item in items)
            has_exported = any(item.get('exported', False) for item in items)
            is_viewed = seg_label in self.loaded_segments
            if seg_label == self.segments[self.current_seg_index][0]:
                excluded = self.excluded_ranges
            else:
                seg_state = self.db.get_segment_state(self.video_id, seg_label)
                excluded = seg_state.get('excluded_ranges', []) if seg_state else []
            self.db.update_segment_state(self.video_id, seg_label, is_viewed=is_viewed, has_starred=has_starred, has_exported=has_exported, excluded_ranges=excluded)
        is_starred = any(item.get('favorite', False) for seg_label, items in self.screenshots.items() for item in items)
        is_exported_from_screenshots = any(item.get('exported', False) for seg_label, items in self.screenshots.items() for item in items)
        is_exported_from_favorites = any(f.get('exported', False) for f in self.favorites if f.get('video_path') == self.video_path)
        is_exported = is_exported_from_screenshots or is_exported_from_favorites
        is_viewed = bool(self.loaded_segments)
        self.db.update_video_state(self.video_id, is_viewed=is_viewed, is_starred=is_starred, is_exported=is_exported)
        existing_favs = self.db.get_favorites(self.video_id)
        existing_set = set()
        for fav in existing_favs: existing_set.add((fav['segment_label'], int(fav['timestamp_ms'])))
        for seg_label, items in self.screenshots.items():
            for item in items:
                if item.get('favorite', False):
                    timestamp_ms = int(item['time'] * 1000)
                    current_key = (seg_label, timestamp_ms)
                    if current_key not in existing_set:
                        nas_path = self._save_favorite_to_nas(seg_label, item['time'], item['path'])
                        self.db.add_favorite(self.video_id, seg_label, timestamp_ms, nas_path, os.path.basename(nas_path), is_exported=item.get('exported', False))
                    else:
                        self.db.update_favorite_exported(self.video_id, seg_label, timestamp_ms)
    def cleanup(self):
        if self._load_task and not self._load_task.done(): self._load_task.cancel()
        if self.video_id and self.video_path: self._save_state_to_db()
        # 注意：cleanup 时不会删除当前临时目录，但用户可以通过清理缓存手动删除
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.db.close()