"""Vercel Python Serverless Function entrypoint for the BRAINOVA FastAPI backend."""

import os
import sys
import traceback
from fastapi import FastAPI
from fastapi.responses import JSONResponse

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import tempfile

os.environ["VERCEL"] = "1"
_default_tmp_dir = "/tmp/brainova_data" if os.name != "nt" else os.path.join(tempfile.gettempdir(), "brainova_data")
os.environ.setdefault("BRAINOVA_DATA_DIR", _default_tmp_dir)
os.environ.setdefault("AETHER_DB_PATH", os.path.join(_default_tmp_dir, "aetherlearn.db"))
os.environ.setdefault("BRAINOVA_DISABLE_SCHEDULER", "1")

_loaded_app = None
_startup_err_msg = ""
_startup_err_tb = ""

try:
    from backend.main import app as _backend_app

    _loaded_app = _backend_app
except Exception as _startup_exc:
    _startup_err_msg = f"{type(_startup_exc).__name__}: {_startup_exc}"
    _startup_err_tb = traceback.format_exc()
    _fallback_app = FastAPI(title="BRAINOVA Startup Diagnostic")

    @_fallback_app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    def _startup_error_fallback(full_path: str):
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"Backend startup error: {_startup_err_msg}",
                "path": full_path,
                "traceback": _startup_err_tb.splitlines()[-8:],
            },
        )

    _loaded_app = _fallback_app

app = _loaded_app
