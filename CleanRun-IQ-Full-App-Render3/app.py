"""Compatibility launcher for older Render service settings.

The production app lives at the repository root in app.main:app. This file keeps
older Render services that start CleanRun-IQ-Full-App-Render3/app.py aligned
with the secured FastAPI application instead of serving the legacy demo app.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

print(
    "[CleanRun boot] "
    f"cwd={Path.cwd()} "
    f"repo_root={REPO_ROOT} "
    f"APP_ENV={os.getenv('APP_ENV') or ''} "
    f"CLEANRUN_ENV={os.getenv('CLEANRUN_ENV') or ''} "
    f"CLEANRUN_STORAGE={os.getenv('CLEANRUN_STORAGE') or ''} "
    f"SUPABASE_URL={'set' if os.getenv('SUPABASE_URL') else 'missing'} "
    f"SUPABASE_PUBLISHABLE_KEY={'set' if os.getenv('SUPABASE_PUBLISHABLE_KEY') else 'missing'} "
    f"SUPABASE_JWT_SECRET={'set' if os.getenv('SUPABASE_JWT_SECRET') else 'missing'} "
    f"SUPABASE_SERVICE_ROLE_KEY={'set' if os.getenv('SUPABASE_SERVICE_ROLE_KEY') else 'missing'}",
    flush=True,
)

from app.main import app  # noqa: E402


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
