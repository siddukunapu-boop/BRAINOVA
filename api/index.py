"""Vercel Python Serverless Function entrypoint for the BRAINOVA FastAPI backend."""

import os
import sys
import traceback

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

os.environ["VERCEL"] = "1"
os.environ.setdefault("BRAINOVA_DATA_DIR", "/tmp/brainova_data")
os.environ.setdefault("AETHER_DB_PATH", "/tmp/brainova_data/aetherlearn.db")
os.environ.setdefault("BRAINOVA_DISABLE_SCHEDULER", "1")

try:
    from backend.database import get_db, init_db
    from backend.main import app as app
    from backend.tech_pulse import seed_official_sources

    try:
        init_db()
        with get_db(commit=True) as _conn:
            seed_official_sources(_conn)
    except Exception:
        pass
except Exception as _startup_exc:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    _err_msg = f"{type(_startup_exc).__name__}: {_startup_exc}"
    _err_tb = traceback.format_exc()
    app = FastAPI(title="BRAINOVA Startup Diagnostic")

    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    def _startup_error_fallback(full_path: str):
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"Backend startup error: {_err_msg}",
                "path": full_path,
                "traceback": _err_tb.splitlines()[-5:],
            },
        )
