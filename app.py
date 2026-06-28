"""Compatibility launcher for Render/manual starts.

The real ASGI app lives at app.main:app. Import it directly here so Render
startup does not depend on Uvicorn resolving a dotted module path from whatever
working directory the service happens to use.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


REPO_ROOT = Path(__file__).resolve().parent
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
