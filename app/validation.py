from __future__ import annotations

from app.models import CloseoutEvidence, Item, ItemCreate, ItemType, ItemUpdate, RectificationEvidence


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


def validate_update_merged(item: Item, payload: ItemUpdate) -> None:
    validate_update(payload)
    merged = item.model_copy(update=payload.model_dump(exclude_unset=True, exclude={"append_original_photos"}))
    if payload.append_original_photos:
        merged = merged.model_copy(update={"original_photos": [*item.original_photos, *payload.append_original_photos]})
    if merged.type in {ItemType.DEFECT, ItemType.CLIENT} and len(merged.original_photos) == 0:
        label = "Client Defect" if merged.type == ItemType.CLIENT else "Defect"
        raise ValidationError(f"A {label} requires at least one original photo.")
    if merged.type == ItemType.CLIENT and _blank(merged.raised_by):
        raise ValidationError("Client Defects require a Raised By / source.")


def validate_issue_target(*, to: str, item: Item) -> None:
    target = (to or item.subcontractor or "").strip()
    if not target:
        raise ValidationError("Issue requires a subcontractor.")
    if _blank(item.trade):
        raise ValidationError("Issue requires a trade.")


def validate_rectification(evidence: RectificationEvidence) -> None:
    if _blank(evidence.photo) and _blank(evidence.comment):
        raise ValidationError("Rectification requires a photo or comment.")


def validate_ready_for_review(item: Item) -> None:
    if not item.rectification_evidence:
        raise ValidationError("Mark ready for review requires rectification evidence.")


def validate_reject_reason(reason: str) -> None:
    if _blank(reason):
        raise ValidationError("Rejection reason is required.")


def validate_closeout(item: Item, evidence: CloseoutEvidence) -> None:
    if item.type == ItemType.INCOMPLETE:
        return
    if _blank(evidence.photo):
        raise ValidationError("Closeout requires a photo for defects and client defects.")
    if _blank(evidence.confirmation):
        raise ValidationError("Closeout requires supervisor confirmation.")
