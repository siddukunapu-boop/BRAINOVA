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
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.ai_engine import (
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
    ensure_user_preferences,
    get_current_user,
    hash_password,
    sanitize_preferences_for_client,
    verify_password,
)
from backend.database import (
    AUDIO_DIR,
    BASE_DIR,
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
from backend.multilang_engine import SUPPORTED_LANGUAGES, normalize_language
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
    resume_incomplete_jobs_on_startup()


# ============================================================================
# PYDANTIC REQUEST SCHEMAS
# ============================================================================
class SignupRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=160)
    password: str = Field(..., min_length=6, max_length=128)
    target_role: Optional[str] = "Full Stack Developer"


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


class QuizSubmissionRequest(BaseModel):
    answers: Dict[str, int] = Field(default_factory=dict)  # question_id or index -> selected_option_index (0..3)
    duration_seconds: int = 0


class StudioGenerateRequest(BaseModel):
    tool_type: str
    title: Optional[str] = None
    source_ids: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)


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
@app.post("/api/auth/signup")
def signup(req: SignupRequest) -> Dict[str, Any]:
    email_clean = req.email.strip().lower()
    if "@" not in email_clean:
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")

    with get_db(commit=True) as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email_clean,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="An account with this email already exists.")

        user_id = new_id("usr")
        now = utc_now()
        pw_hash = hash_password(req.password)
        colors = ["#6366f1", "#38bdf8", "#8b5cf6", "#10b981", "#f59e0b"]
        color = colors[len(email_clean) % len(colors)]

        conn.execute(
            """
            INSERT INTO users (id, email, name, password_hash, role, target_role, bio, avatar_color, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'student', ?, '', ?, ?, ?)
            """,
            (user_id, email_clean, req.name.strip(), pw_hash, (req.target_role or "Full Stack Developer").strip(), color, now, now),
        )
        prefs = ensure_user_preferences(conn, user_id)
        log_activity(conn, user_id, "signup", "user", user_id, "Created AetherLearn account", 2)

        user_row = conn.execute(
            "SELECT id, email, name, role, target_role, bio, avatar_color, created_at, updated_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        user_row["preferences"] = sanitize_preferences_for_client(prefs)

    token = create_access_token(user_id, email_clean)
    return {"token": token, "user": user_row}


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
def logout() -> Dict[str, Any]:
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
                updates[field] = val

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
                # Allow setting or clearing key
                updates[key_field] = val.strip()

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


def _format_reading_row(reading_row: Optional[Dict[str, Any]], topic_title_fallback: str = "Topic") -> Optional[Dict[str, Any]]:
    if not reading_row:
        return None
    t_title = reading_row.get("title") or topic_title_fallback
    diagrams = json.loads(reading_row.get("diagrams_json") or "[]")
    if not diagrams:
        diagrams = [
            {
                "id": "diag-arch",
                "title": f"{t_title} — Core System Architecture & Data Flow",
                "type": "architecture",
                "caption": f"End-to-end execution pipeline and validation boundaries for {t_title}.",
                "nodes": [
                    {"id": "n1", "step": "01", "label": "Input & Contract Gate", "sublabel": "Boundary Validation", "role": "Schema & input verification"},
                    {"id": "n2", "step": "02", "label": "Core Processing Engine", "sublabel": "State Transformation", "role": "Deterministic execution logic"},
                    {"id": "n3", "step": "03", "label": "Resilience & Optimization", "sublabel": "Performance & Caching", "role": "Indexing & fault isolation"},
                    {"id": "n4", "step": "04", "label": "Verified Output & Audit", "sublabel": "Persistence Layer", "role": "Transactional storage & telemetry"},
                ],
            },
            {
                "id": "diag-lifecycle",
                "title": f"{t_title} — Step-by-Step Engineering Lifecycle",
                "type": "process",
                "caption": "Four-phase cycle from specification to production verification.",
                "nodes": [
                    {"id": "p1", "step": "Phase A", "label": "Define Invariants", "sublabel": "Contracts & types", "role": "Design"},
                    {"id": "p2", "step": "Phase B", "label": "Modular Build", "sublabel": "Decoupled units", "role": "Implement"},
                    {"id": "p3", "step": "Phase C", "label": "Boundary Testing", "sublabel": "Edge & load checks", "role": "Verify"},
                    {"id": "p4", "step": "Phase D", "label": "Observability", "sublabel": "Metrics & audit", "role": "Operate"},
                ],
            },
        ]

    has_custom = bool(reading_row.get("has_custom_reading", 0)) and bool((reading_row.get("custom_markdown") or "").strip())
    key_defs = json.loads(reading_row.get("key_definitions_json") or "[]")
    common_m = json.loads(reading_row.get("common_mistakes_json") or "[]")
    sections_list = json.loads(reading_row.get("sections_json") or "[]")
    takeaways_list = [s.get("heading") for s in sections_list if s.get("heading")]
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
        if req.topic_id and not roadmap_id:
            t = conn.execute("SELECT roadmap_id FROM roadmap_topics WHERE id = ? AND user_id = ?", (req.topic_id, uid)).fetchone()
            if t:
                roadmap_id = t["roadmap_id"]

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


@app.get("/api/studio/outputs")
def list_studio_outputs(
    tool_type: Optional[str] = Query(default=None),
    language: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(default="newest"),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db() as conn:
        if tool_type and tool_type != "all":
            rows = conn.execute(
                "SELECT * FROM studio_outputs WHERE user_id = ? AND tool_type = ? ORDER BY created_at DESC",
                (uid, tool_type),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM studio_outputs WHERE user_id = ? ORDER BY created_at DESC",
                (uid,),
            ).fetchall()
        items = [_format_studio_output(conn, r) for r in rows]

    if language and language != "all":
        items = [i for i in items if (i.get("language") or "English").lower() == language.strip().lower()]

    if search and search.strip():
        q = search.strip().lower()
        items = [
            i
            for i in items
            if q in i["title"].lower()
            or q in i["tool_type"].lower()
            or q in (i.get("language") or "").lower()
            or any(q in s["title"].lower() for s in (i.get("source_titles") or []))
        ]

    if sort == "oldest":
        items.sort(key=lambda x: x["created_at"])
    elif sort == "title":
        items.sort(key=lambda x: x["title"].lower())
    else:
        items.sort(key=lambda x: x["created_at"], reverse=True)

    return {"outputs": items, "total_count": len(items), "supported_languages": SUPPORTED_LANGUAGES}


@app.post("/api/studio/generate")
def generate_studio_tool_output(
    req: StudioGenerateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    if req.tool_type not in VALID_STUDIO_TOOLS:
        raise HTTPException(status_code=400, detail=f"Invalid AI Studio tool '{req.tool_type}'.")

    output_id = new_id("std")
    now = utc_now()
    language = normalize_language(req.config.get("language") or "English")
    req.config["language"] = language
    if req.title:
        req.config["title"] = req.title.strip()

    with get_db(commit=True) as conn:
        prefs = ensure_user_preferences(conn, uid)
        query_hint = req.config.get("topic") or req.config.get("instructions") or req.title or req.tool_type
        chunks = retrieve_relevant_chunks(conn, uid, req.source_ids, str(query_hint), top_k=10)
        openai_key = (prefs.get("openai_api_key") or os.environ.get("OPENAI_API_KEY") or "").strip()

        audio_path = ""
        video_path = ""
        duration_label = str(req.config.get("duration") or req.config.get("video_duration") or "")
        style_label = str(req.config.get("style") or "")

        if req.tool_type == "audio_overview":
            content = generateAudioScript(chunks, req.config, user_prefs=prefs)
            audio_meta = synthesize_podcast_audio(
                output_id,
                content["dialogue"],
                openai_api_key=openai_key,
                language=language,
            )
            content["audio"] = audio_meta
            audio_path = audio_meta["file_path"]

        elif req.tool_type == "slide_deck":
            content = generateSlideDeck(chunks, req.config, user_prefs=prefs)

        elif req.tool_type == "video_overview":
            content = generateVideoStoryboard(chunks, req.config, user_prefs=prefs)
            dur_lbl = duration_label or "3–5 minutes"
            sty_lbl = style_label or "Concept Breakdown & Architecture"
            video_meta = synthesize_educational_video(
                output_id=output_id,
                storyboard=content,
                language=language,
                duration_label=dur_lbl,
                style_label=sty_lbl,
                openai_api_key=openai_key,
            )
            content["video"] = video_meta
            video_path = video_meta["file_path"]
            audio_path = video_meta["audio_file_path"]
            duration_label = dur_lbl
            style_label = sty_lbl

        elif req.tool_type == "mind_map":
            content = generateMindMap(chunks, req.config, user_prefs=prefs)

        elif req.tool_type == "study_guide":
            content = generateStudyGuide(chunks, req.config, user_prefs=prefs)

        elif req.tool_type == "flashcards":
            content = generateFlashcards(chunks, req.config, user_prefs=prefs)

        elif req.tool_type == "quiz":
            q_count = int(req.config.get("question_count") or 20)
            diff = req.config.get("difficulty") or "Intermediate"
            topic_name = req.config.get("topic") or (chunks[0]["source_title"] if chunks else "Source Mastery Exam")
            content = generateTopicQuiz(
                topic_title=topic_name,
                topic_description=f"Source-grounded assessment from {len(req.source_ids)} selected source(s).",
                difficulty=diff,
                question_count=q_count,
                source_passages=chunks,
                user_prefs=prefs,
                language=language,
            )
            content["practice_mode_allowed"] = bool(req.config.get("practice_mode", False))

        elif req.tool_type == "infographic":
            content = generateInfographicStructure(chunks, req.config, user_prefs=prefs)

        elif req.tool_type == "data_table":
            content = extractStructuredTable(chunks, req.config, user_prefs=prefs)

        content["language"] = language
        final_title = (req.title or content.get("title") or f"BRAINOVA Studio: {req.tool_type}").strip()
        conn.execute(
            """
            INSERT INTO studio_outputs (
                id, user_id, tool_type, title, source_ids_json, config_json,
                content_json, audio_file_path, video_file_path, language, duration_label, style_label,
                status, is_user_edited, error_message, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', 0, '', ?, ?)
            """,
            (
                output_id,
                uid,
                req.tool_type,
                final_title,
                json.dumps(req.source_ids),
                json.dumps(req.config),
                json.dumps(content),
                audio_path,
                video_path,
                language,
                duration_label,
                style_label,
                now,
                now,
            ),
        )

        # If flashcards tool, persist individual flashcards in `flashcards` table with status = 'new'
        if req.tool_type == "flashcards":
            for card in content.get("cards", []):
                conn.execute(
                    """
                    INSERT INTO flashcards (
                        id, user_id, studio_output_id, topic_id, front, back, hint, category,
                        status, review_count, ease_factor, interval_days, next_due_at, last_reviewed_at,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, 'new', 0, 2.5, 0, ?, '', ?, ?)
                    """,
                    (
                        new_id("fc"),
                        uid,
                        output_id,
                        card["front"],
                        card["back"],
                        card.get("hint", ""),
                        card.get("category", "Core"),
                        now,
                        now,
                        now,
                    ),
                )

        log_activity(conn, uid, f"studio_{req.tool_type}", "studio_output", output_id, f"Generated {final_title}", 6)
        saved_row = conn.execute("SELECT * FROM studio_outputs WHERE id = ? AND user_id = ?", (output_id, uid)).fetchone()
        formatted = _format_studio_output(conn, saved_row)

    return {"output": formatted}


@app.get("/api/studio/outputs/{output_id}")
def get_studio_output(
    output_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db() as conn:
        row = conn.execute("SELECT * FROM studio_outputs WHERE id = ? AND user_id = ?", (output_id, uid)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Studio output not found or access denied.")
        formatted = _format_studio_output(conn, row)
    return {"output": formatted}


@app.put("/api/studio/outputs/{output_id}")
def update_studio_output(
    output_id: str,
    req: StudioUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        row = conn.execute("SELECT * FROM studio_outputs WHERE id = ? AND user_id = ?", (output_id, uid)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Studio output not found.")
        new_title = req.title.strip() if req.title else row["title"]
        new_content_json = json.dumps(req.content) if req.content is not None else row["content_json"]
        edited_flag = 1 if req.content is not None else row["is_user_edited"]

        conn.execute(
            """
            UPDATE studio_outputs
            SET title = ?, content_json = ?, is_user_edited = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (new_title, new_content_json, edited_flag, utc_now(), output_id, uid),
        )
        updated_row = conn.execute("SELECT * FROM studio_outputs WHERE id = ? AND user_id = ?", (output_id, uid)).fetchone()
        formatted = _format_studio_output(conn, updated_row)
    return {"output": formatted}


@app.post("/api/studio/outputs/{output_id}/regenerate")
def regenerate_studio_output(
    output_id: str,
    req: RegenerateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        row = conn.execute("SELECT * FROM studio_outputs WHERE id = ? AND user_id = ?", (output_id, uid)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Studio output not found.")
        if row.get("is_user_edited") and not req.confirm_overwrite:
            raise HTTPException(
                status_code=409,
                detail="You have personal edits on this Studio output. Please confirm overwrite before regenerating.",
            )
        source_ids = json.loads(row.get("source_ids_json") or "[]")
        config = json.loads(row.get("config_json") or "{}")
        language = normalize_language(row.get("language") or config.get("language") or "English")
        config["language"] = language
        tool_type = row["tool_type"]
        prefs = ensure_user_preferences(conn, uid)
        chunks = retrieve_relevant_chunks(conn, uid, source_ids, row["title"], top_k=10)
        openai_key = (prefs.get("openai_api_key") or os.environ.get("OPENAI_API_KEY") or "").strip()

        audio_path = row.get("audio_file_path", "")
        video_path = row.get("video_file_path", "")
        if tool_type == "audio_overview":
            content = generateAudioScript(chunks, config, user_prefs=prefs)
            audio_meta = synthesize_podcast_audio(output_id, content["dialogue"], openai_api_key=openai_key, language=language)
            content["audio"] = audio_meta
            audio_path = audio_meta["file_path"]
        elif tool_type == "slide_deck":
            content = generateSlideDeck(chunks, config, user_prefs=prefs)
        elif tool_type == "video_overview":
            content = generateVideoStoryboard(chunks, config, user_prefs=prefs)
            video_meta = synthesize_educational_video(
                output_id=output_id,
                storyboard=content,
                language=language,
                duration_label=str(config.get("duration") or "3–5 minutes"),
                style_label=str(config.get("style") or "Concept Breakdown & Architecture"),
                openai_api_key=openai_key,
            )
            content["video"] = video_meta
            video_path = video_meta["file_path"]
            audio_path = video_meta["audio_file_path"]
        elif tool_type == "mind_map":
            content = generateMindMap(chunks, config, user_prefs=prefs)
        elif tool_type == "study_guide":
            content = generateStudyGuide(chunks, config, user_prefs=prefs)
        elif tool_type == "flashcards":
            content = generateFlashcards(chunks, config, user_prefs=prefs)
        elif tool_type == "quiz":
            content = generateTopicQuiz(
                topic_title=row["title"],
                difficulty=config.get("difficulty", "Intermediate"),
                question_count=int(config.get("question_count") or 20),
                source_passages=chunks,
                user_prefs=prefs,
                language=language,
            )
        elif tool_type == "infographic":
            content = generateInfographicStructure(chunks, config, user_prefs=prefs)
        else:
            content = extractStructuredTable(chunks, config, user_prefs=prefs)

        conn.execute(
            """
            UPDATE studio_outputs
            SET content_json = ?, audio_file_path = ?, video_file_path = ?, is_user_edited = 0, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (json.dumps(content), audio_path, video_path, utc_now(), output_id, uid),
        )
        updated_row = conn.execute("SELECT * FROM studio_outputs WHERE id = ? AND user_id = ?", (output_id, uid)).fetchone()
        formatted = _format_studio_output(conn, updated_row)
    return {"output": formatted}


@app.delete("/api/studio/outputs/{output_id}")
def delete_studio_output(
    output_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Deletes ONLY the selected AI Studio output; never deletes original source documents."""
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        row = conn.execute("SELECT * FROM studio_outputs WHERE id = ? AND user_id = ?", (output_id, uid)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Studio output not found.")
        audio_path = row.get("audio_file_path", "")
        video_path = row.get("video_file_path", "")
        conn.execute("DELETE FROM studio_outputs WHERE id = ? AND user_id = ?", (output_id, uid))

    for p in (audio_path, video_path):
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    return {"ok": True, "deleted_id": output_id}


@app.get("/api/studio/audio/{filename}")
def stream_studio_audio(
    filename: str,
    playback_token: Optional[str] = Query(default=None),
) -> FileResponse:
    safe_name = os.path.basename(filename)
    if not safe_name.lower().endswith(".wav") or not playback_token:
        raise HTTPException(status_code=401, detail="A valid audio playback link is required.")

    token_id = safe_name[:-4]
    user_id = decode_audio_playback_token(playback_token, token_id)
    base_output_id = token_id[:-4] if token_id.endswith("_vid") else token_id
    with get_db() as conn:
        output = conn.execute(
            "SELECT audio_file_path FROM studio_outputs WHERE id = ? AND user_id = ? AND tool_type IN ('audio_overview', 'video_overview')",
            (base_output_id, user_id),
        ).fetchone()

    expected_path = os.path.realpath(os.path.join(AUDIO_DIR, safe_name))
    stored_path = os.path.realpath(output.get("audio_file_path") or "") if output else ""
    if not output or stored_path != expected_path or not os.path.isfile(expected_path):
        raise HTTPException(status_code=404, detail="Audio file not found.")
    return FileResponse(expected_path, media_type="audio/wav", filename=safe_name)


@app.get("/api/studio/video/{filename}")
def stream_studio_video(
    filename: str,
    playback_token: Optional[str] = Query(default=None),
) -> FileResponse:
    safe_name = os.path.basename(filename)
    if not safe_name.lower().endswith(".mp4") or not playback_token:
        raise HTTPException(status_code=401, detail="A valid video playback link is required.")

    output_id = safe_name[:-4]
    user_id = decode_video_playback_token(playback_token, output_id)
    with get_db() as conn:
        output = conn.execute(
            "SELECT video_file_path FROM studio_outputs WHERE id = ? AND user_id = ? AND tool_type = 'video_overview'",
            (output_id, user_id),
        ).fetchone()

    expected_path = os.path.realpath(os.path.join(VIDEOS_DIR, safe_name))
    stored_path = os.path.realpath(output.get("video_file_path") or "") if output else ""
    if not output or stored_path != expected_path or not os.path.isfile(expected_path):
        raise HTTPException(status_code=404, detail="Video file not found.")
    return FileResponse(expected_path, media_type="video/mp4", filename=safe_name)


@app.post("/api/studio/outputs/{output_id}/quiz-submit")
def submit_studio_quiz(
    output_id: str,
    req: QuizSubmissionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        row = conn.execute("SELECT * FROM studio_outputs WHERE id = ? AND user_id = ? AND tool_type = 'quiz'", (output_id, uid)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Studio Quiz not found.")
        content = json.loads(row.get("content_json") or "{}")
        questions = content.get("questions", [])
        attempt = _grade_and_record_quiz_submission(
            conn=conn,
            user_id=uid,
            questions=questions,
            submitted_answers=req.answers,
            duration_seconds=req.duration_seconds,
            topic_title=row["title"],
            studio_output_id=output_id,
        )
    return {"attempt": attempt}


# --- FLASHCARD CRUD & SPACED REPETITION REVIEW ---
@app.post("/api/flashcards")
def create_flashcard(
    req: FlashcardCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    fc_id = new_id("fc")
    now = utc_now()
    with get_db(commit=True) as conn:
        if req.studio_output_id:
            deck = conn.execute("SELECT id FROM studio_outputs WHERE id = ? AND user_id = ?", (req.studio_output_id, uid)).fetchone()
            if not deck:
                raise HTTPException(status_code=404, detail="Flashcard deck not found.")
        conn.execute(
            """
            INSERT INTO flashcards (
                id, user_id, studio_output_id, topic_id, front, back, hint, category,
                status, review_count, ease_factor, interval_days, next_due_at, last_reviewed_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new', 0, 2.5, 0, ?, '', ?, ?)
            """,
            (fc_id, uid, req.studio_output_id, req.topic_id, req.front.strip(), req.back.strip(), req.hint.strip(), req.category.strip(), now, now, now),
        )
        card = conn.execute("SELECT * FROM flashcards WHERE id = ? AND user_id = ?", (fc_id, uid)).fetchone()
    return {"flashcard": card}


@app.put("/api/flashcards/{card_id}")
def update_or_review_flashcard(
    card_id: str,
    req: FlashcardUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        card = conn.execute("SELECT * FROM flashcards WHERE id = ? AND user_id = ?", (card_id, uid)).fetchone()
        if not card:
            raise HTTPException(status_code=404, detail="Flashcard not found.")

        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        new_status = req.status if req.status in ("new", "learning", "review", "known") else card["status"]
        rev_count = card["review_count"]
        interval = card["interval_days"]
        ease = card["ease_factor"]
        next_due = card["next_due_at"]
        last_rev = card["last_reviewed_at"]

        if req.status in ("learning", "review", "known"):
            rev_count += 1
            last_rev = now_iso
            if req.status == "known":
                interval = max(1, (interval * 2) if interval > 0 else 3)
                ease = min(3.0, ease + 0.1)
                next_due = (now_dt + timedelta(days=interval)).isoformat()
            elif req.status == "learning":
                interval = 1
                next_due = (now_dt + timedelta(days=1)).isoformat()
            else:  # 'review' (needs review soon)
                interval = 0
                ease = max(1.3, ease - 0.2)
                next_due = (now_dt + timedelta(hours=4)).isoformat()

        conn.execute(
            """
            UPDATE flashcards
            SET front = ?, back = ?, hint = ?, category = ?, status = ?,
                review_count = ?, ease_factor = ?, interval_days = ?,
                next_due_at = ?, last_reviewed_at = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                req.front.strip() if req.front else card["front"],
                req.back.strip() if req.back else card["back"],
                req.hint.strip() if req.hint is not None else card["hint"],
                req.category.strip() if req.category else card["category"],
                new_status,
                rev_count,
                ease,
                interval,
                next_due,
                last_rev,
                now_iso,
                card_id,
                uid,
            ),
        )
        updated = conn.execute("SELECT * FROM flashcards WHERE id = ? AND user_id = ?", (card_id, uid)).fetchone()
    return {"flashcard": updated}


@app.delete("/api/flashcards/{card_id}")
def delete_flashcard(
    card_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = current_user["id"]
    with get_db(commit=True) as conn:
        card = conn.execute("SELECT id FROM flashcards WHERE id = ? AND user_id = ?", (card_id, uid)).fetchone()
        if not card:
            raise HTTPException(status_code=404, detail="Flashcard not found.")
        conn.execute("DELETE FROM flashcards WHERE id = ? AND user_id = ?", (card_id, uid))
    return {"ok": True, "deleted_id": card_id}


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
            JOIN roadmaps r ON r.id = t.roadmap_id
            JOIN roadmap_phases p ON p.id = t.phase_id
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
            LEFT JOIN roadmap_topics t ON t.id = n.topic_id
            LEFT JOIN roadmaps r ON r.id = n.roadmap_id
            WHERE n.user_id = ?
            ORDER BY n.is_pinned DESC, n.updated_at DESC
            """,
            (uid,),
        ).fetchall()
        raw_tutorials = conn.execute(
            """
            SELECT tut.*, t.title AS topic_title, r.title AS roadmap_title
            FROM topic_tutorials tut
            JOIN roadmap_topics t ON t.id = tut.topic_id
            JOIN roadmaps r ON r.id = tut.roadmap_id
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
            JOIN roadmap_topics t ON t.id = rd.topic_id
            JOIN roadmaps r ON r.id = rd.roadmap_id
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

        for std in conn.execute("SELECT id, title, tool_type FROM studio_outputs WHERE user_id = ?", (uid,)).fetchall():
            if query in std["title"].lower() or query in std["tool_type"].lower():
                results.append({"type": "AI Studio Library", "title": std["title"], "subtitle": std["tool_type"].replace("_", " ").title(), "link": f"/studio-library?open={std['id']}"})

        for nt in conn.execute("SELECT id, title, content, topic_id, roadmap_id FROM personal_notes WHERE user_id = ?", (uid,)).fetchall():
            if query in nt["title"].lower() or query in nt["content"].lower():
                link = f"/roadmaps/{nt['roadmap_id']}?expand={nt['topic_id']}" if nt["roadmap_id"] and nt["topic_id"] else "/resources"
                results.append({"type": "Note", "title": nt["title"], "subtitle": nt["content"][:80], "link": link})

    return {"results": results[:20]}


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

