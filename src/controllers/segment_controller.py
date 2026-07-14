# src/controllers/segment_controller.py

import os
import asyncio
import random
import tempfile
import shutil
import logging
from typing import Dict, List, Set, Tuple, Optional
from datetime import timedelta

from src.database import Database
from src.video_scanner import get_video_duration, calculate_segments, extract_frame

logger = logging.getLogger(__name__)


class SegmentController:
    """业务逻辑控制器 - 管理视频数据、截图、收藏、持久化"""

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

        # 导出目录
        self.export_base: str = os.path.join(os.getcwd(), "StillPic")

        # 异步任务
        self._load_task: Optional[asyncio.Task] = None

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
        elif num > 10:
            num = 10
        if self.num_segments != num and self.video_path and self.duration > 0:
            self.num_segments = num
            self.segments = calculate_segments(self.duration, self.num_segments)
            self.screenshots = {}
            self.loaded_segments = set()
            self.current_seg_index = 0
            self._notify_data_changed()

    def get_num_segments(self) -> int:
        return self.num_segments

    # ============================================================
    # 自定义分区（时间轴自定义）
    # ============================================================

    def apply_custom_segments(self, segments: List[Tuple[str, float, float]]):
        """
        应用自定义分区列表
        segments: [(label, start, end), ...]
        """
        if not segments or len(segments) < 2:
            logger.warning("自定义分区至少需要2个区")
            return

        # 验证分区是否有效
        for label, start, end in segments:
            if start >= end or start < 0 or end > self.duration:
                logger.error(f"无效分区: {label} {start}-{end}")
                return

        self.num_segments = -1  # 标记为自定义
        self.segments = segments
        self.screenshots = {}
        self.loaded_segments = set()
        self.current_seg_index = 0
        self._notify_data_changed()

        # 自动加载第一个分区
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
        # 如果之前是自定义分区，重置为默认 5
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

        if added_count > 0:
            self._save_state_to_db()
            self._notify_data_changed()

        return added_count, skipped_count

    def unfavorite_selected(self, seg_label: str, positions: List[int]) -> int:
        items = self.screenshots.get(seg_label, [])
        removed_count = 0

        for pos in positions:
            if pos >= len(items):
                continue
            item = items[pos]
            if item.get('favorite', False):
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

        if removed_count > 0:
            self._save_state_to_db()
            self._notify_data_changed()

        return removed_count

    def get_current_favorites(self) -> List[dict]:
        return [f for f in self.favorites if f.get('video_path') == self.video_path]

    # ============================================================
    # 导出
    # ============================================================

    def export_selected(self, seg_label: str, positions: List[int]) -> Tuple[int, List[Tuple[str, str]]]:
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

        video_name = os.path.splitext(os.path.basename(self.video_path))[0]
        export_dir = os.path.join(self.export_base, video_name)
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
        items = self.screenshots.get(seg_label, [])
        count = 0
        for pos in positions:
            if pos < len(items):
                items[pos]['locked'] = True
                count += 1
        if count > 0:
            self._notify_data_changed()
        return count

    def unlock_selected(self, seg_label: str, positions: List[int]) -> int:
        items = self.screenshots.get(seg_label, [])
        count = 0
        for pos in positions:
            if pos < len(items):
                items[pos]['locked'] = False
                count += 1
        if count > 0:
            self._notify_data_changed()
        return count

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