"""
AetherLearn AI — Persistent Database-Backed Asynchronous Background Job Queue
Handles non-blocking generation of topic tutorials, reading materials, and 20-MCQ exams
with concurrency limits, duplicate prevention, retry policies, and restart recovery.
"""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from backend.ai_engine import generateTopicQuiz, generateTopicReading, generateVideoStoryboard, recommendTutorials
from backend.auth import ensure_user_preferences
from backend.crypto import redact_sensitive_text
from backend.database import get_db, new_id, utc_now
from backend.doc_processor import diagnose_and_recover_source_chunks, retrieve_relevant_chunks
from backend.multilang_engine import normalize_language
from backend.video_engine import synthesize_educational_video

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
            job_type = job.get("job_type", "topic_resource")
            topic_id = job["topic_id"]
            roadmap_id = job["roadmap_id"]
            r_type = job["resource_type"]
            prefs = ensure_user_preferences(conn, user_id)

        if job_type == "studio_video":
            return _execute_studio_video_job(job_id, job["studio_output_id"], user_id, prefs)

        with get_db(commit=True) as conn:
            topic = conn.execute(
                "SELECT * FROM roadmap_topics WHERE id = ? AND user_id = ?",
                (topic_id, user_id),
            ).fetchone()
            roadmap = conn.execute(
                "SELECT * FROM roadmaps WHERE id = ? AND user_id = ?",
                (roadmap_id, user_id),
            ).fetchone()

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
        safe_err = redact_sensitive_text(str(exc))[:300] or "Resource generation failed."
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


def _update_studio_video_progress(
    output_id: str,
    user_id: str,
    content_base: Dict[str, Any],
    stage_key: str,
    stage_label: str,
    progress: int,
    audio_file_path: Optional[str] = None,
) -> None:
    payload = {
        **(content_base or {}),
        "video": {
            "ready": False,
            "video_ready": False,
            "status": stage_key,
            "stage": stage_label,
            "progress": max(0, min(99, int(progress))),
        },
    }
    with get_db(commit=True) as conn:
        if audio_file_path:
            conn.execute(
                "UPDATE studio_outputs SET content_json = ?, audio_file_path = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                (json.dumps(payload), audio_file_path, utc_now(), output_id, user_id),
            )
        else:
            conn.execute(
                "UPDATE studio_outputs SET content_json = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                (json.dumps(payload), utc_now(), output_id, user_id),
            )


def _execute_studio_video_job(job_id: str, output_id: str, user_id: str, prefs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Executes an asynchronous multi-batch 1080p 24fps Video Overview job with genuine progress & checkpoints."""
    import os
    from backend.video_engine import AUDIO_DIR

    try:
        with get_db(commit=True) as conn:
            row = conn.execute(
                "SELECT * FROM studio_outputs WHERE id = ? AND user_id = ?",
                (output_id, user_id),
            ).fetchone()
            if not row:
                raise RuntimeError("Target Studio output record no longer exists.")
            source_ids = json.loads(row.get("source_ids_json") or "[]")
            config = json.loads(row.get("config_json") or "{}")
            existing_content = json.loads(row.get("content_json") or "{}")
            existing_audio_path = str(row.get("audio_file_path") or "")
            language = normalize_language(row.get("language") or config.get("language") or "English")
            config["language"] = language
            query_hint = config.get("topic") or row.get("title") or ""
            conn.execute(
                "UPDATE studio_outputs SET status = 'processing', error_message = '', updated_at = ? WHERE id = ? AND user_id = ?",
                (utc_now(), output_id, user_id),
            )

        content: Dict[str, Any] = existing_content if isinstance(existing_content, dict) else {}
        collected_scenes: List[Dict[str, Any]] = list(content.get("scenes") or [])
        completed_offsets = set(int(x) for x in (content.get("completed_batch_offsets") or []))
        storyboard_complete = bool(content.get("storyboard_complete")) and len(collected_scenes) >= 1

        if not storyboard_complete:
            _update_studio_video_progress(
                output_id, user_id, content, "source_analysis", "Source analysis: retrieving complete document passages", 10
            )
            with get_db(commit=True) as conn:
                chunks, retrieval_diag = diagnose_and_recover_source_chunks(conn, user_id, source_ids, str(query_hint), top_k=60)
            if source_ids and not chunks:
                content["error_code"] = retrieval_diag.get("error_code", "insufficient_source_evidence")
                content["error_retryable"] = bool(retrieval_diag.get("retryable", False))
                raise RuntimeError(
                    retrieval_diag.get("user_message")
                    or "This document does not contain enough readable educational content to create a reliable Video Overview."
                )

            _update_studio_video_progress(
                output_id, user_id, content, "concept_planning", "Concept planning: analyzing complexity & visual formats", 18
            )

            seen_global = set(
                int(s.get("global_scene_number") or s.get("scene_number") or idx)
                for idx, s in enumerate(collected_scenes, start=1)
            )
            batch_offset = int(content.get("next_batch_offset") or 0)
            safety_loops = 0
            while safety_loops < 20:
                safety_loops += 1
                if batch_offset in completed_offsets:
                    batch_limit = int((content.get("planning_metrics") or {}).get("batch_limit") or 24)
                    batch_offset += batch_limit
                    continue

                batch_num = len(completed_offsets) + 1
                _update_studio_video_progress(
                    output_id,
                    user_id,
                    content,
                    "storyboard_generation",
                    f"Storyboard generation (Batch {batch_num}, offset {batch_offset})",
                    min(42, 22 + len(completed_offsets) * 8),
                )
                batch_sb = generateVideoStoryboard(
                    chunks,
                    {**config, "batch_offset": batch_offset},
                    user_prefs=prefs,
                    source_ids=source_ids,
                )
                pm = batch_sb.get("planning_metrics") or {}
                for sc in batch_sb.get("scenes") or []:
                    gnum = int(sc.get("global_scene_number") or sc.get("scene_number") or (len(collected_scenes) + 1))
                    if gnum not in seen_global:
                        seen_global.add(gnum)
                        sc_copy = dict(sc)
                        sc_copy["global_scene_number"] = gnum
                        sc_copy["scene_number"] = len(collected_scenes) + 1
                        collected_scenes.append(sc_copy)

                completed_offsets.add(batch_offset)
                has_more = bool(pm.get("has_more_batches"))
                next_off = pm.get("next_batch_offset")
                total_planned = int(pm.get("total_planned_scenes") or len(collected_scenes))

                content = {
                    **batch_sb,
                    "scenes": collected_scenes,
                    "completed_batch_offsets": sorted(completed_offsets),
                    "has_more_batches": has_more,
                    "next_batch_offset": next_off,
                    "storyboard_complete": not has_more,
                    "planning_metrics": {
                        **pm,
                        "planned_scenes": len(collected_scenes),
                        "batches_processed": len(completed_offsets),
                    },
                }

                pct = 24 + int(20 * (len(collected_scenes) / max(1, total_planned)))
                _update_studio_video_progress(
                    output_id,
                    user_id,
                    content,
                    "batch_processing",
                    f"Batch processing: {len(collected_scenes)} / {total_planned} scenes planned",
                    pct,
                )
                if not has_more or next_off is None:
                    break
                batch_offset = int(next_off)

        dur_lbl = str(row.get("duration_label") or config.get("duration") or "Adaptive (Content-Driven)")
        sty_lbl = str(row.get("style_label") or config.get("style") or "Concept Breakdown & Visual Synthesis")
        openai_key = (prefs.get("openai_api_key") or os.environ.get("OPENAI_API_KEY") or "").strip()

        def _on_render_progress(stage_key: str, stage_label: str, pct: int) -> None:
            ckpt_wav = os.path.join(AUDIO_DIR, f"{output_id}_vid.wav")
            wav_to_save = ckpt_wav if os.path.exists(ckpt_wav) and os.path.getsize(ckpt_wav) > 1000 else None
            _update_studio_video_progress(
                output_id, user_id, content, stage_key, stage_label, pct, audio_file_path=wav_to_save
            )

        video_meta = synthesize_educational_video(
            output_id=output_id,
            storyboard=content,
            language=language,
            duration_label=dur_lbl,
            style_label=sty_lbl,
            openai_api_key=openai_key,
            resume_audio_path=existing_audio_path or None,
            progress_callback=_on_render_progress,
        )
        if not video_meta.get("video_ready"):
            raise RuntimeError("Final MP4 validation did not pass.")

        content["video"] = video_meta
        content["language"] = language
        content["total_duration_seconds"] = video_meta.get("duration_seconds", content.get("total_duration_seconds", 0))

        with get_db(commit=True) as conn:
            now = utc_now()
            conn.execute(
                """
                UPDATE studio_outputs
                SET content_json = ?, audio_file_path = ?, video_file_path = ?, status = 'completed', error_message = '', updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (json.dumps(content), video_meta.get("audio_file_path", ""), video_meta.get("file_path", ""), now, output_id, user_id),
            )
            conn.execute(
                "UPDATE generation_jobs SET status = 'completed', result_id = ?, error_message = '', completed_at = ? WHERE id = ?",
                (output_id, now, job_id),
            )
            return conn.execute("SELECT * FROM generation_jobs WHERE id = ?", (job_id,)).fetchone()
    except Exception as exc:
        safe_err = redact_sensitive_text(str(exc))[:500]
        err_code = getattr(exc, "code", None) or (content.get("error_code") if "content" in locals() and isinstance(content, dict) else None) or "processing_failure"
        non_retryable_codes = {
            "scanned_pdf_ocr_unavailable",
            "corrupt_document",
            "insufficient_source_evidence",
            "unauthorized_source",
        }
        is_retryable = err_code not in non_retryable_codes
        if "content" in locals() and isinstance(content, dict):
            content["error_code"] = err_code
            content["error_retryable"] = is_retryable
        now = utc_now()
        with get_db(commit=True) as conn:
            if "content" in locals() and isinstance(content, dict):
                conn.execute(
                    "UPDATE studio_outputs SET content_json = ?, status = 'failed', error_message = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                    (json.dumps(content), safe_err, now, output_id, user_id),
                )
            else:
                conn.execute(
                    "UPDATE studio_outputs SET status = 'failed', error_message = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                    (safe_err, now, output_id, user_id),
                )
            conn.execute(
                "UPDATE generation_jobs SET status = 'failed', retry_count = retry_count + 1, error_message = ?, completed_at = ? WHERE id = ?",
                (safe_err, now, job_id),
            )
            return conn.execute("SELECT * FROM generation_jobs WHERE id = ?", (job_id,)).fetchone()


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


def shutdown_job_executor(wait: bool = False) -> None:
    """Safely shut down the background job executor without blocking application exit."""
    _EXECUTOR.shutdown(wait=wait, cancel_futures=True)

