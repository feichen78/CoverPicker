# src/controllers/segment_controller.py

import os
import asyncio
import random
import tempfile
import shutil
import logging
from typing import Dict, List, Set, Tuple, Optional, Any
from datetime import timedelta
from dataclasses import dataclass

from src.database import Database
from src.video_scanner import get_video_duration, calculate_segments, extract_frame

logger = logging.getLogger(__name__)


@dataclass
class Action:
    """撤销/重做操作记录"""
    type: str          # 'favorite', 'unfavorite', 'lock', 'unlock'
    video_id: int
    seg_label: str
    timestamp_ms: int
    old_state: bool
    new_state: bool


class SegmentController:
    """业务逻辑控制器 - 管理视频数据、截图、收藏、持久化、撤销/重做"""

    def __init__(self):
        self.db = Database()

        # 当前视频信息
        self.video_path: Optional[str] = None
        self.video_id: Optional[int] = None
        self.duration: float = 0.0
        self.video_name: str = ""

        # 分段信息
        self.num_segments: int = 5  # 默认 5 个分区，-1 表示自定义分区
        self.segments: List[Tuple[str, float, float]] = []  # [(label, start, end), ...]
        self.current_seg_index: int = 0

        # 截图数据
        self.screenshots: Dict[str, List[dict]] = {}

        # 收藏数据（跨视频）
        self.favorites: List[dict] = []

        # 已加载的分段
        self.loaded_segments: Set[str] = set()

        # 截图生成配置
        self.density: int = 9
        self.skip_ratio: float = 0.15
        self.excluded_ranges: List[Tuple[float, float]] = []

        # 临时目录
        self.temp_dir: str = tempfile.mkdtemp(prefix="CoverPicker_")

        # 导出目录（默认，但允许用户在导出时覆盖）
        self.export_base: str = os.path.join(os.getcwd(), "StillPic")

        # 异步任务
        self._load_task: Optional[asyncio.Task] = None

        # 撤销/重做
        self.undo_stack: List[Action] = []
        self.redo_stack: List[Action] = []
        self._is_undo_or_redo: bool = False

        # 回调
        self._on_data_changed: Optional[callable] = None
        self._on_progress_update: Optional[callable] = None

    def set_data_changed_callback(self, callback: callable):
        self._on_data_changed = callback

    def set_progress_callback(self, callback: callable):
        self._on_progress_update = callback

    def _notify_data_changed(self):
        if self._on_data_changed:
            self._on_data_changed()

    def _notify_progress(self, message: str):
        if self._on_progress_update:
            self._on_progress_update(message)

    # ============================================================
    # 分区数量管理
    # ============================================================

    def set_num_segments(self, num: int):
        if num < 3:
            num = 3
        elif num > 7:
            num = 7
        if self.num_segments != num and self.video_path and self.duration > 0:
            self.num_segments = num
            self.segments = calculate_segments(self.duration, self.num_segments)
            self.screenshots = {}
            self.loaded_segments = set()
            self.current_seg_index = 0
            self._clear_history()
            self._notify_data_changed()

    def get_num_segments(self) -> int:
        return self.num_segments

    # ============================================================
    # 自定义分区
    # ============================================================

    def apply_custom_segments(self, segments: List[Tuple[str, float, float]]):
        if not segments or len(segments) < 2:
            logger.warning("自定义分区至少需要2个区")
            return

        for label, start, end in segments:
            if start >= end or start < 0 or end > self.duration:
                logger.error(f"无效分区: {label} {start}-{end}")
                return

        self.num_segments = -1
        self.segments = segments
        self.screenshots = {}
        self.loaded_segments = set()
        self.current_seg_index = 0
        self._clear_history()
        self._notify_data_changed()

        if self.video_path:
            asyncio.create_task(self.load_segment(0, restore_locks=True, randomize=False))

    # ============================================================
    # 视频加载
    # ============================================================

    async def load_video(self, video_path: str) -> bool:
        if self._load_task and not self._load_task.done():
            self._load_task.cancel()
            logger.debug(f"取消之前的加载任务: {self.video_path}")

        self.video_path = video_path
        self.video_name = os.path.basename(video_path)

        duration = get_video_duration(video_path)
        if duration is None:
            logger.error(f"无法获取视频时长: {video_path}")
            return False

        self.duration = duration
        if self.num_segments == -1:
            self.num_segments = 5
        self.segments = calculate_segments(duration, self.num_segments)

        file_name = os.path.basename(video_path)
        self.video_id = self.db.get_or_create_video(
            video_path,
            file_name,
            int(duration),
            "",
            int(os.path.getsize(video_path)),
            int(os.path.getmtime(video_path))
        )

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

        if self.loaded_segments:
            self.db.update_video_state(self.video_id, is_viewed=True)

        self._notify_data_changed()
        return True

    async def load_segment(self, seg_idx: int, restore_locks: bool = True, randomize: bool = False):
        if not self.video_path or not self.segments:
            return

        if self._load_task and not self._load_task.done():
            self._load_task.cancel()

        self.current_seg_index = seg_idx
        self._load_task = asyncio.create_task(
            self._load_segment(seg_idx, restore_locks, randomize)
        )
        await self._load_task
        self._load_task = None

        self._notify_data_changed()

    async def _load_segment(self, seg_idx: int, restore_locks: bool = True, randomize: bool = False):
        if not self.video_path or not self.segments:
            return

        current_task = asyncio.current_task()
        if current_task and current_task.cancelled():
            logger.debug(f"分段 {seg_idx} 加载被取消（任务状态检查）")
            return

        label, start, end = self.segments[seg_idx]
        offset = (end - start) * self.skip_ratio
        start_cropped = start + offset
        end_cropped = end - offset
        if end_cropped <= start_cropped:
            start_cropped = start
            end_cropped = end

        logger.info(f"加载分段 {label}: {start_cropped:.1f}s - {end_cropped:.1f}s")

        count = self.density
        seg_key = label
        old_items = self.screenshots.get(seg_key, [])

        new_times = [random.uniform(start_cropped, end_cropped) for _ in range(count)]
        new_times.sort()
        new_times = self._filter_excluded_random(new_times, start_cropped, end_cropped, count)

        new_items = []
        total = len(new_times)

        for idx, t in enumerate(new_times):
            if current_task and current_task.cancelled():
                logger.debug(f"分段 {seg_idx} 加载被取消（循环中检查）")
                return

            self._notify_progress(f"正在生成 {label} 第 {idx+1}/{total} 张 @ {t:.2f}s")

            matched = None
            if restore_locks:
                for item in old_items:
                    if abs(item['time'] - t) < 0.5:
                        matched = item
                        break

            if matched:
                new_items.append({
                    'time': matched['time'],
                    'path': matched['path'],
                    'locked': matched.get('locked', False),
                    'favorite': matched.get('favorite', False),
                    'exported': matched.get('exported', False),
                })
                self._notify_progress(f"恢复锁定: {label} {idx+1}/{total} @ {t:.2f}s")
                continue

            temp_path = os.path.join(self.temp_dir, f"seg_{label}_{t:.2f}.jpg")
            try:
                success = await asyncio.to_thread(extract_frame, self.video_path, t, temp_path)
                if success:
                    new_items.append({
                        'time': t,
                        'path': temp_path,
                        'locked': False,
                        'favorite': False,
                        'exported': False,
                    })
                    logger.info(f"截图成功: {label} {idx} @ {t:.2f}s")
                    self._notify_progress(f"截图成功: {label} {idx+1}/{total} @ {t:.2f}s")
                else:
                    new_items.append({
                        'time': t,
                        'path': None,
                        'locked': False,
                        'favorite': False,
                        'exported': False,
                    })
                    logger.warning(f"截图失败: {label} {idx} @ {t:.2f}s")
                    self._notify_progress(f"截图失败: {label} {idx+1}/{total} @ {t:.2f}s")
            except asyncio.CancelledError:
                logger.debug(f"截图任务被取消: {label} {idx} @ {t:.2f}s")
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                raise

        if current_task and current_task.cancelled():
            logger.debug(f"分段 {seg_idx} 加载被取消（完成后检查）")
            return

        self.screenshots[seg_key] = new_items
        self.loaded_segments.add(label)

        self._restore_favorites_to_screenshots()

        self._notify_progress(f"{label} 分段加载完成 ({len(new_items)} 张)")
        self._notify_data_changed()

    # ============================================================
    # 收藏管理
    # ============================================================

    def favorite_selected(self, seg_label: str, positions: List[int]) -> Tuple[int, int]:
        if self._is_undo_or_redo:
            return self._favorite_selected_impl(seg_label, positions, record_history=False)
        return self._favorite_selected_impl(seg_label, positions, record_history=True)

    def _favorite_selected_impl(self, seg_label: str, positions: List[int], record_history: bool) -> Tuple[int, int]:
        items = self.screenshots.get(seg_label, [])
        processed_keys = set()
        added_count = 0
        skipped_count = 0

        for pos in positions:
            if pos >= len(items):
                continue
            item = items[pos]
            key = (self.video_path, seg_label, item['time'])

            if key in processed_keys:
                skipped_count += 1
                continue
            processed_keys.add(key)

            if not item.get('favorite', False):
                old_state = False
                new_state = True
                item['favorite'] = True
                if self.video_id:
                    timestamp_ms = int(item['time'] * 1000)
                    if not self.db.is_favorite(self.video_id, seg_label, timestamp_ms):
                        self.db.add_favorite(
                            self.video_id, seg_label, timestamp_ms,
                            item.get('path', ''),
                            is_exported=item.get('exported', False)
                        )
                self.favorites.append({
                    'video_path': self.video_path,
                    'segment': seg_label,
                    'time': item['time'],
                    'path': item['path'],
                    'exported': item.get('exported', False),
                })
                added_count += 1

                if record_history:
                    self._push_action(Action(
                        type='favorite',
                        video_id=self.video_id,
                        seg_label=seg_label,
                        timestamp_ms=timestamp_ms,
                        old_state=old_state,
                        new_state=new_state
                    ))

        if added_count > 0:
            self._save_state_to_db()
            self._notify_data_changed()

        return added_count, skipped_count

    def unfavorite_selected(self, seg_label: str, positions: List[int]) -> int:
        if self._is_undo_or_redo:
            return self._unfavorite_selected_impl(seg_label, positions, record_history=False)
        return self._unfavorite_selected_impl(seg_label, positions, record_history=True)

    def _unfavorite_selected_impl(self, seg_label: str, positions: List[int], record_history: bool) -> int:
        items = self.screenshots.get(seg_label, [])
        removed_count = 0

        for pos in positions:
            if pos >= len(items):
                continue
            item = items[pos]
            if item.get('favorite', False):
                old_state = True
                new_state = False
                item['favorite'] = False
                if self.video_id:
                    timestamp_ms = int(item['time'] * 1000)
                    self.db.remove_favorite(self.video_id, seg_label, timestamp_ms)
                self.favorites = [
                    f for f in self.favorites
                    if not (f.get('video_path') == self.video_path and
                            f.get('segment') == seg_label and
                            abs(f.get('time', 0) - item['time']) < 0.01)
                ]
                removed_count += 1

                if record_history:
                    self._push_action(Action(
                        type='unfavorite',
                        video_id=self.video_id,
                        seg_label=seg_label,
                        timestamp_ms=timestamp_ms,
                        old_state=old_state,
                        new_state=new_state
                    ))

        if removed_count > 0:
            self._save_state_to_db()
            self._notify_data_changed()

        return removed_count

    def get_current_favorites(self) -> List[dict]:
        return [f for f in self.favorites if f.get('video_path') == self.video_path]

    # ============================================================
    # 导出（支持自定义目录）
    # ============================================================

    def export_selected(self, seg_label: str, positions: List[int], export_dir: Optional[str] = None) -> Tuple[int, List[Tuple[str, str]]]:
        """
        导出选中的截图。
        
        Args:
            seg_label: 分区标签
            positions: 截图位置列表
            export_dir: 自定义导出目录（如果为 None，使用默认目录）
        
        Returns:
            (导出数量, [(时间戳, 导出路径), ...])
        """
        items = self.screenshots.get(seg_label, [])
        export_paths = []

        for pos in positions:
            if pos >= len(items):
                continue
            item = items[pos]
            if item.get('path') and os.path.exists(item['path']):
                export_paths.append((item['time'], item['path'], pos))

        if not export_paths:
            return 0, []

        # 确定导出目录
        if export_dir is None:
            video_name = os.path.splitext(os.path.basename(self.video_path))[0]
            export_dir = os.path.join(self.export_base, video_name)
        else:
            # 如果传入的目录是用户选择的根目录，自动创建视频名子目录
            # 但为了灵活性，我们直接使用传入的目录（用户可能希望直接放在选择的目录下）
            # 但仍然建议在用户选择的目录下创建视频名子目录以避免混乱
            # 这里我们使用传入的目录 + 视频名子目录
            video_name = os.path.splitext(os.path.basename(self.video_path))[0]
            export_dir = os.path.join(export_dir, video_name)

        os.makedirs(export_dir, exist_ok=True)

        exported = 0
        exported_list = []

        for time_sec, src_path, pos in export_paths:
            dest_name = f"cover_{time_sec:.2f}s.jpg"
            dest_path = os.path.join(export_dir, dest_name)
            try:
                shutil.copy2(src_path, dest_path)
                exported += 1
                exported_list.append((time_sec, dest_path))
                items[pos]['exported'] = True
                if self.video_id:
                    timestamp_ms = int(time_sec * 1000)
                    self.db.update_favorite_exported(self.video_id, seg_label, timestamp_ms)
            except Exception as e:
                logger.error(f"导出失败 {src_path}: {e}")

        if exported > 0:
            self._save_state_to_db()
            self._notify_data_changed()

        return exported, exported_list

    # ============================================================
    # Zoom 精修 - 替换截图
    # ============================================================

    def replace_screenshot(
        self,
        seg_label: str,
        pos: int,
        new_time: float,
        new_path: str,
        old_time: float
    ) -> bool:
        items = self.screenshots.get(seg_label, [])
        if pos >= len(items):
            logger.error(f"替换失败: pos {pos} 超出范围")
            return False

        original = items[pos]

        locked = original.get('locked', False)
        favorite = original.get('favorite', False)
        exported = original.get('exported', False)

        import shutil
        new_temp_path = os.path.join(self.temp_dir, f"seg_{seg_label}_{new_time:.2f}_replaced.jpg")
        try:
            shutil.copy2(new_path, new_temp_path)
        except Exception as e:
            logger.error(f"复制图片失败: {e}")
            return False

        original['time'] = new_time
        original['path'] = new_temp_path
        original['locked'] = locked
        original['favorite'] = favorite
        original['exported'] = exported

        if favorite and self.video_id:
            old_timestamp_ms = int(old_time * 1000)
            new_timestamp_ms = int(new_time * 1000)

            self.db.remove_favorite(self.video_id, seg_label, old_timestamp_ms)
            self.db.add_favorite(
                self.video_id,
                seg_label,
                new_timestamp_ms,
                new_temp_path,
                is_exported=exported
            )

            for fav in self.favorites:
                if (fav.get('video_path') == self.video_path and
                    fav.get('segment') == seg_label and
                    abs(fav.get('time', 0) - old_time) < 0.01):
                    fav['time'] = new_time
                    fav['path'] = new_temp_path
                    fav['exported'] = exported
                    break

        self._notify_data_changed()
        logger.info(f"替换成功: {seg_label} pos={pos} {old_time:.2f}s -> {new_time:.2f}s")
        return True

    # ============================================================
    # 锁定/解锁
    # ============================================================

    def lock_selected(self, seg_label: str, positions: List[int]) -> int:
        if self._is_undo_or_redo:
            return self._lock_selected_impl(seg_label, positions, record_history=False)
        return self._lock_selected_impl(seg_label, positions, record_history=True)

    def _lock_selected_impl(self, seg_label: str, positions: List[int], record_history: bool) -> int:
        items = self.screenshots.get(seg_label, [])
        count = 0
        for pos in positions:
            if pos < len(items):
                item = items[pos]
                if not item.get('locked', False):
                    old_state = False
                    new_state = True
                    item['locked'] = True
                    count += 1
                    if record_history and self.video_id:
                        timestamp_ms = int(item['time'] * 1000)
                        self._push_action(Action(
                            type='lock',
                            video_id=self.video_id,
                            seg_label=seg_label,
                            timestamp_ms=timestamp_ms,
                            old_state=old_state,
                            new_state=new_state
                        ))
        if count > 0:
            self._notify_data_changed()
        return count

    def unlock_selected(self, seg_label: str, positions: List[int]) -> int:
        if self._is_undo_or_redo:
            return self._unlock_selected_impl(seg_label, positions, record_history=False)
        return self._unlock_selected_impl(seg_label, positions, record_history=True)

    def _unlock_selected_impl(self, seg_label: str, positions: List[int], record_history: bool) -> int:
        items = self.screenshots.get(seg_label, [])
        count = 0
        for pos in positions:
            if pos < len(items):
                item = items[pos]
                if item.get('locked', False):
                    old_state = True
                    new_state = False
                    item['locked'] = False
                    count += 1
                    if record_history and self.video_id:
                        timestamp_ms = int(item['time'] * 1000)
                        self._push_action(Action(
                            type='unlock',
                            video_id=self.video_id,
                            seg_label=seg_label,
                            timestamp_ms=timestamp_ms,
                            old_state=old_state,
                            new_state=new_state
                        ))
        if count > 0:
            self._notify_data_changed()
        return count

    # ============================================================
    # 撤销/重做
    # ============================================================

    def _push_action(self, action: Action):
        self.undo_stack.append(action)
        self.redo_stack.clear()
        if len(self.undo_stack) > 100:
            self.undo_stack = self.undo_stack[-100:]

    def _clear_history(self):
        self.undo_stack.clear()
        self.redo_stack.clear()

    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

    def undo(self):
        if not self.can_undo():
            return
        action = self.undo_stack.pop()
        self._execute_action(action, reverse=True)
        self.redo_stack.append(action)
        self._save_state_to_db()
        self._notify_data_changed()

    def redo(self):
        if not self.can_redo():
            return
        action = self.redo_stack.pop()
        self._execute_action(action, reverse=False)
        self.undo_stack.append(action)
        self._save_state_to_db()
        self._notify_data_changed()

    def _execute_action(self, action: Action, reverse: bool):
        self._is_undo_or_redo = True
        try:
            if action.type == 'favorite':
                if reverse:
                    self._apply_favorite_state(action, False)
                else:
                    self._apply_favorite_state(action, True)
            elif action.type == 'unfavorite':
                if reverse:
                    self._apply_favorite_state(action, True)
                else:
                    self._apply_favorite_state(action, False)
            elif action.type == 'lock':
                if reverse:
                    self._apply_lock_state(action, False)
                else:
                    self._apply_lock_state(action, True)
            elif action.type == 'unlock':
                if reverse:
                    self._apply_lock_state(action, True)
                else:
                    self._apply_lock_state(action, False)
        finally:
            self._is_undo_or_redo = False

    def _apply_favorite_state(self, action: Action, set_favorite: bool):
        items = self.screenshots.get(action.seg_label, [])
        target_time = action.timestamp_ms / 1000.0
        for item in items:
            if abs(item['time'] - target_time) < 0.01:
                item['favorite'] = set_favorite
                break
        if set_favorite:
            if not self.db.is_favorite(action.video_id, action.seg_label, action.timestamp_ms):
                thumb_path = ""
                for item in items:
                    if abs(item['time'] - target_time) < 0.01:
                        thumb_path = item.get('path', '')
                        break
                self.db.add_favorite(action.video_id, action.seg_label,
                                     action.timestamp_ms, thumb_path,
                                     is_exported=False)
                self.favorites.append({
                    'video_path': self.video_path,
                    'segment': action.seg_label,
                    'time': target_time,
                    'path': thumb_path,
                    'exported': False,
                })
        else:
            self.db.remove_favorite(action.video_id, action.seg_label, action.timestamp_ms)
            self.favorites = [
                f for f in self.favorites
                if not (f.get('video_path') == self.video_path and
                        f.get('segment') == action.seg_label and
                        abs(f.get('time', 0) - target_time) < 0.01)
            ]

    def _apply_lock_state(self, action: Action, set_locked: bool):
        items = self.screenshots.get(action.seg_label, [])
        target_time = action.timestamp_ms / 1000.0
        for item in items:
            if abs(item['time'] - target_time) < 0.01:
                item['locked'] = set_locked
                break

    # ============================================================
    # 刷新/重抽
    # ============================================================

    async def refresh_unlocked(self, seg_idx: int) -> int:
        if not self.video_path or not self.segments:
            return 0

        seg_label, start, end = self.segments[seg_idx]
        offset = (end - start) * self.skip_ratio
        start_cropped = start + offset
        end_cropped = end - offset
        if end_cropped <= start_cropped:
            start_cropped = start
            end_cropped = end

        items = self.screenshots.get(seg_label, [])
        unlocked_positions = [i for i, item in enumerate(items) if not item.get('locked', False)]
        if not unlocked_positions:
            return 0

        locked_times = [item['time'] for item in items if item.get('locked', False)]
        refreshed = 0
        total = len(unlocked_positions)

        for idx, pos in enumerate(unlocked_positions):
            self._notify_progress(f"刷新未锁定 {idx+1}/{total}")
            for _ in range(20):
                t = random.uniform(start_cropped, end_cropped)
                excluded = False
                for low, high in self.excluded_ranges:
                    if low <= t <= high:
                        excluded = True
                        break
                if not excluded and all(abs(t - lt) > 0.5 for lt in locked_times):
                    break

            temp_path = os.path.join(self.temp_dir, f"seg_{seg_label}_{t:.2f}_new.jpg")
            try:
                success = await asyncio.to_thread(extract_frame, self.video_path, t, temp_path)
                if success:
                    items[pos]['time'] = t
                    items[pos]['path'] = temp_path
                    items[pos]['locked'] = False
                    refreshed += 1
                    logger.info(f"刷新未锁定: {seg_label} {pos} -> {t:.2f}s")
                    self._notify_progress(f"刷新成功: {seg_label} {idx+1}/{total} @ {t:.2f}s")
                else:
                    self._notify_progress(f"刷新失败: {seg_label} {idx+1}/{total} @ {t:.2f}s")
            except asyncio.CancelledError:
                logger.debug(f"刷新未锁定被取消: {seg_label} {pos}")
                raise

        if refreshed > 0:
            self._notify_data_changed()

        self._notify_progress(f"刷新完成: {refreshed} 张")
        return refreshed

    async def reset_segment(self, seg_idx: int):
        seg_label = self.segments[seg_idx][0]
        logger.info(f"全部重抽: 分段 {seg_label}")
        self.screenshots[seg_label] = []
        self._clear_history()
        await self._load_segment(seg_idx, restore_locks=False, randomize=True)
        self._notify_data_changed()

    # ============================================================
    # 状态图标
    # ============================================================

    def get_video_state_icon(self, video_path: str) -> str:
        video_data = self.db.get_video_by_path(video_path)
        if not video_data:
            return ""
        if video_data.get('is_exported', 0):
            return "✅"
        elif video_data.get('is_starred', 0):
            return "⭐"
        elif video_data.get('is_viewed', 0):
            return "👁️"
        return ""

    def get_video_state(self, video_path: str) -> dict:
        return self.db.get_video_by_path(video_path)

    # ============================================================
    # 删除视频
    # ============================================================

    def remove_video(self, video_path: str) -> bool:
        video_data = self.db.get_video_by_path(video_path)
        if not video_data:
            logger.warning(f"视频不存在于数据库: {video_path}")
            return False

        video_id = video_data['id']

        if self.video_path == video_path:
            if self._load_task and not self._load_task.done():
                self._load_task.cancel()
            self.video_path = None
            self.video_id = None
            self.duration = 0.0
            self.video_name = ""
            self.segments = []
            self.screenshots = {}
            self.loaded_segments = set()
            self.favorites = []
            self.current_seg_index = 0
            self._clear_history()
            self._notify_data_changed()

        try:
            self.db.delete_video(video_id)
            logger.info(f"已从数据库移除视频: {video_path}")
            return True
        except Exception as e:
            logger.error(f"删除视频记录失败: {e}")
            return False

    # ============================================================
    # 缓存管理（v2.0）
    # ============================================================

    def get_cache_size(self) -> int:
        """获取缓存目录总大小（字节）"""
        if not os.path.exists(self.temp_dir):
            return 0
        total = 0
        for root, dirs, files in os.walk(self.temp_dir):
            for f in files:
                file_path = os.path.join(root, f)
                try:
                    total += os.path.getsize(file_path)
                except OSError:
                    pass
        return total

    def get_cache_size_mb(self) -> float:
        """获取缓存目录总大小（MB）"""
        return self.get_cache_size() / (1024 * 1024)

    def get_cache_size_gb(self) -> float:
        """获取缓存目录总大小（GB）"""
        return self.get_cache_size() / (1024 * 1024 * 1024)

    def get_cache_file_count(self) -> int:
        """获取缓存目录文件数量"""
        if not os.path.exists(self.temp_dir):
            return 0
        count = 0
        for root, dirs, files in os.walk(self.temp_dir):
            count += len(files)
        return count

    def clear_cache(self) -> int:
        """清理所有缓存文件，返回删除文件数"""
        if not os.path.exists(self.temp_dir):
            return 0
        count = 0
        for root, dirs, files in os.walk(self.temp_dir):
            for f in files:
                try:
                    os.remove(os.path.join(root, f))
                    count += 1
                except Exception as e:
                    logger.warning(f"删除缓存文件失败: {f} - {e}")
        return count

    def auto_clean_cache(self, threshold_gb: float = 5.0) -> Tuple[int, float]:
        """
        自动清理缓存，删除最旧的文件直到总大小低于阈值。
        
        Args:
            threshold_gb: 阈值（GB），默认 5GB
        
        Returns:
            (删除文件数, 释放空间MB)
        """
        if not os.path.exists(self.temp_dir):
            return 0, 0.0

        current_size = self.get_cache_size()
        threshold_bytes = threshold_gb * 1024 * 1024 * 1024

        if current_size <= threshold_bytes:
            return 0, 0.0

        # 收集所有缓存文件信息（路径，修改时间，大小）
        files_info = []
        for root, dirs, files in os.walk(self.temp_dir):
            for f in files:
                file_path = os.path.join(root, f)
                try:
                    mtime = os.path.getmtime(file_path)
                    size = os.path.getsize(file_path)
                    files_info.append((file_path, mtime, size))
                except OSError:
                    pass

        # 按修改时间排序（最旧在前）
        files_info.sort(key=lambda x: x[1])

        # 删除最旧的文件直到低于阈值（清理到90%避免频繁触发）
        deleted_count = 0
        freed_bytes = 0
        target_bytes = threshold_bytes * 0.9

        for file_path, mtime, size in files_info:
            if current_size - freed_bytes <= target_bytes:
                break
            try:
                os.remove(file_path)
                deleted_count += 1
                freed_bytes += size
            except OSError:
                pass

        freed_mb = freed_bytes / (1024 * 1024)
        return deleted_count, freed_mb

    # ============================================================
    # 工具方法
    # ============================================================

    def get_current_segment(self) -> Optional[Tuple[str, float, float]]:
        if 0 <= self.current_seg_index < len(self.segments):
            return self.segments[self.current_seg_index]
        return None

    def get_segment_items(self, seg_label: str) -> List[dict]:
        return self.screenshots.get(seg_label, [])

    def get_segments(self) -> List[Tuple[str, float, float]]:
        return self.segments

    def get_segment_count(self) -> int:
        return len(self.segments)

    def get_duration(self) -> float:
        return self.duration

    def get_video_name(self) -> str:
        return self.video_name

    def get_video_path(self) -> Optional[str]:
        return self.video_path

    def get_video_id(self) -> Optional[int]:
        return self.video_id

    def get_export_base(self) -> str:
        return self.export_base

    def get_temp_dir(self) -> str:
        return self.temp_dir

    def get_loaded_segments(self) -> Set[str]:
        return self.loaded_segments

    def get_favorites_count(self) -> int:
        return len(self.get_current_favorites())

    def is_segment_loaded(self, seg_label: str) -> bool:
        return seg_label in self.loaded_segments

    # ============================================================
    # 私有方法
    # ============================================================

    def _filter_excluded_random(self, times: List[float], start: float, end: float, target_count: int) -> List[float]:
        if not self.excluded_ranges:
            return times
        valid = []
        for t in times:
            excluded = False
            for low, high in self.excluded_ranges:
                if low <= t <= high:
                    excluded = True
                    break
            if not excluded:
                valid.append(t)
        while len(valid) < target_count:
            t = random.uniform(start, end)
            excluded = False
            for low, high in self.excluded_ranges:
                if low <= t <= high:
                    excluded = True
                    break
            if not excluded:
                valid.append(t)
        if len(valid) > target_count:
            valid = valid[:target_count]
        valid.sort()
        return valid

    def _save_state_to_db(self):
        if not self.video_path or not self.video_id:
            return

        logger.info(f"[保存状态] 开始保存: {self.video_path}")

        for seg_label, items in self.screenshots.items():
            has_starred = any(item.get('favorite', False) for item in items)
            has_exported = any(item.get('exported', False) for item in items)
            is_viewed = seg_label in self.loaded_segments
            self.db.update_segment_state(
                self.video_id,
                seg_label,
                is_viewed=is_viewed,
                has_starred=has_starred,
                has_exported=has_exported
            )

        is_starred = any(
            item.get('favorite', False)
            for seg_label, items in self.screenshots.items()
            for item in items
        )
        is_exported_from_screenshots = any(
            item.get('exported', False)
            for seg_label, items in self.screenshots.items()
            for item in items
        )
        is_exported_from_favorites = any(
            f.get('exported', False)
            for f in self.favorites
            if f.get('video_path') == self.video_path
        )
        is_exported = is_exported_from_screenshots or is_exported_from_favorites
        is_viewed = bool(self.loaded_segments)

        self.db.update_video_state(
            self.video_id,
            is_viewed=is_viewed,
            is_starred=is_starred,
            is_exported=is_exported
        )

        existing_favs = self.db.get_favorites(self.video_id)
        existing_set = set()
        for fav in existing_favs:
            key = (fav['segment_label'], int(fav['timestamp_ms']))
            existing_set.add(key)

        for seg_label, items in self.screenshots.items():
            for item in items:
                if item.get('favorite', False):
                    timestamp_ms = int(item['time'] * 1000)
                    current_key = (seg_label, timestamp_ms)
                    if current_key not in existing_set:
                        self.db.add_favorite(
                            self.video_id,
                            seg_label,
                            timestamp_ms,
                            item.get('path', ''),
                            is_exported=item.get('exported', False)
                        )
                        logger.debug(f"[保存状态] 新增收藏: seg={seg_label}, time={item['time']:.2f}")
                    else:
                        self.db.update_favorite_exported(self.video_id, seg_label, timestamp_ms)
                        logger.debug(f"[保存状态] 更新导出状态: seg={seg_label}, time={item['time']:.2f}")

        logger.info(f"[保存状态] 完成: is_starred={is_starred}, is_exported={is_exported}")

    def _restore_favorites_from_db(self):
        if not self.video_path or not self.video_id:
            return

        db_favs = self.db.get_favorites(self.video_id)
        if not db_favs:
            self.favorites = []
            return

        self.favorites = []
        video_name = os.path.splitext(os.path.basename(self.video_path))[0]
        export_dir = os.path.join(self.export_base, video_name)

        for fav in db_favs:
            exported = bool(fav.get('is_exported', 0))
            if exported:
                time_sec = fav['timestamp_ms'] / 1000
                expected_file = os.path.join(export_dir, f"cover_{time_sec:.2f}s.jpg")
                if not os.path.exists(expected_file):
                    exported = False
                    self.db.update_favorite_exported(self.video_id, fav['segment_label'], fav['timestamp_ms'])

            self.favorites.append({
                'video_path': self.video_path,
                'segment': fav['segment_label'],
                'time': fav['timestamp_ms'] / 1000,
                'path': fav['thumbnail_path'],
                'exported': exported,
            })

        logger.info(f"[恢复收藏] 共恢复 {len(self.favorites)} 个收藏")

    def _restore_favorites_to_screenshots(self):
        if not self.video_path:
            return

        fav_items = [f for f in self.favorites if f.get('video_path') == self.video_path]
        if not fav_items:
            return

        for seg_label, items in self.screenshots.items():
            for item in items:
                matched_favs = [
                    f for f in fav_items
                    if f.get('segment') == seg_label and abs(f.get('time', 0) - item['time']) < 0.1
                ]
                if matched_favs:
                    matched = next((f for f in matched_favs if f.get('exported', False)), matched_favs[0])
                    item['favorite'] = True
                    item['exported'] = matched.get('exported', False)

    # ============================================================
    # 清理
    # ============================================================

    def cleanup(self):
        if self._load_task and not self._load_task.done():
            self._load_task.cancel()

        if self.video_id and self.video_path:
            self._save_state_to_db()

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.db.close()