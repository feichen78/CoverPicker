# src/database.py

import os
import sqlite3
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class Database:
    """CoverPicker SQLite 数据库管理类 - 状态持久化"""

    # 数据库版本
    DB_VERSION = 1

    def __init__(self, db_path: Optional[str] = None):
        """初始化数据库连接

        Args:
            db_path: 数据库文件路径，默认为 ~/.coverpicker/coverpicker.db
        """
        if db_path is None:
            home = Path.home()
            data_dir = home / ".coverpicker"
            data_dir.mkdir(exist_ok=True)
            db_path = data_dir / "coverpicker.db"
        self.db_path = str(db_path)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接（使用 row_factory 返回字典）"""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            # 启用外键约束
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def _init_db(self) -> None:
        """初始化数据库表结构"""
        conn = self._get_conn()
        cursor = conn.cursor()

        # 创建 videos 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL UNIQUE,
                file_name TEXT NOT NULL,
                duration INTEGER,
                resolution TEXT,
                file_size INTEGER,
                modified_time INTEGER,
                is_viewed INTEGER DEFAULT 0,
                is_starred INTEGER DEFAULT 0,
                is_exported INTEGER DEFAULT 0,
                last_edited INTEGER,
                created_at INTEGER DEFAULT (strftime('%s','now'))
            )
        """)

        # 创建 segments 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS segments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL,
                segment_label TEXT NOT NULL,
                time_start INTEGER NOT NULL,
                time_end INTEGER NOT NULL,
                is_viewed INTEGER DEFAULT 0,
                has_starred INTEGER DEFAULT 0,
                has_exported INTEGER DEFAULT 0,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
                UNIQUE(video_id, segment_label)
            )
        """)

        # 创建 favorites 表 - 包含 is_exported 字段
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL,
                segment_label TEXT NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                thumbnail_path TEXT,
                is_exported INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT (strftime('%s','now')),
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
            )
        """)

        # 迁移：为已存在的 favorites 表添加 is_exported 列（如果不存在）
        try:
            cursor.execute("ALTER TABLE favorites ADD COLUMN is_exported INTEGER DEFAULT 0")
            logger.info("数据库迁移: favorites 表添加 is_exported 列")
        except sqlite3.OperationalError:
            # 列已存在，忽略
            pass

        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_viewed ON videos(is_viewed)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_starred ON videos(is_starred)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_exported ON videos(is_exported)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_favorites_video ON favorites(video_id)")

        # 创建版本表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        cursor.execute(
            "INSERT OR IGNORE INTO metadata (key, value) VALUES ('db_version', ?)",
            (str(self.DB_VERSION),)
        )

        conn.commit()
        logger.info(f"数据库初始化完成: {self.db_path}")

    def close(self) -> None:
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None

    # ========== 视频操作 ==========

    def get_or_create_video(self, file_path: str, file_name: str, duration: int,
                            resolution: str = "", file_size: int = 0,
                            modified_time: int = 0) -> int:
        """
        获取或创建视频记录，返回视频 ID。
        如果文件已存在但文件大小或修改时间变化，自动更新 duration。
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # 检查是否已存在
        cursor.execute("SELECT id, duration, file_size, modified_time FROM videos WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        if row:
            vid = row['id']
            # 如果文件大小或修改时间变化，更新 duration
            if row['file_size'] != file_size or row['modified_time'] != modified_time:
                cursor.execute("""
                    UPDATE videos SET 
                        file_size = ?, modified_time = ?, duration = ?, resolution = ?
                    WHERE id = ?
                """, (file_size, modified_time, duration, resolution, vid))
                conn.commit()
                logger.debug(f"更新视频元数据: {file_name} (ID: {vid})")
            return vid

        # 不存在则插入
        cursor.execute("""
            INSERT INTO videos (
                file_path, file_name, duration, resolution, file_size, modified_time
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (file_path, file_name, duration, resolution, file_size, modified_time))
        conn.commit()
        return cursor.lastrowid

    def get_video_by_path(self, file_path: str) -> Optional[Dict]:
        """根据路径查询视频记录"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_video_state(self, video_id: int, is_viewed: Optional[bool] = None,
                           is_starred: Optional[bool] = None,
                           is_exported: Optional[bool] = None) -> None:
        """更新视频状态"""
        conn = self._get_conn()
        cursor = conn.cursor()

        updates = []
        params = []
        if is_viewed is not None:
            updates.append("is_viewed = ?")
            params.append(1 if is_viewed else 0)
        if is_starred is not None:
            updates.append("is_starred = ?")
            params.append(1 if is_starred else 0)
        if is_exported is not None:
            updates.append("is_exported = ?")
            params.append(1 if is_exported else 0)

        if not updates:
            return

        updates.append("last_edited = strftime('%s','now')")
        params.append(video_id)

        cursor.execute(f"""
            UPDATE videos SET {', '.join(updates)}
            WHERE id = ?
        """, params)
        conn.commit()

    def get_all_videos(self) -> List[Dict]:
        """获取所有视频记录"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, file_path, file_name, duration, resolution, file_size,
                   is_viewed, is_starred, is_exported
            FROM videos
            ORDER BY file_name
        """)
        return [dict(row) for row in cursor.fetchall()]

    # ========== 分区操作 ==========

    def get_or_create_segment(self, video_id: int, segment_label: str,
                              time_start: int, time_end: int) -> int:
        """获取或创建分区记录，返回分区 ID"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id FROM segments WHERE video_id = ? AND segment_label = ?
        """, (video_id, segment_label))
        row = cursor.fetchone()
        if row:
            return row['id']

        cursor.execute("""
            INSERT INTO segments (video_id, segment_label, time_start, time_end)
            VALUES (?, ?, ?, ?)
        """, (video_id, segment_label, time_start, time_end))
        conn.commit()
        return cursor.lastrowid

    def update_segment_state(self, video_id: int, segment_label: str,
                             is_viewed: Optional[bool] = None,
                             has_starred: Optional[bool] = None,
                             has_exported: Optional[bool] = None) -> None:
        """更新分区状态"""
        conn = self._get_conn()
        cursor = conn.cursor()

        updates = []
        params = []
        if is_viewed is not None:
            updates.append("is_viewed = ?")
            params.append(1 if is_viewed else 0)
        if has_starred is not None:
            updates.append("has_starred = ?")
            params.append(1 if has_starred else 0)
        if has_exported is not None:
            updates.append("has_exported = ?")
            params.append(1 if has_exported else 0)

        if not updates:
            return

        params.extend([video_id, segment_label])
        cursor.execute(f"""
            UPDATE segments SET {', '.join(updates)}
            WHERE video_id = ? AND segment_label = ?
        """, params)
        conn.commit()

    def get_segment_state(self, video_id: int, segment_label: str) -> Optional[Dict]:
        """获取分区状态"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT is_viewed, has_starred, has_exported
            FROM segments
            WHERE video_id = ? AND segment_label = ?
        """, (video_id, segment_label))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_segments(self, video_id: int) -> List[Dict]:
        """获取视频的所有分区"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT segment_label, is_viewed, has_starred, has_exported
            FROM segments
            WHERE video_id = ?
            ORDER BY segment_label
        """, (video_id,))
        return [dict(row) for row in cursor.fetchall()]

    # ========== 收藏操作 ==========

    def add_favorite(self, video_id: int, segment_label: str,
                     timestamp_ms: int, thumbnail_path: str = "",
                     is_exported: bool = False) -> int:
        """添加收藏"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO favorites (video_id, segment_label, timestamp_ms, thumbnail_path, is_exported)
            VALUES (?, ?, ?, ?, ?)
        """, (video_id, segment_label, timestamp_ms, thumbnail_path, 1 if is_exported else 0))
        conn.commit()
        return cursor.lastrowid

    def remove_favorite(self, video_id: int, segment_label: str, timestamp_ms: int) -> None:
        """删除收藏"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM favorites
            WHERE video_id = ? AND segment_label = ? AND timestamp_ms = ?
        """, (video_id, segment_label, timestamp_ms))
        conn.commit()

    def update_favorite_exported(self, video_id: int, segment_label: str, timestamp_ms: int) -> None:
        """标记收藏为已导出"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE favorites SET is_exported = 1
            WHERE video_id = ? AND segment_label = ? AND timestamp_ms = ?
        """, (video_id, segment_label, timestamp_ms))
        conn.commit()

    def clear_favorites(self, video_id: int) -> None:
        """清空视频的所有收藏"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM favorites WHERE video_id = ?", (video_id,))
        conn.commit()

    def get_favorites(self, video_id: int) -> List[Dict]:
        """获取视频的所有收藏"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT segment_label, timestamp_ms, thumbnail_path, is_exported, created_at
            FROM favorites
            WHERE video_id = ?
            ORDER BY segment_label, timestamp_ms
        """, (video_id,))
        return [dict(row) for row in cursor.fetchall()]

    def is_favorite(self, video_id: int, segment_label: str, timestamp_ms: int) -> bool:
        """检查是否为收藏"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 1 FROM favorites
            WHERE video_id = ? AND segment_label = ? AND timestamp_ms = ?
        """, (video_id, segment_label, timestamp_ms))
        return cursor.fetchone() is not None

    # ========== 批量操作 ==========

    def save_video_state(self, video_id: int, segments: Dict[str, Dict],
                         favorites: List[Tuple[str, int, str]]) -> None:
        """批量保存视频状态（用于加载时恢复）"""
        conn = self._get_conn()
        cursor = conn.cursor()

        # 更新分区状态
        for seg_label, state in segments.items():
            cursor.execute("""
                UPDATE segments SET
                    is_viewed = ?,
                    has_starred = ?,
                    has_exported = ?
                WHERE video_id = ? AND segment_label = ?
            """, (
                1 if state.get('is_viewed', False) else 0,
                1 if state.get('has_starred', False) else 0,
                1 if state.get('has_exported', False) else 0,
                video_id, seg_label
            ))

        # 清空旧收藏并重新插入
        cursor.execute("DELETE FROM favorites WHERE video_id = ?", (video_id,))
        for seg_label, timestamp_ms, thumbnail_path in favorites:
            cursor.execute("""
                INSERT INTO favorites (video_id, segment_label, timestamp_ms, thumbnail_path)
                VALUES (?, ?, ?, ?)
            """, (video_id, seg_label, timestamp_ms, thumbnail_path))

        conn.commit()

    def get_video_full_state(self, video_id: int) -> Dict:
        """获取视频完整状态"""
        conn = self._get_conn()
        cursor = conn.cursor()

        # 视频信息
        cursor.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
        video = cursor.fetchone()

        # 分区状态
        cursor.execute("""
            SELECT segment_label, is_viewed, has_starred, has_exported
            FROM segments WHERE video_id = ?
        """, (video_id,))
        segments = [dict(row) for row in cursor.fetchall()]

        # 收藏
        cursor.execute("""
            SELECT segment_label, timestamp_ms, thumbnail_path
            FROM favorites WHERE video_id = ?
        """, (video_id,))
        favorites = [dict(row) for row in cursor.fetchall()]

        return {
            'video': dict(video) if video else None,
            'segments': segments,
            'favorites': favorites
        }

    # ========== 清理 ==========

    def vacuum(self) -> None:
        """压缩数据库"""
        conn = self._get_conn()
        conn.execute("VACUUM")
        conn.commit()

    def delete_video(self, video_id: int) -> None:
        """删除视频及其所有关联数据"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        conn.commit()