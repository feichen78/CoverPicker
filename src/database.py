# src/database.py
# 修复 file_id 列迁移问题（使用更可靠的列检查方法）

import os
import sqlite3
import logging
import shutil
import time
import json
import hashlib
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class Database:
    """CoverPicker SQLite 数据库管理类 - 支持跨设备视频状态同步"""

    DB_VERSION = 2

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            home = Path.home()
            data_dir = home / ".coverpicker"
            data_dir.mkdir(exist_ok=True)
            db_path = data_dir / "coverpicker.db"
        self.db_path = str(db_path)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def _compute_file_id(self, file_path: str, file_size: int, modified_time: int) -> str:
        """计算文件唯一标识（跨设备一致）"""
        file_name = os.path.basename(file_path)
        unique_str = f"{file_name}|{file_size}|{modified_time}"
        return hashlib.md5(unique_str.encode('utf-8')).hexdigest()

    def _column_exists(self, table: str, column: str) -> bool:
        """检查表中是否存在指定列（更可靠的方法）"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            # 使用 PRAGMA table_info 获取所有列
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [row[1].lower() for row in cursor.fetchall()]
            return column.lower() in columns
        except sqlite3.OperationalError:
            return False

    def _init_db(self) -> None:
        """初始化数据库表结构（支持跨设备同步）"""
        conn = self._get_conn()
        cursor = conn.cursor()

        # 创建 videos 表（先创建基础表）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
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
        conn.commit()

        # ============================================================
        # 迁移：添加 file_id 列（使用更可靠的方法）
        # ============================================================
        try:
            # 先检查列是否存在
            cursor.execute("PRAGMA table_info(videos)")
            existing_columns = [row[1].lower() for row in cursor.fetchall()]
            
            if 'file_id' not in existing_columns:
                logger.info("正在添加 file_id 列...")
                # 先尝试直接添加
                try:
                    cursor.execute("ALTER TABLE videos ADD COLUMN file_id TEXT UNIQUE")
                    conn.commit()
                    logger.info("成功添加 file_id 列")
                except sqlite3.OperationalError as e:
                    logger.warning(f"直接添加失败: {e}")
                    # 如果直接添加失败，尝试重建表
                    self._migrate_add_file_id()
        except Exception as e:
            logger.error(f"file_id 迁移失败: {e}")

        # 再次检查 file_id 是否存在
        cursor.execute("PRAGMA table_info(videos)")
        existing_columns = [row[1].lower() for row in cursor.fetchall()]
        
        if 'file_id' in existing_columns:
            # 为现有视频生成 file_id
            cursor.execute("SELECT id, file_path, file_size, modified_time FROM videos WHERE file_id IS NULL")
            rows = cursor.fetchall()
            for row in rows:
                file_id = self._compute_file_id(
                    row['file_path'],
                    row['file_size'] or 0,
                    row['modified_time'] or 0
                )
                cursor.execute(
                    "UPDATE videos SET file_id = ? WHERE id = ?",
                    (file_id, row['id'])
                )
            if rows:
                conn.commit()
                logger.info(f"为 {len(rows)} 个视频生成了 file_id")

            # 创建 file_id 索引
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_file_id ON videos(file_id)")
                conn.commit()
            except sqlite3.OperationalError as e:
                logger.warning(f"创建索引失败: {e}")

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
                excluded_ranges TEXT DEFAULT '[]',
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
                UNIQUE(video_id, segment_label)
            )
        """)

        # 迁移：为 segments 表添加 excluded_ranges 列（如果不存在）
        if not self._column_exists('segments', 'excluded_ranges'):
            try:
                cursor.execute("ALTER TABLE segments ADD COLUMN excluded_ranges TEXT DEFAULT '[]'")
                conn.commit()
                logger.info("数据库迁移: segments 表添加 excluded_ranges 列")
            except sqlite3.OperationalError as e:
                logger.warning(f"添加 excluded_ranges 列失败: {e}")

        # 创建 favorites 表
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

        # 迁移：为 favorites 表添加 is_exported 列（如果不存在）
        if not self._column_exists('favorites', 'is_exported'):
            try:
                cursor.execute("ALTER TABLE favorites ADD COLUMN is_exported INTEGER DEFAULT 0")
                conn.commit()
                logger.info("数据库迁移: favorites 表添加 is_exported 列")
            except sqlite3.OperationalError as e:
                logger.warning(f"添加 is_exported 列失败: {e}")

        # 创建索引
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_viewed ON videos(is_viewed)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_starred ON videos(is_starred)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_exported ON videos(is_exported)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_favorites_video ON favorites(video_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_file_path ON videos(file_path)")
        except sqlite3.OperationalError as e:
            logger.warning(f"创建索引失败: {e}")

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

    def _migrate_add_file_id(self):
        """通过重建表的方式添加 file_id 列（备用方案）"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            logger.info("使用备用方案添加 file_id 列...")
            
            # 1. 创建新表（包含 file_id）
            cursor.execute("""
                CREATE TABLE videos_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT UNIQUE,
                    file_path TEXT NOT NULL,
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
            
            # 2. 复制数据
            cursor.execute("""
                INSERT INTO videos_new (
                    id, file_path, file_name, duration, resolution,
                    file_size, modified_time, is_viewed, is_starred,
                    is_exported, last_edited, created_at
                )
                SELECT 
                    id, file_path, file_name, duration, resolution,
                    file_size, modified_time, is_viewed, is_starred,
                    is_exported, last_edited, created_at
                FROM videos
            """)
            
            # 3. 生成 file_id
            cursor.execute("SELECT id, file_path, file_size, modified_time FROM videos_new")
            rows = cursor.fetchall()
            for row in rows:
                file_id = self._compute_file_id(
                    row['file_path'],
                    row['file_size'] or 0,
                    row['modified_time'] or 0
                )
                cursor.execute(
                    "UPDATE videos_new SET file_id = ? WHERE id = ?",
                    (file_id, row['id'])
                )
            
            # 4. 删除旧表，重命名新表
            cursor.execute("DROP TABLE videos")
            cursor.execute("ALTER TABLE videos_new RENAME TO videos")
            
            conn.commit()
            logger.info("备用方案成功添加 file_id 列")
        except Exception as e:
            logger.error(f"备用方案失败: {e}")
            conn.rollback()
            raise

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ============================================================
    # 视频操作（支持跨设备同步）
    # ============================================================

    def get_or_create_video(self, file_path: str, file_name: str, duration: int,
                            resolution: str = "", file_size: int = 0,
                            modified_time: int = 0) -> int:
        """获取或创建视频记录，返回视频 ID。使用 file_id 作为跨设备唯一标识。"""
        conn = self._get_conn()
        cursor = conn.cursor()

        # 计算文件唯一标识
        file_id = self._compute_file_id(file_path, file_size, modified_time)

        # 先通过 file_id 查找
        cursor.execute("SELECT id, file_path, duration, file_size, modified_time FROM videos WHERE file_id = ?", (file_id,))
        row = cursor.fetchone()

        if row:
            vid = row['id']
            if row['file_path'] != file_path:
                cursor.execute("UPDATE videos SET file_path = ? WHERE id = ?", (file_path, vid))
            if row['file_size'] != file_size or row['modified_time'] != modified_time:
                cursor.execute("""
                    UPDATE videos SET 
                        file_size = ?, modified_time = ?, duration = ?, resolution = ?
                    WHERE id = ?
                """, (file_size, modified_time, duration, resolution, vid))
                conn.commit()
                logger.debug(f"更新视频元数据: {file_name} (ID: {vid})")
            return vid

        # 如果没有 file_id，尝试通过文件路径查找（兼容旧数据）
        cursor.execute("SELECT id, file_size, modified_time FROM videos WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        if row:
            vid = row['id']
            cursor.execute("UPDATE videos SET file_id = ? WHERE id = ?", (file_id, vid))
            conn.commit()
            return vid

        # 创建新记录
        cursor.execute("""
            INSERT INTO videos (
                file_id, file_path, file_name, duration, resolution, file_size, modified_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (file_id, file_path, file_name, duration, resolution, file_size, modified_time))
        conn.commit()
        return cursor.lastrowid

    def get_video_by_path(self, file_path: str) -> Optional[Dict]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_video_by_file_id(self, file_id: str) -> Optional[Dict]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE file_id = ?", (file_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_video_id_by_path_or_file_id(self, file_path: str, file_size: int, modified_time: int) -> Optional[int]:
        conn = self._get_conn()
        cursor = conn.cursor()

        file_id = self._compute_file_id(file_path, file_size, modified_time)

        cursor.execute("SELECT id FROM videos WHERE file_id = ?", (file_id,))
        row = cursor.fetchone()
        if row:
            return row['id']

        cursor.execute("SELECT id FROM videos WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE videos SET file_id = ? WHERE id = ?", (file_id, row['id']))
            conn.commit()
            return row['id']

        return None

    def update_video_state(self, video_id: int, is_viewed: Optional[bool] = None,
                           is_starred: Optional[bool] = None,
                           is_exported: Optional[bool] = None) -> None:
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
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, file_path, file_name, duration, resolution, file_size,
                   is_viewed, is_starred, is_exported
            FROM videos
            ORDER BY file_name
        """)
        return [dict(row) for row in cursor.fetchall()]

    # ============================================================
    # 分区操作（含排除区间）
    # ============================================================

    def get_or_create_segment(self, video_id: int, segment_label: str,
                              time_start: int, time_end: int) -> int:
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, excluded_ranges FROM segments WHERE video_id = ? AND segment_label = ?
        """, (video_id, segment_label))
        row = cursor.fetchone()
        if row:
            return row['id']

        cursor.execute("""
            INSERT INTO segments (video_id, segment_label, time_start, time_end, excluded_ranges)
            VALUES (?, ?, ?, ?, ?)
        """, (video_id, segment_label, time_start, time_end, '[]'))
        conn.commit()
        return cursor.lastrowid

    def update_segment_state(self, video_id: int, segment_label: str,
                             is_viewed: Optional[bool] = None,
                             has_starred: Optional[bool] = None,
                             has_exported: Optional[bool] = None,
                             excluded_ranges: Optional[List[Tuple[float, float]]] = None) -> None:
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
        if excluded_ranges is not None:
            updates.append("excluded_ranges = ?")
            params.append(json.dumps(excluded_ranges))

        if not updates:
            return

        params.extend([video_id, segment_label])
        cursor.execute(f"""
            UPDATE segments SET {', '.join(updates)}
            WHERE video_id = ? AND segment_label = ?
        """, params)
        conn.commit()

    def get_segment_state(self, video_id: int, segment_label: str) -> Optional[Dict]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT is_viewed, has_starred, has_exported, excluded_ranges
            FROM segments
            WHERE video_id = ? AND segment_label = ?
        """, (video_id, segment_label))
        row = cursor.fetchone()
        if row:
            result = dict(row)
            if result.get('excluded_ranges'):
                try:
                    result['excluded_ranges'] = json.loads(result['excluded_ranges'])
                except:
                    result['excluded_ranges'] = []
            else:
                result['excluded_ranges'] = []
            return result
        return None

    def get_all_segments(self, video_id: int) -> List[Dict]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT segment_label, is_viewed, has_starred, has_exported, excluded_ranges
            FROM segments
            WHERE video_id = ?
            ORDER BY segment_label
        """, (video_id,))
        results = []
        for row in cursor.fetchall():
            item = dict(row)
            if item.get('excluded_ranges'):
                try:
                    item['excluded_ranges'] = json.loads(item['excluded_ranges'])
                except:
                    item['excluded_ranges'] = []
            else:
                item['excluded_ranges'] = []
            results.append(item)
        return results

    # ============================================================
    # 收藏操作
    # ============================================================

    def add_favorite(self, video_id: int, segment_label: str,
                     timestamp_ms: int, thumbnail_path: str = "",
                     is_exported: bool = False) -> int:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO favorites (video_id, segment_label, timestamp_ms, thumbnail_path, is_exported)
            VALUES (?, ?, ?, ?, ?)
        """, (video_id, segment_label, timestamp_ms, thumbnail_path, 1 if is_exported else 0))
        conn.commit()
        return cursor.lastrowid

    def remove_favorite(self, video_id: int, segment_label: str, timestamp_ms: int) -> None:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM favorites
            WHERE video_id = ? AND segment_label = ? AND timestamp_ms = ?
        """, (video_id, segment_label, timestamp_ms))
        conn.commit()

    def update_favorite_exported(self, video_id: int, segment_label: str, timestamp_ms: int) -> None:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE favorites SET is_exported = 1
            WHERE video_id = ? AND segment_label = ? AND timestamp_ms = ?
        """, (video_id, segment_label, timestamp_ms))
        conn.commit()

    def clear_favorites(self, video_id: int) -> None:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM favorites WHERE video_id = ?", (video_id,))
        conn.commit()

    def get_favorites(self, video_id: int) -> List[Dict]:
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
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 1 FROM favorites
            WHERE video_id = ? AND segment_label = ? AND timestamp_ms = ?
        """, (video_id, segment_label, timestamp_ms))
        return cursor.fetchone() is not None

    # ============================================================
    # 备份与恢复（云同步支持）
    # ============================================================

    def backup(self, backup_dir: str) -> Tuple[bool, str]:
        try:
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)

            if self._conn:
                self._conn.close()
                self._conn = None

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_name = f"coverpicker_backup_{timestamp}.db"
            backup_path = os.path.join(backup_dir, backup_name)

            shutil.copy2(self.db_path, backup_path)

            self._init_db()

            return True, backup_path
        except Exception as e:
            logger.error(f"备份数据库失败: {e}")
            return False, str(e)

    def restore(self, backup_path: str) -> Tuple[bool, str]:
        try:
            if not os.path.exists(backup_path):
                return False, f"备份文件不存在: {backup_path}"

            if self._conn:
                self._conn.close()
                self._conn = None

            old_path = self.db_path + ".old"
            if os.path.exists(self.db_path):
                shutil.copy2(self.db_path, old_path)

            shutil.copy2(backup_path, self.db_path)

            self._init_db()

            return True, f"成功从 {backup_path} 恢复数据库"
        except Exception as e:
            logger.error(f"恢复数据库失败: {e}")
            return False, str(e)

    def get_backup_history(self, backup_dir: str, limit: int = 20) -> List[Dict]:
        if not os.path.exists(backup_dir):
            return []

        backups = []
        for f in os.listdir(backup_dir):
            if f.startswith("coverpicker_backup_") and f.endswith(".db"):
                file_path = os.path.join(backup_dir, f)
                stat = os.stat(file_path)
                backups.append({
                    'path': file_path,
                    'name': f,
                    'size': stat.st_size,
                    'time': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    'mtime': stat.st_mtime
                })

        backups.sort(key=lambda x: x['mtime'], reverse=True)
        return backups[:limit]

    # ============================================================
    # 其他方法
    # ============================================================

    def vacuum(self) -> None:
        conn = self._get_conn()
        conn.execute("VACUUM")
        conn.commit()

    def delete_video(self, video_id: int) -> None:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        conn.commit()