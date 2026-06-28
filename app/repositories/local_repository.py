from __future__ import annotations

from pathlib import Path

from app.store import CleanRunStore


class LocalCleanRunRepository(CleanRunStore):
    """Local JSON repository for development and demos only."""

    def __init__(self, path: Path | None = None) -> None:
        super().__init__(path=path) if path else super().__init__()
