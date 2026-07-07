# PersistManager: SQLite single source persistent storage
import sqlite3
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import asdict
from config import DB_PATH, CACHE_EXPIRE_DAYS

TABLES = [
    """
    CREATE TABLE IF NOT EXISTS app_config (
        key TEXT PRIMARY KEY,
        value TEXT,
        update_ts REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS video_meta (
        video_hash TEXT PRIMARY KEY,
        full_path TEXT,
        total_duration REAL,
        last_scan_ts REAL,
        is_offline INTEGER DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS segment_state (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_hash TEXT,
        seg_id TEXT,
        start REAL,
        end REAL,
        visited INTEGER DEFAULT 0,
        FOREIGN KEY(video_hash) REFERENCES video_meta(video_hash)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS slot_record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_hash TEXT,
        seg_id TEXT,
        gen_id INTEGER,
        frame_ts REAL,
        cache_path TEXT,
        favorite INTEGER DEFAULT 0,
        locked INTEGER DEFAULT 0,
        quality_score REAL DEFAULT 0.0,
        FOREIGN KEY(video_hash) REFERENCES video_meta(video_hash)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS export_record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_hash TEXT,
        slot_id INTEGER,
        export_type TEXT,
        output_path TEXT,
        export_ts REAL,
        FOREIGN KEY(slot_id) REFERENCES slot_record(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cache_file (
        cache_path TEXT PRIMARY KEY,
        video_hash TEXT,
        create_ts REAL,
        expire_ts REAL
    )
    """
]

class PersistManager:
    def __init__(self, db_file: Path):
        self.db_file = db_file
        self.conn = None

    def connect(self):
        self.conn = sqlite3.connect(str(self.db_file), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        return self.conn.cursor()

    def close(self):
        if self.conn:
            self.conn.commit()
            self.conn.close()
            self.conn = None

    def init_db(self):
        cur = self.connect()
        for sql in TABLES:
            cur.execute(sql)
        self.close()

    # Config CRUD
    def set_config(self, key: str, value):
        cur = self.connect()
        val_str = json.dumps(value)
        ts = time.time()
        cur.execute("""
            INSERT OR REPLACE INTO app_config (key, value, update_ts)
            VALUES (?, ?, ?)
        """, (key, val_str, ts))
        self.close()

    def get_config(self, key: str, default=None):
        cur = self.connect()
        row = cur.execute("SELECT value FROM app_config WHERE key=?", (key,)).fetchone()
        self.close()
        if not row:
            return default
        return json.loads(row[0])

    # Video Meta
    def save_video_meta(self, video_hash: str, path: str, duration: float, offline=0):
        cur = self.connect()
        cur.execute("""
            INSERT OR REPLACE INTO video_meta
            (video_hash, full_path, total_duration, last_scan_ts, is_offline)
            VALUES (?,?,?,?,?)
        """, (video_hash, path, duration, time.time(), offline))
        self.close()

    def get_video_meta(self, video_hash: str):
        cur = self.connect()
        row = cur.execute("SELECT * FROM video_meta WHERE video_hash=?", (video_hash,)).fetchone()
        self.close()
        return row

    # Segment State
    def batch_save_segments(self, video_hash: str, seg_list):
        cur = self.connect()
        cur.execute("DELETE FROM segment_state WHERE video_hash=?", (video_hash,))
        for seg in seg_list:
            cur.execute("""
                INSERT INTO segment_state
                (video_hash, seg_id, start, end, visited)
                VALUES (?,?,?,?,?)
            """, (video_hash, seg.id, seg.start_time, seg.end_time, int(seg.visited)))
        self.close()

    def load_segments(self, video_hash: str):
        cur = self.connect()
        rows = cur.execute("""
            SELECT seg_id, start, end, visited FROM segment_state
            WHERE video_hash=? ORDER BY seg_id
        """, (video_hash,)).fetchall()
        self.close()
        return rows

    # Slot Records
    def clear_slots(self, video_hash: str):
        cur = self.connect()
        cur.execute("DELETE FROM slot_record WHERE video_hash=?", (video_hash,))
        self.close()

    def batch_save_slots(self, video_hash: str, slots):
        cur = self.connect()
        self.clear_slots(video_hash)
        for slot in slots:
            cur.execute("""
                INSERT INTO slot_record
                (video_hash, seg_id, gen_id, frame_ts, cache_path, favorite, locked, quality_score)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                video_hash, slot.source_segment, slot.generation_id,
                slot.frame.timestamp, slot.frame.cache_path,
                int(slot.favorite), int(slot.locked), slot.quality_score
            ))
        self.close()

    def load_slots(self, video_hash: str):
        cur = self.connect()
        rows = cur.execute("""
            SELECT seg_id, gen_id, frame_ts, cache_path, favorite, locked, quality_score
            FROM slot_record WHERE video_hash=?
        """, (video_hash,)).fetchall()
        self.close()
        return rows

    # Cache file record
    def add_cache_record(self, cache_path: str, video_hash: str):
        cur = self.connect()
        now = time.time()
        expire = now + timedelta(days=CACHE_EXPIRE_DAYS).total_seconds()
        cur.execute("""
            INSERT OR REPLACE INTO cache_file (cache_path, video_hash, create_ts, expire_ts)
            VALUES (?,?,?,?)
        """, (cache_path, video_hash, now, expire))
        self.close()

    def get_expired_cache_paths(self):
        cur = self.connect()
        now = time.time()
        rows = cur.execute("SELECT cache_path FROM cache_file WHERE expire_ts < ?", (now,)).fetchall()
        self.close()
        return [r[0] for r in rows]

    def delete_cache_record(self, cache_path: str):
        cur = self.connect()
        cur.execute("DELETE FROM cache_file WHERE cache_path=?", (cache_path,))
        self.close()