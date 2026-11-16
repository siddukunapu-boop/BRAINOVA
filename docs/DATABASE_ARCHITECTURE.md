# StudyOS — Database Architecture (Phase 1)

## 1. Overview & Authoritative Source of Truth

StudyOS enforces a strict **Single Authoritative Database per Environment** policy:

| Environment | Trigger / Detection | Authoritative Database | Ephemeral / Local Role |
|---|---|---|---|
| **Production (Serverless)** | `VERCEL=1`, `RENDER=1`, or `STUDYOS_ENV=production` | **MongoDB Atlas** (`MONGODB_URI`, database `MONGODB_DB_NAME`) | `/tmp/brainova_data/aetherlearn.db` serves strictly as an in-container SQLite relational query cache hydrated from MongoDB Atlas. |
| **Local Development** | Default local execution (`STUDYOS_ENV=development`) | **Local SQLite** (`data/aetherlearn.db` with WAL + Foreign Keys) | No automatic cloud sync; local work never overwrites production MongoDB Atlas. |
| **Automated Testing** | Non-default `AETHER_DB_PATH`, `PYTEST_CURRENT_TEST`, or `STUDYOS_ENV=test` | **Isolated Temp SQLite** (`tempfile` DB path) | Completely isolated from both `data/aetherlearn.db` and MongoDB Atlas. |

> **Fail-Closed Production Guarantee:** In production (`VERCEL=1` / `STUDYOS_ENV=production`), `validate_database_configuration()` raises `DatabaseConfigurationError` (HTTP `503`) if `MONGODB_URI` is missing. Production never silently falls back to ephemeral `/tmp` SQLite.

---

## 2. Data Flow & Request Lifecycle

```text
Frontend (React SPA)
  │  Authorization: Bearer <JWT>
  ▼
Backend API (FastAPI — backend/main.py, api/index.py)
  │
  ▼
Database Access Layer (backend/database.py :: get_db(commit=...))
  ├─► [Development / Test] ──► SQLite (PRAGMA foreign_keys=ON, WAL, recursive_triggers=ON)
  │
  └─► [Production]
        1. Pre-request Hydration (hydrate_sqlite_from_mongo_authoritative):
           • Checks `_meta_sync.global_seq` in MongoDB Atlas.
           • On cold start or `local_seq != remote_seq`, refreshes all `SYNC_TABLES`
             from MongoDB Atlas into `/tmp` SQLite inside a single transaction.
        2. Transactional Execution:
           • Executes relational queries & `ON DELETE CASCADE` in SQLite.
           • When `commit=True`, TEMP triggers (`_chg_ins_*`, `_chg_upd_*`, `_chg_del_*`)
             capture exact `(table, op, pk)` mutations in `_mongo_changelog`.
        3. Synchronous Authoritative Commit (apply_changelog_to_mongo):
           • Commits SQLite transaction.
           • Pushes ONLY the exact captured upserts (`ReplaceOne`) and explicit PK
             deletes (`delete_many({"_id": {"$in": pks}})`) synchronously to MongoDB Atlas.
           • Atomically increments `_meta_sync.global_seq`.
```

---

## 3. Synchronization & Resurrection Prevention Rules

1. **Zero Destructive Bidirectional Sync (Eliminates AUD-01):** `sync_sqlite_to_mongo()` strictly performs upserts only and is never called automatically on partial `/tmp` SQLite writes. The codebase contains **zero** `delete_many({"_id": {"$nin": ...}})` calls.
2. **Zero Record Resurrection (Eliminates AUD-02):** Deletions (including deleting the last row in a table and `ON DELETE CASCADE` child deletions) are captured by `AFTER DELETE` TEMP triggers (`PRAGMA recursive_triggers = ON`) and deleted explicitly by `_id` in MongoDB Atlas before the HTTP response returns.
3. **Zero Serverless Daemon Thread Writes (Eliminates AUD-03):** All production writes to MongoDB Atlas complete synchronously inside `get_db(commit=True)` prior to returning the HTTP response.

---

## 4. Core Tables & Ownership Model

Every user-owned entity enforces `user_id` ownership verification on every read, update, and delete route (`WHERE id = ? AND user_id = ?`) and cascades cleanly on user deletion (`REFERENCES users(id) ON DELETE CASCADE`):

- **Identity & Security:** `users` (PK `id`, UNIQUE `email`), `user_preferences` (PK `user_id`), `pending_registrations` (PK `id`), `registration_rate_limits` (PK `rate_key`), `login_rate_limits` (PK `rate_key`), `revoked_tokens` (PK `jti`).
- **Learning & Roadmaps:** `roadmaps`, `roadmap_phases`, `roadmap_topics`, `topic_tutorials`, `topic_readings`, `mcq_sets`, `quiz_attempts`, `personal_notes`, `generation_jobs`.
- **Sources & Studio:** `sources`, `source_chunks`, `studio_outputs`, `flashcards`, `activity_logs`.
- **Personal Productivity:** `diary_entries`, `study_journal_entries`, `focus_sessions`, `focus_events`, `user_music_tracks`.
- **Career & Intelligence:** `career_profiles`, `career_skill_assessments`, `mentor_rate_limits`, `ai_conversations`, `tech_pulse_sources`, `tech_pulse_stories`, `tech_pulse_daily_feed`, `tech_pulse_bookmarks`.
- **Migrations:** `schema_migrations` (PK `version`).

---

## 5. Indexes & Integrity Constraints

- **SQLite:** `PRAGMA foreign_keys = ON`, `PRAGMA journal_mode = WAL`, `PRAGMA synchronous = NORMAL`, `UNIQUE(email)` on `users`, `UNIQUE(user_id, story_id)` on `tech_pulse_bookmarks`, plus targeted composite indexes (`idx_roadmaps_user`, `idx_topics_roadmap`, `idx_topic_tutorials_user`, `idx_topic_readings_user`, `idx_user_music_tracks_user`, `idx_user_music_tracks_storage`, `idx_pending_reg_email`, `idx_revoked_tokens_exp`).
- **MongoDB Atlas:** `ensure_mongo_indexes(db)` enforces matching unique and query indexes (`idx_users_email_unique`, `idx_prefs_user_unique`, `idx_revoked_jti_unique`, `idx_tp_bookmark_unique`, `idx_roadmaps_user`, `idx_conv_user`, `idx_music_user`).
