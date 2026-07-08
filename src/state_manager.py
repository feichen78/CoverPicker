# region --- 全局状态管理器 ---
import json
import os

class StateManager:
    """
    负责管理应用的全局状态，确保数据驱动 UI。
    """
    STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app_state.json")

    def __init__(self):
        self.state = self._load_state()

    def _load_state(self):
        """从本地 JSON 加载状态，如果不存在则初始化默认状态"""
        if os.path.exists(self.STATE_FILE):
            try:
                with open(self.STATE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        
        # 默认状态结构
        return {
            "settings": {"grid_density": 16},
            "videos": {}  # { "video_path": { "segments": [...], "favorites": [], "locked": [] } }
        }

    def save_state(self):
        """将当前状态持久化到本地 JSON"""
        try:
            with open(self.STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[错误] 保存状态失败: {e}")

    def get_video_state(self, video_path):
        """获取指定视频的状态，如果不存在则初始化"""
        if video_path not in self.state["videos"]:
            self.state["videos"][video_path] = {
                "segments": [],
                "favorites": [],
                "locked": []
            }
        return self.state["videos"][video_path]

    def toggle_favorite(self, video_path, img_path):
        """切换收藏状态"""
        video_state = self.get_video_state(video_path)
        if img_path in video_state["favorites"]:
            video_state["favorites"].remove(img_path)
        else:
            video_state["favorites"].append(img_path)
        self.save_state()

    def toggle_lock(self, video_path, img_path):
        """切换锁定状态"""
        video_state = self.get_video_state(video_path)
        if img_path in video_state["locked"]:
            video_state["locked"].remove(img_path)
        else:
            video_state["locked"].append(img_path)
        self.save_state()

    def set_grid_density(self, density):
        """设置网格密度"""
        self.state["settings"]["grid_density"] = density
        self.save_state()

# endregion