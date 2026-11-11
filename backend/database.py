"""
BRAINOVA — Relational Database Architecture (SQLite + WAL + Foreign Key Integrity)
Models all core entities with explicit ownership checks, cascade rules, indexes, and non-destructive migrations.
"""

import os
import json
import uuid
import sqlite3
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
AUDIO_DIR = os.path.join(DATA_DIR, "audio")
VIDEOS_DIR = os.path.join(DATA_DIR, "videos")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)


def get_db_path() -> str:
    custom = os.environ.get("AETHER_DB_PATH")
    if custom:
        if os.path.isabs(custom):
            return custom
        return os.path.join(BASE_DIR, custom)
    return os.path.join(DATA_DIR, "aetherlearn.db")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str = "") -> str:
    uid = uuid.uuid4().hex[:16]
    return f"{prefix}_{uid}" if prefix else uid


def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> Dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


@contextmanager
def get_db(commit: bool = False):
    conn = sqlite3.connect(get_db_path(), timeout=30.0, check_same_thread=False)
    conn.row_factory = dict_factory
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    try:
        yield conn
        if commit:
            conn.commit()
    except Exception:
        if commit:
            conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'student',
    target_role TEXT DEFAULT 'Full Stack Developer',
    bio TEXT DEFAULT '',
    avatar_color TEXT DEFAULT '#6366f1',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    ai_provider TEXT NOT NULL DEFAULT 'auto',
    gemini_api_key TEXT DEFAULT '',
    gemini_model TEXT DEFAULT 'gemini-2.5-flash',
    openai_api_key TEXT DEFAULT '',
    openai_model TEXT DEFAULT 'gpt-4o-mini',
    anthropic_api_key TEXT DEFAULT '',
    anthropic_model TEXT DEFAULT 'claude-3-5-sonnet-latest',
    youtube_api_key TEXT DEFAULT '',
    elevenlabs_api_key TEXT DEFAULT '',
    video_provider_key TEXT DEFAULT '',
    default_skill_level TEXT DEFAULT 'Intermediate',
    study_hours_per_week INTEGER DEFAULT 12,
    auto_generate_policy TEXT DEFAULT 'all_async',
    show_demo_data INTEGER NOT NULL DEFAULT 0,
    reduced_motion INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'uploading',
    error_message TEXT DEFAULT '',
    extracted_text TEXT DEFAULT '',
    word_count INTEGER NOT NULL DEFAULT 0,
    page_count INTEGER NOT NULL DEFAULT 1,
    summary TEXT DEFAULT '',
    tags_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sources_user ON sources(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS source_chunks (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    page_number INTEGER NOT NULL DEFAULT 1,
    section_title TEXT DEFAULT '',
    content TEXT NOT NULL,
    token_estimate INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_source_chunks_source ON source_chunks(source_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_source_chunks_user ON source_chunks(user_id);

CREATE TABLE IF NOT EXISTS roadmaps (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    target_role TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    skill_level TEXT NOT NULL DEFAULT 'Intermediate',
    existing_knowledge TEXT DEFAULT '',
    target_completion_date TEXT DEFAULT '',
    hours_per_week INTEGER NOT NULL DEFAULT 10,
    preferred_stack TEXT DEFAULT '',
    priorities TEXT DEFAULT '',
    exam_goals TEXT DEFAULT '',
    total_estimated_hours INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_roadmaps_user ON roadmaps(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS roadmap_phases (
    id TEXT PRIMARY KEY,
    roadmap_id TEXT NOT NULL REFERENCES roadmaps(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    phase_order INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    estimated_hours INTEGER NOT NULL DEFAULT 0,
    completion_criteria TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_phases_roadmap ON roadmap_phases(roadmap_id, phase_order);

CREATE TABLE IF NOT EXISTS roadmap_topics (
    id TEXT PRIMARY KEY,
    roadmap_id TEXT NOT NULL REFERENCES roadmaps(id) ON DELETE CASCADE,
    phase_id TEXT NOT NULL REFERENCES roadmap_phases(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic_order INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    subtopics_json TEXT NOT NULL DEFAULT '[]',
    prerequisites_json TEXT NOT NULL DEFAULT '[]',
    difficulty TEXT NOT NULL DEFAULT 'Intermediate',
    estimated_hours INTEGER NOT NULL DEFAULT 4,
    learning_objectives_json TEXT NOT NULL DEFAULT '[]',
    practical_exercises_json TEXT NOT NULL DEFAULT '[]',
    project_checkpoint TEXT DEFAULT '',
    completion_criteria TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'not_started',
    reading_progress INTEGER NOT NULL DEFAULT 0,
    time_spent_minutes INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_topics_roadmap ON roadmap_topics(roadmap_id, phase_id, topic_order);
CREATE INDEX IF NOT EXISTS idx_topics_user ON roadmap_topics(user_id);

CREATE TABLE IF NOT EXISTS topic_tutorials (
    id TEXT PRIMARY KEY,
    topic_id TEXT NOT NULL REFERENCES roadmap_topics(id) ON DELETE CASCADE,
    roadmap_id TEXT NOT NULL REFERENCES roadmaps(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    channel_name TEXT NOT NULL DEFAULT '',
    video_id TEXT NOT NULL DEFAULT '',
    video_url TEXT NOT NULL,
    thumbnail_url TEXT NOT NULL DEFAULT '',
    duration_label TEXT DEFAULT '',
    source_type TEXT NOT NULL DEFAULT 'ai_recommended',
    is_primary INTEGER NOT NULL DEFAULT 1,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tutorials_topic ON topic_tutorials(topic_id, is_primary DESC);

CREATE TABLE IF NOT EXISTS topic_readings (
    id TEXT PRIMARY KEY,
    topic_id TEXT UNIQUE NOT NULL REFERENCES roadmap_topics(id) ON DELETE CASCADE,
    roadmap_id TEXT NOT NULL REFERENCES roadmaps(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    overview TEXT NOT NULL DEFAULT '',
    sections_json TEXT NOT NULL DEFAULT '[]',
    markdown_content TEXT NOT NULL DEFAULT '',
    key_definitions_json TEXT NOT NULL DEFAULT '[]',
    code_examples_json TEXT NOT NULL DEFAULT '[]',
    comparison_tables_json TEXT NOT NULL DEFAULT '[]',
    common_mistakes_json TEXT NOT NULL DEFAULT '[]',
    interview_questions_json TEXT NOT NULL DEFAULT '[]',
    summary TEXT NOT NULL DEFAULT '',
    references_json TEXT NOT NULL DEFAULT '[]',
    is_user_edited INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS personal_notes (
    id TEXT PRIMARY KEY,
    topic_id TEXT REFERENCES roadmap_topics(id) ON DELETE CASCADE,
    roadmap_id TEXT REFERENCES roadmaps(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    tags_json TEXT NOT NULL DEFAULT '[]',
    is_pinned INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_notes_user_topic ON personal_notes(user_id, topic_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS mcq_sets (
    id TEXT PRIMARY KEY,
    topic_id TEXT UNIQUE REFERENCES roadmap_topics(id) ON DELETE CASCADE,
    roadmap_id TEXT REFERENCES roadmaps(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    difficulty TEXT NOT NULL DEFAULT 'Intermediate',
    question_count INTEGER NOT NULL DEFAULT 20,
    questions_json TEXT NOT NULL DEFAULT '[]',
    passing_score INTEGER NOT NULL DEFAULT 14,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mcq_set_id TEXT REFERENCES mcq_sets(id) ON DELETE SET NULL,
    topic_id TEXT REFERENCES roadmap_topics(id) ON DELETE CASCADE,
    roadmap_id TEXT REFERENCES roadmaps(id) ON DELETE CASCADE,
    phase_id TEXT REFERENCES roadmap_phases(id) ON DELETE SET NULL,
    studio_output_id TEXT DEFAULT '',
    topic_title TEXT NOT NULL DEFAULT '',
    score INTEGER NOT NULL,
    max_score INTEGER NOT NULL DEFAULT 20,
    percentage REAL NOT NULL,
    correct_count INTEGER NOT NULL,
    incorrect_count INTEGER NOT NULL,
    unanswered_count INTEGER NOT NULL,
    passed INTEGER NOT NULL DEFAULT 0,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    answers_json TEXT NOT NULL DEFAULT '{}',
    questions_snapshot_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attempts_user_topic ON quiz_attempts(user_id, topic_id, created_at DESC);

CREATE TABLE IF NOT EXISTS studio_outputs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tool_type TEXT NOT NULL,
    title TEXT NOT NULL,
    source_ids_json TEXT NOT NULL DEFAULT '[]',
    config_json TEXT NOT NULL DEFAULT '{}',
    content_json TEXT NOT NULL DEFAULT '{}',
    audio_file_path TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'completed',
    is_user_edited INTEGER NOT NULL DEFAULT 0,
    error_message TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_studio_user_tool ON studio_outputs(user_id, tool_type, created_at DESC);

CREATE TABLE IF NOT EXISTS flashcards (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    studio_output_id TEXT REFERENCES studio_outputs(id) ON DELETE CASCADE,
    topic_id TEXT REFERENCES roadmap_topics(id) ON DELETE SET NULL,
    front TEXT NOT NULL,
    back TEXT NOT NULL,
    hint TEXT DEFAULT '',
    category TEXT DEFAULT 'General',
    status TEXT NOT NULL DEFAULT 'new',
    review_count INTEGER NOT NULL DEFAULT 0,
    ease_factor REAL NOT NULL DEFAULT 2.5,
    interval_days INTEGER NOT NULL DEFAULT 0,
    next_due_at TEXT DEFAULT '',
    last_reviewed_at TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_flashcards_deck ON flashcards(studio_output_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_flashcards_user ON flashcards(user_id, status);

CREATE TABLE IF NOT EXISTS generation_jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_type TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    roadmap_id TEXT REFERENCES roadmaps(id) ON DELETE CASCADE,
    phase_id TEXT REFERENCES roadmap_phases(id) ON DELETE CASCADE,
    topic_id TEXT REFERENCES roadmap_topics(id) ON DELETE CASCADE,
    studio_output_id TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'queued',
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    error_message TEXT DEFAULT '',
    result_id TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    started_at TEXT DEFAULT '',
    completed_at TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_jobs_user_roadmap ON generation_jobs(user_id, roadmap_id, status);
CREATE INDEX IF NOT EXISTS idx_jobs_topic ON generation_jobs(topic_id, resource_type);

CREATE TABLE IF NOT EXISTS ai_conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    context_type TEXT NOT NULL DEFAULT 'roadmap_agent',
    title TEXT NOT NULL,
    source_ids_json TEXT NOT NULL DEFAULT '[]',
    messages_json TEXT NOT NULL DEFAULT '[]',
    draft_roadmap_json TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conversations_user ON ai_conversations(user_id, context_type, updated_at DESC);

CREATE TABLE IF NOT EXISTS activity_logs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    activity_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 5,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_logs(user_id, created_at DESC);
"""


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = conn.execute(f"PRAGMA table_info({table})").fetchall()
    col_names = {row["name"] for row in existing}
    if column not in col_names:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def run_migrations(conn: sqlite3.Connection) -> None:
    """Safely migrate existing SQLite tables without losing or altering existing user records."""
    # Users profile image support
    _ensure_column(conn, "users", "avatar_url", "TEXT NOT NULL DEFAULT ''")
    # User preferences: 4-theme selector and 6-language selector
    _ensure_column(conn, "user_preferences", "theme", "TEXT NOT NULL DEFAULT 'neural_night'")
    _ensure_column(conn, "user_preferences", "preferred_language", "TEXT NOT NULL DEFAULT 'English'")
    # Topic readings: non-destructive CUSTOMIZED vs ORIGINAL reading storage
    _ensure_column(conn, "topic_readings", "diagrams_json", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_column(conn, "topic_readings", "has_custom_reading", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "topic_readings", "custom_title", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "topic_readings", "custom_markdown", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "topic_readings", "custom_updated_at", "TEXT NOT NULL DEFAULT ''")
    # Studio outputs: language metadata, playable video file path, duration, and style
    _ensure_column(conn, "studio_outputs", "language", "TEXT NOT NULL DEFAULT 'English'")
    _ensure_column(conn, "studio_outputs", "video_file_path", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "studio_outputs", "duration_label", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "studio_outputs", "style_label", "TEXT NOT NULL DEFAULT ''")


def init_db() -> None:
    with get_db(commit=True) as conn:
        conn.executescript(SCHEMA_SQL)
        run_migrations(conn)


def log_activity(
    conn: sqlite3.Connection,
    user_id: str,
    activity_type: str,
    entity_type: str,
    entity_id: str,
    title: str,
    duration_minutes: int = 5,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    conn.execute(
        """
        INSERT INTO activity_logs (id, user_id, activity_type, entity_type, entity_id, title, duration_minutes, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id("act"),
            user_id,
            activity_type,
            entity_type,
            entity_id,
            title,
            duration_minutes,
            json.dumps(metadata or {}),
            utc_now(),
        ),
    )

