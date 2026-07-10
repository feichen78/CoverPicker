import sqlite3
import os
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class StateManager:
    """管理视频状态（锁定、收藏、导出、已浏览）的 SQLite 持久化"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        db_path = os.path.join(os.path.dirname(__file__), "coverpicker_state.db")
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        # 创建表（包含所有字段）
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS video_state (
                video_path TEXT,
                segment_label TEXT,
                position INTEGER,
                locked INTEGER DEFAULT 0,
                viewed INTEGER DEFAULT 0,
                exported INTEGER DEFAULT 0,
                favorite INTEGER DEFAULT 0,
                PRIMARY KEY (video_path, segment_label, position)
            )
        ''')
        # 为旧表添加字段（安全方式）
        for col in ['favorite', 'exported']:
            try:
                self.cursor.execute(f"ALTER TABLE video_state ADD COLUMN {col} INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # 字段已存在
        self.conn.commit()

    def load_state(self, video_path: str, segment_label: str) -> Dict[int, Dict]:
        """加载某个视频某个分段的所有位置状态"""
        try:
            self.cursor.execute(
                "SELECT position, locked, viewed, exported, favorite FROM video_state WHERE video_path=? AND segment_label=?",
                (video_path, segment_label)
            )
            rows = self.cursor.fetchall()
            state = {}
            for pos, locked, viewed, exported, favorite in rows:
                state[pos] = {
                    'locked': bool(locked),
                    'viewed': bool(viewed),
                    'exported': bool(exported),
                    'favorite': bool(favorite)
                }
            return state
        except Exception as e:
            logger.error(f"load_state error: {e}")
            return {}

    def save_state(self, video_path: str, segment_label: str, position: int,
                   locked: Optional[bool] = None,
                   viewed: Optional[bool] = None,
                   exported: Optional[bool] = None,
                   favorite: Optional[bool] = None):
        """保存单个位置状态（若某个字段为 None 则不更新）"""
        try:
            # 获取当前值
            self.cursor.execute(
                "SELECT locked, viewed, exported, favorite FROM video_state WHERE video_path=? AND segment_label=? AND position=?",
                (video_path, segment_label, position)
            )
            row = self.cursor.fetchone()
            if row:
                cur_locked, cur_viewed, cur_exported, cur_favorite = row
            else:
                cur_locked, cur_viewed, cur_exported, cur_favorite = 0, 0, 0, 0

            new_locked = locked if locked is not None else cur_locked
            new_viewed = viewed if viewed is not None else cur_viewed
            new_exported = exported if exported is not None else cur_exported
            new_favorite = favorite if favorite is not None else cur_favorite

            self.cursor.execute('''
                INSERT OR REPLACE INTO video_state (video_path, segment_label, position, locked, viewed, exported, favorite)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (video_path, segment_label, position, int(new_locked), int(new_viewed),
                  int(new_exported), int(new_favorite)))
            self.conn.commit()
        except Exception as e:
            logger.error(f"save_state error: {e}")

    def save_all_states(self, video_path: str, segment_label: str, states: Dict[int, Dict]):
        """批量保存某个分段的所有位置状态"""
        for pos, state in states.items():
            self.save_state(video_path, segment_label, pos,
                            locked=state.get('locked'),
                            viewed=state.get('viewed'),
                            exported=state.get('exported'),
                            favorite=state.get('favorite'))

    def clear_segment_states(self, video_path: str, segment_label: str):
        """清除某个分段的所有状态（用于全部重抽时）"""
        try:
            self.cursor.execute(
                "DELETE FROM video_state WHERE video_path=? AND segment_label=?",
                (video_path, segment_label)
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"clear_segment_states error: {e}")