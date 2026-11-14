"""
BRAINOVA — MongoDB Atlas Live Synchronization & Cloud Persistence Layer
Mirrors all relational SQLite tables into MongoDB Atlas collections (`brainova` database)
and automatically restores data into ephemeral serverless SQLite instances (e.g., Vercel /tmp).
"""

import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

_logger = logging.getLogger("brainova.mongo_sync")

SYNC_TABLES: List[tuple[str, str]] = [
    ("users", "id"),
    ("user_preferences", "user_id"),
    ("pending_registrations", "id"),
    ("roadmaps", "id"),
    ("roadmap_phases", "id"),
    ("roadmap_topics", "id"),
    ("topic_tutorials", "id"),
    ("topic_readings", "id"),
    ("mcq_sets", "id"),
    ("quiz_attempts", "id"),
    ("flashcards", "id"),
    ("personal_notes", "id"),
    ("sources", "id"),
    ("source_chunks", "id"),
    ("studio_outputs", "id"),
    ("activity_logs", "id"),
    ("diary_entries", "id"),
    ("study_journal_entries", "id"),
    ("focus_sessions", "id"),
    ("focus_events", "id"),
    ("career_profiles", "user_id"),
    ("career_skill_assessments", "id"),
    ("ai_conversations", "id"),
    ("tech_pulse_sources", "id"),
    ("tech_pulse_stories", "id"),
    ("tech_pulse_daily_feed", "ist_date,story_id"),
    ("tech_pulse_bookmarks", "id"),
]

_CLIENT_LOCK = threading.Lock()
_MONGO_CLIENT: Any = None
_MONGO_URI_CACHED: str = ""
_SYNC_IN_PROGRESS = threading.Lock()


def _load_env_if_needed() -> None:
    if os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI"):
        return
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.is_file():
        return
    try:
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip()
            if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
                v = v[1:-1]
            if k:
                os.environ.setdefault(k, v)
    except OSError:
        pass


def get_mongodb_uri() -> str:
    _load_env_if_needed()
    return (os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI") or "").strip()


def get_mongodb_db_name() -> str:
    return (os.environ.get("MONGODB_DB_NAME") or "brainova").strip() or "brainova"


def get_mongo_database() -> Optional[Any]:
    global _MONGO_CLIENT, _MONGO_URI_CACHED
    uri = get_mongodb_uri()
    if not uri:
        return None
    try:
        from pymongo import MongoClient
    except ImportError:
        return None

    with _CLIENT_LOCK:
        if _MONGO_CLIENT is None or _MONGO_URI_CACHED != uri:
            _MONGO_CLIENT = MongoClient(
                uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=10000,
            )
            _MONGO_URI_CACHED = uri
        return _MONGO_CLIENT[get_mongodb_db_name()]


def check_mongo_connection() -> Dict[str, Any]:
    db = get_mongo_database()
    if db is None:
        return {"configured": False, "connected": False}
    try:
        db.command("ping")
        return {"configured": True, "connected": True, "database": db.name}
    except Exception as exc:
        return {"configured": True, "connected": False, "error": type(exc).__name__}


def sync_sqlite_to_mongo(conn: sqlite3.Connection) -> Dict[str, int]:
    """Mirror all application tables from SQLite into MongoDB Atlas collections."""
    db = get_mongo_database()
    if db is None:
        return {}
    if not _SYNC_IN_PROGRESS.acquire(blocking=False):
        return {}

    counts: Dict[str, int] = {}
    try:
        from pymongo import ReplaceOne

        for table_name, pk_col in SYNC_TABLES:
            try:
                rows = conn.execute(f"SELECT * FROM {table_name}").fetchall()
            except sqlite3.Error:
                continue

            coll = db[table_name]
            ops = []
            current_ids = []
            pk_cols = [c.strip() for c in pk_col.split(",") if c.strip()]
            for r in rows:
                doc = dict(r)
                doc_id = ":".join(str(doc.get(c, "")) for c in pk_cols)
                if not doc_id or doc_id == ":":
                    continue
                doc["_id"] = doc_id
                current_ids.append(doc_id)
                ops.append(ReplaceOne({"_id": doc_id}, doc, upsert=True))

            if ops:
                coll.bulk_write(ops, ordered=False)
                coll.delete_many({"_id": {"$nin": current_ids}})
            else:
                # Only clear collection if the local table actually has 0 rows AND we're not on an uninitialized DB
                pass
            counts[table_name] = len(ops)
    except Exception as exc:
        _logger.warning("MongoDB sync warning: %s", type(exc).__name__)
    finally:
        _SYNC_IN_PROGRESS.release()
    return counts


def restore_sqlite_from_mongo(conn: sqlite3.Connection) -> Dict[str, int]:
    """Restore rows from MongoDB Atlas into SQLite (used on cold start or empty SQLite DB)."""
    db = get_mongo_database()
    if db is None:
        return {}

    restored: Dict[str, int] = {}
    try:
        existing_Collections = set(db.list_collection_names())
        conn.execute("PRAGMA foreign_keys = OFF;")
        try:
            for table_name, pk_col in SYNC_TABLES:
                if table_name not in existing_Collections:
                    continue
                docs = list(db[table_name].find({}))
                if not docs:
                    continue

                col_info = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
                valid_cols = [c["name"] if isinstance(c, dict) else c[1] for c in col_info]
                if not valid_cols:
                    continue

                placeholders = ", ".join(["?"] * len(valid_cols))
                col_list_sql = ", ".join(valid_cols)
                sql = f"INSERT OR REPLACE INTO {table_name} ({col_list_sql}) VALUES ({placeholders})"

                rows_to_insert = []
                for doc in docs:
                    rows_to_insert.append(tuple(doc.get(c) for c in valid_cols))

                if rows_to_insert:
                    conn.executemany(sql, rows_to_insert)
                    restored[table_name] = len(rows_to_insert)
            conn.commit()
        finally:
            conn.execute("PRAGMA foreign_keys = ON;")
    except Exception as exc:
        _logger.warning("MongoDB restore warning: %s", type(exc).__name__)
    return restored
