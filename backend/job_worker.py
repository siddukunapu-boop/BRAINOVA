"""
AetherLearn AI — Persistent Database-Backed Asynchronous Background Job Queue
Handles non-blocking generation of topic tutorials, reading materials, and 20-MCQ exams
with concurrency limits, duplicate prevention, retry policies, and restart recovery.
"""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from backend.ai_engine import generateTopicQuiz, generateTopicReading, recommendTutorials
from backend.auth import ensure_user_preferences
from backend.database import get_db, new_id, utc_now

_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix="aether_job_worker")
_ACTIVE_LOCK = threading.Lock()
_IN_FLIGHT_JOB_IDS = set()


def enqueue_topic_resource_jobs(
    conn,
    user_id: str,
    roadmap_id: str,
    phase_id: str,
    topic_id: str,
    resource_types: Optional[List[str]] = None,
    force_regenerate: bool = False,
) -> List[Dict[str, Any]]:
    """
    Queues generation jobs for a topic's tutorial, reading material, and 20-MCQ quiz.
    Prevents duplicate active jobs and preserves existing resources unless force_regenerate=True.
    """
    types_to_queue = resource_types or ["tutorial", "reading", "quiz"]
    created_jobs: List[Dict[str, Any]] = []

    for r_type in types_to_queue:
        # Check if an active job already exists for this topic + resource_type
        existing_active = conn.execute(
            """
            SELECT * FROM generation_jobs
            WHERE user_id = ? AND topic_id = ? AND resource_type = ? AND status IN ('queued', 'processing')
            ORDER BY created_at DESC LIMIT 1
            """,
            (user_id, topic_id, r_type),
        ).fetchone()
        if existing_active:
            created_jobs.append(existing_active)
            continue

        # If not forcing regeneration, check if resource already exists
        if not force_regenerate:
            if r_type == "tutorial":
                has_tut = conn.execute(
                    "SELECT id FROM topic_tutorials WHERE topic_id = ? AND user_id = ? LIMIT 1",
                    (topic_id, user_id),
                ).fetchone()
                if has_tut:
                    continue
            elif r_type == "reading":
                has_read = conn.execute(
                    "SELECT id FROM topic_readings WHERE topic_id = ? AND user_id = ? LIMIT 1",
                    (topic_id, user_id),
                ).fetchone()
                if has_read:
                    continue
            elif r_type == "quiz":
                has_quiz = conn.execute(
                    "SELECT id FROM mcq_sets WHERE topic_id = ? AND user_id = ? LIMIT 1",
                    (topic_id, user_id),
                ).fetchone()
                if has_quiz:
                    continue

        job_id = new_id("job")
        now = utc_now()
        conn.execute(
            """
            INSERT INTO generation_jobs (
                id, user_id, job_type, resource_type, roadmap_id, phase_id, topic_id,
                status, retry_count, max_retries, error_message, result_id, created_at
            ) VALUES (?, ?, 'topic_resource', ?, ?, ?, ?, 'queued', 0, 3, '', '', ?)
            """,
            (job_id, user_id, r_type, roadmap_id, phase_id, topic_id, now),
        )
        job_row = conn.execute("SELECT * FROM generation_jobs WHERE id = ?", (job_id,)).fetchone()
        if job_row:
            created_jobs.append(job_row)

    return created_jobs


def execute_job_sync(job_id: str, force_overwrite: bool = False) -> Optional[Dict[str, Any]]:
    """Executes a single generation job synchronously (called either by worker pool or direct test/retry)."""
    with _ACTIVE_LOCK:
        if job_id in _IN_FLIGHT_JOB_IDS:
            return None
        _IN_FLIGHT_JOB_IDS.add(job_id)

    try:
        with get_db(commit=True) as conn:
            job = conn.execute("SELECT * FROM generation_jobs WHERE id = ?", (job_id,)).fetchone()
            if not job or job["status"] == "cancelled":
                return job

            conn.execute(
                "UPDATE generation_jobs SET status = 'processing', started_at = ?, error_message = '' WHERE id = ?",
                (utc_now(), job_id),
            )

            user_id = job["user_id"]
            topic_id = job["topic_id"]
            roadmap_id = job["roadmap_id"]
            r_type = job["resource_type"]

            topic = conn.execute(
                "SELECT * FROM roadmap_topics WHERE id = ? AND user_id = ?",
                (topic_id, user_id),
            ).fetchone()
            roadmap = conn.execute(
                "SELECT * FROM roadmaps WHERE id = ? AND user_id = ?",
                (roadmap_id, user_id),
            ).fetchone()
            prefs = ensure_user_preferences(conn, user_id)

        if not topic or not roadmap:
            with get_db(commit=True) as conn:
                conn.execute(
                    "UPDATE generation_jobs SET status = 'failed', error_message = 'Target topic or roadmap no longer exists.', completed_at = ? WHERE id = ?",
                    (utc_now(), job_id),
                )
                return conn.execute("SELECT * FROM generation_jobs WHERE id = ?", (job_id,)).fetchone()

        subtopics = json.loads(topic.get("subtopics_json") or "[]")
        prereqs = json.loads(topic.get("prerequisites_json") or "[]")
        result_id = ""

        if r_type == "tutorial":
            recs = recommendTutorials(
                topic_title=topic["title"],
                topic_description=topic.get("description", ""),
                target_role=roadmap.get("target_role", ""),
                user_prefs=prefs,
            )
            with get_db(commit=True) as conn:
                # Preserve user_custom tutorials; only replace ai_recommended if forcing or none exist
                existing_ai = conn.execute(
                    "SELECT id FROM topic_tutorials WHERE topic_id = ? AND user_id = ? AND source_type = 'ai_recommended'",
                    (topic_id, user_id),
                ).fetchone()
                if existing_ai and force_overwrite:
                    conn.execute(
                        "DELETE FROM topic_tutorials WHERE topic_id = ? AND user_id = ? AND source_type = 'ai_recommended'",
                        (topic_id, user_id),
                    )
                    existing_ai = None

                if not existing_ai:
                    for rec in recs:
                        tut_id = new_id("tut")
                        if not result_id:
                            result_id = tut_id
                        now = utc_now()
                        conn.execute(
                            """
                            INSERT INTO topic_tutorials (
                                id, topic_id, roadmap_id, user_id, title, channel_name, video_id,
                                video_url, thumbnail_url, duration_label, source_type, is_primary, notes,
                                created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                tut_id,
                                topic_id,
                                roadmap_id,
                                user_id,
                                rec["title"],
                                rec["channel_name"],
                                rec["video_id"],
                                rec["video_url"],
                                rec["thumbnail_url"],
                                rec.get("duration_label", ""),
                                "ai_recommended",
                                rec.get("is_primary", 1),
                                rec.get("notes", ""),
                                now,
                                now,
                            ),
                        )
                else:
                    result_id = existing_ai["id"]

        elif r_type == "reading":
            with get_db(commit=False) as conn:
                existing_read = conn.execute(
                    "SELECT id, is_user_edited, version FROM topic_readings WHERE topic_id = ? AND user_id = ?",
                    (topic_id, user_id),
                ).fetchone()

            if existing_read and existing_read.get("is_user_edited") and not force_overwrite:
                result_id = existing_read["id"]
            else:
                gen = generateTopicReading(
                    topic_title=topic["title"],
                    topic_description=topic.get("description", ""),
                    subtopics=subtopics,
                    prerequisites=prereqs,
                    difficulty=topic.get("difficulty", "Intermediate"),
                    target_role=roadmap.get("target_role", ""),
                    user_prefs=prefs,
                )
                now = utc_now()
                with get_db(commit=True) as conn:
                    if existing_read:
                        result_id = existing_read["id"]
                        conn.execute(
                            """
                            UPDATE topic_readings
                            SET title = ?, overview = ?, sections_json = ?, diagrams_json = ?, markdown_content = ?,
                                key_definitions_json = ?, code_examples_json = ?, comparison_tables_json = ?,
                                common_mistakes_json = ?, interview_questions_json = ?, summary = ?,
                                references_json = ?, is_user_edited = 0, version = version + 1, updated_at = ?
                            WHERE id = ? AND user_id = ?
                            """,
                            (
                                gen["title"],
                                gen["overview"],
                                json.dumps(gen["sections"]),
                                json.dumps(gen.get("diagrams", [])),
                                gen["markdown_content"],
                                json.dumps(gen["key_definitions"]),
                                json.dumps(gen["code_examples"]),
                                json.dumps(gen["comparison_tables"]),
                                json.dumps(gen["common_mistakes"]),
                                json.dumps(gen["interview_questions"]),
                                gen["summary"],
                                json.dumps(gen["references"]),
                                now,
                                result_id,
                                user_id,
                            ),
                        )
                    else:
                        result_id = new_id("read")
                        conn.execute(
                            """
                            INSERT INTO topic_readings (
                                id, topic_id, roadmap_id, user_id, title, overview, sections_json, diagrams_json,
                                markdown_content, key_definitions_json, code_examples_json,
                                comparison_tables_json, common_mistakes_json, interview_questions_json,
                                summary, references_json, is_user_edited, version, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?, ?)
                            """,
                            (
                                result_id,
                                topic_id,
                                roadmap_id,
                                user_id,
                                gen["title"],
                                gen["overview"],
                                json.dumps(gen["sections"]),
                                json.dumps(gen.get("diagrams", [])),
                                gen["markdown_content"],
                                json.dumps(gen["key_definitions"]),
                                json.dumps(gen["code_examples"]),
                                json.dumps(gen["comparison_tables"]),
                                json.dumps(gen["common_mistakes"]),
                                json.dumps(gen["interview_questions"]),
                                gen["summary"],
                                json.dumps(gen["references"]),
                                now,
                                now,
                            ),
                        )

        elif r_type == "quiz":
            gen_q = generateTopicQuiz(
                topic_title=topic["title"],
                topic_description=topic.get("description", ""),
                subtopics=subtopics,
                difficulty=topic.get("difficulty", "Intermediate"),
                question_count=20,
                user_prefs=prefs,
            )
            now = utc_now()
            with get_db(commit=True) as conn:
                existing_q = conn.execute(
                    "SELECT id FROM mcq_sets WHERE topic_id = ? AND user_id = ?",
                    (topic_id, user_id),
                ).fetchone()
                if existing_q:
                    result_id = existing_q["id"]
                    if force_overwrite:
                        conn.execute(
                            """
                            UPDATE mcq_sets
                            SET title = ?, difficulty = ?, question_count = ?, questions_json = ?,
                                passing_score = ?, version = version + 1, updated_at = ?
                            WHERE id = ? AND user_id = ?
                            """,
                            (
                                gen_q["title"],
                                gen_q["difficulty"],
                                len(gen_q["questions"]),
                                json.dumps(gen_q["questions"]),
                                gen_q["passing_score"],
                                now,
                                result_id,
                                user_id,
                            ),
                        )
                else:
                    result_id = new_id("mcq")
                    conn.execute(
                        """
                        INSERT INTO mcq_sets (
                            id, topic_id, roadmap_id, user_id, title, difficulty,
                            question_count, questions_json, passing_score, version, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                        """,
                        (
                            result_id,
                            topic_id,
                            roadmap_id,
                            user_id,
                            gen_q["title"],
                            gen_q["difficulty"],
                            len(gen_q["questions"]),
                            json.dumps(gen_q["questions"]),
                            gen_q["passing_score"],
                            now,
                            now,
                        ),
                    )

        with get_db(commit=True) as conn:
            conn.execute(
                """
                UPDATE generation_jobs
                SET status = 'completed', result_id = ?, error_message = '', completed_at = ?
                WHERE id = ?
                """,
                (result_id, utc_now(), job_id),
            )
            return conn.execute("SELECT * FROM generation_jobs WHERE id = ?", (job_id,)).fetchone()

    except Exception as exc:
        safe_err = str(exc)[:300] or "Resource generation failed."
        with get_db(commit=True) as conn:
            conn.execute(
                """
                UPDATE generation_jobs
                SET status = 'failed', retry_count = retry_count + 1, error_message = ?, completed_at = ?
                WHERE id = ?
                """,
                (safe_err, utc_now(), job_id),
            )
            return conn.execute("SELECT * FROM generation_jobs WHERE id = ?", (job_id,)).fetchone()
    finally:
        with _ACTIVE_LOCK:
            _IN_FLIGHT_JOB_IDS.discard(job_id)


def dispatch_jobs_async(job_ids: List[str], force_overwrite: bool = False) -> None:
    """Submits queued job IDs to the bounded background ThreadPoolExecutor."""
    for jid in job_ids:
        _EXECUTOR.submit(execute_job_sync, jid, force_overwrite)


def resume_incomplete_jobs_on_startup() -> int:
    """Finds any jobs left in 'queued' or 'processing' state after a server restart and resumes them."""
    with get_db(commit=True) as conn:
        rows = conn.execute(
            "SELECT id FROM generation_jobs WHERE status IN ('queued', 'processing') ORDER BY created_at ASC LIMIT 50"
        ).fetchall()
    job_ids = [r["id"] for r in rows]
    if job_ids:
        dispatch_jobs_async(job_ids)
    return len(job_ids)

