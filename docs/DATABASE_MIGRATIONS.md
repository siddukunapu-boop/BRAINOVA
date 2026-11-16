# StudyOS — Database Migrations Guide

## 1. Versioned Migration Strategy

All schema evolutions are managed through ordered, idempotent, versioned migrations defined in `backend/database.py` (`SCHEMA_MIGRATIONS`) and tracked in the `schema_migrations` table:

| Version | Name | Purpose |
|---|---|---|
| `1` | `baseline_columns` | Adds backward-compatible columns (`users.avatar_url`, `users.email_verified`, `user_preferences.theme`, `user_preferences.preferred_language`, `topic_readings.custom_*`, `studio_outputs.*`, `study_journal_entries.title`, `user_preferences.music_*`). |
| `2` | `phase1_integrity_indexes` | Creates composite ownership and lookup indexes (`idx_topic_tutorials_user`, `idx_topic_readings_user`, `idx_pending_reg_email`, `idx_user_music_tracks_storage`). |
| `3` | `encrypt_legacy_credentials` | Migrates any legacy plaintext API credentials in `user_preferences` to AES-256-GCM encrypted values at rest. |

## 2. Execution & Safety Rules

- **Ordered Execution:** `run_migrations(conn)` checks `SELECT version FROM schema_migrations` and executes only unapplied versions in ascending numerical order.
- **Transactional Boundaries:** Migrations run inside the `get_db(commit=True)` transaction boundary. Any failure triggers `conn.rollback()` before recording the version in `schema_migrations`.
- **Non-Destructive Policy:** Migrations never drop tables, drop populated columns, or recreate tables destructively.
- **Idempotency:** `_ensure_column()` inspects `PRAGMA table_info(<table>)` before issuing `ALTER TABLE ... ADD COLUMN`. Repeated calls to `init_db()` or `run_migrations(conn)` are safe no-ops.

## 3. Adding a New Migration

1. Append a new tuple `(next_version, "descriptive_name", _migration_xxx_fn)` to `SCHEMA_MIGRATIONS` in `backend/database.py`.
2. Ensure `_migration_xxx_fn(conn)` uses additive `ALTER TABLE` / `CREATE INDEX IF NOT EXISTS` or validated row transformations.
3. Add a corresponding unit test in `tests/test_phase1_database_integrity.py` verifying fresh initialization, upgrade from an earlier version, and repeated execution.
