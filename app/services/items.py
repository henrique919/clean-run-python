from __future__ import annotations

from typing import Any

from app.models import Item, ItemCreate, ItemUpdate
from app.repositories.base import CleanRunRepository


def list_items(repository: CleanRunRepository, *, project: str | None = None, status: str | None = None) -> list[Item]:
    return repository.list_items(project=project, status=status)


def get_item(repository: CleanRunRepository, item_id: str) -> Item:
    return repository.get_item(item_id)


def create_item(
    repository: CleanRunRepository,
    payload: ItemCreate,
    *,
    issue_now: bool = False,
    actor: dict[str, Any] | None = None,
) -> Item:
    return repository.create_item(payload, issue_now=issue_now, actor=actor)


def update_item(
    repository: CleanRunRepository,
    item_id: str,
    payload: ItemUpdate,
    *,
    by: str | None = None,
    actor: dict[str, Any] | None = None,
) -> Item:
    return repository.update_item(item_id, payload, by=by, actor=actor)
