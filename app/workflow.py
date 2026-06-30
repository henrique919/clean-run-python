from __future__ import annotations

from app.models import STATUS_LABEL, Item, ItemStatus


class WorkflowError(Exception):
    """Raised when an item action is not valid for the current workflow status."""


ISSUE_FROM = {ItemStatus.OPEN, ItemStatus.REJECTED}
IN_PROGRESS_FROM = {ItemStatus.ISSUED, ItemStatus.REJECTED}
READY_FROM = {ItemStatus.IN_PROGRESS}
INSPECTION_FROM = {ItemStatus.READY_FOR_REVIEW}
REJECT_FROM = {ItemStatus.READY_FOR_REVIEW, ItemStatus.UNDER_INSPECTION}
CLOSE_FROM = {ItemStatus.UNDER_INSPECTION}
RECTIFICATION_FROM = {ItemStatus.ISSUED, ItemStatus.IN_PROGRESS, ItemStatus.REJECTED}


def require_status(item: Item, allowed: set[ItemStatus], *, action: str) -> None:
    if item.status not in allowed:
        current = STATUS_LABEL.get(item.status, str(item.status))
        raise WorkflowError(f"Cannot {action} while item is {current}.")
