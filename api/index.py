"""Vercel Python Serverless Function entrypoint for the BRAINOVA FastAPI backend."""

import os

os.environ.setdefault("BRAINOVA_DISABLE_SCHEDULER", "1")

from backend.database import get_db, init_db
from backend.main import app
from backend.tech_pulse import seed_official_sources

try:
    init_db()
    with get_db(commit=True) as _conn:
        seed_official_sources(_conn)
except Exception:
    pass
