from __future__ import annotations

from app.models import Settings
from app.repositories.base import CleanRunRepository


def get_settings(repository: CleanRunRepository) -> Settings:
    return repository.snapshot().settings


def update_settings(repository: CleanRunRepository, settings: Settings) -> Settings:
    return repository.update_settings(settings)
