from __future__ import annotations

from app.models import ItemCreate, ItemType, ItemUpdate


class ValidationError(ValueError):
    pass


def _blank(value: str | None) -> bool:
    return not value or not value.strip()


def validate_capture(payload: ItemCreate, *, for_issue: bool = False) -> None:
    """Strict CleanRun IQ capture validation.

    Defects and Client Defects need enough context to be actionable:
    building + unit/area + description + original photo.
    Incomplete Works can save without a photo, but the UI warns first.
    """
    if _blank(payload.project):
        raise ValidationError("Select a project.")
    if _blank(payload.building):
        raise ValidationError("Select a building.")
    if _blank(payload.unit):
        raise ValidationError("Select a unit / area.")
    if _blank(payload.description):
        raise ValidationError("Add a short description.")

    if payload.type in {ItemType.DEFECT, ItemType.CLIENT} and len(payload.original_photos) == 0:
        label = "Client Defect" if payload.type == ItemType.CLIENT else "Defect"
        raise ValidationError(f"A {label} requires at least one original photo.")

    if payload.type == ItemType.CLIENT and _blank(payload.raised_by):
        raise ValidationError("Client Defects require a Raised By / source.")

    if for_issue:
        if _blank(payload.trade):
            raise ValidationError("Issue Now requires a trade.")
        if _blank(payload.subcontractor):
            raise ValidationError("Issue Now requires a subcontractor.")


def validate_update(payload: ItemUpdate) -> None:
    if payload.description is not None and _blank(payload.description):
        raise ValidationError("Description cannot be blank.")
    if payload.building is not None and _blank(payload.building):
        raise ValidationError("Building cannot be blank.")
    if payload.unit is not None and _blank(payload.unit):
        raise ValidationError("Unit / Area cannot be blank.")
