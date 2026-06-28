"""Compatibility launcher for Render/manual starts.

The real ASGI app lives at app.main:app.
"""

import os

import uvicorn


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
