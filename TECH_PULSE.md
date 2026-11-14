# BRAINOVA — Tech Pulse Architecture & Operations Guide

## 1. Overview
**Tech Pulse** is BRAINOVA's verified daily technology intelligence platform for students and developers. It monitors official engineering blogs, research archives, and developer communities via real RSS/Atom/JSON endpoints, deduplicates stories, assigns explicit verification states, generates grounded technical explanations, and serves a shared global feed scoped to the **Asia/Kolkata (IST)** calendar day (`00:00`–`23:59 IST`).

## 2. Database Schema & Migrations
All tables are created idempotently via `backend/database.py` (`SCHEMA_SQL` / `init_db()`):
- `tech_pulse_sources`: Official & discovery source registry, priority, feed type (`rss`, `json_hn`), health tracking (`last_fetched_at`, `last_success_at`, `error_count`, `last_error`).
- `tech_pulse_ingestion_runs`: Audit trail for each scheduled or manual ingestion cycle.
- `tech_pulse_discovered_articles`: Raw normalized article evidence archive (canonical URL, sanitized excerpt, publication UTC timestamp, discovery UTC timestamp, content hash).
- `tech_pulse_stories`: Canonical deduplicated stories with verification state, supporting sources JSON, structured summary JSON, and optional correction note.
- `tech_pulse_daily_feed`: Shared global IST daily feed (`ist_date`, `story_id`, `rank_score`, `status` = `active` | `expired`).
- `tech_pulse_bookmarks`: Per-user private bookmarks (`user_id`, `story_id`, `snapshot_json`) that survive daily IST feed expiration.
- `tech_pulse_locks`: Database-backed distributed lock (`tech_pulse_locks`) preventing concurrent duplicate ingestion across workers.

## 3. IST Daily Lifecycle & Late-Update Handling
- Timezone: `ZoneInfo("Asia/Kolkata")` with fixed `UTC+05:30` fallback when host `tzdata` is unavailable.
- Every feed read and ingestion cycle checks `ist_date` and expires any `tech_pulse_daily_feed` rows where `ist_date < current_ist_date`.
- **Same-day stories** (`published_ist_date == discovered_ist_date`) enter the active IST feed normally.
- **Late-discovered stories** (`published_ist_date < discovered_ist_date` within 72 hours) are published to today's active IST feed with `is_late_update = True` and an explicit label: `Late update — originally published <DD Mon YYYY, HH:MM IST>`.
- Stale archive items older than 72 hours are excluded from the daily feed.

## 4. Verification States
- **Verified primary source**: Supported by at least one official primary engineering/research source (`is_official = 1`).
- **Independently corroborated**: Supported by 2 or more independent non-official domains/sources.
- **Unconfirmed report**: Single non-official source only.
- **Corrected**: Explicitly updated via `mark_story_corrected(conn, story_id, correction_note)` with a visible correction banner.

## 5. Security & Grounding Rules
- All external feed HTML/XML is stripped of `<script>`, `<style>`, `<iframe>`, `<!DOCTYPE>` entities, and control characters (`sanitize_external_text`).
- Only validated `http://` and `https://` URLs are stored and rendered; external links use `rel="noopener noreferrer"`.
- AI explanations reuse `backend/ai_engine.py` (`call_llm_json` + `_resolve_active_provider`), wrap external text inside `<untrusted_source_material>` tags, and fall back to an honest excerpt-based summary (`fallback_notice`) when AI is unavailable.

## 6. API Endpoints (Authenticated)
- `GET /api/tech-pulse/feed`
- `GET /api/tech-pulse/categories`
- `GET /api/tech-pulse/metadata`
- `GET /api/tech-pulse/stories/{story_id}`
- `GET /api/tech-pulse/saved`
- `POST /api/tech-pulse/saved/{story_id}`
- `DELETE /api/tech-pulse/saved/{story_id}`
- `POST /api/tech-pulse/refresh`

