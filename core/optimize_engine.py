# OptimizeEngine v3.1 全局分区重采样引擎
# 规则：默认保留 locked / favorite 帧，仅刷新普通Slot
from typing import List
from core.state_manager import Video, Segment, Frame, Slot
from core.sampling_engine import SamplingEngine

class OptimizeEngine:
    def __init__(self, sampling_engine: SamplingEngine):
        self.sampling_engine = sampling_engine

    def global_resample_current_segment(
        self,
        video: Video,
        target_seg: Segment,
        grid_size: int,
        gen_id: int,
        force_refresh_favorite: bool = False
    ) -> List[Frame]:
        """
        对当前Segment执行全局均衡重采样
        :param force_refresh_favorite: True=强制替换收藏帧；False=保留收藏帧（默认）
        :return 全新候选帧列表，用于替换可刷新Slot
        """
        all_new_frames = self.sampling_engine.sample_segment(
            video=video,
            target_seg=target_seg,
            grid_size=grid_size,
            gen_id=gen_id
        )
        return all_new_frames

    def filter_replaceable_slots(self, slots: List[Slot], force_refresh_favorite: bool = False) -> List[Slot]:
        """
        筛选允许被替换的Slot
        锁定帧永远不可替换；收藏帧仅在强制模式下可替换
        """
        replaceable = []
        for slot in slots:
            if slot.locked:
                continue
            if slot.favorite and not force_refresh_favorite:
                continue
            replaceable.append(slot)
        return replaceable