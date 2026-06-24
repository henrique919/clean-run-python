"""Business services translating the Rork AppStore workflow into Python."""

from __future__ import annotations

from dataclasses import dataclass

from cleanrun_iq.models import (
    AuditEvent,
    CloseoutEvidence,
    Comment,
    CreateItemInput,
    InspectionEvent,
    IssueEvent,
    Item,
    ItemStatus,
    RectificationEvidence,
    SyncState,
    UpdateItemInput,
)
from cleanrun_iq.store import JsonStore
from cleanrun_iq.utils import make_id, next_code, now_iso


class WorkflowError(ValueError):
    """Raised when a status transition is invalid."""


@dataclass(slots=True)
class CleanRunService:
    """Application service containing item workflow operations.

    Args:
        store: Data store instance.
        online: Whether operations should be marked synced or pending.
    """

    store: JsonStore
    online: bool = True

    def create_item(self, payload: CreateItemInput) -> Item:
        """Create an item.

        Args:
            payload: Item creation payload.

        Returns:
            Created item.

        Raises:
            ValueError: If required fields are invalid.
        """
        if not payload.description.strip():
            raise ValueError("description is required")
        now = now_iso()
        items = self.store.get_items()
        code = next_code(items, payload.type)
        item = Item(
            **payload.model_dump(by_alias=True),
            id=make_id(),
            code=code,
            createdAt=now,
            updatedAt=now,
            rectificationEvidence=[],
            closeoutEvidence=[],
            comments=[],
            issueHistory=[],
            inspectionHistory=[],
            auditEvents=[AuditEvent(at=now, action=f"Created ({code})" + (" via Voice-to-Note" if payload.voice_transcript else ""), by=payload.created_by)],
            sync=SyncState.SYNCED if self.online else SyncState.PENDING,
        )
        self.store.save_items([item, *items])
        return item

    def update_item(self, item_id: str, payload: UpdateItemInput, by: str | None = None) -> Item:
        """Edit item details without changing evidence or workflow history.

        Args:
            item_id: Item ID.
            payload: Update payload.
            by: Actor name.

        Returns:
            Updated item.
        """
        updates = payload.model_dump(exclude_none=True)
        now = now_iso()

        def mutate(item: Item) -> Item:
            data = item.model_dump(by_alias=True)
            data.update(updates)
            if updates.get("type") != "client" and "type" in updates:
                data.pop("raisedBy", None)
            data["updatedAt"] = now
            data["auditEvents"] = [*item.audit_events, AuditEvent(at=now, action="Item details edited", by=by)]
            data["sync"] = SyncState.SYNCED if self.online else SyncState.PENDING
            return Item.model_validate(data)

        return self.store.patch_item(item_id, mutate)

    def issue_item(self, item_id: str, to: str, by: str | None = None, note: str | None = None, reissue: bool = False) -> Item:
        """Issue item to a subcontractor.

        Args:
            item_id: Item ID.
            to: Subcontractor name.
            by: Actor name.
            note: Optional note.
            reissue: Whether this is a re-issue.

        Returns:
            Updated item.
        """
        now = now_iso()
        event = IssueEvent(at=now, to=to, by=by, note=note, reissue=reissue)

        def mutate(item: Item) -> Item:
            return self._audit(item.model_copy(update={
                "subcontractor": to,
                "status": ItemStatus.ISSUED,
                "issued_at": now,
                "issue_history": [*item.issue_history, event],
            }), f"{'Re-issued' if reissue else 'Issued'} to {to}", by, note)

        return self.store.patch_item(item_id, mutate)

    def mark_in_progress(self, item_id: str, by: str) -> Item:
        """Mark an issued item as in progress."""
        now = now_iso()
        return self.store.patch_item(
            item_id,
            lambda item: self._audit(item.model_copy(update={"status": ItemStatus.IN_PROGRESS, "in_progress_at": now}), "Marked in progress", by),
        )

    def add_rectification_evidence(self, item_id: str, by: str, photo: str | None = None, comment: str | None = None) -> Item:
        """Add rectification evidence.

        Raises:
            ValueError: If neither photo nor comment is supplied.
        """
        if not photo and not comment:
            raise ValueError("photo or comment is required")
        now = now_iso()
        evidence = RectificationEvidence(id=make_id(), photo=photo, comment=comment, by=by, at=now)

        def mutate(item: Item) -> Item:
            next_item = item.model_copy(update={"rectification_evidence": [*item.rectification_evidence, evidence]})
            return self._audit(next_item, "Rectification evidence added", by, comment)

        return self.store.patch_item(item_id, mutate)

    def mark_ready_for_review(self, item_id: str, by: str) -> Item:
        """Move item to ready for review."""
        now = now_iso()
        return self.store.patch_item(
            item_id,
            lambda item: self._audit(item.model_copy(update={"status": ItemStatus.READY_FOR_REVIEW, "ready_for_review_at": now}), "Marked ready for review", by),
        )

    def start_inspection(self, item_id: str, by: str) -> Item:
        """Move item into under-inspection status."""
        now = now_iso()
        event = InspectionEvent(at=now, by=by, action="started")
        return self.store.patch_item(
            item_id,
            lambda item: self._audit(
                item.model_copy(update={"status": ItemStatus.UNDER_INSPECTION, "under_inspection_at": now, "inspection_history": [*item.inspection_history, event]}),
                "Inspection started",
                by,
            ),
        )

    def reject_item(self, item_id: str, by: str, reason: str) -> Item:
        """Reject an item under inspection."""
        if not reason.strip():
            raise ValueError("reason is required")
        now = now_iso()
        event = InspectionEvent(at=now, by=by, action="rejected", reason=reason)
        return self.store.patch_item(
            item_id,
            lambda item: self._audit(
                item.model_copy(update={"status": ItemStatus.REJECTED, "rejection_reason": reason, "inspection_history": [*item.inspection_history, event]}),
                "Rejected during inspection",
                by,
                reason,
            ),
        )

    def close_with_evidence(self, item_id: str, by: str, role: str, photo: str | None = None, note: str | None = None, confirmation: str | None = None) -> Item:
        """Close an item with site-team closeout evidence.

        Args:
            item_id: Item ID.
            by: Actor name.
            role: Actor role.
            photo: Optional closeout photo.
            note: Optional note.
            confirmation: Optional confirmation.

        Returns:
            Closed item.
        """
        now = now_iso()
        evidence = CloseoutEvidence(id=make_id(), photo=photo, by=by, role=role, note=note, confirmation=confirmation, at=now)
        event = InspectionEvent(at=now, by=by, action="accepted")

        def mutate(item: Item) -> Item:
            final_status = ItemStatus.COMPLETE if item.type == "incomplete" else ItemStatus.CLOSED
            next_item = item.model_copy(update={
                "status": final_status,
                "closed_at": now,
                "closeout_evidence": [*item.closeout_evidence, evidence],
                "inspection_history": [*item.inspection_history, event],
            })
            return self._audit(next_item, "Closed with evidence", by, note)

        return self.store.patch_item(item_id, mutate)

    def add_comment(self, item_id: str, text: str, by: str) -> Item:
        """Add a comment to an item."""
        if not text.strip():
            raise ValueError("comment text is required")
        now = now_iso()
        comment = Comment(id=make_id(), text=text, by=by, at=now)
        return self.store.patch_item(
            item_id,
            lambda item: self._audit(item.model_copy(update={"comments": [*item.comments, comment]}), "Comment added", by, text),
        )

    def _audit(self, item: Item, action: str, by: str | None = None, note: str | None = None) -> Item:
        now = now_iso()
        event = AuditEvent(at=now, action=action, by=by, note=note)
        return item.model_copy(update={
            "updated_at": now,
            "audit_events": [*item.audit_events, event],
            "sync": SyncState.SYNCED if self.online else SyncState.PENDING,
        })
