# BestEngine v3.1 优先级评分系统
from typing import List, Optional

class BestEngine:
    LOCK_WEIGHT = 10.0
    FAVORITE_WEIGHT = 5.0
    QUALITY_MAX_SCORE = 5.0

    @staticmethod
    def calc_single_slot_score(slot) -> float:
        """计算单Slot综合优先级分数"""
        base = 0.0
        if slot.locked:
            base += BestEngine.LOCK_WEIGHT
        if slot.favorite:
            base += BestEngine.FAVORITE_WEIGHT
        base += slot.quality_score
        return base

    @staticmethod
    def compute_best_slot(slots) -> Optional[int]:
        """遍历全部Slot，返回最优slot id，无数据返回None"""
        if not slots:
            return None
        best_slot = max(slots, key=lambda s: BestEngine.calc_single_slot_score(s))
        return best_slot.id

    @staticmethod
    def calculate_frame_quality(img_brightness: float) -> float:
        """基础画质分 0~5，亮度适中分数高，过暗过亮降低分数"""
        mid = 128
        diff = abs(img_brightness - mid)
        score = BestEngine.QUALITY_MAX_SCORE - (diff / mid) * BestEngine.QUALITY_MAX_SCORE
        return round(max(0.0, score), 2)