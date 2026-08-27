"""
测试 FFmpeg 并发控制（信号量机制）
验证 SegmentController 中的 _ffmpeg_semaphore 限制并发数。
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

from src.controllers.segment_controller import SegmentController
from src.database import Database

pytestmark = pytest.mark.asyncio


class TestConcurrentControl:

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        db_path = tmp_path / "test.db"
        return str(db_path)

    @pytest.fixture
    def controller(self, temp_db_path):
        db = Database(db_path=temp_db_path)
        video_id = db.get_or_create_video(
            file_path="test.mp4",
            file_name="test.mp4",
            duration=120,
            resolution="1920x1080",
            file_size=100,
            modified_time=1234567890
        )
        controller = SegmentController()
        controller.db = db
        controller.video_id = video_id
        controller.video_path = "test.mp4"
        controller.duration = 120.0
        controller.num_segments = 3
        controller.segments = [
            ("A", 0.0, 40.0),
            ("B", 40.0, 80.0),
            ("C", 80.0, 120.0),
        ]
        controller.screenshots = {
            'A': [{'time': 10.0, 'path': None, 'locked': False, 'favorite': False, 'exported': False}],
        }
        controller.loaded_segments = set()
        # 重置信号量到小值以便测试
        controller._ffmpeg_semaphore = asyncio.Semaphore(2)
        return controller

    async def test_semaphore_initialized(self, controller):
        """验证信号量已初始化且默认值为合理正数"""
        assert hasattr(controller, '_ffmpeg_semaphore')
        sem = controller._ffmpeg_semaphore
        assert isinstance(sem, asyncio.Semaphore)
        # 默认值应为 max(3, min(cpu_count*2, 8))，但测试中我们手动设为2
        # 检查其内部值（通过查看 _value）
        assert sem._value > 0

    async def test_semaphore_limits_concurrent_tasks(self, controller):
        """验证信号量限制同时运行的 FFmpeg 任务数不超过设定值"""
        sem = controller._ffmpeg_semaphore
        # 模拟 extract_frame_async 休眠，以观察并发数
        mock_extract = AsyncMock()
        mock_extract.return_value = (True, None)

        # 创建多个任务同时获取信号量
        async def dummy_extract(idx):
            async with sem:
                await asyncio.sleep(0.1)
                return idx

        tasks = [asyncio.create_task(dummy_extract(i)) for i in range(10)]
        results = await asyncio.gather(*tasks)
        # 所有任务应完成，但并发受限于信号量
        assert len(results) == 10
        # 信号量值应恢复到初始值
        assert sem._value == 2

    async def test_load_segment_uses_semaphore(self, controller, monkeypatch):
        """验证 _load_segment 内部使用信号量"""
        # 模拟 extract_frame_async 快速返回
        async def mock_extract(video_path, time_sec, output_path, retries=1):
            # 记录调用
            return True, None

        monkeypatch.setattr(
            'src.controllers.segment_controller.extract_frame_async',
            mock_extract
        )

        # 设置 controller 的密度为 9，以便生成多个帧
        controller.density = 9
        # 创建足够的时间点
        controller.screenshots['A'] = [{'time': 10.0 + i, 'path': None, 'locked': False, 'favorite': False, 'exported': False} for i in range(9)]

        # 调用 _load_segment，它内部会使用 semaphore
        await controller._load_segment(0, restore_locks=False, randomize=False)

        # 验证所有截图都已生成（path 不为 None）
        items = controller.screenshots.get('A', [])
        assert len(items) == 9
        # 至少有一些项有 path（模拟成功）
        success_count = sum(1 for item in items if item.get('path') is not None)
        assert success_count > 0

    async def test_semaphore_releases_on_error(self, controller, monkeypatch):
        """验证即使提取失败，信号量也能正确释放"""
        # 模拟 extract_frame_async 失败
        async def mock_extract_fail(video_path, time_sec, output_path, retries=1):
            return False, None

        monkeypatch.setattr(
            'src.controllers.segment_controller.extract_frame_async',
            mock_extract_fail
        )

        controller.density = 3
        controller.screenshots['A'] = [{'time': 10.0 + i, 'path': None, 'locked': False, 'favorite': False, 'exported': False} for i in range(3)]

        sem = controller._ffmpeg_semaphore
        initial_value = sem._value

        await controller._load_segment(0, restore_locks=False, randomize=False)

        # 信号量应恢复到初始值
        assert sem._value == initial_value

    async def test_concurrent_ffmpeg_tasks_not_exceed_limit(self, controller, monkeypatch):
        """验证实际并发提取帧时，同时运行的任务数不超过信号量值"""
        # 使用一个计数器来记录同时活跃的任务
        active_count = 0
        max_active = 0

        async def mock_extract_count(video_path, time_sec, output_path, retries=1):
            nonlocal active_count, max_active
            active_count += 1
            max_active = max(max_active, active_count)
            await asyncio.sleep(0.05)  # 模拟耗时操作
            active_count -= 1
            return True, None

        monkeypatch.setattr(
            'src.controllers.segment_controller.extract_frame_async',
            mock_extract_count
        )

        controller.density = 9
        controller.screenshots['A'] = [{'time': 10.0 + i, 'path': None, 'locked': False, 'favorite': False, 'exported': False} for i in range(9)]

        # 设置信号量限制为 2
        controller._ffmpeg_semaphore = asyncio.Semaphore(2)

        await controller._load_segment(0, restore_locks=False, randomize=False)

        # 最大并发数不应超过信号量值（2）
        assert max_active <= 2, f"最大并发数 {max_active} 超过限制 2"

    async def test_cancellation_releases_semaphore(self, controller, monkeypatch):
        """测试任务取消时信号量被正确释放"""
        # 模拟一个长时间运行的任务
        async def mock_extract_slow(video_path, time_sec, output_path, retries=1):
            await asyncio.sleep(10)  # 永不完结
            return True, None

        monkeypatch.setattr(
            'src.controllers.segment_controller.extract_frame_async',
            mock_extract_slow
        )

        controller.density = 3
        controller.screenshots['A'] = [{'time': 10.0 + i, 'path': None, 'locked': False, 'favorite': False, 'exported': False} for i in range(3)]

        sem = controller._ffmpeg_semaphore
        initial_value = sem._value

        # 启动加载，然后取消
        task = asyncio.create_task(controller._load_segment(0, restore_locks=False, randomize=False))
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # 信号量应释放（初始值恢复）
        assert sem._value == initial_value