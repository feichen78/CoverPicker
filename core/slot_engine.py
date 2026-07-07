# SlotEngine 管理Slot生命周期、收藏、锁定、替换逻辑
from typing import List
from core.state_manager import Slot, Frame

class SlotEngine:
    @staticmethod
    def create_slots(frames: List[Frame], seg_id: str, gen_id: int, start_slot_id: int) -> List[Slot]:
        slot_list = []
        current_id = start_slot_id
        for frame in frames:
            slot = Slot(
                id=current_id,
                frame=frame,
                state="GENERATED",
                source_segment=seg_id,
                generation_id=gen_id
            )
            slot_list.append(slot)
            current_id += 1
        return slot_list, current_id

    @staticmethod
    def toggle_favorite(slot: Slot):
        if slot.locked:
            return
        slot.favorite = not slot.favorite
        if slot.favorite:
            slot.state = "SELECTED"
        else:
            slot.state = "VIEWED"

    @staticmethod
    def toggle_lock(slot: Slot):
        slot.locked = not slot.locked
        if slot.locked:
            slot.state = "LOCKED"
        else:
            if slot.favorite:
                slot.state = "SELECTED"
            else:
                slot.state = "VIEWED"

    @staticmethod
    def replace_unlocked_slots(slots: List[Slot], new_frames: List[Frame], seg_id: str, gen_id: int):
        ptr = 0
        for slot in slots:
            if slot.locked:
                continue
            if ptr >= len(new_frames):
                break
            slot.frame = new_frames[ptr]
            slot.state = "GENERATED"
            slot.generation_id = gen_id
            slot.source_segment = seg_id
            ptr += 1
        return slots