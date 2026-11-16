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


def resolve_data_dir() -> str:
    """Resolve the persistent data root from BRAINOVA_DATA_DIR, defaulting to <BASE_DIR>/data (or /tmp on Vercel)."""
    custom = (os.environ.get("BRAINOVA_DATA_DIR") or "").strip()
    if os.environ.get("VERCEL"):
        if custom and custom.startswith("/tmp"):
            return os.path.abspath(custom)
        if os.name == "nt":
            import tempfile
            return os.path.join(tempfile.gettempdir(), "brainova_data")
        return "/tmp/brainova_data"
    if custom:
        if os.path.isabs(custom):
            return os.path.abspath(custom)
        return os.path.abspath(os.path.join(BASE_DIR, custom))
    return os.path.join(BASE_DIR, "data")


DATA_DIR = resolve_data_dir()
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
AUDIO_DIR = os.path.join(DATA_DIR, "audio")
VIDEOS_DIR = os.path.join(DATA_DIR, "videos")
MENTOR_IMAGES_DIR = os.path.join(DATA_DIR, "mentor_images")


def ensure_data_directories() -> None:
    """Ensure all persistent data and media directories exist, falling back to /tmp on read-only filesystems."""
    global DATA_DIR, UPLOADS_DIR, AUDIO_DIR, VIDEOS_DIR, MENTOR_IMAGES_DIR
    try:
        for directory in (DATA_DIR, UPLOADS_DIR, AUDIO_DIR, VIDEOS_DIR, MENTOR_IMAGES_DIR):
            os.makedirs(directory, exist_ok=True)
    except OSError:
        import tempfile
        DATA_DIR = "/tmp/brainova_data" if os.name != "nt" else os.path.join(tempfile.gettempdir(), "brainova_data")
        UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
        AUDIO_DIR = os.path.join(DATA_DIR, "audio")
        VIDEOS_DIR = os.path.join(DATA_DIR, "videos")
        MENTOR_IMAGES_DIR = os.path.join(DATA_DIR, "mentor_images")
        for directory in (DATA_DIR, UPLOADS_DIR, AUDIO_DIR, VIDEOS_DIR, MENTOR_IMAGES_DIR):
            os.makedirs(directory, exist_ok=True)


ensure_data_directories()


def get_db_path() -> str:
    custom = (os.environ.get("AETHER_DB_PATH") or "").strip()
    if os.environ.get("VERCEL"):
        if custom and custom.startswith("/tmp"):
            return os.path.abspath(custom)
        return os.path.join(DATA_DIR, "aetherlearn.db")
    if custom:
        if os.path.isabs(custom):
            return os.path.abspath(custom)
        return os.path.abspath(os.path.join(BASE_DIR, custom))
    return os.path.join(DATA_DIR, "aetherlearn.db")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str = "") -> str:
    uid = uuid.uuid4().hex[:16]
    return f"{prefix}_{uid}" if prefix else uid


def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> Dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


_VERCEL_INIT_PATHS = set()
_INITIALIZED_SCHEMA_PATHS = set()


def get_database_environment() -> str:
    """Explicitly classify the active runtime environment: 'production', 'test', or 'development'."""
    explicit = (os.environ.get("STUDYOS_ENV") or os.environ.get("BRAINOVA_ENV") or "").strip().lower()
    if explicit in ("production", "test", "development"):
        return explicit
    db_path = get_db_path()
    if os.path.basename(db_path) != "aetherlearn.db" or os.environ.get("PYTEST_CURRENT_TEST"):
        return "test"
    if os.environ.get("VERCEL") or os.environ.get("RENDER"):
        return "production"
    return "development"


def is_mongo_authoritative(db_path: Optional[str] = None) -> bool:
    """
    Determine whether MongoDB Atlas is the authoritative database for this connection.
    - Production (VERCEL / STUDYOS_ENV=production): MongoDB Atlas is ALWAYS authoritative.
    - Test / Local Development: SQLite is authoritative unless STUDYOS_ENV=production is set.
    """
    if os.environ.get("BRAINOVA_DISABLE_MONGO_SYNC") == "1":
        return False
    target_path = db_path or get_db_path()
    if os.path.basename(target_path) != "aetherlearn.db":
        return False
    env = get_database_environment()
    if env == "production":
        if os.environ.get("BRAINOVA_ALLOW_EPHEMERAL_SQLITE_FOR_TESTS") == "1":
            return False
        return True
    return False


def validate_database_configuration() -> Dict[str, Any]:
    """
    Validate database configuration for the current environment without leaking secrets.
    In production, fails explicitly if MONGODB_URI is missing rather than silently falling back to /tmp SQLite.
    """
    env = get_database_environment()
    db_path = get_db_path()
    mongo_auth = is_mongo_authoritative(db_path)
    from backend.mongo_sync import DatabaseConfigurationError, get_mongodb_uri

    uri_present = bool(get_mongodb_uri())
    if env == "production" and not os.environ.get("BRAINOVA_ALLOW_EPHEMERAL_SQLITE_FOR_TESTS") and not uri_present:
        raise DatabaseConfigurationError(
            "Production database configuration is missing (MONGODB_URI). Ephemeral SQLite fallback is disabled."
        )
    return {
        "environment": env,
        "authoritative_db": "mongodb" if mongo_auth else "sqlite",
        "mongodb_configured": uri_present,
    }


@contextmanager
def get_db(commit: bool = False):
    db_path = get_db_path()
    db_parent = os.path.dirname(db_path)
    if db_parent:
        os.makedirs(db_parent, exist_ok=True)
    mongo_auth = is_mongo_authoritative(db_path)
    if mongo_auth:
        validate_database_configuration()

    conn = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
    conn.row_factory = dict_factory
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")

    if db_path not in _INITIALIZED_SCHEMA_PATHS:
        conn.executescript(SCHEMA_SQL)
        run_migrations(conn)
        conn.commit()
        _INITIALIZED_SCHEMA_PATHS.add(db_path)

    if mongo_auth:
        from backend.mongo_sync import (
            apply_changelog_to_mongo,
            hydrate_sqlite_from_mongo_authoritative,
            install_changelog_triggers,
        )

        hydrate_sqlite_from_mongo_authoritative(conn, db_path)
        if commit:
            install_changelog_triggers(conn)

    try:
        yield conn
        if commit:
            conn.commit()
            if mongo_auth:
                apply_changelog_to_mongo(conn, db_path)
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

CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL,
    revoked_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_revoked_tokens_user ON revoked_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_revoked_tokens_exp ON revoked_tokens(expires_at);

CREATE TABLE IF NOT EXISTS diary_entries (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT '',
    entry_date TEXT NOT NULL,
    pages_json TEXT NOT NULL DEFAULT '[""]',
    is_draft INTEGER NOT NULL DEFAULT 0,
    client_draft_key TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_diary_user_date ON diary_entries(user_id, is_draft, entry_date DESC, updated_at DESC);

CREATE TABLE IF NOT EXISTS study_journal_entries (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    topic TEXT NOT NULL DEFAULT '',
    chapter_or_module TEXT NOT NULL DEFAULT '',
    study_date TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 0,
    learning_status TEXT NOT NULL DEFAULT 'understood',
    key_concepts TEXT NOT NULL DEFAULT '',
    learning_outcomes TEXT NOT NULL DEFAULT '',
    revision_notes TEXT NOT NULL DEFAULT '',
    pages_json TEXT NOT NULL DEFAULT '[{"type":"doc","blocks":[{"type":"paragraph","runs":[]}]}]',
    is_draft INTEGER NOT NULL DEFAULT 0,
    client_draft_key TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_study_journal_user_date ON study_journal_entries(user_id, is_draft, study_date DESC, updated_at DESC);

CREATE TABLE IF NOT EXISTS focus_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_title TEXT NOT NULL DEFAULT '',
    duration_seconds INTEGER NOT NULL,
    short_break_minutes INTEGER NOT NULL DEFAULT 0,
    sound_enabled INTEGER NOT NULL DEFAULT 1,
    animations_enabled INTEGER NOT NULL DEFAULT 1,
    started_at TEXT NOT NULL,
    ends_at TEXT NOT NULL,
    completed_at TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    distraction_event_count INTEGER NOT NULL DEFAULT 0,
    client_request_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_focus_sessions_user_status ON focus_sessions(user_id, status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_focus_sessions_client_req ON focus_sessions(user_id, client_request_id);

CREATE TABLE IF NOT EXISTS focus_events (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES focus_sessions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_focus_events_session ON focus_events(session_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_focus_events_user ON focus_events(user_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS pending_registrations (
    id TEXT PRIMARY KEY,
    pending_token TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    target_role TEXT NOT NULL DEFAULT 'Full Stack Developer',
    otp_hmac TEXT NOT NULL,
    otp_expires_at TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    resend_count INTEGER NOT NULL DEFAULT 0,
    resend_window_start TEXT NOT NULL,
    last_sent_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pending_reg_token ON pending_registrations(pending_token);
CREATE INDEX IF NOT EXISTS idx_pending_reg_expires ON pending_registrations(otp_expires_at);

CREATE TABLE IF NOT EXISTS registration_rate_limits (
    rate_key TEXT PRIMARY KEY,
    window_start TEXT NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_delivery_logs (
    id TEXT PRIMARY KEY,
    correlation_id TEXT UNIQUE NOT NULL,
    provider_message_id TEXT NOT NULL DEFAULT '',
    recipient_domain TEXT NOT NULL,
    provider TEXT NOT NULL,
    status TEXT NOT NULL,
    smtp_code INTEGER,
    connect_duration_ms REAL NOT NULL DEFAULT 0,
    submit_duration_ms REAL NOT NULL DEFAULT 0,
    total_duration_ms REAL NOT NULL DEFAULT 0,
    error_category TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_email_delivery_corr ON email_delivery_logs(correlation_id);
CREATE INDEX IF NOT EXISTS idx_email_delivery_domain_status ON email_delivery_logs(recipient_domain, status, created_at DESC);

CREATE TABLE IF NOT EXISTS email_suppressions (
    email_hash TEXT PRIMARY KEY,
    recipient_domain TEXT NOT NULL,
    reason TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_webhook_events (
    event_id TEXT PRIMARY KEY,
    correlation_id TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS career_profiles (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    target_career TEXT NOT NULL DEFAULT 'Software Engineer',
    target_job_role TEXT NOT NULL DEFAULT 'SDE-1 / Fresher',
    target_company TEXT NOT NULL DEFAULT '',
    graduation_year INTEGER NOT NULL DEFAULT 2026,
    current_skill_level TEXT NOT NULL DEFAULT 'Intermediate',
    available_hours_per_week INTEGER NOT NULL DEFAULT 14,
    target_deadline TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS career_skill_assessments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_career TEXT NOT NULL DEFAULT 'Software Engineer',
    total_questions INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    overall_score INTEGER NOT NULL DEFAULT 0,
    category_scores_json TEXT NOT NULL DEFAULT '{}',
    answers_json TEXT NOT NULL DEFAULT '[]',
    project_evidence_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_career_assess_user ON career_skill_assessments(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS mentor_rate_limits (
    user_id TEXT NOT NULL,
    window_start_epoch INTEGER NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, window_start_epoch)
);

CREATE TABLE IF NOT EXISTS tech_pulse_sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    organization TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 2,
    feed_url TEXT NOT NULL UNIQUE,
    feed_type TEXT NOT NULL DEFAULT 'rss',
    is_official INTEGER NOT NULL DEFAULT 1,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_fetched_at TEXT NOT NULL DEFAULT '',
    last_success_at TEXT NOT NULL DEFAULT '',
    last_status TEXT NOT NULL DEFAULT '',
    error_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tech_pulse_ingestion_runs (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'running',
    trigger_type TEXT NOT NULL DEFAULT 'scheduler',
    sources_checked INTEGER NOT NULL DEFAULT 0,
    discovered_count INTEGER NOT NULL DEFAULT 0,
    published_count INTEGER NOT NULL DEFAULT 0,
    error_summary TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tech_pulse_discovered_articles (
    id TEXT PRIMARY KEY,
    canonical_url TEXT NOT NULL UNIQUE,
    raw_url TEXT NOT NULL,
    title TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    is_official_source INTEGER NOT NULL DEFAULT 0,
    published_at_utc TEXT NOT NULL,
    source_timezone TEXT NOT NULL DEFAULT 'UTC',
    discovered_at_utc TEXT NOT NULL,
    raw_excerpt TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL,
    story_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tp_discovered_story ON tech_pulse_discovered_articles(story_id);
CREATE INDEX IF NOT EXISTS idx_tp_discovered_hash ON tech_pulse_discovered_articles(content_hash);

CREATE TABLE IF NOT EXISTS tech_pulse_stories (
    id TEXT PRIMARY KEY,
    dedup_key TEXT NOT NULL UNIQUE,
    canonical_url TEXT NOT NULL,
    title TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    category TEXT NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'Unconfirmed report',
    correction_note TEXT NOT NULL DEFAULT '',
    original_source_name TEXT NOT NULL,
    original_source_url TEXT NOT NULL,
    supporting_sources_json TEXT NOT NULL DEFAULT '[]',
    published_at_utc TEXT NOT NULL,
    discovered_at_utc TEXT NOT NULL,
    processed_at_utc TEXT NOT NULL,
    is_late_update INTEGER NOT NULL DEFAULT 0,
    late_update_label TEXT NOT NULL DEFAULT '',
    summary_json TEXT NOT NULL DEFAULT '{}',
    evidence_excerpt TEXT NOT NULL DEFAULT '',
    ai_provider TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tp_stories_cat ON tech_pulse_stories(category, published_at_utc DESC);
CREATE INDEX IF NOT EXISTS idx_tp_stories_hash ON tech_pulse_stories(content_hash);

CREATE TABLE IF NOT EXISTS tech_pulse_daily_feed (
    ist_date TEXT NOT NULL,
    story_id TEXT NOT NULL REFERENCES tech_pulse_stories(id) ON DELETE CASCADE,
    rank_score REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    added_at_utc TEXT NOT NULL,
    expired_at_utc TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (ist_date, story_id)
);

CREATE INDEX IF NOT EXISTS idx_tp_daily_feed_active ON tech_pulse_daily_feed(ist_date, status, rank_score DESC);

CREATE TABLE IF NOT EXISTS tech_pulse_bookmarks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    story_id TEXT NOT NULL REFERENCES tech_pulse_stories(id) ON DELETE CASCADE,
    snapshot_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE (user_id, story_id)
);

CREATE INDEX IF NOT EXISTS idx_tp_bookmarks_user ON tech_pulse_bookmarks(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS tech_pulse_locks (
    lock_name TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    acquired_at_epoch INTEGER NOT NULL,
    expires_at_epoch INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS user_music_tracks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    storage_filename TEXT NOT NULL,
    file_format TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    file_size INTEGER NOT NULL DEFAULT 0,
    duration_seconds REAL NOT NULL DEFAULT 0,
    category TEXT NOT NULL DEFAULT 'uploaded',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_music_tracks_user ON user_music_tracks(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS login_rate_limits (
    rate_key TEXT PRIMARY KEY,
    window_start TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS career_weekly_tasks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    week_start_date TEXT NOT NULL,
    day_of_week TEXT NOT NULL DEFAULT 'Mon',
    topic TEXT NOT NULL,
    skill_category TEXT NOT NULL DEFAULT 'programming',
    learning_objective TEXT NOT NULL DEFAULT '',
    activity_type TEXT NOT NULL DEFAULT 'learning',
    planned_minutes INTEGER NOT NULL DEFAULT 45,
    actual_minutes INTEGER NOT NULL DEFAULT 0,
    priority TEXT NOT NULL DEFAULT 'high',
    completion_criteria TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    source_type TEXT NOT NULL DEFAULT 'planner',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_career_weekly_tasks_user ON career_weekly_tasks(user_id, week_start_date, status);

CREATE TABLE IF NOT EXISTS topic_mastery_reviews (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic_key TEXT NOT NULL,
    topic_title TEXT NOT NULL,
    skill_category TEXT NOT NULL DEFAULT 'programming',
    roadmap_topic_id TEXT NOT NULL DEFAULT '',
    mastery_score REAL NOT NULL DEFAULT 50,
    ease_factor REAL NOT NULL DEFAULT 2.5,
    interval_days INTEGER NOT NULL DEFAULT 1,
    repetitions INTEGER NOT NULL DEFAULT 0,
    last_score REAL NOT NULL DEFAULT 0,
    last_reviewed_at TEXT NOT NULL DEFAULT '',
    next_review_at TEXT NOT NULL,
    retention_history_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_topic_mastery_reviews_user ON topic_mastery_reviews(user_id, next_review_at);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
"""


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = conn.execute(f"PRAGMA table_info({table})").fetchall()
    col_names = {row["name"] for row in existing}
    if column not in col_names:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _migration_001_baseline_columns(conn: sqlite3.Connection) -> None:
    """Ensure all backward-compatible columns exist across core tables without touching existing rows."""
    _ensure_column(conn, "users", "avatar_url", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "users", "email_verified", "INTEGER NOT NULL DEFAULT 1")
    _ensure_column(conn, "email_delivery_logs", "provider_message_id", "TEXT NOT NULL DEFAULT ''")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_delivery_msgid ON email_delivery_logs(provider_message_id)")
    _ensure_column(conn, "user_preferences", "theme", "TEXT NOT NULL DEFAULT 'midnight_luxe'")
    conn.execute(
        """
        UPDATE user_preferences
        SET theme = 'midnight_luxe'
        WHERE theme IS NULL
           OR theme NOT IN ('midnight_luxe', 'obsidian_emerald', 'midnight_sapphire', 'onyx_burgundy')
        """
    )
    _ensure_column(conn, "user_preferences", "preferred_language", "TEXT NOT NULL DEFAULT 'English'")
    _ensure_column(conn, "topic_readings", "diagrams_json", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_column(conn, "topic_readings", "has_custom_reading", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "topic_readings", "custom_title", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "topic_readings", "custom_markdown", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "topic_readings", "custom_updated_at", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "studio_outputs", "language", "TEXT NOT NULL DEFAULT 'English'")
    _ensure_column(conn, "studio_outputs", "video_file_path", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "studio_outputs", "duration_label", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "studio_outputs", "style_label", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "study_journal_entries", "title", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "user_preferences", "music_last_track_id", "TEXT NOT NULL DEFAULT 'builtin_study_gentle'")
    _ensure_column(conn, "user_preferences", "music_last_category", "TEXT NOT NULL DEFAULT 'all'")
    _ensure_column(conn, "user_preferences", "music_volume", "REAL NOT NULL DEFAULT 0.65")
    _ensure_column(conn, "user_preferences", "music_playback_enabled", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "user_preferences", "music_last_position", "REAL NOT NULL DEFAULT 0")


def _migration_002_phase1_integrity_indexes(conn: sqlite3.Connection) -> None:
    """Create targeted query & ownership indexes for Phase 1 data integrity."""
    conn.execute("CREATE INDEX IF NOT EXISTS idx_topic_tutorials_user ON topic_tutorials(user_id, topic_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_topic_readings_user ON topic_readings(user_id, topic_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pending_reg_email ON pending_registrations(email)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_music_tracks_storage ON user_music_tracks(user_id, storage_filename)"
    )


def _migration_003_encrypt_credentials(conn: sqlite3.Connection) -> None:
    """Migrate any legacy plaintext API credentials to AES-256-GCM at rest."""
    from backend.crypto import migrate_plaintext_credentials

    migrate_plaintext_credentials(conn)


def _migration_004_career_planner_and_srs(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS career_weekly_tasks (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            week_start_date TEXT NOT NULL,
            day_of_week TEXT NOT NULL DEFAULT 'Mon',
            topic TEXT NOT NULL,
            skill_category TEXT NOT NULL DEFAULT 'programming',
            learning_objective TEXT NOT NULL DEFAULT '',
            activity_type TEXT NOT NULL DEFAULT 'learning',
            planned_minutes INTEGER NOT NULL DEFAULT 45,
            actual_minutes INTEGER NOT NULL DEFAULT 0,
            priority TEXT NOT NULL DEFAULT 'high',
            completion_criteria TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            source_type TEXT NOT NULL DEFAULT 'planner',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_career_weekly_tasks_user ON career_weekly_tasks(user_id, week_start_date, status)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS topic_mastery_reviews (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            topic_key TEXT NOT NULL,
            topic_title TEXT NOT NULL,
            skill_category TEXT NOT NULL DEFAULT 'programming',
            roadmap_topic_id TEXT NOT NULL DEFAULT '',
            mastery_score REAL NOT NULL DEFAULT 50,
            ease_factor REAL NOT NULL DEFAULT 2.5,
            interval_days INTEGER NOT NULL DEFAULT 1,
            repetitions INTEGER NOT NULL DEFAULT 0,
            last_score REAL NOT NULL DEFAULT 0,
            last_reviewed_at TEXT NOT NULL DEFAULT '',
            next_review_at TEXT NOT NULL,
            retention_history_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_topic_mastery_reviews_user ON topic_mastery_reviews(user_id, next_review_at)"
    )


SCHEMA_MIGRATIONS = [
    (1, "baseline_columns", _migration_001_baseline_columns),
    (2, "phase1_integrity_indexes", _migration_002_phase1_integrity_indexes),
    (3, "encrypt_legacy_credentials", _migration_003_encrypt_credentials),
    (4, "career_planner_and_srs", _migration_004_career_planner_and_srs),
]


def run_migrations(conn: sqlite3.Connection) -> None:
    """
    Execute versioned, ordered, idempotent schema migrations inside explicit transactions
    and record completion in `schema_migrations`.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )
    applied_versions = {
        int(row["version"] if isinstance(row, dict) else row[0])
        for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
    }

    for version, name, migration_fn in SCHEMA_MIGRATIONS:
        if version in applied_versions:
            continue
        migration_fn(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
            (version, name, utc_now()),
        )

    # Always run safe additive column/credential checks idempotently for pre-versioned DBs
    _migration_001_baseline_columns(conn)
    _migration_002_phase1_integrity_indexes(conn)
    _migration_003_encrypt_credentials(conn)
    _migration_004_career_planner_and_srs(conn)


def init_db() -> None:
    db_path = get_db_path()
    validate_database_configuration()
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

