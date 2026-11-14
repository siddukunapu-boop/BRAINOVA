"""
BRAINOVA — Principal Full-Stack FastAPI Backend Server
Provides all REST API endpoints for Authentication, Dashboard, Source Library & RAG,
Conversational AI Roadmap Agent, Inline Expandable Topic Workspaces, Customized Roadmap,
20-MCQ Exam Engine, All 9 AI Studio Tools, Dedicated AI Studio Library, 1080p Video Overview
Synthesis, 6-Language Localization, Flashcard Spaced Repetition, and Settings.
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.email_service import load_local_env_file

load_local_env_file()

from backend.ai_engine import (
    AudioGenerationError,
    StudioGenerationError,
    answerFromSources,
    extractStructuredTable,
    extract_youtube_video_id,
    generateAudioScript,
    generateFlashcards,
    generateInfographicStructure,
    generateMindMap,
    generateRoadmap,
    generateSlideDeck,
    generateStudyGuide,
    generateTopicQuiz,
    generateTopicReading,
    generateVideoStoryboard,
    recommendTutorials,
    validate_and_repair_roadmap,
    verify_youtube_oembed,
)
from backend.auth import (
    create_audio_playback_token,
    create_access_token,
    create_video_playback_token,
    decode_audio_playback_token,
    decode_video_playback_token,
    encrypt_user_preference_credentials,
    ensure_user_preferences,
    extract_bearer_token,
    get_current_user,
    hash_password,
    revoke_access_token,
    sanitize_preferences_for_client,
    verify_password,
)
from backend.crypto import redact_sensitive_text
from backend.career_launchpad import (
    CAREER_BENCHMARKS,
    SKILL_CATEGORIES,
    build_weekly_performance,
    check_and_increment_mentor_rate_limit,
    compute_skill_gap_and_readiness,
    extract_conversation_title,
    generate_mentor_image,
    get_public_assessment_questions,
    grade_skill_assessment,
    stream_mentor_reply,
)
from backend.database import (
    AUDIO_DIR,
    BASE_DIR,
    DATA_DIR,
    UPLOADS_DIR,
    VIDEOS_DIR,
    get_db,
    init_db,
    log_activity,
    new_id,
    utc_now,
)
from backend.doc_processor import (
    SUPPORTED_EXTENSIONS,
    process_and_index_source,
    retrieve_relevant_chunks,
)
from backend.job_worker import (
    dispatch_jobs_async,
    enqueue_topic_resource_jobs,
    execute_job_sync,
    resume_incomplete_jobs_on_startup,
)
from backend.tech_pulse import (
    TECH_PULSE_CATEGORIES,
    get_daily_feed,
    get_story_detail,
    list_saved_stories,
    remove_story_bookmark,
    run_ingestion_cycle,
    save_story_bookmark,
    seed_official_sources,
    start_tech_pulse_scheduler,
    to_ist_date_str,
)
from backend.multilang_engine import SUPPORTED_LANGUAGES, normalize_language, validate_supported_language
from backend.tts_engine import synthesize_podcast_audio
from backend.video_engine import synthesize_educational_video

app = FastAPI(
    title="BRAINOVA Platform API",
    version="2.0.0",
    description="BRAINOVA — Learn Smarter. Think Bigger. AI Learning Studio & Intelligent Roadmap Platform",
)

DEFAULT_CORS_ORIGINS = (
    "http://127.0.0.1:8000,http://localhost:8000,"
    "http://127.0.0.1:5173,http://localhost:5173"
)
ALLOWED_CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("AETHER_CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    with get_db(commit=True) as conn:
        seed_official_sources(conn)
    resume_incomplete_jobs_on_startup()
    start_tech_pulse_scheduler(interval_seconds=1200)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Never expose internal stack traces, SQL strings, or secret values in unhandled error responses.
    """
    _ = redact_sensitive_text(str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."},
    )


# ============================================================================
# PYDANTIC REQUEST SCHEMAS
# ============================================================================
class SignupRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=160)
    password: str = Field(..., min_length=6, max_length=128)
    confirm_password: Optional[str] = None
    target_role: Optional[str] = "Full Stack Developer"


class VerifyEmailRequest(BaseModel):
    pending_token: str = Field(..., min_length=10, max_length=256)
    otp_code: str = Field(..., min_length=6, max_length=6)


class ResendVerificationRequest(BaseModel):
    pending_token: str = Field(..., min_length=10, max_length=256)


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    target_role: Optional[str] = None
    bio: Optional[str] = None
    avatar_color: Optional[str] = None
    avatar_url: Optional[str] = None


class PreferencesUpdateRequest(BaseModel):
    ai_provider: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    anthropic_model: Optional[str] = None
    youtube_api_key: Optional[str] = None
    elevenlabs_api_key: Optional[str] = None
    video_provider_key: Optional[str] = None
    default_skill_level: Optional[str] = None
    study_hours_per_week: Optional[int] = None
    auto_generate_policy: Optional[str] = None
    show_demo_data: Optional[bool] = None
    reduced_motion: Optional[bool] = None
    theme: Optional[str] = None
    preferred_language: Optional[str] = None


class TutorialValidateRequest(BaseModel):
    url: str = Field(..., min_length=5)


class CustomReadingUpdateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=240)
    markdown_content: str = Field(..., min_length=10)


class SourceRenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    tags: Optional[List[str]] = None


class TextSourceCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=20)
    file_type: str = ".md"
    tags: Optional[List[str]] = None


class SourceQuestionRequest(BaseModel):
    question: str = Field(..., min_length=2)
    source_ids: Optional[List[str]] = None


class RoadmapGenerateRequest(BaseModel):
    target_role: str = Field(..., min_length=2, max_length=180)
    skill_level: str = "Intermediate"
    hours_per_week: int = 10
    preferred_stack: str = ""
    existing_knowledge: str = ""
    target_completion_date: str = ""
    priorities: str = ""
    exam_goals: str = ""
    conversation_message: Optional[str] = None


class RoadmapSaveRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    target_role: str = Field(..., min_length=2, max_length=180)
    description: str = ""
    skill_level: str = "Intermediate"
    existing_knowledge: str = ""
    target_completion_date: str = ""
    hours_per_week: int = 10
    preferred_stack: str = ""
    priorities: str = ""
    exam_goals: str = ""
    generation_policy: str = "all_async"  # 'all_async' | 'phase_1_only' | 'on_demand'
    run_sync_for_first_topic: bool = True
    phases: List[Dict[str, Any]]


class RoadmapUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    target_role: Optional[str] = None
    skill_level: Optional[str] = None
    hours_per_week: Optional[int] = None
    preferred_stack: Optional[str] = None
    status: Optional[str] = None
    phases: Optional[List[Dict[str, Any]]] = None


class PhaseCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    description: str = ""
    estimated_hours: int = 10
    completion_criteria: str = ""


class TopicCreateRequest(BaseModel):
    phase_id: str
    title: str = Field(..., min_length=2, max_length=200)
    description: str = ""
    subtopics: List[str] = []
    prerequisites: List[str] = []
    difficulty: str = "Intermediate"
    estimated_hours: int = 6
    learning_objectives: List[str] = []
    practical_exercises: List[str] = []
    project_checkpoint: str = ""
    completion_criteria: str = ""


class TopicUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    subtopics: Optional[List[str]] = None
    prerequisites: Optional[List[str]] = None
    difficulty: Optional[str] = None
    estimated_hours: Optional[int] = None
    learning_objectives: Optional[List[str]] = None
    practical_exercises: Optional[List[str]] = None
    project_checkpoint: Optional[str] = None
    completion_criteria: Optional[str] = None
    status: Optional[str] = None
    reading_progress: Optional[int] = None
    time_spent_minutes: Optional[int] = None


class TutorialInputRequest(BaseModel):
    url: str = Field(..., min_length=5)
    title: Optional[str] = None
    channel_name: Optional[str] = None
    channel: Optional[str] = None
    duration_label: Optional[str] = None
    duration: Optional[str] = None
    notes: Optional[str] = None
    is_primary: bool = True
    replace_existing_id: Optional[str] = None


class ReadingUpdateRequest(BaseModel):
    title: Optional[str] = None
    overview: Optional[str] = None
    sections: Optional[List[Dict[str, Any]]] = None
    markdown_content: Optional[str] = None
    summary: Optional[str] = None


class RegenerateRequest(BaseModel):
    confirm_overwrite: bool = False


class NoteCreateOrUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = ""
    topic_id: Optional[str] = None
    roadmap_id: Optional[str] = None
    tags: Optional[List[str]] = None
    is_pinned: Optional[bool] = False


class DiaryEntryCreateRequest(BaseModel):
    title: str = Field(default="", max_length=200)
    entry_date: Optional[str] = None
    pages: List[str] = Field(default_factory=lambda: [""])
    is_draft: bool = False
    client_draft_key: str = Field(default="", max_length=100)


class DiaryEntryUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    pages: Optional[List[str]] = None
    is_draft: Optional[bool] = None


class StudyJournalCreateRequest(BaseModel):
    title: str = Field(default="", max_length=200)
    subject: str = Field(default="", max_length=150)
    topic: str = Field(default="", max_length=200)
    chapter_or_module: str = Field(default="", max_length=200)
    study_date: Optional[str] = None
    duration_minutes: int = 0
    learning_status: str = "understood"
    key_concepts: str = Field(default="", max_length=2000)
    learning_outcomes: str = Field(default="", max_length=2000)
    revision_notes: str = Field(default="", max_length=2000)
    pages: List[Dict[str, Any]] = Field(default_factory=lambda: [{"type": "doc", "blocks": [{"type": "paragraph", "runs": []}]}])
    is_draft: bool = False
    client_draft_key: str = Field(default="", max_length=100)


class StudyJournalUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    subject: Optional[str] = Field(default=None, max_length=150)
    topic: Optional[str] = Field(default=None, max_length=200)
    chapter_or_module: Optional[str] = Field(default=None, max_length=200)
    study_date: Optional[str] = None
    duration_minutes: Optional[int] = None
    learning_status: Optional[str] = None
    key_concepts: Optional[str] = Field(default=None, max_length=2000)
    learning_outcomes: Optional[str] = Field(default=None, max_length=2000)
    revision_notes: Optional[str] = Field(default=None, max_length=2000)
    pages: Optional[List[Dict[str, Any]]] = None
    is_draft: Optional[bool] = None


class QuizSubmissionRequest(BaseModel):
    answers: Dict[str, int] = Field(default_factory=dict)  # question_id or index -> selected_option_index (0..3)
    duration_seconds: int = 0


class StudioGenerateRequest(BaseModel):
    tool_type: str
    title: Optional[str] = None
    source_ids: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)
    async_mode: bool = False


class StudioUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[Dict[str, Any]] = None


class FlashcardCreateRequest(BaseModel):
    front: str = Field(..., min_length=1)
    back: str = Field(..., min_length=1)
    hint: str = ""
    category: str = "Custom"
    studio_output_id: Optional[str] = None
    topic_id: Optional[str] = None


class FlashcardUpdateRequest(BaseModel):
    front: Optional[str] = None
    back: Optional[str] = None
    hint: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None  # 'new' | 'learning' | 'review' | 'known'


# ============================================================================
# AUTHENTICATION & USER PROFILE ROUTES
# ============================================================================
@app.post("/api/auth/register")
@app.post("/api/auth/signup")
def register_account(req: SignupRequest, request: Request) -> Dict[str, Any]:
    from backend.otp_auth import initiate_pending_registration

    client_ip = request.client.host if request.client else ""
    return initiate_pending_registration(
        name=req.name,
        email=req.email,
        password=req.password,
        confirm_password=req.confirm_password,
        target_role=req.target_role or "Full Stack Developer",
        client_ip=client_ip,
    )


@app.post("/api/auth/verify-email")
def verify_email_otp(req: VerifyEmailRequest) -> Dict[str, Any]:
    from backend.otp_auth import verify_pending_registration_otp

    return verify_pending_registration_otp(req.pending_token, req.otp_code)


@app.post("/api/auth/resend-verification")
def resend_email_otp(req: ResendVerificationRequest) -> Dict[str, Any]:
    from backend.otp_auth import resend_pending_verification

    return resend_pending_verification(req.pending_token)


@app.get("/api/auth/pending-registration/{pending_token}")
def get_pending_registration(pending_token: str) -> Dict[str, Any]:
    from backend.otp_auth import get_pending_registration_status

    return get_pending_registration_status(pending_token)


@app.delete("/api/auth/pending-registration/{pending_token}")
def delete_pending_registration(pending_token: str) -> Dict[str, Any]:
    from backend.otp_auth import cancel_pending_registration

    return cancel_pending_registration(pending_token)


@app.post("/api/email/webhook")
def receive_email_provider_webhook(payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    import hmac as _hmac
    from backend.email_service import record_provider_webhook_event

    configured_secret = os.environ.get("EMAIL_WEBHOOK_SECRET", "").strip()
    if not configured_secret:
        raise HTTPException(status_code=503, detail="Email webhook receiver is not configured.")
    provided_secret = request.headers.get("x-email-webhook-secret", "").strip()
    if not provided_secret or not _hmac.compare_digest(provided_secret, configured_secret):
        raise HTTPException(status_code=401, detail="Unauthorized webhook request.")

    # Support both Resend webhook format (type + data) and generic webhook format
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    event_id = (
        str(payload.get("event_id", "")).strip()
        or request.headers.get("svix-id", "").strip()
    )
    event_type = str(payload.get("event") or payload.get("type") or "").strip()
    correlation_id = str(payload.get("correlation_id", "")).strip()
    provider_message_id = str(
        payload.get("provider_message_id") or data.get("email_id") or ""
    ).strip()
    to_list = data.get("to") if isinstance(data.get("to"), list) else []
    recipient_email = payload.get("recipient_email") or (to_list[0] if to_list else None)
    provider = str(payload.get("provider") or ("resend" if payload.get("type") else "webhook")).strip()

    if not event_type or (not correlation_id and not provider_message_id):
        raise HTTPException(
            status_code=400,
            detail="event/type and correlation_id or provider_message_id are required.",
        )
    try:
        return record_provider_webhook_event(
            correlation_id=correlation_id,
            provider_message_id=provider_message_id,
            event_type=event_type,
            event_id=event_id,
            recipient_email=str(recipient_email) if recipient_email else None,
            provider=provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/auth/login")
def login(req: LoginRequest) -> Dict[str, Any]:
    email_clean = req.email.strip().lower()
    with get_db(commit=True) as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email_clean,)).fetchone()
        if not row or not verify_password(req.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password.")

        prefs = ensure_user_preferences(conn, row["id"])
        user_data = {
            "id": row["id"],
            "email": row["email"],
            "name": row["name"],
            "role": row["role"],
            "target_role": row["target_role"],
            "bio": row["bio"],
            "avatar_color": row["avatar_color"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "preferences": sanitize_preferences_for_client(prefs),
        }
    token = create_access_token(row["id"], row["email"])
    return {"token": token, "user": user_data}


@app.get("/api/auth/me")
def get_me(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return {"user": current_user}


@app.post("/api/auth/logout")
def logout(
    token: str = Depends(extract_bearer_token),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    revoke_access_token(token, expected_user_id=current_user["id"])
    return {"ok": True, "message": "Logged out successfully."}


@app.put("/api/settings/profile")
def update_profile(
    req: ProfileUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        name = req.name.strip() if req.name is not None and req.name.strip() else row["name"]
        target_role = req.target_role.strip() if req.target_role is not None else row["target_role"]
        bio = req.bio.strip() if req.bio is not None else row["bio"]
        avatar_color = req.avatar_color if req.avatar_color is not None else row["avatar_color"]
        avatar_url = req.avatar_url if req.avatar_url is not None else (row.get("avatar_url") or "")

        conn.execute(
            """
            UPDATE users SET name = ?, target_role = ?, bio = ?, avatar_color = ?, avatar_url = ?, updated_at = ?
            WHERE id = ?
            """,
            (name, target_role, bio, avatar_color, avatar_url, utc_now(), uid),
        )
        updated = conn.execute(
            "SELECT id, email, name, role, target_role, bio, avatar_color, avatar_url, created_at, updated_at FROM users WHERE id = ?",
            (uid,),
        ).fetchone()
        prefs = ensure_user_preferences(conn, uid)
        updated["preferences"] = sanitize_preferences_for_client(prefs)
    return {"user": updated}


@app.put("/api/settings/preferences")
def update_preferences(
    req: PreferencesUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        pref = ensure_user_preferences(conn, uid)
        updates: Dict[str, Any] = {}
        for field in (
            "ai_provider",
            "gemini_model",
            "openai_model",
            "anthropic_model",
            "default_skill_level",
            "study_hours_per_week",
            "auto_generate_policy",
            "theme",
            "preferred_language",
        ):
            val = getattr(req, field)
            if val is not None:
                if field == "theme" and val not in ("midnight_luxe", "obsidian_emerald", "midnight_sapphire", "onyx_burgundy"):
                    raise HTTPException(status_code=400, detail="Invalid theme selection.")
                updates[field] = val

        raw_credentials: Dict[str, str] = {}
        for key_field in (
            "gemini_api_key",
            "openai_api_key",
            "anthropic_api_key",
            "youtube_api_key",
            "elevenlabs_api_key",
            "video_provider_key",
        ):
            val = getattr(req, key_field)
            if val is not None:
                # Allow setting or clearing key; encrypt at rest before persisting to SQLite
                raw_credentials[key_field] = val.strip()

        if raw_credentials:
            updates.update(encrypt_user_preference_credentials(uid, raw_credentials))

        if req.show_demo_data is not None:
            updates["show_demo_data"] = 1 if req.show_demo_data else 0
        if req.reduced_motion is not None:
            updates["reduced_motion"] = 1 if req.reduced_motion else 0

        if updates:
            updates["updated_at"] = utc_now()
            set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
            conn.execute(
                f"UPDATE user_preferences SET {set_clause} WHERE user_id = ?",
                [*updates.values(), uid],
            )
        new_pref = ensure_user_preferences(conn, uid)
    return {"preferences": sanitize_preferences_for_client(new_pref)}


# ============================================================================
# SOURCE LIBRARY & DOCUMENT PROCESSING PIPELINE (PART 7)
# ============================================================================
def _format_source_row(row: Dict[str, Any], include_text: bool = False) -> Dict[str, Any]:
    data = {
        "id": row["id"],
        "user_id": row["user_id"],
        "title": row["title"],
        "original_filename": row["original_filename"],
        "file_type": row["file_type"],
        "file_size": row["file_size"],
        "status": row["status"],
        "error_message": row.get("error_message", ""),
        "word_count": row.get("word_count", 0),
        "page_count": row.get("page_count", 1),
        "summary": row.get("summary", ""),
        "tags": json.loads(row.get("tags_json") or "[]"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_text:
        data["extracted_text"] = row.get("extracted_text", "")
    return data


@app.get("/api/sources")
def list_sources(
    search: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM sources WHERE user_id = ? ORDER BY created_at DESC",
            (uid,),
        ).fetchall()

    items = [_format_source_row(r, include_text=False) for r in rows]
    if status_filter and status_filter != "all":
        items = [i for i in items if i["status"] == status_filter]
    if search and search.strip():
        q = search.strip().lower()
        items = [
            i
            for i in items
            if q in i["title"].lower()
            or q in i["original_filename"].lower()
            or q in i["summary"].lower()
            or any(q in t.lower() for t in i["tags"])
        ]
    return {"sources": items, "supported_formats": SUPPORTED_EXTENSIONS}


@app.post("/api/sources/upload")
async def upload_source(
    file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
    tags: Optional[str] = Form(default="[]"),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    orig_name = file.filename or "document.txt"
    ext = os.path.splitext(orig_name)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS.keys()))}",
        )

    raw_bytes = await file.read()
    if len(raw_bytes) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 25 MB maximum upload size.")

    source_id = new_id("src")
    user_upload_dir = os.path.join(UPLOADS_DIR, uid)
    os.makedirs(user_upload_dir, exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", orig_name)
    disk_path = os.path.join(user_upload_dir, f"{source_id}_{safe_name}")

    with open(disk_path, "wb") as f:
        f.write(raw_bytes)

    try:
        parsed_tags = json.loads(tags) if tags else []
        if not isinstance(parsed_tags, list):
            parsed_tags = []
    except Exception:
        parsed_tags = []

    doc_title = (title or os.path.splitext(orig_name)[0]).strip() or orig_name
    now = utc_now()

    with get_db(commit=True) as conn:
        conn.execute(
            """
            INSERT INTO sources (
                id, user_id, title, original_filename, file_path, file_type, file_size,
                status, error_message, extracted_text, word_count, page_count, summary, tags_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'uploading', '', '', 0, 1, '', ?, ?, ?)
            """,
            (source_id, uid, doc_title, orig_name, disk_path, ext, len(raw_bytes), json.dumps(parsed_tags), now, now),
        )
        processed = process_and_index_source(conn, source_id, uid, disk_path, orig_name)
        log_activity(conn, uid, "upload_source", "source", source_id, f"Uploaded source: {doc_title}", 5)

    return {"source": _format_source_row(processed, include_text=True)}


@app.post("/api/sources/text")
def create_text_source(
    req: TextSourceCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    source_id = new_id("src")
    ext = req.file_type if req.file_type in SUPPORTED_EXTENSIONS else ".md"
    orig_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", req.title.strip()[:50]) + ext
    user_upload_dir = os.path.join(UPLOADS_DIR, uid)
    os.makedirs(user_upload_dir, exist_ok=True)
    disk_path = os.path.join(user_upload_dir, f"{source_id}_{orig_name}")

    encoded = req.content.encode("utf-8")
    with open(disk_path, "wb") as f:
        f.write(encoded)

    now = utc_now()
    with get_db(commit=True) as conn:
        conn.execute(
            """
            INSERT INTO sources (
                id, user_id, title, original_filename, file_path, file_type, file_size,
                status, error_message, extracted_text, word_count, page_count, summary, tags_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'uploading', '', '', 0, 1, '', ?, ?, ?)
            """,
            (
                source_id,
                uid,
                req.title.strip(),
                orig_name,
                disk_path,
                ext,
                len(encoded),
                json.dumps(req.tags or []),
                now,
                now,
            ),
        )
        processed = process_and_index_source(conn, source_id, uid, disk_path, orig_name)
        log_activity(conn, uid, "create_source", "source", source_id, f"Added study source: {req.title.strip()}", 5)

    return {"source": _format_source_row(processed, include_text=True)}


@app.get("/api/sources/{source_id}")
def get_source_detail(
    source_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db() as conn:
        row = conn.execute("SELECT * FROM sources WHERE id = ? AND user_id = ?", (source_id, uid)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Source document not found or access denied.")
        chunks = conn.execute(
            "SELECT id, chunk_index, page_number, section_title, content, token_estimate FROM source_chunks WHERE source_id = ? AND user_id = ? ORDER BY chunk_index ASC",
            (source_id, uid),
        ).fetchall()

    formatted = _format_source_row(row, include_text=True)
    formatted["chunks"] = chunks
    return {"source": formatted}


@app.put("/api/sources/{source_id}")
def rename_source(
    source_id: str,
    req: SourceRenameRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        row = conn.execute("SELECT * FROM sources WHERE id = ? AND user_id = ?", (source_id, uid)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Source document not found.")
        tags_json = json.dumps(req.tags) if req.tags is not None else row["tags_json"]
        conn.execute(
            "UPDATE sources SET title = ?, tags_json = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (req.title.strip(), tags_json, utc_now(), source_id, uid),
        )
        updated = conn.execute("SELECT * FROM sources WHERE id = ? AND user_id = ?", (source_id, uid)).fetchone()
    return {"source": _format_source_row(updated, include_text=True)}


@app.post("/api/sources/{source_id}/retry")
def retry_source_processing(
    source_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        row = conn.execute("SELECT * FROM sources WHERE id = ? AND user_id = ?", (source_id, uid)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Source document not found.")
        processed = process_and_index_source(conn, source_id, uid, row["file_path"], row["original_filename"])
    return {"source": _format_source_row(processed, include_text=True)}


@app.delete("/api/sources/{source_id}")
def delete_source(
    source_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        row = conn.execute("SELECT * FROM sources WHERE id = ? AND user_id = ?", (source_id, uid)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Source document not found.")
        file_path = row.get("file_path", "")
        conn.execute("DELETE FROM sources WHERE id = ? AND user_id = ?", (source_id, uid))

    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass
    return {"ok": True, "deleted_id": source_id}


def _verify_user_owns_sources(conn, user_id: str, source_ids: Optional[List[str]]) -> None:
    if not source_ids:
        return
    unique_ids = [sid.strip() for sid in set(source_ids) if sid and sid.strip()]
    if not unique_ids:
        return
    placeholders = ",".join("?" for _ in unique_ids)
    owned_rows = conn.execute(
        f"SELECT id FROM sources WHERE user_id = ? AND id IN ({placeholders})",
        [user_id, *unique_ids],
    ).fetchall()
    if len(owned_rows) != len(unique_ids):
        raise HTTPException(
            status_code=404,
            detail="One or more selected source documents were not found or access is denied.",
        )


@app.post("/api/sources/ask")
def ask_sources_grounded(
    req: SourceQuestionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        prefs = ensure_user_preferences(conn, uid)
        chunks = retrieve_relevant_chunks(conn, uid, req.source_ids, req.question, top_k=6)
        result = answerFromSources(req.question, chunks, user_prefs=prefs)
        log_activity(conn, uid, "source_qa", "source", "", f"Asked source question: {req.question[:60]}", 3)
    return result


# ============================================================================
# INTELLIGENT AI ROADMAP AGENT & COMPLETE ROADMAP LIFECYCLE (PART 8)
# ============================================================================
def _assemble_roadmap_detail(conn, roadmap_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    rm = conn.execute("SELECT * FROM roadmaps WHERE id = ? AND user_id = ?", (roadmap_id, user_id)).fetchone()
    if not rm:
        return None

    phases = conn.execute(
        "SELECT * FROM roadmap_phases WHERE roadmap_id = ? AND user_id = ? ORDER BY phase_order ASC",
        (roadmap_id, user_id),
    ).fetchall()
    topics = conn.execute(
        "SELECT * FROM roadmap_topics WHERE roadmap_id = ? AND user_id = ? ORDER BY topic_order ASC",
        (roadmap_id, user_id),
    ).fetchall()

    # Check resource readiness and active jobs for each topic
    tutorials = conn.execute(
        "SELECT id, topic_id, source_type FROM topic_tutorials WHERE roadmap_id = ? AND user_id = ?",
        (roadmap_id, user_id),
    ).fetchall()
    readings = conn.execute(
        "SELECT id, topic_id, is_user_edited, has_custom_reading FROM topic_readings WHERE roadmap_id = ? AND user_id = ?",
        (roadmap_id, user_id),
    ).fetchall()
    mcqs = conn.execute(
        "SELECT id, topic_id, question_count FROM mcq_sets WHERE roadmap_id = ? AND user_id = ?",
        (roadmap_id, user_id),
    ).fetchall()
    attempts = conn.execute(
        "SELECT id, topic_id, score, max_score, percentage, passed, created_at FROM quiz_attempts WHERE roadmap_id = ? AND user_id = ? ORDER BY created_at DESC",
        (roadmap_id, user_id),
    ).fetchall()
    jobs = conn.execute(
        "SELECT * FROM generation_jobs WHERE roadmap_id = ? AND user_id = ? ORDER BY created_at DESC",
        (roadmap_id, user_id),
    ).fetchall()

    tut_by_topic: Dict[str, int] = {}
    custom_tut_by_topic: Dict[str, bool] = {}
    for t in tutorials:
        tut_by_topic[t["topic_id"]] = tut_by_topic.get(t["topic_id"], 0) + 1
        if t.get("source_type") == "user_custom":
            custom_tut_by_topic[t["topic_id"]] = True

    read_by_topic = {r["topic_id"]: r for r in readings}
    mcq_by_topic = {m["topic_id"]: m for m in mcqs}

    best_attempt_by_topic: Dict[str, Dict[str, Any]] = {}
    attempt_count_by_topic: Dict[str, int] = {}
    for att in attempts:
        tid = att["topic_id"]
        if not tid:
            continue
        attempt_count_by_topic[tid] = attempt_count_by_topic.get(tid, 0) + 1
        if tid not in best_attempt_by_topic or att["score"] > best_attempt_by_topic[tid]["score"]:
            best_attempt_by_topic[tid] = att

    jobs_by_topic: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for j in jobs:
        tid = j["topic_id"]
        rtype = j["resource_type"]
        if tid not in jobs_by_topic:
            jobs_by_topic[tid] = {}
        if rtype not in jobs_by_topic[tid]:
            jobs_by_topic[tid][rtype] = j

    topics_by_phase: Dict[str, List[Dict[str, Any]]] = {}
    total_topics = len(topics)
    completed_topics = 0

    for t in topics:
        tid = t["id"]
        if t["status"] == "completed":
            completed_topics += 1
        t_jobs = jobs_by_topic.get(tid, {})
        formatted_topic = {
            "id": tid,
            "roadmap_id": t["roadmap_id"],
            "phase_id": t["phase_id"],
            "topic_order": t["topic_order"],
            "title": t["title"],
            "description": t["description"],
            "subtopics": json.loads(t.get("subtopics_json") or "[]"),
            "prerequisites": json.loads(t.get("prerequisites_json") or "[]"),
            "difficulty": t["difficulty"],
            "estimated_hours": t["estimated_hours"],
            "learning_objectives": json.loads(t.get("learning_objectives_json") or "[]"),
            "practical_exercises": json.loads(t.get("practical_exercises_json") or "[]"),
            "project_checkpoint": t.get("project_checkpoint", ""),
            "completion_criteria": t.get("completion_criteria", ""),
            "status": t["status"],
            "reading_progress": t.get("reading_progress", 0),
            "time_spent_minutes": t.get("time_spent_minutes", 0),
            "completed_at": t.get("completed_at", ""),
            "resources_status": {
                "tutorial_ready": tut_by_topic.get(tid, 0) > 0,
                "tutorial_count": tut_by_topic.get(tid, 0),
                "has_custom_tutorial": bool(custom_tut_by_topic.get(tid, False)),
                "reading_ready": tid in read_by_topic,
                "has_custom_reading": bool(read_by_topic[tid].get("has_custom_reading", 0)) if tid in read_by_topic else False,
                "quiz_ready": tid in mcq_by_topic,
                "quiz_question_count": mcq_by_topic[tid]["question_count"] if tid in mcq_by_topic else 0,
                "attempt_count": attempt_count_by_topic.get(tid, 0),
                "best_attempt": best_attempt_by_topic.get(tid),
                "jobs": t_jobs,
            },
        }
        topics_by_phase.setdefault(t["phase_id"], []).append(formatted_topic)

    formatted_phases = []
    for p in phases:
        p_topics = topics_by_phase.get(p["id"], [])
        p_done = sum(1 for pt in p_topics if pt["status"] == "completed")
        formatted_phases.append(
            {
                "id": p["id"],
                "roadmap_id": p["roadmap_id"],
                "phase_order": p["phase_order"],
                "title": p["title"],
                "description": p["description"],
                "estimated_hours": p["estimated_hours"],
                "completion_criteria": p.get("completion_criteria", ""),
                "total_topics": len(p_topics),
                "completed_topics": p_done,
                "progress_percent": int(round((p_done / len(p_topics)) * 100)) if p_topics else 0,
                "topics": p_topics,
            }
        )

    progress_pct = int(round((completed_topics / total_topics) * 100)) if total_topics > 0 else 0
    return {
        **rm,
        "total_topics": total_topics,
        "completed_topics": completed_topics,
        "progress_percent": progress_pct,
        "phases": formatted_phases,
        "jobs_summary": {
            "total": len(jobs),
            "queued": sum(1 for j in jobs if j["status"] == "queued"),
            "processing": sum(1 for j in jobs if j["status"] == "processing"),
            "completed": sum(1 for j in jobs if j["status"] == "completed"),
            "failed": sum(1 for j in jobs if j["status"] == "failed"),
        },
    }


@app.post("/api/roadmaps/generate")
def generate_roadmap_preview(
    req: RoadmapGenerateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        prefs = ensure_user_preferences(conn, uid)
        draft = generateRoadmap(
            target_role=req.target_role,
            skill_level=req.skill_level,
            hours_per_week=req.hours_per_week,
            preferred_stack=req.preferred_stack,
            existing_knowledge=req.existing_knowledge,
            target_completion_date=req.target_completion_date,
            priorities=req.priorities,
            exam_goals=req.exam_goals,
            user_prefs=prefs,
        )
        # Save conversation turn in ai_conversations
        conv_id = new_id("conv")
        now = utc_now()
        agent_reply = (
            f"I've designed an editable **{draft['title']}** tailored to a **{req.skill_level}** level "
            f"at **{req.hours_per_week} hrs/week** ({draft['total_estimated_hours']} total hours across {len(draft['phases'])} phases). "
            f"You can expand every phase below, edit topic titles or study hours, reorder or add topics, and click **Save Roadmap** when ready."
        )
        follow_up_suggestions = [
            "Focus more on hands-on portfolio projects",
            "Adapt for technical interview & coding assessment preparation",
            "Compress schedule for an accelerated 6-week sprint",
        ]
        messages = [
            {
                "role": "user",
                "content": req.conversation_message or f"Generate a {req.skill_level} roadmap for {req.target_role}",
                "timestamp": now,
            },
            {
                "role": "assistant",
                "content": agent_reply,
                "follow_up_suggestions": follow_up_suggestions,
                "timestamp": now,
            },
        ]
        conn.execute(
            """
            INSERT INTO ai_conversations (id, user_id, context_type, title, source_ids_json, messages_json, draft_roadmap_json, created_at, updated_at)
            VALUES (?, ?, 'roadmap_agent', ?, '[]', ?, ?, ?, ?)
            """,
            (conv_id, uid, draft["title"], json.dumps(messages), json.dumps(draft), now, now),
        )
    return {
        "draft_roadmap": draft,
        "conversation_id": conv_id,
        "agent_message": agent_reply,
        "follow_up_suggestions": follow_up_suggestions,
    }


@app.post("/api/roadmaps")
def save_roadmap(
    req: RoadmapSaveRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    fallback_params = {
        "target_role": req.target_role,
        "skill_level": req.skill_level,
        "hours_per_week": req.hours_per_week,
        "preferred_stack": req.preferred_stack,
        "existing_knowledge": req.existing_knowledge,
        "priorities": req.priorities,
        "exam_goals": req.exam_goals,
    }
    validated = validate_and_repair_roadmap(req.model_dump(), fallback_params)

    with get_db(commit=True) as conn:
        # Prevent accidental duplicate submission within 8 seconds
        recent = conn.execute(
            "SELECT id, created_at FROM roadmaps WHERE user_id = ? AND title = ? ORDER BY created_at DESC LIMIT 1",
            (uid, req.title.strip()),
        ).fetchone()
        if recent:
            try:
                created_dt = datetime.fromisoformat(recent["created_at"])
                if (datetime.now(timezone.utc) - created_dt).total_seconds() < 8:
                    return {"roadmap": _assemble_roadmap_detail(conn, recent["id"], uid), "deduplicated": True}
            except Exception:
                pass

        roadmap_id = new_id("rm")
        now = utc_now()
        conn.execute(
            """
            INSERT INTO roadmaps (
                id, user_id, title, target_role, description, skill_level, existing_knowledge,
                target_completion_date, hours_per_week, preferred_stack, priorities, exam_goals,
                total_estimated_hours, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (
                roadmap_id,
                uid,
                req.title.strip() or validated["title"],
                req.target_role.strip(),
                req.description.strip() or validated["description"],
                req.skill_level,
                req.existing_knowledge,
                req.target_completion_date,
                req.hours_per_week,
                req.preferred_stack,
                req.priorities,
                req.exam_goals,
                validated["total_estimated_hours"],
                now,
                now,
            ),
        )

        all_queued_job_ids: List[str] = []
        first_topic_job_ids: List[str] = []

        for p_idx, p in enumerate(validated["phases"], start=1):
            phase_id = new_id("phs")
            conn.execute(
                """
                INSERT INTO roadmap_phases (
                    id, roadmap_id, user_id, phase_order, title, description,
                    estimated_hours, completion_criteria, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    phase_id,
                    roadmap_id,
                    uid,
                    p_idx,
                    p["title"],
                    p.get("description", ""),
                    p.get("estimated_hours", 10),
                    p.get("completion_criteria", ""),
                    now,
                    now,
                ),
            )
            for t_idx, t in enumerate(p["topics"], start=1):
                topic_id = new_id("top")
                conn.execute(
                    """
                    INSERT INTO roadmap_topics (
                        id, roadmap_id, phase_id, user_id, topic_order, title, description,
                        subtopics_json, prerequisites_json, difficulty, estimated_hours,
                        learning_objectives_json, practical_exercises_json, project_checkpoint,
                        completion_criteria, status, reading_progress, time_spent_minutes,
                        completed_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'not_started', 0, 0, '', ?, ?)
                    """,
                    (
                        topic_id,
                        roadmap_id,
                        phase_id,
                        uid,
                        t_idx,
                        t["title"],
                        t.get("description", ""),
                        json.dumps(t.get("subtopics", [])),
                        json.dumps(t.get("prerequisites", [])),
                        t.get("difficulty", req.skill_level),
                        t.get("estimated_hours", 8),
                        json.dumps(t.get("learning_objectives", [])),
                        json.dumps(t.get("practical_exercises", [])),
                        t.get("project_checkpoint", ""),
                        t.get("completion_criteria", ""),
                        now,
                        now,
                    ),
                )

                should_queue = (
                    req.generation_policy == "all_async"
                    or (req.generation_policy == "phase_1_only" and p_idx == 1)
                    or (p_idx == 1 and t_idx == 1)
                )
                if should_queue:
                    jobs = enqueue_topic_resource_jobs(conn, uid, roadmap_id, phase_id, topic_id)
                    for j in jobs:
                        if p_idx == 1 and t_idx == 1 and req.run_sync_for_first_topic:
                            first_topic_job_ids.append(j["id"])
                        else:
                            all_queued_job_ids.append(j["id"])

        log_activity(conn, uid, "create_roadmap", "roadmap", roadmap_id, f"Saved roadmap: {req.title.strip()}", 10)

    # Execute the first topic's resources immediately so the student can start Topic 1 with zero wait,
    # and dispatch all remaining topic jobs to the bounded background worker queue!
    for jid in first_topic_job_ids:
        execute_job_sync(jid)
    if all_queued_job_ids:
        dispatch_jobs_async(all_queued_job_ids)

    with get_db() as conn:
        full_rm = _assemble_roadmap_detail(conn, roadmap_id, uid)
    return {"roadmap": full_rm}


@app.get("/api/roadmaps")
def list_roadmaps(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db() as conn:
        rows = conn.execute("SELECT id FROM roadmaps WHERE user_id = ? ORDER BY updated_at DESC", (uid,)).fetchall()
        roadmaps = [_assemble_roadmap_detail(conn, r["id"], uid) for r in rows]
    return {"roadmaps": [rm for rm in roadmaps if rm is not None]}


@app.get("/api/roadmaps/{roadmap_id}")
def get_roadmap(
    roadmap_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db() as conn:
        rm = _assemble_roadmap_detail(conn, roadmap_id, uid)
        if not rm:
            raise HTTPException(status_code=404, detail="Roadmap not found or access denied.")
    return {"roadmap": rm}


@app.put("/api/roadmaps/{roadmap_id}")
def update_roadmap(
    roadmap_id: str,
    req: RoadmapUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        existing = conn.execute("SELECT * FROM roadmaps WHERE id = ? AND user_id = ?", (roadmap_id, uid)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Roadmap not found or access denied.")

        title = req.title.strip() if req.title is not None and req.title.strip() else existing["title"]
        desc = req.description.strip() if req.description is not None else existing["description"]
        t_role = req.target_role.strip() if req.target_role is not None and req.target_role.strip() else existing["target_role"]
        s_level = req.skill_level if req.skill_level is not None else existing["skill_level"]
        hpw = req.hours_per_week if req.hours_per_week is not None else existing["hours_per_week"]
        stack = req.preferred_stack if req.preferred_stack is not None else existing["preferred_stack"]
        st = req.status if req.status is not None else existing["status"]

        conn.execute(
            """
            UPDATE roadmaps
            SET title = ?, description = ?, target_role = ?, skill_level = ?,
                hours_per_week = ?, preferred_stack = ?, status = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (title, desc, t_role, s_level, hpw, stack, st, utc_now(), roadmap_id, uid),
        )
        rm = _assemble_roadmap_detail(conn, roadmap_id, uid)
    return {"roadmap": rm}


@app.delete("/api/roadmaps/{roadmap_id}")
def delete_roadmap(
    roadmap_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        existing = conn.execute("SELECT id, title FROM roadmaps WHERE id = ? AND user_id = ?", (roadmap_id, uid)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Roadmap not found or access denied.")

        topic_count = conn.execute("SELECT COUNT(*) AS cnt FROM roadmap_topics WHERE roadmap_id = ? AND user_id = ?", (roadmap_id, uid)).fetchone()["cnt"]
        note_count = conn.execute("SELECT COUNT(*) AS cnt FROM personal_notes WHERE roadmap_id = ? AND user_id = ?", (roadmap_id, uid)).fetchone()["cnt"]
        attempt_count = conn.execute("SELECT COUNT(*) AS cnt FROM quiz_attempts WHERE roadmap_id = ? AND user_id = ?", (roadmap_id, uid)).fetchone()["cnt"]

        conn.execute("DELETE FROM roadmaps WHERE id = ? AND user_id = ?", (roadmap_id, uid))

    return {
        "ok": True,
        "deleted_roadmap_id": roadmap_id,
        "cleanup_summary": {
            "topics_removed": topic_count,
            "notes_removed": note_count,
            "quiz_attempts_removed": attempt_count,
        },
    }


@app.post("/api/roadmaps/{roadmap_id}/phases")
def add_roadmap_phase(
    roadmap_id: str,
    req: PhaseCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        rm = conn.execute("SELECT id FROM roadmaps WHERE id = ? AND user_id = ?", (roadmap_id, uid)).fetchone()
        if not rm:
            raise HTTPException(status_code=404, detail="Roadmap not found.")
        max_order = conn.execute(
            "SELECT COALESCE(MAX(phase_order), 0) AS m FROM roadmap_phases WHERE roadmap_id = ? AND user_id = ?",
            (roadmap_id, uid),
        ).fetchone()["m"]
        phase_id = new_id("phs")
        now = utc_now()
        conn.execute(
            """
            INSERT INTO roadmap_phases (id, roadmap_id, user_id, phase_order, title, description, estimated_hours, completion_criteria, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (phase_id, roadmap_id, uid, max_order + 1, req.title.strip(), req.description.strip(), req.estimated_hours, req.completion_criteria, now, now),
        )
        conn.execute("UPDATE roadmaps SET updated_at = ? WHERE id = ?", (now, roadmap_id))
        updated_rm = _assemble_roadmap_detail(conn, roadmap_id, uid)
    return {"roadmap": updated_rm}


@app.post("/api/roadmaps/{roadmap_id}/topics")
def add_roadmap_topic(
    roadmap_id: str,
    req: TopicCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        phs = conn.execute(
            "SELECT id FROM roadmap_phases WHERE id = ? AND roadmap_id = ? AND user_id = ?",
            (req.phase_id, roadmap_id, uid),
        ).fetchone()
        if not phs:
            raise HTTPException(status_code=404, detail="Roadmap phase not found.")
        max_order = conn.execute(
            "SELECT COALESCE(MAX(topic_order), 0) AS m FROM roadmap_topics WHERE phase_id = ? AND user_id = ?",
            (req.phase_id, uid),
        ).fetchone()["m"]
        topic_id = new_id("top")
        now = utc_now()
        conn.execute(
            """
            INSERT INTO roadmap_topics (
                id, roadmap_id, phase_id, user_id, topic_order, title, description,
                subtopics_json, prerequisites_json, difficulty, estimated_hours,
                learning_objectives_json, practical_exercises_json, project_checkpoint,
                completion_criteria, status, reading_progress, time_spent_minutes,
                completed_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'not_started', 0, 0, '', ?, ?)
            """,
            (
                topic_id,
                roadmap_id,
                req.phase_id,
                uid,
                max_order + 1,
                req.title.strip(),
                req.description.strip(),
                json.dumps(req.subtopics),
                json.dumps(req.prerequisites),
                req.difficulty,
                req.estimated_hours,
                json.dumps(req.learning_objectives),
                json.dumps(req.practical_exercises),
                req.project_checkpoint,
                req.completion_criteria,
                now,
                now,
            ),
        )
        jobs = enqueue_topic_resource_jobs(conn, uid, roadmap_id, req.phase_id, topic_id)
        job_ids = [j["id"] for j in jobs]

    if job_ids:
        dispatch_jobs_async(job_ids)

    with get_db() as conn:
        updated_rm = _assemble_roadmap_detail(conn, roadmap_id, uid)
    return {"roadmap": updated_rm, "created_topic_id": topic_id}


# ============================================================================
# TOPIC LEARNING WORKSPACE (PART 9: TUTORIAL, READING, NOTES, 20-MCQ EXAM)
# ============================================================================
def _format_tutorial_row(t: Dict[str, Any]) -> Dict[str, Any]:
    vid = t.get("video_id") or ""
    raw_notes = (t.get("notes") or "").strip()
    if raw_notes.startswith("Curated verified lecture") or raw_notes.startswith("Retrieved via YouTube Data API") or raw_notes == "User-saved custom YouTube tutorial.":
        raw_notes = ""
    is_custom = t.get("source_type") == "user_custom"
    watch_url = f"https://www.youtube.com/watch?v={vid}" if vid else t.get("video_url", "")
    return {
        **t,
        "notes": raw_notes,
        "url": watch_url,
        "watch_url": watch_url,
        "channel": t.get("channel_name") or "YouTube Educator",
        "duration": t.get("duration_label") or "25m",
        "is_user_added": is_custom,
        "source_badge": "CUSTOMIZED" if is_custom else "ORIGINAL",
    }


def _normalize_mistakes_list(raw_mistakes: Any) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    if not isinstance(raw_mistakes, list):
        return out
    for item in raw_mistakes:
        if isinstance(item, dict):
            m = str(item.get("mistake") or item.get("title") or item.get("pitfall") or "").strip()
            why = str(item.get("why_it_happens") or item.get("why") or item.get("reason") or "").strip()
            fix = str(item.get("fix") or item.get("solution") or "").strip()
            if m or why or fix:
                out.append({"mistake": m or "Common Pitfall", "why_it_happens": why, "fix": fix})
        elif isinstance(item, str) and item.strip():
            out.append({"mistake": item.strip(), "why_it_happens": "", "fix": ""})
    return out


def _format_reading_row(reading_row: Optional[Dict[str, Any]], topic_title_fallback: str = "Topic") -> Optional[Dict[str, Any]]:
    if not reading_row:
        return None
    from backend.reading_templates import normalize_diagrams

    t_title = reading_row.get("title") or topic_title_fallback
    raw_diagrams = json.loads(reading_row.get("diagrams_json") or "[]")
    sections_list = json.loads(reading_row.get("sections_json") or "[]")
    sec_headings = [str(s.get("heading") or "").strip() for s in sections_list if isinstance(s, dict) and s.get("heading")]
    diagrams = normalize_diagrams(raw_diagrams, t_title, sec_headings)

    has_custom = bool(reading_row.get("has_custom_reading", 0)) and bool((reading_row.get("custom_markdown") or "").strip())
    key_defs = json.loads(reading_row.get("key_definitions_json") or "[]")
    common_m = _normalize_mistakes_list(json.loads(reading_row.get("common_mistakes_json") or "[]"))
    takeaways_list = [s.get("heading") for s in sections_list if isinstance(s, dict) and s.get("heading")]
    return {
        "id": reading_row["id"],
        "topic_id": reading_row["topic_id"],
        "title": reading_row.get("custom_title") if has_custom and reading_row.get("custom_title") else reading_row["title"],
        "overview": reading_row["overview"],
        "sections": sections_list,
        "diagrams": diagrams,
        "markdown_content": reading_row.get("custom_markdown") if has_custom else reading_row.get("markdown_content", ""),
        "original_title": reading_row["title"],
        "original_overview": reading_row["overview"],
        "original_sections": sections_list,
        "original_markdown": reading_row.get("markdown_content", ""),
        "has_custom_reading": has_custom,
        "custom_title": reading_row.get("custom_title", ""),
        "custom_markdown": reading_row.get("custom_markdown", ""),
        "custom_updated_at": reading_row.get("custom_updated_at", ""),
        "source_badge": "CUSTOMIZED" if has_custom else "ORIGINAL",
        "key_definitions": key_defs,
        "terminology": key_defs,
        "code_examples": json.loads(reading_row.get("code_examples_json") or "[]"),
        "comparison_tables": json.loads(reading_row.get("comparison_tables_json") or "[]"),
        "common_mistakes": common_m,
        "mistakes": common_m,
        "takeaways": takeaways_list,
        "interview_questions": json.loads(reading_row.get("interview_questions_json") or "[]"),
        "summary": reading_row.get("summary", ""),
        "references": json.loads(reading_row.get("references_json") or "[]"),
        "is_user_edited": bool(reading_row.get("is_user_edited", 0)) or has_custom,
        "version": reading_row.get("version", 1),
        "updated_at": reading_row["updated_at"],
    }


@app.get("/api/topics/{topic_id}")
def get_topic_workspace(
    topic_id: str,
    auto_prepare: bool = Query(default=True),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        topic = conn.execute("SELECT * FROM roadmap_topics WHERE id = ? AND user_id = ?", (topic_id, uid)).fetchone()
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found or access denied.")

        roadmap = conn.execute("SELECT id, title, target_role, skill_level FROM roadmaps WHERE id = ? AND user_id = ?", (topic["roadmap_id"], uid)).fetchone()
        phase = conn.execute("SELECT id, title, phase_order FROM roadmap_phases WHERE id = ? AND user_id = ?", (topic["phase_id"], uid)).fetchone()

        # Check if resources exist; if auto_prepare is True and any resource is missing, generate synchronously
        has_tut = conn.execute("SELECT id FROM topic_tutorials WHERE topic_id = ? AND user_id = ? LIMIT 1", (topic_id, uid)).fetchone()
        has_read = conn.execute("SELECT id FROM topic_readings WHERE topic_id = ? AND user_id = ? LIMIT 1", (topic_id, uid)).fetchone()
        has_mcq = conn.execute("SELECT id FROM mcq_sets WHERE topic_id = ? AND user_id = ? LIMIT 1", (topic_id, uid)).fetchone()

        missing_types = []
        if not has_tut:
            missing_types.append("tutorial")
        if not has_read:
            missing_types.append("reading")
        if not has_mcq:
            missing_types.append("quiz")

        if auto_prepare and missing_types:
            jobs = enqueue_topic_resource_jobs(conn, uid, topic["roadmap_id"], topic["phase_id"], topic_id, resource_types=missing_types)
            sync_ids = [j["id"] for j in jobs]
        else:
            sync_ids = []

    for jid in sync_ids:
        execute_job_sync(jid)

    with get_db() as conn:
        raw_tutorials = conn.execute(
            "SELECT * FROM topic_tutorials WHERE topic_id = ? AND user_id = ? ORDER BY is_primary DESC, created_at DESC",
            (topic_id, uid),
        ).fetchall()
        reading_row = conn.execute(
            "SELECT * FROM topic_readings WHERE topic_id = ? AND user_id = ?",
            (topic_id, uid),
        ).fetchone()
        notes = conn.execute(
            "SELECT * FROM personal_notes WHERE topic_id = ? AND user_id = ? ORDER BY is_pinned DESC, updated_at DESC",
            (topic_id, uid),
        ).fetchall()
        mcq_row = conn.execute(
            "SELECT * FROM mcq_sets WHERE topic_id = ? AND user_id = ?",
            (topic_id, uid),
        ).fetchone()
        attempts = conn.execute(
            "SELECT id, score, max_score, percentage, correct_count, incorrect_count, unanswered_count, passed, duration_seconds, created_at FROM quiz_attempts WHERE topic_id = ? AND user_id = ? ORDER BY created_at DESC",
            (topic_id, uid),
        ).fetchall()
        jobs = conn.execute(
            "SELECT * FROM generation_jobs WHERE topic_id = ? AND user_id = ? ORDER BY created_at DESC",
            (topic_id, uid),
        ).fetchall()

    tutorials = [_format_tutorial_row(t) for t in raw_tutorials]
    formatted_reading = _format_reading_row(reading_row, topic["title"])

    # IMPORTANT RULE (Part 6 Tool 7 & Part 9C):
    # Never reveal correct_index or explanations before exam submission!
    sanitized_quiz = None
    if mcq_row:
        raw_questions = json.loads(mcq_row.get("questions_json") or "[]")
        exam_questions = [
            {
                "id": q["id"],
                "number": q["number"],
                "category": q.get("category", "Core"),
                "difficulty": q.get("difficulty", topic["difficulty"]),
                "question": q["question"],
                "options": q["options"],
            }
            for q in raw_questions
        ]
        sanitized_quiz = {
            "id": mcq_row["id"],
            "topic_id": mcq_row["topic_id"],
            "title": mcq_row["title"],
            "difficulty": mcq_row["difficulty"],
            "question_count": len(exam_questions),
            "max_score": len(exam_questions),
            "passing_score": mcq_row.get("passing_score", 14),
            "marking_scheme": "+1 mark for each correct answer, 0 marks for incorrect or unanswered questions.",
            "questions": exam_questions,
            "version": mcq_row.get("version", 1),
        }

    formatted_notes = [
        {
            **n,
            "tags": json.loads(n.get("tags_json") or "[]"),
            "is_pinned": bool(n.get("is_pinned", 0)),
        }
        for n in notes
    ]

    return {
        "topic": {
            **topic,
            "subtopics": json.loads(topic.get("subtopics_json") or "[]"),
            "prerequisites": json.loads(topic.get("prerequisites_json") or "[]"),
            "learning_objectives": json.loads(topic.get("learning_objectives_json") or "[]"),
            "practical_exercises": json.loads(topic.get("practical_exercises_json") or "[]"),
            "tutorials": tutorials,
            "reading": formatted_reading,
            "notes": formatted_notes,
            "quiz": sanitized_quiz,
            "attempts": attempts,
            "jobs": jobs,
        },
        "roadmap": roadmap,
        "phase": phase,
        "tutorials": tutorials,
        "reading": formatted_reading,
        "notes": formatted_notes,
        "quiz": sanitized_quiz,
        "attempts": attempts,
        "jobs": jobs,
    }


@app.put("/api/topics/{topic_id}")
def update_topic(
    topic_id: str,
    req: TopicUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        t = conn.execute("SELECT * FROM roadmap_topics WHERE id = ? AND user_id = ?", (topic_id, uid)).fetchone()
        if not t:
            raise HTTPException(status_code=404, detail="Topic not found.")

        now = utc_now()
        new_status = req.status if req.status is not None else t["status"]
        completed_at = now if (new_status == "completed" and t["status"] != "completed") else ("" if new_status != "completed" else t["completed_at"])

        conn.execute(
            """
            UPDATE roadmap_topics
            SET title = ?, description = ?, subtopics_json = ?, prerequisites_json = ?,
                difficulty = ?, estimated_hours = ?, learning_objectives_json = ?,
                practical_exercises_json = ?, project_checkpoint = ?, completion_criteria = ?,
                status = ?, reading_progress = ?, time_spent_minutes = ?, completed_at = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                req.title.strip() if req.title else t["title"],
                req.description if req.description is not None else t["description"],
                json.dumps(req.subtopics) if req.subtopics is not None else t["subtopics_json"],
                json.dumps(req.prerequisites) if req.prerequisites is not None else t["prerequisites_json"],
                req.difficulty if req.difficulty is not None else t["difficulty"],
                req.estimated_hours if req.estimated_hours is not None else t["estimated_hours"],
                json.dumps(req.learning_objectives) if req.learning_objectives is not None else t["learning_objectives_json"],
                json.dumps(req.practical_exercises) if req.practical_exercises is not None else t["practical_exercises_json"],
                req.project_checkpoint if req.project_checkpoint is not None else t["project_checkpoint"],
                req.completion_criteria if req.completion_criteria is not None else t["completion_criteria"],
                new_status,
                req.reading_progress if req.reading_progress is not None else t["reading_progress"],
                req.time_spent_minutes if req.time_spent_minutes is not None else t["time_spent_minutes"],
                completed_at,
                now,
                topic_id,
                uid,
            ),
        )
        if req.status == "completed" and t["status"] != "completed":
            log_activity(conn, uid, "complete_topic", "topic", topic_id, f"Completed topic: {t['title']}", 15)
        updated = conn.execute("SELECT * FROM roadmap_topics WHERE id = ? AND user_id = ?", (topic_id, uid)).fetchone()
    return {"topic": updated}


@app.delete("/api/topics/{topic_id}")
def delete_topic(
    topic_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        t = conn.execute("SELECT id, title, roadmap_id FROM roadmap_topics WHERE id = ? AND user_id = ?", (topic_id, uid)).fetchone()
        if not t:
            raise HTTPException(status_code=404, detail="Topic not found.")
        conn.execute("DELETE FROM roadmap_topics WHERE id = ? AND user_id = ?", (topic_id, uid))
    return {"ok": True, "deleted_topic_id": topic_id, "roadmap_id": t["roadmap_id"]}


# --- SECTION A: TUTORIAL MANAGEMENT & CUSTOMIZED ROADMAP TUTORIALS ---
@app.post("/api/tutorials/validate-url")
def validate_youtube_tutorial_url(
    req: TutorialValidateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    vid = extract_youtube_video_id(req.url)
    if not vid:
        raise HTTPException(
            status_code=400,
            detail="Invalid YouTube URL. Please enter a valid https://www.youtube.com/watch?v=... or https://youtu.be/... link.",
        )
    oembed_meta = verify_youtube_oembed(vid) or {}
    return {
        "valid": True,
        "video_id": vid,
        "title": oembed_meta.get("title") or f"YouTube Educational Lecture ({vid})",
        "channel_name": oembed_meta.get("channel_name") or "YouTube Creator",
        "thumbnail_url": oembed_meta.get("thumbnail_url") or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
        "watch_url": f"https://www.youtube.com/watch?v={vid}",
        "duration_label": "Custom Video",
    }


@app.post("/api/topics/{topic_id}/tutorials")
def add_or_replace_topic_tutorial(
    topic_id: str,
    req: TutorialInputRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    vid = extract_youtube_video_id(req.url)
    if not vid:
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid YouTube video URL (e.g., https://www.youtube.com/watch?v=... or https://youtu.be/...).",
        )

    oembed_meta = verify_youtube_oembed(vid) or {}
    clean_title = (req.title or oembed_meta.get("title") or "").strip()
    clean_channel = (req.channel_name or req.channel or oembed_meta.get("channel_name") or "YouTube Creator").strip()
    clean_duration = (req.duration_label or req.duration or "Custom Video").strip()
    thumb = oembed_meta.get("thumbnail_url") or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    watch_url = f"https://www.youtube.com/watch?v={vid}"

    with get_db(commit=True) as conn:
        topic = conn.execute("SELECT id, title, roadmap_id FROM roadmap_topics WHERE id = ? AND user_id = ?", (topic_id, uid)).fetchone()
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found.")

        if not clean_title:
            clean_title = f"Custom Tutorial — {topic['title']}"

        if req.is_primary:
            conn.execute("UPDATE topic_tutorials SET is_primary = 0 WHERE topic_id = ? AND user_id = ?", (topic_id, uid))

        now = utc_now()
        # Check if a user_custom tutorial already exists on this topic when replacing or saving from Customized Roadmap
        existing_custom = conn.execute(
            "SELECT id FROM topic_tutorials WHERE topic_id = ? AND user_id = ? AND source_type = 'user_custom' LIMIT 1",
            (topic_id, uid),
        ).fetchone()
        target_replace_id = req.replace_existing_id or (existing_custom["id"] if existing_custom else None)

        if target_replace_id:
            existing = conn.execute(
                "SELECT id, source_type FROM topic_tutorials WHERE id = ? AND topic_id = ? AND user_id = ?",
                (target_replace_id, topic_id, uid),
            ).fetchone()
            if existing and existing["source_type"] == "user_custom":
                tut_id = existing["id"]
                conn.execute(
                    """
                    UPDATE topic_tutorials
                    SET title = ?, channel_name = ?, video_id = ?, video_url = ?, thumbnail_url = ?,
                        duration_label = ?, source_type = 'user_custom', is_primary = ?, notes = ?, updated_at = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (
                        clean_title,
                        clean_channel,
                        vid,
                        watch_url,
                        thumb,
                        clean_duration,
                        1 if req.is_primary else 0,
                        (req.notes or "").strip(),
                        now,
                        tut_id,
                        uid,
                    ),
                )
            else:
                target_replace_id = None

        if not target_replace_id:
            tut_id = new_id("tut")
            conn.execute(
                """
                INSERT INTO topic_tutorials (
                    id, topic_id, roadmap_id, user_id, title, channel_name, video_id,
                    video_url, thumbnail_url, duration_label, source_type, is_primary, notes,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'user_custom', ?, ?, ?, ?)
                """,
                (
                    tut_id,
                    topic_id,
                    topic["roadmap_id"],
                    uid,
                    clean_title,
                    clean_channel,
                    vid,
                    watch_url,
                    thumb,
                    clean_duration,
                    1 if req.is_primary else 0,
                    (req.notes or "").strip(),
                    now,
                    now,
                ),
            )

        raw_tutorials = conn.execute(
            "SELECT * FROM topic_tutorials WHERE topic_id = ? AND user_id = ? ORDER BY is_primary DESC, created_at DESC",
            (topic_id, uid),
        ).fetchall()
    return {"tutorials": [_format_tutorial_row(t) for t in raw_tutorials], "saved_tutorial_id": tut_id}


@app.delete("/api/tutorials/{tutorial_id}")
def delete_tutorial(
    tutorial_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Deleting a customized tutorial automatically restores the ORIGINAL AI tutorial as primary."""
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        row = conn.execute("SELECT * FROM topic_tutorials WHERE id = ? AND user_id = ?", (tutorial_id, uid)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Tutorial not found.")
        topic_id = row["topic_id"]
        conn.execute("DELETE FROM topic_tutorials WHERE id = ? AND user_id = ?", (tutorial_id, uid))
        # Ensure at least one remaining tutorial (e.g. the original AI tutorial) is marked primary
        rem_check = conn.execute(
            "SELECT id, is_primary FROM topic_tutorials WHERE topic_id = ? AND user_id = ? ORDER BY is_primary DESC, created_at ASC",
            (topic_id, uid),
        ).fetchall()
        if rem_check and not any(r["is_primary"] for r in rem_check):
            conn.execute("UPDATE topic_tutorials SET is_primary = 1 WHERE id = ? AND user_id = ?", (rem_check[0]["id"], uid))
        remaining = conn.execute(
            "SELECT * FROM topic_tutorials WHERE topic_id = ? AND user_id = ? ORDER BY is_primary DESC, created_at DESC",
            (topic_id, uid),
        ).fetchall()
    return {"ok": True, "deleted_tutorial_id": tutorial_id, "topic_id": topic_id, "tutorials": [_format_tutorial_row(t) for t in remaining]}


@app.delete("/api/topics/{topic_id}/custom-tutorial")
def remove_topic_custom_tutorial(
    topic_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Removes the CUSTOMIZED tutorial for a topic and restores the ORIGINAL AI-recommended tutorial."""
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        conn.execute(
            "DELETE FROM topic_tutorials WHERE topic_id = ? AND user_id = ? AND source_type = 'user_custom'",
            (topic_id, uid),
        )
        conn.execute(
            "UPDATE topic_tutorials SET is_primary = 1 WHERE topic_id = ? AND user_id = ? AND source_type = 'ai_recommended'",
            (topic_id, uid),
        )
        remaining = conn.execute(
            "SELECT * FROM topic_tutorials WHERE topic_id = ? AND user_id = ? ORDER BY is_primary DESC, created_at DESC",
            (topic_id, uid),
        ).fetchall()
    return {"ok": True, "topic_id": topic_id, "tutorials": [_format_tutorial_row(t) for t in remaining]}


# --- SECTION B: READING MATERIAL, CUSTOMIZED READING & PERSONAL NOTES ---
@app.put("/api/topics/{topic_id}/reading")
def update_topic_reading(
    topic_id: str,
    req: ReadingUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        row = conn.execute("SELECT * FROM topic_readings WHERE topic_id = ? AND user_id = ?", (topic_id, uid)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Reading material not found.")

        title = req.title.strip() if req.title else row["title"]
        overview = req.overview if req.overview is not None else row["overview"]
        sections_json = json.dumps(req.sections) if req.sections is not None else row["sections_json"]
        md = req.markdown_content if req.markdown_content is not None else row["markdown_content"]
        summary = req.summary if req.summary is not None else row["summary"]

        conn.execute(
            """
            UPDATE topic_readings
            SET title = ?, overview = ?, sections_json = ?, markdown_content = ?, summary = ?,
                is_user_edited = 1, version = version + 1, updated_at = ?
            WHERE topic_id = ? AND user_id = ?
            """,
            (title, overview, sections_json, md, summary, utc_now(), topic_id, uid),
        )
        updated = conn.execute("SELECT * FROM topic_readings WHERE topic_id = ? AND user_id = ?", (topic_id, uid)).fetchone()

    return {"reading": _format_reading_row(updated)}


@app.put("/api/topics/{topic_id}/custom-reading")
def save_topic_custom_reading(
    topic_id: str,
    req: CustomReadingUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Saves a CUSTOMIZED reading material for a roadmap topic while preserving the ORIGINAL
    AI-generated reading columns so deleting the custom reading restores the original.
    """
    uid = current_user["id"]
    # Ensure topic workspace reading exists first so original columns are populated
    get_topic_workspace(topic_id, auto_prepare=True, current_user=current_user)
    now = utc_now()
    with get_db(commit=True) as conn:
        row = conn.execute("SELECT * FROM topic_readings WHERE topic_id = ? AND user_id = ?", (topic_id, uid)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Topic reading record not found.")
        conn.execute(
            """
            UPDATE topic_readings
            SET has_custom_reading = 1, custom_title = ?, custom_markdown = ?, custom_updated_at = ?, updated_at = ?
            WHERE topic_id = ? AND user_id = ?
            """,
            (req.title.strip(), req.markdown_content.strip(), now, now, topic_id, uid),
        )
        updated = conn.execute("SELECT * FROM topic_readings WHERE topic_id = ? AND user_id = ?", (topic_id, uid)).fetchone()
    return {"reading": _format_reading_row(updated)}


@app.delete("/api/topics/{topic_id}/custom-reading")
def delete_topic_custom_reading(
    topic_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Deletes the CUSTOMIZED reading material and immediately restores the ORIGINAL AI reading material."""
    uid = current_user["id"]
    now = utc_now()
    with get_db(commit=True) as conn:
        row = conn.execute("SELECT * FROM topic_readings WHERE topic_id = ? AND user_id = ?", (topic_id, uid)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Reading material not found.")
        conn.execute(
            """
            UPDATE topic_readings
            SET has_custom_reading = 0, custom_title = '', custom_markdown = '', custom_updated_at = '', updated_at = ?
            WHERE topic_id = ? AND user_id = ?
            """,
            (now, topic_id, uid),
        )
        updated = conn.execute("SELECT * FROM topic_readings WHERE topic_id = ? AND user_id = ?", (topic_id, uid)).fetchone()
    return {"ok": True, "reading": _format_reading_row(updated)}


@app.post("/api/topics/{topic_id}/reading/regenerate")
def regenerate_topic_reading(
    topic_id: str,
    req: RegenerateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Preserves personal edits unless confirm_overwrite=True is passed."""
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        topic = conn.execute("SELECT * FROM roadmap_topics WHERE id = ? AND user_id = ?", (topic_id, uid)).fetchone()
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found.")
        existing = conn.execute("SELECT * FROM topic_readings WHERE topic_id = ? AND user_id = ?", (topic_id, uid)).fetchone()
        if existing and existing.get("is_user_edited") and not req.confirm_overwrite:
            raise HTTPException(
                status_code=409,
                detail="You have saved personal edits to this reading material. Please confirm overwrite to regenerate.",
            )
        jobs = enqueue_topic_resource_jobs(
            conn,
            uid,
            topic["roadmap_id"],
            topic["phase_id"],
            topic_id,
            resource_types=["reading"],
            force_regenerate=True,
        )
        job_id = jobs[0]["id"]

    execute_job_sync(job_id, force_overwrite=True)
    return get_topic_workspace(topic_id, auto_prepare=False, current_user=current_user)


@app.get("/api/notes")
def list_notes(
    topic_id: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db() as conn:
        if topic_id:
            rows = conn.execute(
                "SELECT * FROM personal_notes WHERE user_id = ? AND topic_id = ? ORDER BY is_pinned DESC, updated_at DESC",
                (uid, topic_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM personal_notes WHERE user_id = ? ORDER BY is_pinned DESC, updated_at DESC",
                (uid,),
            ).fetchall()
    notes = [
        {
            **r,
            "tags": json.loads(r.get("tags_json") or "[]"),
            "is_pinned": bool(r.get("is_pinned", 0)),
        }
        for r in rows
    ]
    if search and search.strip():
        q = search.strip().lower()
        notes = [n for n in notes if q in n["title"].lower() or q in n["content"].lower()]
    return {"notes": notes}


@app.post("/api/notes")
def create_note(
    req: NoteCreateOrUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    note_id = new_id("note")
    now = utc_now()
    with get_db(commit=True) as conn:
        roadmap_id = req.roadmap_id
        if req.topic_id:
            t = conn.execute(
                "SELECT id, roadmap_id FROM roadmap_topics WHERE id = ? AND user_id = ?",
                (req.topic_id, uid),
            ).fetchone()
            if not t:
                raise HTTPException(status_code=404, detail="Topic not found or access denied.")
            if roadmap_id and roadmap_id != t["roadmap_id"]:
                raise HTTPException(status_code=404, detail="Roadmap not found or access denied.")
            roadmap_id = t["roadmap_id"]
        elif roadmap_id:
            rm = conn.execute(
                "SELECT id FROM roadmaps WHERE id = ? AND user_id = ?",
                (roadmap_id, uid),
            ).fetchone()
            if not rm:
                raise HTTPException(status_code=404, detail="Roadmap not found or access denied.")

        conn.execute(
            """
            INSERT INTO personal_notes (id, topic_id, roadmap_id, user_id, title, content, tags_json, is_pinned, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                note_id,
                req.topic_id,
                roadmap_id,
                uid,
                req.title.strip(),
                req.content,
                json.dumps(req.tags or []),
                1 if req.is_pinned else 0,
                now,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM personal_notes WHERE id = ? AND user_id = ?", (note_id, uid)).fetchone()
        log_activity(conn, uid, "create_note", "note", note_id, f"Saved note: {req.title.strip()}", 4)
    return {
        "note": {
            **row,
            "tags": json.loads(row.get("tags_json") or "[]"),
            "is_pinned": bool(row.get("is_pinned", 0)),
        }
    }


@app.put("/api/notes/{note_id}")
def update_note(
    note_id: str,
    req: NoteCreateOrUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        existing = conn.execute("SELECT * FROM personal_notes WHERE id = ? AND user_id = ?", (note_id, uid)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Note not found.")
        conn.execute(
            """
            UPDATE personal_notes
            SET title = ?, content = ?, tags_json = ?, is_pinned = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                req.title.strip(),
                req.content,
                json.dumps(req.tags if req.tags is not None else json.loads(existing.get("tags_json") or "[]")),
                1 if req.is_pinned else 0,
                utc_now(),
                note_id,
                uid,
            ),
        )
        row = conn.execute("SELECT * FROM personal_notes WHERE id = ? AND user_id = ?", (note_id, uid)).fetchone()
    return {
        "note": {
            **row,
            "tags": json.loads(row.get("tags_json") or "[]"),
            "is_pinned": bool(row.get("is_pinned", 0)),
        }
    }


@app.delete("/api/notes/{note_id}")
def delete_note(
    note_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Deleting a note must NEVER delete the generated reading material or topic."""
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        existing = conn.execute("SELECT id, topic_id FROM personal_notes WHERE id = ? AND user_id = ?", (note_id, uid)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Note not found.")
        conn.execute("DELETE FROM personal_notes WHERE id = ? AND user_id = ?", (note_id, uid))
    return {"ok": True, "deleted_note_id": note_id, "topic_id": existing["topic_id"]}


# ============================================================================
# PERSONAL DIARY (SEPARATE FROM STUDY JOURNAL)
# ============================================================================
def _normalize_diary_pages(pages: Any) -> List[str]:
    if not isinstance(pages, list):
        raise HTTPException(status_code=400, detail="Diary pages must be an ordered list of text pages.")
    if len(pages) == 0:
        return [""]
    if len(pages) > 200:
        raise HTTPException(status_code=400, detail="A diary entry cannot exceed 200 pages.")
    out: List[str] = []
    for p in pages:
        if not isinstance(p, str):
            raise HTTPException(status_code=400, detail="Each diary page must be a text string.")
        out.append(p)
    return out


def _validate_diary_date(entry_date: Optional[str]) -> str:
    from datetime import date
    if not entry_date or not str(entry_date).strip():
        return date.today().isoformat()
    raw = str(entry_date).strip()
    try:
        parsed = date.fromisoformat(raw[:10])
        return parsed.isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry_date format. Expected YYYY-MM-DD.")


def _format_diary_entry(row: Dict[str, Any]) -> Dict[str, Any]:
    try:
        pages = json.loads(row.get("pages_json") or '[""]')
        if not isinstance(pages, list) or len(pages) == 0:
            pages = [""]
        pages = [str(p) for p in pages]
    except Exception:
        pages = [""]
    combined = " ".join(p.strip() for p in pages if p.strip())
    preview = combined[:160] + ("..." if len(combined) > 160 else "")
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "title": row.get("title") or "",
        "entry_date": row["entry_date"],
        "pages": pages,
        "page_count": len(pages),
        "preview": preview,
        "is_draft": bool(row.get("is_draft", 0)),
        "client_draft_key": row.get("client_draft_key") or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@app.get("/api/diary")
def list_diary_entries(
    include_drafts: bool = Query(default=True),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db() as conn:
        if include_drafts:
            rows = conn.execute(
                "SELECT * FROM diary_entries WHERE user_id = ? ORDER BY entry_date DESC, updated_at DESC",
                (uid,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM diary_entries WHERE user_id = ? AND is_draft = 0 ORDER BY entry_date DESC, updated_at DESC",
                (uid,),
            ).fetchall()
    return {"entries": [_format_diary_entry(r) for r in rows]}


@app.get("/api/diary/draft")
def get_latest_diary_draft(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM diary_entries WHERE user_id = ? AND is_draft = 1 ORDER BY updated_at DESC LIMIT 1",
            (uid,),
        ).fetchone()
    return {"draft": _format_diary_entry(row) if row else None}


@app.get("/api/diary/{entry_id}")
def get_diary_entry(
    entry_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM diary_entries WHERE id = ? AND user_id = ?",
            (entry_id, uid),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Diary entry not found.")
    return {"entry": _format_diary_entry(row)}


@app.post("/api/diary")
def create_diary_entry(
    req: DiaryEntryCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    pages = _normalize_diary_pages(req.pages)
    title = (req.title or "").strip()
    has_content = bool(title) or any(p.strip() for p in pages)
    if not req.is_draft and not has_content:
        raise HTTPException(status_code=400, detail="Please write a title or some diary content before saving.")

    entry_date = _validate_diary_date(req.entry_date)
    draft_key = (req.client_draft_key or "").strip()
    now = utc_now()

    with get_db(commit=True) as conn:
        # Idempotent draft/retry protection: reuse existing row if client_draft_key matches
        if draft_key:
            existing = conn.execute(
                "SELECT * FROM diary_entries WHERE user_id = ? AND client_draft_key = ? LIMIT 1",
                (uid, draft_key),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE diary_entries
                    SET title = ?, pages_json = ?, is_draft = ?, updated_at = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (
                        title,
                        json.dumps(pages),
                        1 if req.is_draft else 0,
                        now,
                        existing["id"],
                        uid,
                    ),
                )
                updated = conn.execute(
                    "SELECT * FROM diary_entries WHERE id = ? AND user_id = ?",
                    (existing["id"], uid),
                ).fetchone()
                return {"entry": _format_diary_entry(updated)}

        entry_id = new_id("diary")
        conn.execute(
            """
            INSERT INTO diary_entries (
                id, user_id, title, entry_date, pages_json, is_draft, client_draft_key, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                uid,
                title,
                entry_date,
                json.dumps(pages),
                1 if req.is_draft else 0,
                draft_key,
                now,
                now,
            ),
        )
        created = conn.execute(
            "SELECT * FROM diary_entries WHERE id = ? AND user_id = ?",
            (entry_id, uid),
        ).fetchone()
    return {"entry": _format_diary_entry(created)}


@app.put("/api/diary/{entry_id}")
def update_diary_entry(
    entry_id: str,
    req: DiaryEntryUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    now = utc_now()
    with get_db(commit=True) as conn:
        existing = conn.execute(
            "SELECT * FROM diary_entries WHERE id = ? AND user_id = ?",
            (entry_id, uid),
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Diary entry not found.")

        title = existing["title"] if req.title is None else req.title.strip()
        if req.pages is not None:
            pages = _normalize_diary_pages(req.pages)
        else:
            pages = _format_diary_entry(existing)["pages"]
        is_draft = bool(existing["is_draft"]) if req.is_draft is None else bool(req.is_draft)

        if not is_draft and not title and not any(p.strip() for p in pages):
            raise HTTPException(status_code=400, detail="Please write a title or some diary content before saving.")

        # Original entry_date is strictly preserved on edits
        conn.execute(
            """
            UPDATE diary_entries
            SET title = ?, pages_json = ?, is_draft = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (title, json.dumps(pages), 1 if is_draft else 0, now, entry_id, uid),
        )
        updated = conn.execute(
            "SELECT * FROM diary_entries WHERE id = ? AND user_id = ?",
            (entry_id, uid),
        ).fetchone()
    return {"entry": _format_diary_entry(updated)}


@app.delete("/api/diary/{entry_id}")
def delete_diary_entry(
    entry_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        existing = conn.execute(
            "SELECT id FROM diary_entries WHERE id = ? AND user_id = ?",
            (entry_id, uid),
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Diary entry not found.")
        conn.execute(
            "DELETE FROM diary_entries WHERE id = ? AND user_id = ?",
            (entry_id, uid),
        )
    return {"ok": True, "deleted_entry_id": entry_id}


# ============================================================================
# STUDY JOURNAL (SEPARATE ACADEMIC RICH-TEXT NOTEBOOK)
# ============================================================================
_VALID_STUDY_FONTS = {"handwriting", "serif", "sans", "soft", "typewriter"}
_VALID_STUDY_GLITTERS = {
    "default",
    "glitter-blue",
    "royal-violet",
    "rose-glitter",
    "golden-sparkle",
    "emerald-glow",
    "aqua-crystal",
    "sunset-copper",
    "pink-diamond",
    "sapphire",
    "champagne-gold",
    "amethyst",
    "mint-crystal",
}
_VALID_BLOCK_TYPES = {"paragraph", "heading", "bulletList", "orderedList", "romanList"}
_VALID_LEARNING_STATUSES = {"understood", "needs_revision"}


def _validate_study_runs(runs: Any) -> List[Dict[str, Any]]:
    if not isinstance(runs, list):
        raise HTTPException(status_code=400, detail="Invalid rich-text runs structure.")
    out: List[Dict[str, Any]] = []
    for r in runs:
        if not isinstance(r, dict) or not isinstance(r.get("text"), str):
            raise HTTPException(status_code=400, detail="Each rich-text run must contain a string 'text' field.")
        font = str(r.get("font") or "handwriting")
        if font not in _VALID_STUDY_FONTS:
            font = "handwriting"
        glitter = str(r.get("glitter") or "default")
        if glitter not in _VALID_STUDY_GLITTERS:
            glitter = "default"
        clean_run: Dict[str, Any] = {
            "text": r["text"],
            "bold": bool(r.get("bold", False)),
            "italic": bool(r.get("italic", False)),
            "underline": bool(r.get("underline", False)),
            "font": font,
            "glitter": glitter,
        }
        if isinstance(r.get("color"), str) and r["color"].strip():
            clean_run["color"] = r["color"].strip()[:40]
        out.append(clean_run)
    return out


def _validate_study_pages(pages: Any) -> List[Dict[str, Any]]:
    if not isinstance(pages, list):
        raise HTTPException(status_code=400, detail="Study journal pages must be an ordered list of structured documents.")
    if len(pages) == 0:
        return [{"type": "doc", "blocks": [{"type": "paragraph", "runs": []}]}]
    if len(pages) > 200:
        raise HTTPException(status_code=400, detail="A study journal entry cannot exceed 200 pages.")
    clean_pages: List[Dict[str, Any]] = []
    for page in pages:
        if not isinstance(page, dict) or page.get("type") != "doc" or not isinstance(page.get("blocks"), list):
            raise HTTPException(status_code=400, detail="Each study journal page must be a valid 'doc' object with 'blocks'.")
        clean_blocks: List[Dict[str, Any]] = []
        for blk in page["blocks"]:
            if not isinstance(blk, dict):
                raise HTTPException(status_code=400, detail="Malformed block in study journal document.")
            btype = blk.get("type")
            if btype not in _VALID_BLOCK_TYPES:
                raise HTTPException(status_code=400, detail=f"Unsupported block type: {btype}")
            if btype in ("paragraph", "heading"):
                clean_blk: Dict[str, Any] = {
                    "type": btype,
                    "runs": _validate_study_runs(blk.get("runs", [])),
                }
                if btype == "heading":
                    lvl = blk.get("level", 1)
                    clean_blk["level"] = lvl if lvl in (1, 2, 3) else 1
                clean_blocks.append(clean_blk)
            else:
                raw_items = blk.get("items")
                if not isinstance(raw_items, list):
                    raise HTTPException(status_code=400, detail="List block must contain 'items'.")
                clean_items = [_validate_study_runs(it) for it in raw_items]
                clean_blocks.append({"type": btype, "items": clean_items})
        if not clean_blocks:
            clean_blocks = [{"type": "paragraph", "runs": []}]
        clean_pages.append({"type": "doc", "blocks": clean_blocks})
    return clean_pages


def _extract_study_full_text(pages: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for page in pages:
        for blk in page.get("blocks", []):
            if blk.get("type") in ("paragraph", "heading"):
                txt = "".join(r.get("text", "") for r in blk.get("runs", []))
                if txt.strip():
                    parts.append(txt.strip())
            else:
                for item in blk.get("items", []):
                    txt = "".join(r.get("text", "") for r in item)
                    if txt.strip():
                        parts.append(txt.strip())
    return " ".join(parts)


def _extract_study_preview(pages: List[Dict[str, Any]]) -> str:
    joined = _extract_study_full_text(pages)
    return joined[:180] + ("..." if len(joined) > 180 else "")


def _validate_study_duration(duration: Any) -> int:
    if not isinstance(duration, int) or isinstance(duration, bool):
        raise HTTPException(status_code=400, detail="Study duration must be an integer number of minutes.")
    if duration < 0 or duration > 1440:
        raise HTTPException(status_code=400, detail="Study duration must be between 0 and 1440 minutes.")
    return duration


def _validate_learning_status(status: Optional[str]) -> str:
    val = (status or "understood").strip().lower()
    if val not in _VALID_LEARNING_STATUSES:
        raise HTTPException(status_code=400, detail="Learning status must be 'understood' or 'needs_revision'.")
    return val


def _format_study_journal_entry(row: Dict[str, Any]) -> Dict[str, Any]:
    try:
        pages = json.loads(row.get("pages_json") or "[]")
        if not isinstance(pages, list) or len(pages) == 0:
            pages = [{"type": "doc", "blocks": [{"type": "paragraph", "runs": []}]}]
    except Exception:
        pages = [{"type": "doc", "blocks": [{"type": "paragraph", "runs": []}]}]
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "title": row.get("title") or "",
        "subject": row.get("subject") or "",
        "topic": row.get("topic") or "",
        "chapter_or_module": row.get("chapter_or_module") or "",
        "study_date": row["study_date"],
        "duration_minutes": int(row.get("duration_minutes") or 0),
        "learning_status": row.get("learning_status") or "understood",
        "key_concepts": row.get("key_concepts") or "",
        "learning_outcomes": row.get("learning_outcomes") or "",
        "revision_notes": row.get("revision_notes") or "",
        "pages": pages,
        "page_count": len(pages),
        "preview": _extract_study_preview(pages),
        "is_draft": bool(row.get("is_draft", 0)),
        "client_draft_key": row.get("client_draft_key") or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@app.get("/api/study-journal")
def list_study_journal_entries(
    search: Optional[str] = Query(default=None),
    subject: Optional[str] = Query(default=None),
    study_date: Optional[str] = Query(default=None),
    learning_status: Optional[str] = Query(default=None),
    sort: str = Query(default="newest"),
    include_drafts: bool = Query(default=True),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    order_dir = "ASC" if sort == "oldest" else "DESC"
    with get_db() as conn:
        sql = "SELECT * FROM study_journal_entries WHERE user_id = ?"
        params: List[Any] = [uid]
        if not include_drafts:
            sql += " AND is_draft = 0"
        if subject and subject.strip():
            sql += " AND LOWER(subject) = LOWER(?)"
            params.append(subject.strip())
        if study_date and study_date.strip():
            sql += " AND study_date = ?"
            params.append(study_date.strip()[:10])
        if learning_status and learning_status.strip():
            sql += " AND learning_status = ?"
            params.append(_validate_learning_status(learning_status))
        sql += f" ORDER BY study_date {order_dir}, updated_at {order_dir}"
        rows = conn.execute(sql, tuple(params)).fetchall()

    entries = [_format_study_journal_entry(r) for r in rows]
    if search and search.strip():
        q = search.strip().lower()
        entries = [
            e
            for e in entries
            if q in e["title"].lower()
            or q in e["subject"].lower()
            or q in e["topic"].lower()
            or q in e["chapter_or_module"].lower()
            or q in e["key_concepts"].lower()
            or q in e["learning_outcomes"].lower()
            or q in e["revision_notes"].lower()
            or q in _extract_study_full_text(e["pages"]).lower()
        ]
    return {"entries": entries}


@app.get("/api/study-journal/draft")
def get_latest_study_journal_draft(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM study_journal_entries WHERE user_id = ? AND is_draft = 1 ORDER BY updated_at DESC LIMIT 1",
            (uid,),
        ).fetchone()
    return {"draft": _format_study_journal_entry(row) if row else None}


@app.get("/api/study-journal/{entry_id}")
def get_study_journal_entry(
    entry_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM study_journal_entries WHERE id = ? AND user_id = ?",
            (entry_id, uid),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Study journal entry not found.")
    return {"entry": _format_study_journal_entry(row)}


@app.post("/api/study-journal")
def create_study_journal_entry(
    req: StudyJournalCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    pages = _validate_study_pages(req.pages)
    title = (req.title or "").strip()
    subject = (req.subject or "").strip()
    topic = (req.topic or "").strip()
    duration = _validate_study_duration(req.duration_minutes)
    status = _validate_learning_status(req.learning_status)
    study_date = _validate_diary_date(req.study_date)

    if not req.is_draft and (not subject or not topic):
        raise HTTPException(status_code=400, detail="Subject name and topic studied are required to save a study journal entry.")

    draft_key = (req.client_draft_key or "").strip()
    now = utc_now()

    with get_db(commit=True) as conn:
        if draft_key:
            existing = conn.execute(
                "SELECT * FROM study_journal_entries WHERE user_id = ? AND client_draft_key = ? LIMIT 1",
                (uid, draft_key),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE study_journal_entries
                    SET title = ?, subject = ?, topic = ?, chapter_or_module = ?, study_date = ?,
                        duration_minutes = ?, learning_status = ?, key_concepts = ?,
                        learning_outcomes = ?, revision_notes = ?, pages_json = ?,
                        is_draft = ?, updated_at = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (
                        title,
                        subject,
                        topic,
                        (req.chapter_or_module or "").strip(),
                        study_date,
                        duration,
                        status,
                        (req.key_concepts or "").strip(),
                        (req.learning_outcomes or "").strip(),
                        (req.revision_notes or "").strip(),
                        json.dumps(pages),
                        1 if req.is_draft else 0,
                        now,
                        existing["id"],
                        uid,
                    ),
                )
                updated = conn.execute(
                    "SELECT * FROM study_journal_entries WHERE id = ? AND user_id = ?",
                    (existing["id"], uid),
                ).fetchone()
                return {"entry": _format_study_journal_entry(updated)}

        entry_id = new_id("sjournal")
        conn.execute(
            """
            INSERT INTO study_journal_entries (
                id, user_id, title, subject, topic, chapter_or_module, study_date,
                duration_minutes, learning_status, key_concepts, learning_outcomes,
                revision_notes, pages_json, is_draft, client_draft_key, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                uid,
                title,
                subject,
                topic,
                (req.chapter_or_module or "").strip(),
                study_date,
                duration,
                status,
                (req.key_concepts or "").strip(),
                (req.learning_outcomes or "").strip(),
                (req.revision_notes or "").strip(),
                json.dumps(pages),
                1 if req.is_draft else 0,
                draft_key,
                now,
                now,
            ),
        )
        created = conn.execute(
            "SELECT * FROM study_journal_entries WHERE id = ? AND user_id = ?",
            (entry_id, uid),
        ).fetchone()
    return {"entry": _format_study_journal_entry(created)}


@app.put("/api/study-journal/{entry_id}")
def update_study_journal_entry(
    entry_id: str,
    req: StudyJournalUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    now = utc_now()
    with get_db(commit=True) as conn:
        existing = conn.execute(
            "SELECT * FROM study_journal_entries WHERE id = ? AND user_id = ?",
            (entry_id, uid),
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Study journal entry not found.")

        title = existing["title"] if req.title is None else req.title.strip()
        subject = existing["subject"] if req.subject is None else req.subject.strip()
        topic = existing["topic"] if req.topic is None else req.topic.strip()
        chapter = existing["chapter_or_module"] if req.chapter_or_module is None else req.chapter_or_module.strip()
        study_date = existing["study_date"] if req.study_date is None else _validate_diary_date(req.study_date)
        duration = existing["duration_minutes"] if req.duration_minutes is None else _validate_study_duration(req.duration_minutes)
        status = existing["learning_status"] if req.learning_status is None else _validate_learning_status(req.learning_status)
        key_concepts = existing["key_concepts"] if req.key_concepts is None else req.key_concepts.strip()
        outcomes = existing["learning_outcomes"] if req.learning_outcomes is None else req.learning_outcomes.strip()
        rev_notes = existing["revision_notes"] if req.revision_notes is None else req.revision_notes.strip()
        pages = _format_study_journal_entry(existing)["pages"] if req.pages is None else _validate_study_pages(req.pages)
        is_draft = bool(existing["is_draft"]) if req.is_draft is None else bool(req.is_draft)

        if not is_draft and (not subject or not topic):
            raise HTTPException(status_code=400, detail="Subject name and topic studied are required to save a study journal entry.")

        conn.execute(
            """
            UPDATE study_journal_entries
            SET title = ?, subject = ?, topic = ?, chapter_or_module = ?, study_date = ?,
                duration_minutes = ?, learning_status = ?, key_concepts = ?,
                learning_outcomes = ?, revision_notes = ?, pages_json = ?,
                is_draft = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                title,
                subject,
                topic,
                chapter,
                study_date,
                duration,
                status,
                key_concepts,
                outcomes,
                rev_notes,
                json.dumps(pages),
                1 if is_draft else 0,
                now,
                entry_id,
                uid,
            ),
        )
        updated = conn.execute(
            "SELECT * FROM study_journal_entries WHERE id = ? AND user_id = ?",
            (entry_id, uid),
        ).fetchone()
    return {"entry": _format_study_journal_entry(updated)}


@app.delete("/api/study-journal/{entry_id}")
def delete_study_journal_entry(
    entry_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        existing = conn.execute(
            "SELECT id FROM study_journal_entries WHERE id = ? AND user_id = ?",
            (entry_id, uid),
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Study journal entry not found.")
        conn.execute(
            "DELETE FROM study_journal_entries WHERE id = ? AND user_id = ?",
            (entry_id, uid),
        )
    return {"ok": True, "deleted_entry_id": entry_id}


# --- SECTION C: 20-MCQ EXAMINATION ENGINE & ATTEMPT HISTORY ---
def _grade_and_record_quiz_submission(
    conn,
    user_id: str,
    questions: List[Dict[str, Any]],
    submitted_answers: Dict[str, int],
    duration_seconds: int,
    topic_title: str,
    mcq_set_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    roadmap_id: Optional[str] = None,
    phase_id: Optional[str] = None,
    studio_output_id: str = "",
) -> Dict[str, Any]:
    max_score = len(questions)
    correct_count = 0
    incorrect_count = 0
    unanswered_count = 0
    review_items = []

    for idx, q in enumerate(questions):
        qid = str(q.get("id") or f"q_{idx+1}")
        num_str = str(q.get("number") or (idx + 1))
        user_choice = submitted_answers.get(qid)
        if user_choice is None and num_str in submitted_answers:
            user_choice = submitted_answers.get(num_str)

        correct_idx = int(q["correct_index"])
        if user_choice is None or user_choice < 0 or user_choice > 3:
            unanswered_count += 1
            status_label = "unanswered"
        elif int(user_choice) == correct_idx:
            correct_count += 1
            status_label = "correct"
        else:
            incorrect_count += 1
            status_label = "incorrect"

        review_items.append(
            {
                "id": qid,
                "question_id": qid,
                "number": q.get("number", idx + 1),
                "category": q.get("category", "Core"),
                "difficulty": q.get("difficulty", "Intermediate"),
                "question": q["question"],
                "options": q["options"],
                "selected_index": user_choice if (user_choice is not None and 0 <= int(user_choice) <= 3) else None,
                "correct_index": correct_idx,
                "is_correct": status_label == "correct",
                "status": status_label,
                "explanation": q.get("explanation", ""),
            }
        )

    score = correct_count
    percentage = round((score / max(1, max_score)) * 100.0, 1)
    passed = 1 if percentage >= 70.0 else 0
    attempt_id = new_id("att")
    now = utc_now()

    conn.execute(
        """
        INSERT INTO quiz_attempts (
            id, user_id, mcq_set_id, topic_id, roadmap_id, phase_id, studio_output_id,
            topic_title, score, max_score, percentage, correct_count, incorrect_count,
            unanswered_count, passed, duration_seconds, answers_json, questions_snapshot_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            attempt_id,
            user_id,
            mcq_set_id,
            topic_id,
            roadmap_id,
            phase_id,
            studio_output_id,
            topic_title,
            score,
            max_score,
            percentage,
            correct_count,
            incorrect_count,
            unanswered_count,
            passed,
            max(1, int(duration_seconds or 0)),
            json.dumps(submitted_answers),
            json.dumps(review_items),
            now,
        ),
    )

    if topic_id:
        # Update topic time_spent and auto-mark topic in_progress or completed if passed
        minutes_added = max(1, int(round((duration_seconds or 180) / 60.0)))
        if passed:
            conn.execute(
                """
                UPDATE roadmap_topics
                SET status = 'completed', completed_at = COALESCE(NULLIF(completed_at, ''), ?),
                    time_spent_minutes = time_spent_minutes + ?, updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (now, minutes_added, now, topic_id, user_id),
            )
        else:
            conn.execute(
                """
                UPDATE roadmap_topics
                SET status = CASE WHEN status = 'not_started' THEN 'in_progress' ELSE status END,
                    time_spent_minutes = time_spent_minutes + ?, updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (minutes_added, now, topic_id, user_id),
            )

    log_activity(
        conn,
        user_id,
        "complete_quiz",
        "quiz_attempt",
        attempt_id,
        f"Scored {score}/{max_score} ({percentage}%) on {topic_title}",
        max(2, int(round((duration_seconds or 180) / 60.0))),
        {"score": score, "max_score": max_score, "percentage": percentage, "passed": bool(passed)},
    )

    return {
        "id": attempt_id,
        "user_id": user_id,
        "mcq_set_id": mcq_set_id,
        "topic_id": topic_id,
        "roadmap_id": roadmap_id,
        "phase_id": phase_id,
        "studio_output_id": studio_output_id,
        "topic_title": topic_title,
        "score": score,
        "max_score": max_score,
        "percentage": percentage,
        "correct_count": correct_count,
        "incorrect_count": incorrect_count,
        "unanswered_count": unanswered_count,
        "passed": bool(passed),
        "duration_seconds": max(1, int(duration_seconds or 0)),
        "review_items": review_items,
        "question_results": review_items,
        "created_at": now,
    }


@app.post("/api/topics/{topic_id}/quiz/submit")
def submit_topic_quiz(
    topic_id: str,
    req: QuizSubmissionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        topic = conn.execute("SELECT * FROM roadmap_topics WHERE id = ? AND user_id = ?", (topic_id, uid)).fetchone()
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found or access denied.")
        mcq = conn.execute("SELECT * FROM mcq_sets WHERE topic_id = ? AND user_id = ?", (topic_id, uid)).fetchone()
        if not mcq:
            raise HTTPException(status_code=404, detail="Quiz set not found for this topic.")

        questions = json.loads(mcq.get("questions_json") or "[]")
        attempt = _grade_and_record_quiz_submission(
            conn=conn,
            user_id=uid,
            questions=questions,
            submitted_answers=req.answers,
            duration_seconds=req.duration_seconds,
            topic_title=topic["title"],
            mcq_set_id=mcq["id"],
            topic_id=topic_id,
            roadmap_id=topic["roadmap_id"],
            phase_id=topic["phase_id"],
        )
    return {"attempt": attempt}


@app.post("/api/topics/{topic_id}/quiz/regenerate")
def regenerate_topic_quiz(
    topic_id: str,
    req: Optional[RegenerateRequest] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        topic = conn.execute("SELECT * FROM roadmap_topics WHERE id = ? AND user_id = ?", (topic_id, uid)).fetchone()
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found or access denied.")
        jobs = enqueue_topic_resource_jobs(
            conn,
            uid,
            topic["roadmap_id"],
            topic["phase_id"],
            topic_id,
            resource_types=["quiz"],
            force_regenerate=True,
        )
        job_id = jobs[0]["id"]

    execute_job_sync(job_id, force_overwrite=True)
    return get_topic_workspace(topic_id, auto_prepare=False, current_user=current_user)


@app.get("/api/quizzes/attempts")
def list_quiz_attempts(
    topic_id: Optional[str] = Query(default=None),
    roadmap_id: Optional[str] = Query(default=None),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db() as conn:
        if topic_id:
            rows = conn.execute(
                "SELECT * FROM quiz_attempts WHERE user_id = ? AND topic_id = ? ORDER BY created_at DESC",
                (uid, topic_id),
            ).fetchall()
        elif roadmap_id:
            rows = conn.execute(
                "SELECT * FROM quiz_attempts WHERE user_id = ? AND roadmap_id = ? ORDER BY created_at DESC",
                (uid, roadmap_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM quiz_attempts WHERE user_id = ? ORDER BY created_at DESC",
                (uid,),
            ).fetchall()

    attempts = [
        {
            "id": r["id"],
            "topic_id": r["topic_id"],
            "roadmap_id": r["roadmap_id"],
            "phase_id": r["phase_id"],
            "studio_output_id": r.get("studio_output_id", ""),
            "topic_title": r["topic_title"],
            "score": r["score"],
            "max_score": r["max_score"],
            "percentage": r["percentage"],
            "correct_count": r["correct_count"],
            "incorrect_count": r["incorrect_count"],
            "unanswered_count": r["unanswered_count"],
            "passed": bool(r["passed"]),
            "duration_seconds": r["duration_seconds"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
    return {"attempts": attempts}


@app.get("/api/quizzes/attempts/{attempt_id}")
def get_quiz_attempt_detail(
    attempt_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db() as conn:
        row = conn.execute("SELECT * FROM quiz_attempts WHERE id = ? AND user_id = ?", (attempt_id, uid)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Quiz attempt not found or access denied.")

    return {
        "attempt": {
            "id": row["id"],
            "topic_id": row["topic_id"],
            "roadmap_id": row["roadmap_id"],
            "phase_id": row["phase_id"],
            "studio_output_id": row.get("studio_output_id", ""),
            "topic_title": row["topic_title"],
            "score": row["score"],
            "max_score": row["max_score"],
            "percentage": row["percentage"],
            "correct_count": row["correct_count"],
            "incorrect_count": row["incorrect_count"],
            "unanswered_count": row["unanswered_count"],
            "passed": bool(row["passed"]),
            "duration_seconds": row["duration_seconds"],
            "review_items": json.loads(row.get("questions_snapshot_json") or "[]"),
            "created_at": row["created_at"],
        }
    }


@app.delete("/api/quizzes/attempts/{attempt_id}")
def delete_quiz_attempt(
    attempt_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Deleting one attempt must NEVER delete other attempts, the topic, or the roadmap."""
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        row = conn.execute("SELECT id, topic_id FROM quiz_attempts WHERE id = ? AND user_id = ?", (attempt_id, uid)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Quiz attempt not found.")
        conn.execute("DELETE FROM quiz_attempts WHERE id = ? AND user_id = ?", (attempt_id, uid))
    return {"ok": True, "deleted_attempt_id": attempt_id, "topic_id": row["topic_id"]}


# ============================================================================
# BACKGROUND GENERATION JOBS API (PART 13)
# ============================================================================
@app.get("/api/jobs")
def list_generation_jobs(
    roadmap_id: Optional[str] = Query(default=None),
    topic_id: Optional[str] = Query(default=None),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db() as conn:
        if topic_id:
            jobs = conn.execute(
                "SELECT * FROM generation_jobs WHERE user_id = ? AND topic_id = ? ORDER BY created_at DESC",
                (uid, topic_id),
            ).fetchall()
        elif roadmap_id:
            jobs = conn.execute(
                "SELECT * FROM generation_jobs WHERE user_id = ? AND roadmap_id = ? ORDER BY created_at DESC",
                (uid, roadmap_id),
            ).fetchall()
        else:
            jobs = conn.execute(
                "SELECT * FROM generation_jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT 100",
                (uid,),
            ).fetchall()
    return {"jobs": jobs}


@app.post("/api/jobs/{job_id}/retry")
def retry_generation_job(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        job = conn.execute("SELECT * FROM generation_jobs WHERE id = ? AND user_id = ?", (job_id, uid)).fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="Generation job not found.")
        conn.execute(
            "UPDATE generation_jobs SET status = 'queued', error_message = '', completed_at = '' WHERE id = ? AND user_id = ?",
            (job_id, uid),
        )
    updated_job = execute_job_sync(job_id, force_overwrite=False)
    return {"job": updated_job}


# ============================================================================
# AI STUDIO — ALL NINE TOOLS (PART 6)
# ============================================================================
VALID_STUDIO_TOOLS = {
    "audio_overview",
    "slide_deck",
    "video_overview",
    "mind_map",
    "study_guide",
    "flashcards",
    "quiz",
    "infographic",
    "data_table",
}


def _format_studio_output(conn, row: Dict[str, Any]) -> Dict[str, Any]:
    content = json.loads(row.get("content_json") or "{}")
    config = json.loads(row.get("config_json") or "{}")
    source_ids = json.loads(row.get("source_ids_json") or "[]")
    output_id = row["id"]
    uid = row["user_id"]
    lang = row.get("language") or content.get("language") or config.get("language") or "English"

    if row["tool_type"] == "audio_overview" and content.get("audio", {}).get("audio_url"):
        playback_token = create_audio_playback_token(uid, output_id)
        content["audio"]["audio_url"] = (
            f"/api/studio/audio/{output_id}.wav?playback_token={playback_token}"
        )
        content["audio"]["playback_token_expires_in"] = 60 * 30

    if row["tool_type"] == "video_overview":
        vid_meta = content.get("video") or {}
        vid_token = create_video_playback_token(uid, output_id)
        aud_token = create_audio_playback_token(uid, f"{output_id}_vid")
        vid_meta["video_url"] = f"/api/studio/video/{output_id}.mp4?playback_token={vid_token}"
        vid_meta["audio_url"] = f"/api/studio/audio/{output_id}_vid.wav?playback_token={aud_token}"
        content["video"] = vid_meta

    if row["tool_type"] == "flashcards":
        cards = conn.execute(
            "SELECT * FROM flashcards WHERE studio_output_id = ? AND user_id = ? ORDER BY created_at ASC",
            (output_id, uid),
        ).fetchall()
        content["cards"] = cards

    # IMPORTANT RULE (Security Area D):
    # Never expose correct_index or explanations in pre-submission AI Studio Quiz responses!
    if row["tool_type"] == "quiz":
        raw_questions = content.get("questions") or []
        content["questions"] = [
            {
                "id": q.get("id", f"q_{idx + 1}"),
                "number": q.get("number", idx + 1),
                "category": q.get("category", "Core"),
                "difficulty": q.get("difficulty", content.get("difficulty", "Intermediate")),
                "question": q.get("question", ""),
                "options": q.get("options", []),
            }
            for idx, q in enumerate(raw_questions)
        ]

    # Resolve associated source document titles for AI Studio Library cards
    source_titles: List[Dict[str, str]] = []
    if source_ids:
        placeholders = ",".join("?" for _ in source_ids)
        src_rows = conn.execute(
            f"SELECT id, title, file_type FROM sources WHERE user_id = ? AND id IN ({placeholders})",
            [uid, *source_ids],
        ).fetchall()
        source_titles = [{"id": s["id"], "title": s["title"], "file_type": s["file_type"]} for s in src_rows]

    return {
        "id": output_id,
        "user_id": uid,
        "tool_type": row["tool_type"],
        "title": row["title"],
        "language": lang,
        "duration_label": row.get("duration_label") or content.get("duration_label") or config.get("duration") or "",
        "style_label": row.get("style_label") or content.get("style_label") or config.get("style") or "",
        "source_ids": source_ids,
        "source_titles": source_titles,
        "config": config,
        "content": content,
        "status": row["status"],
        "is_user_edited": bool(row.get("is_user_edited", 0)),
        "error_message": row.get("error_message", ""),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ============================================================================
# DASHBOARD, PROGRESS & ANALYTICS, AND GLOBAL SEARCH (PARTS 5 & 16)
# ============================================================================
@app.get("/api/dashboard")
def get_dashboard_summary(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db() as conn:
        prefs = ensure_user_preferences(conn, uid)
        rm_ids = [r["id"] for r in conn.execute("SELECT id FROM roadmaps WHERE user_id = ? ORDER BY updated_at DESC", (uid,)).fetchall()]
        roadmaps = [_assemble_roadmap_detail(conn, rid, uid) for rid in rm_ids]
        roadmaps = [r for r in roadmaps if r is not None]

        recent_sources = [
            _format_source_row(r, include_text=False)
            for r in conn.execute("SELECT * FROM sources WHERE user_id = ? ORDER BY updated_at DESC LIMIT 5", (uid,)).fetchall()
        ]
        recent_studio = [
            _format_studio_output(conn, r)
            for r in conn.execute("SELECT * FROM studio_outputs WHERE user_id = ? ORDER BY created_at DESC LIMIT 6", (uid,)).fetchall()
        ]
        recent_attempts = conn.execute(
            "SELECT id, topic_id, roadmap_id, topic_title, score, max_score, percentage, passed, duration_seconds, created_at FROM quiz_attempts WHERE user_id = ? ORDER BY created_at DESC LIMIT 6",
            (uid,),
        ).fetchall()

        all_topics = conn.execute(
            """
            SELECT t.*, r.title AS roadmap_title, p.title AS phase_title
            FROM roadmap_topics t
            JOIN roadmaps r ON r.id = t.roadmap_id AND r.user_id = t.user_id
            JOIN roadmap_phases p ON p.id = t.phase_id AND p.user_id = t.user_id
            WHERE t.user_id = ?
            ORDER BY r.updated_at DESC, p.phase_order ASC, t.topic_order ASC
            """,
            (uid,),
        ).fetchall()

        flashcards_all = conn.execute("SELECT status, next_due_at, front, studio_output_id FROM flashcards WHERE user_id = ?", (uid,)).fetchall()
        activities = conn.execute(
            "SELECT * FROM activity_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT 60",
            (uid,),
        ).fetchall()

    # Calculate Continue Learning & Today's Study Tasks from actual user roadmaps
    continue_topic = None
    todays_tasks = []
    for t in all_topics:
        if t["status"] == "in_progress" and not continue_topic:
            continue_topic = t
        if t["status"] != "completed" and len(todays_tasks) < 4:
            todays_tasks.append(
                {
                    "topic_id": t["id"],
                    "roadmap_id": t["roadmap_id"],
                    "title": t["title"],
                    "roadmap_title": t["roadmap_title"],
                    "phase_title": t["phase_title"],
                    "status": t["status"],
                    "estimated_hours": t["estimated_hours"],
                }
            )
    if not continue_topic and todays_tasks:
        continue_topic = todays_tasks[0]

    # Upcoming revision activities (flashcards needing review + topics with quiz score < 70%)
    upcoming_revisions = []
    due_cards = [c for c in flashcards_all if c["status"] in ("new", "learning", "review")]
    if due_cards:
        upcoming_revisions.append(
            {
                "type": "flashcards",
                "title": f"{len(due_cards)} Flashcards Due for Active Recall",
                "subtitle": "Spaced repetition deck review",
                "link": "/studio?tool=flashcards",
            }
        )
    for att in recent_attempts:
        if not att["passed"] and len(upcoming_revisions) < 4:
            upcoming_revisions.append(
                {
                    "type": "quiz_retake",
                    "title": f"Retake 20-MCQ Exam: {att['topic_title']}",
                    "subtitle": f"Previous score: {att['score']}/{att['max_score']} ({att['percentage']}%) — Target: 70%+",
                    "link": f"/roadmaps/{att['roadmap_id']}/topics/{att['topic_id']}" if att["roadmap_id"] and att["topic_id"] else "/quizzes",
                }
            )

    # Weekly activity aggregation (last 7 days based on real recorded activity_logs)
    today_date = datetime.now(timezone.utc).date()
    weekly_days = []
    for offset in range(6, -1, -1):
        d = today_date - timedelta(days=offset)
        d_str = d.isoformat()
        mins = 0
        actions = 0
        for act in activities:
            if act["created_at"][:10] == d_str:
                mins += int(act.get("duration_minutes") or 5)
                actions += 1
        weekly_days.append(
            {
                "date": d_str,
                "day_label": d.strftime("%a"),
                "minutes": mins,
                "actions": actions,
            }
        )

    total_topics_count = len(all_topics)
    completed_topics_count = sum(1 for t in all_topics if t["status"] == "completed")
    overall_progress = int(round((completed_topics_count / total_topics_count) * 100)) if total_topics_count > 0 else 0
    avg_quiz_score = (
        round(sum(a["percentage"] for a in recent_attempts) / len(recent_attempts), 1)
        if recent_attempts
        else 0.0
    )

    # Isolated demonstration preview data ONLY when explicitly enabled by user in preferences
    demo_data = None
    if bool(prefs.get("show_demo_data", 0)):
        demo_data = {
            "is_demo": True,
            "banner": "Demonstration Preview Mode Active — Isolated sample metrics shown for presentation preview.",
            "sample_score": 85.0,
            "sample_weekly_minutes": [35, 50, 25, 65, 45, 80, 60],
        }

    return {
        "metrics": {
            "active_roadmaps": len(roadmaps),
            "total_topics": total_topics_count,
            "completed_topics": completed_topics_count,
            "overall_progress_percent": overall_progress,
            "total_sources": len(recent_sources),
            "studio_outputs_count": len(recent_studio),
            "quiz_attempts_count": len(recent_attempts),
            "average_quiz_percentage": avg_quiz_score,
        },
        "continue_learning": continue_topic,
        "roadmaps": roadmaps[:4],
        "todays_tasks": todays_tasks,
        "upcoming_revisions": upcoming_revisions,
        "recent_sources": recent_sources,
        "recent_studio_outputs": recent_studio,
        "recent_quiz_attempts": recent_attempts,
        "weekly_activity": weekly_days,
        "demo_data": demo_data,
    }


@app.get("/api/analytics")
def get_progress_and_analytics(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db() as conn:
        rm_ids = [r["id"] for r in conn.execute("SELECT id FROM roadmaps WHERE user_id = ? ORDER BY updated_at DESC", (uid,)).fetchall()]
        roadmaps = [_assemble_roadmap_detail(conn, rid, uid) for rid in rm_ids]
        roadmaps = [r for r in roadmaps if r is not None]

        attempts = conn.execute(
            "SELECT * FROM quiz_attempts WHERE user_id = ? ORDER BY created_at ASC",
            (uid,),
        ).fetchall()
        flashcards = conn.execute("SELECT status FROM flashcards WHERE user_id = ?", (uid,)).fetchall()
        topics = conn.execute("SELECT * FROM roadmap_topics WHERE user_id = ?", (uid,)).fetchall()
        activities = conn.execute("SELECT * FROM activity_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT 30", (uid,)).fetchall()

    # Identify weak topics vs strong topics from actual quiz attempts
    topic_scores: Dict[str, List[float]] = {}
    topic_meta: Dict[str, Dict[str, Any]] = {}
    for att in attempts:
        key = att["topic_id"] or att["topic_title"]
        topic_scores.setdefault(key, []).append(float(att["percentage"]))
        topic_meta[key] = {
            "topic_id": att["topic_id"],
            "roadmap_id": att["roadmap_id"],
            "topic_title": att["topic_title"],
            "latest_score": att["score"],
            "max_score": att["max_score"],
            "latest_percentage": att["percentage"],
        }

    weak_topics = []
    strong_topics = []
    for key, scores in topic_scores.items():
        avg_pct = round(sum(scores) / len(scores), 1)
        entry = {**topic_meta[key], "average_percentage": avg_pct, "attempt_count": len(scores)}
        if avg_pct < 70.0:
            weak_topics.append(entry)
        else:
            strong_topics.append(entry)

    weak_topics.sort(key=lambda x: x["average_percentage"])
    strong_topics.sort(key=lambda x: x["average_percentage"], reverse=True)

    fc_breakdown = {
        "new": sum(1 for c in flashcards if c["status"] == "new"),
        "learning": sum(1 for c in flashcards if c["status"] == "learning"),
        "review": sum(1 for c in flashcards if c["status"] == "review"),
        "known": sum(1 for c in flashcards if c["status"] == "known"),
        "total": len(flashcards),
    }

    total_time_minutes = sum(int(t.get("time_spent_minutes") or 0) for t in topics) + sum(
        int(round((a.get("duration_seconds") or 0) / 60.0)) for a in attempts
    )

    return {
        "roadmaps": roadmaps,
        "quiz_trend": [
            {
                "id": a["id"],
                "topic_title": a["topic_title"],
                "score": a["score"],
                "max_score": a["max_score"],
                "percentage": a["percentage"],
                "passed": bool(a["passed"]),
                "created_at": a["created_at"],
            }
            for a in attempts
        ],
        "weak_topics": weak_topics,
        "strong_topics": strong_topics,
        "flashcard_breakdown": fc_breakdown,
        "topic_status_counts": {
            "not_started": sum(1 for t in topics if t["status"] == "not_started"),
            "in_progress": sum(1 for t in topics if t["status"] == "in_progress"),
            "completed": sum(1 for t in topics if t["status"] == "completed"),
            "total": len(topics),
        },
        "total_time_spent_minutes": total_time_minutes,
        "recent_activities": activities,
    }


@app.get("/api/resources")
def get_all_learning_resources(
    search: Optional[str] = Query(default=None),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db() as conn:
        notes = conn.execute(
            """
            SELECT n.*, t.title AS topic_title, r.title AS roadmap_title
            FROM personal_notes n
            LEFT JOIN roadmap_topics t ON t.id = n.topic_id AND t.user_id = n.user_id
            LEFT JOIN roadmaps r ON r.id = n.roadmap_id AND r.user_id = n.user_id
            WHERE n.user_id = ?
            ORDER BY n.is_pinned DESC, n.updated_at DESC
            """,
            (uid,),
        ).fetchall()
        raw_tutorials = conn.execute(
            """
            SELECT tut.*, t.title AS topic_title, r.title AS roadmap_title
            FROM topic_tutorials tut
            JOIN roadmap_topics t ON t.id = tut.topic_id AND t.user_id = tut.user_id
            JOIN roadmaps r ON r.id = tut.roadmap_id AND r.user_id = tut.user_id
            WHERE tut.user_id = ?
            ORDER BY tut.updated_at DESC
            """,
            (uid,),
        ).fetchall()
        raw_readings = conn.execute(
            """
            SELECT rd.id, rd.topic_id, rd.roadmap_id, rd.title, rd.overview, rd.is_user_edited,
                   rd.has_custom_reading, rd.custom_title, rd.version, rd.updated_at,
                   t.title AS topic_title, r.title AS roadmap_title
            FROM topic_readings rd
            JOIN roadmap_topics t ON t.id = rd.topic_id AND t.user_id = rd.user_id
            JOIN roadmaps r ON r.id = rd.roadmap_id AND r.user_id = rd.user_id
            WHERE rd.user_id = ?
            ORDER BY rd.updated_at DESC
            """,
            (uid,),
        ).fetchall()
        studio_items = [
            _format_studio_output(conn, s)
            for s in conn.execute("SELECT * FROM studio_outputs WHERE user_id = ? ORDER BY updated_at DESC", (uid,)).fetchall()
        ]

    tutorials = [_format_tutorial_row(t) for t in raw_tutorials]
    readings = [
        {
            **r,
            "title": r.get("custom_title") if r.get("has_custom_reading") and r.get("custom_title") else r["title"],
            "source_badge": "CUSTOMIZED" if r.get("has_custom_reading") else "ORIGINAL",
        }
        for r in raw_readings
    ]
    formatted_notes = [
        {**n, "tags": json.loads(n.get("tags_json") or "[]"), "is_pinned": bool(n.get("is_pinned", 0))}
        for n in notes
    ]
    if search and search.strip():
        q = search.strip().lower()
        formatted_notes = [n for n in formatted_notes if q in n["title"].lower() or q in n["content"].lower()]
        tutorials = [t for t in tutorials if q in t["title"].lower() or q in (t.get("topic_title") or "").lower()]
        readings = [r for r in readings if q in r["title"].lower() or q in r["overview"].lower()]
        studio_items = [s for s in studio_items if q in s["title"].lower() or q in s["tool_type"].lower()]

    return {
        "notes": formatted_notes,
        "tutorials": tutorials,
        "readings": readings,
        "studio_outputs": studio_items,
    }


@app.get("/api/search")
def global_search(
    q: str = Query(default=""),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    query = q.strip().lower()
    if not query:
        return {"results": []}

    results: List[Dict[str, Any]] = []
    with get_db() as conn:
        for rm in conn.execute("SELECT id, title, target_role FROM roadmaps WHERE user_id = ?", (uid,)).fetchall():
            if query in rm["title"].lower() or query in rm["target_role"].lower():
                results.append({"type": "Roadmap", "title": rm["title"], "subtitle": rm["target_role"], "link": f"/roadmaps/{rm['id']}"})

        for tp in conn.execute("SELECT id, roadmap_id, title, description FROM roadmap_topics WHERE user_id = ?", (uid,)).fetchall():
            if query in tp["title"].lower() or query in tp["description"].lower():
                results.append({"type": "Topic", "title": tp["title"], "subtitle": tp["description"][:80], "link": f"/roadmaps/{tp['roadmap_id']}?expand={tp['id']}"})

        for src in conn.execute("SELECT id, title, original_filename FROM sources WHERE user_id = ?", (uid,)).fetchall():
            if query in src["title"].lower() or query in src["original_filename"].lower():
                results.append({"type": "Source", "title": src["title"], "subtitle": src["original_filename"], "link": f"/sources?open={src['id']}"})

        for nt in conn.execute("SELECT id, title, content, topic_id, roadmap_id FROM personal_notes WHERE user_id = ?", (uid,)).fetchall():
            if query in nt["title"].lower() or query in nt["content"].lower():
                link = f"/roadmaps/{nt['roadmap_id']}?expand={nt['topic_id']}" if nt["roadmap_id"] and nt["topic_id"] else "/resources"
                results.append({"type": "Note", "title": nt["title"], "subtitle": nt["content"][:80], "link": link})

    return {"results": results[:20]}


# ============================================================================
# STRICT FOCUS MODE — AUTHORITATIVE SESSIONS & DISTRACTION EVENT TRACKING
# ============================================================================
FOCUS_MIN_DURATION_SECONDS = 60
FOCUS_MAX_DURATION_SECONDS = 14400
FOCUS_MAX_SHORT_BREAK_MINUTES = 30

FOCUS_EVENT_TYPES = {
    "visibility_hidden",
    "visibility_visible",
    "window_blur",
    "window_focus",
    "fullscreen_entered",
    "fullscreen_exited",
    "fullscreen_failed",
    "fullscreen_restored",
    "external_navigation_blocked",
    "keyboard_lock_failed",
    "capability_unavailable",
}

FOCUS_DISTRACTION_EVENTS = {
    "visibility_hidden",
    "window_blur",
    "fullscreen_exited",
    "external_navigation_blocked",
}


class FocusSessionStartRequest(BaseModel):
    duration_seconds: int
    session_title: str = ""
    short_break_minutes: int = 0
    sound_enabled: bool = True
    animations_enabled: bool = True
    client_request_id: str = ""


class FocusEventCreateRequest(BaseModel):
    event_type: str
    metadata: Optional[Dict[str, Any]] = None
    occurred_at: Optional[str] = None


def _parse_iso_utc(value: str) -> datetime:
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    dt = datetime.fromisoformat(cleaned)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_focus_session(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "session_title": row.get("session_title") or "",
        "duration_seconds": int(row["duration_seconds"]),
        "short_break_minutes": int(row.get("short_break_minutes") or 0),
        "sound_enabled": bool(row.get("sound_enabled", 1)),
        "animations_enabled": bool(row.get("animations_enabled", 1)),
        "started_at": row["started_at"],
        "ends_at": row["ends_at"],
        "completed_at": row.get("completed_at") or "",
        "status": row["status"],
        "distraction_event_count": int(row.get("distraction_event_count") or 0),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _format_focus_event(row: Dict[str, Any]) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    raw_meta = row.get("metadata_json") or "{}"
    try:
        parsed = json.loads(raw_meta)
        if isinstance(parsed, dict):
            meta = parsed
    except Exception:
        meta = {}
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "user_id": row["user_id"],
        "event_type": row["event_type"],
        "occurred_at": row["occurred_at"],
        "metadata": meta,
    }


def _reconcile_expired_focus_sessions(conn, user_id: str) -> Optional[Dict[str, Any]]:
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    active_rows = conn.execute(
        "SELECT * FROM focus_sessions WHERE user_id = ? AND status = 'active' ORDER BY started_at DESC",
        (user_id,),
    ).fetchall()
    recently_completed: Optional[Dict[str, Any]] = None
    for row in active_rows:
        try:
            ends_dt = _parse_iso_utc(row["ends_at"])
        except Exception:
            continue
        if ends_dt <= now_dt:
            completed_at = row["ends_at"]
            conn.execute(
                """
                UPDATE focus_sessions
                SET status = 'completed', completed_at = ?, updated_at = ?
                WHERE id = ? AND user_id = ? AND status = 'active'
                """,
                (completed_at, now_iso, row["id"], user_id),
            )
            title = (row.get("session_title") or "").strip() or "Strict Focus Session"
            duration_mins = max(1, int(round(int(row["duration_seconds"]) / 60)))
            log_activity(
                conn,
                user_id,
                "focus_session_completed",
                "focus_session",
                row["id"],
                f"Completed Focus: {title}",
                duration_minutes=duration_mins,
                metadata={"distraction_event_count": int(row.get("distraction_event_count") or 0)},
            )
            updated = conn.execute(
                "SELECT * FROM focus_sessions WHERE id = ? AND user_id = ?",
                (row["id"], user_id),
            ).fetchone()
            if updated and recently_completed is None:
                recently_completed = _format_focus_session(updated)
    return recently_completed


@app.post("/api/focus/sessions/start")
def start_focus_session(
    req: FocusSessionStartRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    if not isinstance(req.duration_seconds, int) or req.duration_seconds < FOCUS_MIN_DURATION_SECONDS or req.duration_seconds > FOCUS_MAX_DURATION_SECONDS:
        raise HTTPException(
            status_code=400,
            detail=f"Focus duration must be between {FOCUS_MIN_DURATION_SECONDS // 60} and {FOCUS_MAX_DURATION_SECONDS // 60} minutes.",
        )
    if req.short_break_minutes < 0 or req.short_break_minutes > FOCUS_MAX_SHORT_BREAK_MINUTES:
        raise HTTPException(
            status_code=400,
            detail=f"Short break must be between 0 and {FOCUS_MAX_SHORT_BREAK_MINUTES} minutes.",
        )

    clean_title = (req.session_title or "").strip()[:120]
    client_req_id = (req.client_request_id or "").strip()[:80]

    with get_db(commit=True) as conn:
        if client_req_id:
            existing_req = conn.execute(
                "SELECT * FROM focus_sessions WHERE user_id = ? AND client_request_id = ?",
                (uid, client_req_id),
            ).fetchone()
            if existing_req:
                _reconcile_expired_focus_sessions(conn, uid)
                refreshed = conn.execute(
                    "SELECT * FROM focus_sessions WHERE id = ? AND user_id = ?",
                    (existing_req["id"], uid),
                ).fetchone()
                return {
                    "session": _format_focus_session(refreshed or existing_req),
                    "server_time": utc_now(),
                }

        _reconcile_expired_focus_sessions(conn, uid)

        active_existing = conn.execute(
            "SELECT * FROM focus_sessions WHERE user_id = ? AND status = 'active' LIMIT 1",
            (uid,),
        ).fetchone()
        if active_existing:
            raise HTTPException(
                status_code=409,
                detail="An active focus session is already in progress. Complete or end it before starting a new one.",
            )

        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        ends_iso = (now_dt + timedelta(seconds=req.duration_seconds)).isoformat()
        session_id = new_id("focus")

        conn.execute(
            """
            INSERT INTO focus_sessions (
                id, user_id, session_title, duration_seconds, short_break_minutes,
                sound_enabled, animations_enabled, started_at, ends_at, completed_at,
                status, distraction_event_count, client_request_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', 'active', 0, ?, ?, ?)
            """,
            (
                session_id,
                uid,
                clean_title,
                req.duration_seconds,
                req.short_break_minutes,
                1 if req.sound_enabled else 0,
                1 if req.animations_enabled else 0,
                now_iso,
                ends_iso,
                client_req_id,
                now_iso,
                now_iso,
            ),
        )
        created = conn.execute(
            "SELECT * FROM focus_sessions WHERE id = ? AND user_id = ?",
            (session_id, uid),
        ).fetchone()
        return {"session": _format_focus_session(created), "server_time": utc_now()}


@app.get("/api/focus/sessions/active")
def get_active_focus_session(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        recently_completed = _reconcile_expired_focus_sessions(conn, uid)
        active_row = conn.execute(
            "SELECT * FROM focus_sessions WHERE user_id = ? AND status = 'active' ORDER BY started_at DESC LIMIT 1",
            (uid,),
        ).fetchone()
        return {
            "session": _format_focus_session(active_row) if active_row else None,
            "recently_completed": recently_completed,
            "server_time": utc_now(),
        }


@app.get("/api/focus/sessions")
def list_focus_sessions(
    limit: int = Query(default=25, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        _reconcile_expired_focus_sessions(conn, uid)
        rows = conn.execute(
            "SELECT * FROM focus_sessions WHERE user_id = ? ORDER BY started_at DESC LIMIT ?",
            (uid, limit),
        ).fetchall()
        return {
            "sessions": [_format_focus_session(r) for r in rows],
            "server_time": utc_now(),
        }


@app.get("/api/focus/sessions/{session_id}")
def get_focus_session_detail(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        _reconcile_expired_focus_sessions(conn, uid)
        row = conn.execute(
            "SELECT * FROM focus_sessions WHERE id = ? AND user_id = ?",
            (session_id, uid),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Focus session not found.")
        event_rows = conn.execute(
            "SELECT * FROM focus_events WHERE session_id = ? AND user_id = ? ORDER BY occurred_at DESC LIMIT 200",
            (session_id, uid),
        ).fetchall()
        return {
            "session": _format_focus_session(row),
            "events": [_format_focus_event(e) for e in event_rows],
            "server_time": utc_now(),
        }


@app.post("/api/focus/sessions/{session_id}/events")
def record_focus_event(
    session_id: str,
    req: FocusEventCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    event_type = (req.event_type or "").strip()
    if event_type not in FOCUS_EVENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported focus event type: {event_type}")

    safe_meta: Dict[str, Any] = {}
    if isinstance(req.metadata, dict):
        for k, v in list(req.metadata.items())[:10]:
            key = str(k)[:48]
            if isinstance(v, (str, int, float, bool)) or v is None:
                safe_meta[key] = v[:200] if isinstance(v, str) else v
    meta_json = json.dumps(safe_meta)
    if len(meta_json) > 2048:
        meta_json = "{}"

    occurred_iso = utc_now()
    if req.occurred_at:
        try:
            occurred_iso = _parse_iso_utc(req.occurred_at).isoformat()
        except Exception:
            occurred_iso = utc_now()

    with get_db(commit=True) as conn:
        _reconcile_expired_focus_sessions(conn, uid)
        row = conn.execute(
            "SELECT * FROM focus_sessions WHERE id = ? AND user_id = ?",
            (session_id, uid),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Focus session not found.")
        if row["status"] != "active":
            raise HTTPException(status_code=409, detail="Focus session is no longer active.")

        event_id = new_id("fevt")
        now_iso = utc_now()
        conn.execute(
            """
            INSERT INTO focus_events (id, session_id, user_id, event_type, occurred_at, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_id, session_id, uid, event_type, occurred_iso, meta_json),
        )
        inc = 1 if event_type in FOCUS_DISTRACTION_EVENTS else 0
        conn.execute(
            """
            UPDATE focus_sessions
            SET distraction_event_count = distraction_event_count + ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (inc, now_iso, session_id, uid),
        )
        updated = conn.execute(
            "SELECT * FROM focus_sessions WHERE id = ? AND user_id = ?",
            (session_id, uid),
        ).fetchone()
        created_evt = conn.execute(
            "SELECT * FROM focus_events WHERE id = ?",
            (event_id,),
        ).fetchone()
        return {
            "event": _format_focus_event(created_evt),
            "session": _format_focus_session(updated),
        }


@app.post("/api/focus/sessions/{session_id}/complete")
def complete_focus_session(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        row = conn.execute(
            "SELECT * FROM focus_sessions WHERE id = ? AND user_id = ?",
            (session_id, uid),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Focus session not found.")
        if row["status"] == "completed":
            return {"session": _format_focus_session(row), "server_time": utc_now()}
        if row["status"] == "aborted":
            raise HTTPException(status_code=409, detail="Aborted focus session cannot be completed.")

        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        completed_at = now_iso
        try:
            ends_dt = _parse_iso_utc(row["ends_at"])
            if ends_dt <= now_dt:
                completed_at = row["ends_at"]
        except Exception:
            pass

        conn.execute(
            """
            UPDATE focus_sessions
            SET status = 'completed', completed_at = ?, updated_at = ?
            WHERE id = ? AND user_id = ? AND status = 'active'
            """,
            (completed_at, now_iso, session_id, uid),
        )
        title = (row.get("session_title") or "").strip() or "Strict Focus Session"
        duration_mins = max(1, int(round(int(row["duration_seconds"]) / 60)))
        log_activity(
            conn,
            uid,
            "focus_session_completed",
            "focus_session",
            session_id,
            f"Completed Focus: {title}",
            duration_minutes=duration_mins,
            metadata={"distraction_event_count": int(row.get("distraction_event_count") or 0)},
        )
        updated = conn.execute(
            "SELECT * FROM focus_sessions WHERE id = ? AND user_id = ?",
            (session_id, uid),
        ).fetchone()
        return {"session": _format_focus_session(updated), "server_time": utc_now()}


@app.post("/api/focus/sessions/{session_id}/abort")
def abort_focus_session(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        _reconcile_expired_focus_sessions(conn, uid)
        row = conn.execute(
            "SELECT * FROM focus_sessions WHERE id = ? AND user_id = ?",
            (session_id, uid),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Focus session not found.")
        if row["status"] == "aborted":
            return {"session": _format_focus_session(row), "server_time": utc_now()}
        if row["status"] == "completed":
            raise HTTPException(status_code=409, detail="Completed focus session cannot be aborted.")

        now_iso = utc_now()
        conn.execute(
            """
            UPDATE focus_sessions
            SET status = 'aborted', completed_at = ?, updated_at = ?
            WHERE id = ? AND user_id = ? AND status = 'active'
            """,
            (now_iso, now_iso, session_id, uid),
        )
        updated = conn.execute(
            "SELECT * FROM focus_sessions WHERE id = ? AND user_id = ?",
            (session_id, uid),
        ).fetchone()
        return {"session": _format_focus_session(updated), "server_time": utc_now()}


@app.delete("/api/focus/sessions/history")
def clear_focus_session_history(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        _reconcile_expired_focus_sessions(conn, uid)
        eligible_rows = conn.execute(
            "SELECT id FROM focus_sessions WHERE user_id = ? AND status IN ('completed', 'aborted')",
            (uid,),
        ).fetchall()
        eligible_ids = [r["id"] for r in eligible_rows]
        if eligible_ids:
            placeholders = ",".join("?" for _ in eligible_ids)
            conn.execute(
                f"DELETE FROM focus_events WHERE user_id = ? AND session_id IN ({placeholders})",
                [uid, *eligible_ids],
            )
            conn.execute(
                f"DELETE FROM focus_sessions WHERE user_id = ? AND id IN ({placeholders}) AND status IN ('completed', 'aborted')",
                [uid, *eligible_ids],
            )
        active_row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM focus_sessions WHERE user_id = ? AND status = 'active'",
            (uid,),
        ).fetchone()
        active_preserved = bool(active_row and int(active_row["cnt"]) > 0)
        return {
            "deleted_count": len(eligible_ids),
            "active_preserved": active_preserved,
            "server_time": utc_now(),
        }


@app.delete("/api/focus/sessions/{session_id}")
def delete_focus_session(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        _reconcile_expired_focus_sessions(conn, uid)
        row = conn.execute(
            "SELECT * FROM focus_sessions WHERE id = ? AND user_id = ?",
            (session_id, uid),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Focus session not found.")
        if row["status"] == "active":
            raise HTTPException(
                status_code=409,
                detail="Active focus sessions cannot be deleted. End or complete the session first.",
            )
        conn.execute(
            "DELETE FROM focus_events WHERE session_id = ? AND user_id = ?",
            (session_id, uid),
        )
        conn.execute(
            "DELETE FROM focus_sessions WHERE id = ? AND user_id = ?",
            (session_id, uid),
        )
        return {
            "deleted": True,
            "session_id": session_id,
            "server_time": utc_now(),
        }


# ============================================================================
# CAREER LAUNCHPAD & GENERAL-PURPOSE AI MENTOR
# ============================================================================
class CareerProfileUpdateRequest(BaseModel):
    target_career: str = Field(..., min_length=2, max_length=80)
    target_job_role: str = Field("", max_length=120)
    target_company: str = Field("", max_length=120)
    graduation_year: int = Field(2026, ge=2020, le=2035)
    current_skill_level: str = Field("Intermediate", max_length=40)
    available_hours_per_week: int = Field(14, ge=1, le=168)
    target_deadline: str = Field("", max_length=40)


class ProjectEvidencePayload(BaseModel):
    deployed_projects: int = Field(0, ge=0, le=20)
    has_github_portfolio: bool = False
    has_automated_tests: bool = False


class CareerAssessmentSubmitRequest(BaseModel):
    answers: Dict[str, int] = Field(default_factory=dict)
    project_evidence: Optional[ProjectEvidencePayload] = None


class CareerPlanGenerateRequest(BaseModel):
    focus_note: str = Field("", max_length=400)


class MentorConversationCreateRequest(BaseModel):
    title: str = Field("New Mentor Conversation", max_length=120)


class MentorConversationRenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)


class MentorStreamRequest(BaseModel):
    message: str = Field("", max_length=8000)
    regenerate: bool = False


class MentorFeedbackRequest(BaseModel):
    message_id: str = Field(..., min_length=1, max_length=80)
    feedback: str = Field(..., pattern="^(up|down|none)$")


def _get_or_create_career_profile(conn: Any, uid: str) -> Dict[str, Any]:
    row = conn.execute("SELECT * FROM career_profiles WHERE user_id = ?", (uid,)).fetchone()
    if row:
        return dict(row)
    user_row = conn.execute("SELECT target_role FROM users WHERE id = ?", (uid,)).fetchone()
    default_career = (user_row["target_role"] if user_row else "") or "Software Engineer"
    if default_career not in CAREER_BENCHMARKS:
        default_career = "Software Engineer"
    now = utc_now()
    conn.execute(
        """
        INSERT INTO career_profiles (
            user_id, target_career, target_job_role, target_company,
            graduation_year, current_skill_level, available_hours_per_week, target_deadline, updated_at
        ) VALUES (?, ?, ?, '', 2026, 'Intermediate', 14, '', ?)
        """,
        (uid, default_career, f"Fresher {default_career}", now),
    )
    return dict(conn.execute("SELECT * FROM career_profiles WHERE user_id = ?", (uid,)).fetchone())


@app.get("/api/career-launchpad/overview")
def get_career_launchpad_overview(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        profile = _get_or_create_career_profile(conn, uid)
        latest_assess = conn.execute(
            "SELECT * FROM career_skill_assessments WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (uid,),
        ).fetchone()
        latest_dict = dict(latest_assess) if latest_assess else None

        topic_row = conn.execute(
            """
            SELECT COUNT(*) AS total_topics,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_topics
            FROM roadmap_topics WHERE user_id = ?
            """,
            (uid,),
        ).fetchone()
        total_topics = int(topic_row["total_topics"] or 0) if topic_row else 0
        completed_topics = int(topic_row["completed_topics"] or 0) if topic_row else 0
        overall_progress = round((completed_topics / total_topics) * 100) if total_topics > 0 else 0

        quiz_row = conn.execute(
            "SELECT COUNT(*) AS cnt, COALESCE(AVG(percentage), 0) AS avg_pct FROM quiz_attempts WHERE user_id = ?",
            (uid,),
        ).fetchone()

        analysis = compute_skill_gap_and_readiness(
            target_career=profile["target_career"],
            latest_assessment=latest_dict,
            roadmap_stats={"overall_progress_percent": overall_progress},
            quiz_stats={
                "attempts_count": int(quiz_row["cnt"] or 0) if quiz_row else 0,
                "average_percentage": float(quiz_row["avg_pct"] or 0) if quiz_row else 0.0,
            },
        )
        weekly = build_weekly_performance(conn, uid)
        saved_roadmaps = conn.execute(
            "SELECT id, title, target_role, skill_level, hours_per_week, target_completion_date, total_estimated_hours, created_at FROM roadmaps WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
            (uid,),
        ).fetchall()

        parsed_latest = None
        if latest_dict:
            parsed_latest = {
                "id": latest_dict["id"],
                "target_career": latest_dict["target_career"],
                "total_questions": latest_dict["total_questions"],
                "correct_count": latest_dict["correct_count"],
                "overall_score": latest_dict["overall_score"],
                "category_scores": json.loads(latest_dict["category_scores_json"] or "{}"),
                "project_evidence": json.loads(latest_dict["project_evidence_json"] or "{}"),
                "created_at": latest_dict["created_at"],
            }

        return {
            "profile": profile,
            "careers": list(CAREER_BENCHMARKS.keys()),
            "skill_categories": SKILL_CATEGORIES,
            "latest_assessment": parsed_latest,
            "gap_analysis": analysis,
            "weekly_performance": weekly,
            "saved_plans": [dict(r) for r in saved_roadmaps],
        }


@app.put("/api/career-launchpad/profile")
def update_career_profile(
    req: CareerProfileUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    now = utc_now()
    with get_db(commit=True) as conn:
        _get_or_create_career_profile(conn, uid)
        conn.execute(
            """
            UPDATE career_profiles
            SET target_career = ?, target_job_role = ?, target_company = ?,
                graduation_year = ?, current_skill_level = ?, available_hours_per_week = ?,
                target_deadline = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (
                req.target_career.strip(),
                req.target_job_role.strip(),
                req.target_company.strip(),
                req.graduation_year,
                req.current_skill_level.strip(),
                req.available_hours_per_week,
                req.target_deadline.strip(),
                now,
                uid,
            ),
        )
        updated = dict(conn.execute("SELECT * FROM career_profiles WHERE user_id = ?", (uid,)).fetchone())
    return {"profile": updated}


@app.get("/api/career-launchpad/assessment")
def get_career_assessment(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    return {
        "categories": SKILL_CATEGORIES,
        "questions": get_public_assessment_questions(),
    }


@app.post("/api/career-launchpad/assessment/submit")
def submit_career_assessment(
    req: CareerAssessmentSubmitRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        profile = _get_or_create_career_profile(conn, uid)
        evidence_dict = req.project_evidence.model_dump() if req.project_evidence else {}
        graded = grade_skill_assessment(req.answers, evidence_dict)
        assess_id = new_id("cass")
        now = utc_now()
        conn.execute(
            """
            INSERT INTO career_skill_assessments (
                id, user_id, target_career, total_questions, correct_count,
                overall_score, category_scores_json, answers_json, project_evidence_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assess_id,
                uid,
                profile["target_career"],
                graded["total_questions"],
                graded["correct_count"],
                graded["overall_score"],
                json.dumps(graded["category_scores"]),
                json.dumps(graded["graded_answers"]),
                json.dumps(graded["project_evidence"]),
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO activity_logs (id, user_id, activity_type, entity_type, entity_id, title, duration_minutes, metadata_json, created_at)
            VALUES (?, ?, 'career_assessment', 'career_skill_assessments', ?, ?, 15, ?, ?)
            """,
            (
                new_id("act"),
                uid,
                assess_id,
                f"Career Skill Assessment ({profile['target_career']})",
                json.dumps({"overall_score": graded["overall_score"]}),
                now,
            ),
        )
    return {
        "assessment": {
            "id": assess_id,
            "target_career": profile["target_career"],
            "total_questions": graded["total_questions"],
            "correct_count": graded["correct_count"],
            "overall_score": graded["overall_score"],
            "category_scores": graded["category_scores"],
            "project_evidence": graded["project_evidence"],
            "created_at": now,
        }
    }


@app.post("/api/career-launchpad/plan/generate")
def generate_career_preparation_plan(
    req: CareerPlanGenerateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Generate a personalized preparation plan using the EXISTING BRAINOVA AI Roadmap engine."""
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        prefs = ensure_user_preferences(conn, uid)
        profile = _get_or_create_career_profile(conn, uid)
        latest_assess = conn.execute(
            "SELECT * FROM career_skill_assessments WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (uid,),
        ).fetchone()
        latest_dict = dict(latest_assess) if latest_assess else None
        analysis = compute_skill_gap_and_readiness(
            target_career=profile["target_career"],
            latest_assessment=latest_dict,
            roadmap_stats={"overall_progress_percent": 0},
            quiz_stats={"attempts_count": 0, "average_percentage": 0},
        )
        gap_labels = [p["label"] for p in analysis["priority_areas"]] or analysis["missing_skills"][:4]
        priorities_str = ", ".join(gap_labels) if gap_labels else "DSA, System Fundamentals, Portfolio Projects"
        if req.focus_note.strip():
            priorities_str = f"{priorities_str}. {req.focus_note.strip()}"

        role_title = profile["target_job_role"] or profile["target_career"]
        draft = generateRoadmap(
            target_role=role_title,
            skill_level=profile["current_skill_level"] or "Intermediate",
            hours_per_week=int(profile["available_hours_per_week"] or 14),
            preferred_stack=profile["target_career"],
            existing_knowledge=(
                f"Assessed overall score: {latest_dict['overall_score']}%"
                if latest_dict
                else "Baseline skill assessment pending"
            ),
            target_completion_date=profile["target_deadline"] or "",
            priorities=priorities_str,
            exam_goals=f"Internship / Fresher Readiness ({profile['target_company'] or profile['target_career']})",
            user_prefs=prefs,
        )
    return {"draft_roadmap": draft, "profile": profile, "priority_gaps": gap_labels}


@app.get("/api/mentor/conversations")
def list_mentor_conversations(
    q: str = Query("", max_length=120),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    search = q.strip().lower()
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, title, messages_json, created_at, updated_at
            FROM ai_conversations
            WHERE user_id = ? AND context_type = 'career_mentor'
            ORDER BY updated_at DESC
            """,
            (uid,),
        ).fetchall()
    items: List[Dict[str, Any]] = []
    for r in rows:
        msgs = json.loads(r["messages_json"] or "[]")
        if search:
            in_title = search in (r["title"] or "").lower()
            in_msgs = any(search in str(m.get("content") or "").lower() for m in msgs)
            if not (in_title or in_msgs):
                continue
        last_preview = ""
        if msgs:
            last_preview = str(msgs[-1].get("content") or "").strip().replace("\n", " ")[:90]
        items.append({
            "id": r["id"],
            "title": r["title"],
            "message_count": len(msgs),
            "last_preview": last_preview,
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        })
    return {"conversations": items}


@app.post("/api/mentor/conversations")
def create_mentor_conversation(
    req: MentorConversationCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    conv_id = new_id("mconv")
    now = utc_now()
    title = req.title.strip() or "New Mentor Conversation"
    with get_db(commit=True) as conn:
        conn.execute(
            """
            INSERT INTO ai_conversations (id, user_id, context_type, title, source_ids_json, messages_json, draft_roadmap_json, created_at, updated_at)
            VALUES (?, ?, 'career_mentor', ?, '[]', '[]', '', ?, ?)
            """,
            (conv_id, uid, title, now, now),
        )
    return {
        "conversation": {
            "id": conv_id,
            "title": title,
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }
    }


@app.get("/api/mentor/conversations/{conv_id}")
def get_mentor_conversation(
    conv_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT id, title, messages_json, created_at, updated_at
            FROM ai_conversations
            WHERE id = ? AND user_id = ? AND context_type = 'career_mentor'
            """,
            (conv_id, uid),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {
        "conversation": {
            "id": row["id"],
            "title": row["title"],
            "messages": json.loads(row["messages_json"] or "[]"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
    }


@app.patch("/api/mentor/conversations/{conv_id}")
def rename_mentor_conversation(
    conv_id: str,
    req: MentorConversationRenameRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    clean_title = req.title.strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail="Conversation title cannot be empty.")
    now = utc_now()
    with get_db(commit=True) as conn:
        res = conn.execute(
            """
            UPDATE ai_conversations
            SET title = ?, updated_at = ?
            WHERE id = ? AND user_id = ? AND context_type = 'career_mentor'
            """,
            (clean_title, now, conv_id, uid),
        )
        if res.rowcount == 0:
            raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"id": conv_id, "title": clean_title, "updated_at": now}


@app.delete("/api/mentor/conversations/{conv_id}")
def delete_mentor_conversation(
    conv_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        res = conn.execute(
            "DELETE FROM ai_conversations WHERE id = ? AND user_id = ? AND context_type = 'career_mentor'",
            (conv_id, uid),
        )
        if res.rowcount == 0:
            raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"deleted": True, "id": conv_id}


@app.post("/api/mentor/conversations/{conv_id}/feedback")
def set_mentor_message_feedback(
    conv_id: str,
    req: MentorFeedbackRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        row = conn.execute(
            "SELECT messages_json FROM ai_conversations WHERE id = ? AND user_id = ? AND context_type = 'career_mentor'",
            (conv_id, uid),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        msgs = json.loads(row["messages_json"] or "[]")
        found = False
        for m in msgs:
            if m.get("id") == req.message_id:
                m["feedback"] = None if req.feedback == "none" else req.feedback
                found = True
                break
        if not found:
            raise HTTPException(status_code=404, detail="Message not found.")
        conn.execute(
            "UPDATE ai_conversations SET messages_json = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (json.dumps(msgs), utc_now(), conv_id, uid),
        )
    return {"updated": True, "message_id": req.message_id, "feedback": req.feedback}


MENTOR_IMAGES_DIR = os.path.join(DATA_DIR, "mentor_images")


class MentorImageGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=1000)


@app.post("/api/mentor/conversations/{conv_id}/image")
def generate_mentor_conversation_image(
    conv_id: str,
    req: MentorImageGenerateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        allowed, retry_after = check_and_increment_mentor_rate_limit(conn, uid, limit_per_minute=20)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit reached. Please wait {retry_after} seconds before generating an image.",
            )
        row = conn.execute(
            "SELECT id, messages_json FROM ai_conversations WHERE id = ? AND user_id = ? AND context_type = 'career_mentor'",
            (conv_id, uid),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        prefs = ensure_user_preferences(conn, uid)
        existing_msgs = json.loads(row["messages_json"] or "[]")

    img_id = new_id("mimg")
    result = generate_mentor_image(req.prompt, prefs, MENTOR_IMAGES_DIR, uid, img_id)
    if not result.get("ok"):
        raise HTTPException(
            status_code=int(result.get("status") or 502),
            detail={"code": result.get("code", "image_generation_failed"), "message": result.get("message", "Image generation failed.")},
        )

    img_msg = {
        "id": new_id("mmsg"),
        "role": "assistant",
        "content": f"Generated educational illustration (illustrative only) for: *{result['prompt']}*",
        "provider": result["provider"],
        "image": {
            "id": result["image_id"],
            "url": f"/api/mentor/images/{result['image_id']}",
            "prompt": result["prompt"],
            "mime_type": result["mime_type"],
            "illustrative_only": True,
        },
        "timestamp": utc_now(),
    }
    existing_msgs.append(img_msg)
    with get_db(commit=True) as conn:
        conn.execute(
            "UPDATE ai_conversations SET messages_json = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (json.dumps(existing_msgs), utc_now(), conv_id, uid),
        )
    return {"message": img_msg}


@app.get("/api/mentor/images/{image_id}")
def get_mentor_generated_image(
    image_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    uid = current_user["id"]
    safe_uid = re.sub(r"[^A-Za-z0-9_-]", "", uid)
    safe_img = re.sub(r"[^A-Za-z0-9_-]", "", image_id)
    if not safe_img:
        raise HTTPException(status_code=400, detail="Invalid image ID.")
    for ext, media in ((".png", "image/png"), (".jpg", "image/jpeg"), (".webp", "image/webp")):
        candidate = os.path.join(MENTOR_IMAGES_DIR, f"{safe_uid}__{safe_img}{ext}")
        if os.path.isfile(candidate):
            return FileResponse(candidate, media_type=media)
    raise HTTPException(status_code=404, detail="Generated image not found.")


def _create_mentor_sse_generator(
    conv_id: str,
    uid: str,
    title: str,
    msgs: List[Dict[str, Any]],
    prefs: Dict[str, Any],
    career_ctx: Optional[Dict[str, Any]],
):
    assistant_id = new_id("mmsg")
    final_text = ""
    provider_used = ""
    errored = False
    for evt in stream_mentor_reply(msgs, user_prefs=prefs, career_context=career_ctx):
        if evt.get("type") == "done":
            final_text = evt.get("text") or ""
            provider_used = evt.get("provider") or ""
            done_payload = {
                "type": "done",
                "message": {
                    "id": assistant_id,
                    "role": "assistant",
                    "content": final_text,
                    "provider": provider_used,
                    "timestamp": utc_now(),
                },
                "title": title,
            }
            with get_db(commit=True) as save_conn:
                latest_row = save_conn.execute(
                    "SELECT messages_json FROM ai_conversations WHERE id = ? AND user_id = ?",
                    (conv_id, uid),
                ).fetchone()
                if latest_row:
                    latest_msgs = json.loads(latest_row["messages_json"] or "[]")
                    latest_msgs.append(done_payload["message"])
                    save_conn.execute(
                        "UPDATE ai_conversations SET messages_json = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                        (json.dumps(latest_msgs), utc_now(), conv_id, uid),
                    )
            yield f"data: {json.dumps(done_payload)}\n\n"
        elif evt.get("type") == "error":
            errored = True
            yield f"data: {json.dumps(evt)}\n\n"
        else:
            yield f"data: {json.dumps(evt)}\n\n"

    if not final_text and not errored:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Stream ended unexpectedly.'})}\n\n"


@app.post("/api/mentor/conversations/{conv_id}/stream")
def stream_mentor_conversation_turn(
    conv_id: str,
    req: MentorStreamRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    uid = current_user["id"]
    clean_message = req.message.strip()
    if not req.regenerate and not clean_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    with get_db(commit=True) as conn:
        allowed, retry_after = check_and_increment_mentor_rate_limit(conn, uid, limit_per_minute=20)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit reached. Please wait {retry_after} seconds before sending another message.",
            )

        row = conn.execute(
            "SELECT id, title, messages_json FROM ai_conversations WHERE id = ? AND user_id = ? AND context_type = 'career_mentor'",
            (conv_id, uid),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found.")

        msgs: List[Dict[str, Any]] = json.loads(row["messages_json"] or "[]")
        title = row["title"]
        now = utc_now()

        if req.regenerate:
            if msgs and msgs[-1].get("role") == "assistant":
                msgs.pop()
            if not msgs:
                raise HTTPException(status_code=400, detail="No user message to regenerate.")
        else:
            user_msg = {
                "id": new_id("mmsg"),
                "role": "user",
                "content": clean_message,
                "timestamp": now,
            }
            msgs.append(user_msg)
            if len(msgs) == 1 and title in ("New Mentor Conversation", "Untitled Conversation", ""):
                title = extract_conversation_title(clean_message)

        conn.execute(
            "UPDATE ai_conversations SET title = ?, messages_json = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (title, json.dumps(msgs), now, conv_id, uid),
        )
        prefs = ensure_user_preferences(conn, uid)
        profile_row = conn.execute("SELECT target_career, current_skill_level FROM career_profiles WHERE user_id = ?", (uid,)).fetchone()
        career_ctx = dict(profile_row) if profile_row else None

    return StreamingResponse(
        _create_mentor_sse_generator(conv_id, uid, title, msgs, prefs, career_ctx),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ============================================================================
# TECH PULSE — TRUSTWORTHY DAILY TECHNOLOGY INTELLIGENCE
# ============================================================================


@app.get("/api/tech-pulse/feed")
def tech_pulse_feed(
    category: Optional[str] = None,
    verified_only: bool = False,
    q: Optional[str] = None,
    limit: int = 40,
    offset: int = 0,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    with get_db(commit=False) as conn:
        return get_daily_feed(
            conn=conn,
            user_id=current_user["id"],
            category=category,
            verified_only=verified_only,
            query=q,
            limit=limit,
            offset=offset,
        )


@app.get("/api/tech-pulse/categories")
def tech_pulse_categories(current_user: Dict[str, Any] = Depends(get_current_user)):
    _ = current_user
    return {"categories": TECH_PULSE_CATEGORIES}


@app.get("/api/tech-pulse/metadata")
def tech_pulse_metadata(current_user: Dict[str, Any] = Depends(get_current_user)):
    _ = current_user
    with get_db(commit=False) as conn:
        last_run = conn.execute(
            """
            SELECT id, started_at, finished_at, status, sources_checked, discovered_count, published_count
            FROM tech_pulse_ingestion_runs
            ORDER BY started_at DESC LIMIT 1
            """
        ).fetchone()
        active_sources = conn.execute(
            "SELECT COUNT(*) AS cnt FROM tech_pulse_sources WHERE enabled = 1"
        ).fetchone()
        return {
            "ist_date": to_ist_date_str(),
            "timezone": "Asia/Kolkata (IST)",
            "active_source_count": int(active_sources["cnt"]) if active_sources else 0,
            "last_run": last_run,
        }


@app.get("/api/tech-pulse/stories/{story_id}")
def tech_pulse_story_detail(
    story_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    with get_db(commit=False) as conn:
        story = get_story_detail(conn, current_user["id"], story_id)
        if not story:
            raise HTTPException(status_code=404, detail="Tech Pulse story not found.")
        return {"story": story}


@app.get("/api/tech-pulse/saved")
def tech_pulse_saved_list(current_user: Dict[str, Any] = Depends(get_current_user)):
    with get_db(commit=False) as conn:
        return {"stories": list_saved_stories(conn, current_user["id"])}


@app.post("/api/tech-pulse/saved/{story_id}")
def tech_pulse_save_story(
    story_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    with get_db(commit=True) as conn:
        saved = save_story_bookmark(conn, current_user["id"], story_id)
        if not saved:
            raise HTTPException(status_code=404, detail="Tech Pulse story not found.")
        return {"saved": True, "story": saved}


@app.delete("/api/tech-pulse/saved/{story_id}")
def tech_pulse_unsave_story(
    story_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    with get_db(commit=True) as conn:
        removed = remove_story_bookmark(conn, current_user["id"], story_id)
        return {"saved": False, "removed": removed}


@app.post("/api/tech-pulse/refresh")
def tech_pulse_refresh(current_user: Dict[str, Any] = Depends(get_current_user)):
    _ = current_user
    with get_db(commit=True) as conn:
        result = run_ingestion_cycle(conn, trigger_type="manual")
        return result


# ============================================================================
# SPA STATIC SERVING (Preserves browser refreshes & deep routes in production)
# ============================================================================
DIST_DIR = os.path.join(BASE_DIR, "dist")
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
if os.path.exists(os.path.join(DIST_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="assets")


@app.get("/{full_path:path}")
def serve_spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found.")
    clean_rel = os.path.basename(full_path) if "/" not in full_path else ""
    if clean_rel:
        for base_d in (DIST_DIR, PUBLIC_DIR):
            cand = os.path.join(base_d, clean_rel)
            if os.path.isfile(cand):
                return FileResponse(cand)
    index_file = os.path.join(DIST_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse(
        {
            "service": "BRAINOVA Backend API",
            "tagline": "Learn Smarter. Think Bigger.",
            "status": "online",
            "docs": "/docs",
        }
    )

