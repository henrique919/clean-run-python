from __future__ import annotations

from app.models import Settings
from app.repositories.base import CleanRunRepository


class SettingsLockError(ValueError):
    pass


def get_settings(repository: CleanRunRepository) -> Settings:
    return repository.snapshot().settings


def validate_settings_update(current: Settings, proposed: Settings) -> None:
    for project, current_config in current.project_configs.items():
        proposed_config = proposed.project_configs.get(project)
        if not proposed_config or not current_config.code_prefix_locked:
            continue
        if proposed_config.code_prefix != current_config.code_prefix:
            raise SettingsLockError(f"{project} code prefix is locked and cannot be changed.")
        if not proposed_config.code_prefix_locked:
            raise SettingsLockError(f"{project} code prefix is locked and cannot be unlocked.")


def update_settings(repository: CleanRunRepository, settings: Settings) -> Settings:
    validate_settings_update(repository.snapshot().settings, settings)
    return repository.update_settings(settings)
