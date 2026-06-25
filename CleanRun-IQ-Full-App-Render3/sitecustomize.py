from pathlib import Path
import re
import sys
import textwrap


def find_app_path() -> Path | None:
    candidates = []

    if sys.argv and sys.argv[0]:
        candidates.append(Path(sys.argv[0]).resolve())

    candidates.append(Path.cwd() / "app.py")
    candidates.append(Path.cwd() / "CleanRun-IQ-Full-App-Render3" / "app.py")

    for candidate in candidates:
        if candidate.name == "app.py" and candidate.exists():
            return candidate

    return None


HELPER_BLOCK = textwrap.dedent(
    '''
    def use_supabase_storage() -> bool:
        return os.environ.get("CLEANRUN_STORAGE", "local").lower() == "supabase"


    def _photo_looks_like_uploadable_base64(value: str) -> bool:
        if not isinstance(value, str) or not value.strip():
            return False

        value = value.strip()

        if value.startswith("data:image/"):
            return True

        if value.startswith("http://") or value.startswith("https://") or value.startswith("seed://"):
            return False

        return value.startswith(("/9j/", "9j/", "iVBOR", "UklGR"))


    def _split_photo_base64(photo: str) -> tuple[str, str]:
        value = photo.strip()

        if value.startswith("data:"):
            header, encoded = value.split(",", 1)
            mime_type = header.split(";")[0].replace("data:", "") or "image/jpeg"
            return mime_type, encoded

        if value.startswith("iVBOR"):
            return "image/png", value

        if value.startswith("UklGR"):
            return "image/webp", value

        return "image/jpeg", value


    def upload_data_url_to_supabase(data_url: str, folder: str = "evidence") -> str:
        if not _photo_looks_like_uploadable_base64(data_url):
            return data_url

        if not use_supabase_storage():
            return data_url

        mime_type, encoded = _split_photo_base64(data_url)
        extension = mimetypes.guess_extension(mime_type) or ".jpg"
        if extension == ".jpe":
            extension = ".jpg"

        raw_bytes = base64.b64decode(encoded, validate=False)

        max_bytes = int(os.environ.get("CLEANRUN_MAX_IMAGE_BYTES", "8000000"))
        if len(raw_bytes) > max_bytes:
            raise ValueError("uploaded image is too large")

        bucket = os.environ.get("CLEANRUN_STORAGE_BUCKET", "cleanrun-evidence")
        now_path = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        file_path = f"{folder}/{now_path}/{uuid.uuid4().hex}{extension}"

        client = get_supabase_client()
        client.storage.from_(bucket).upload(
            path=file_path,
            file=raw_bytes,
            file_options={
                "content-type": mime_type,
                "upsert": "false",
            },
        )
        return client.storage.from_(bucket).get_public_url(file_path)


    def maybe_upload_photo(photo: Any, folder: str = "evidence") -> Any:
        if not photo or not isinstance(photo, str):
            return photo

        if not _photo_looks_like_uploadable_base64(photo):
            return photo

        return upload_data_url_to_supabase(photo, folder=folder)


    def upload_photo_list(photos: Any, folder: str = "evidence") -> list[Any]:
        if not photos:
            return []

        if not isinstance(photos, list):
            return []

        return [maybe_upload_photo(photo, folder=folder) for photo in photos]
    '''
).strip()


CREATE_ITEM_BLOCK = textwrap.dedent(
    '''
    def create_item(payload: dict[str, Any]) -> dict[str, Any]:
        payload = copy.deepcopy(payload)

        required = ("type", "project", "description", "dueDate")
        if any(not payload.get(field) for field in required):
            raise ValueError("type, project, description and dueDate are required")
        if payload["type"] not in CODE_PREFIX:
            raise ValueError("invalid item type")
        if payload["type"] in {"defect", "client"} and not payload.get("originalPhotos"):
            raise ValueError("defects and client defects require at least one original photo")

        payload["originalPhotos"] = upload_photo_list(
            payload.get("originalPhotos", []),
            folder=f"items/original/{payload.get('project', 'unknown')}",
        )

        at = now_iso()
        code = next_code(payload["type"])
        item = {
            "id": new_id(), "code": code, "status": payload.get("status", "open"),
            "createdAt": at, "updatedAt": at, "rectificationEvidence": [],
            "closeoutEvidence": [], "comments": [], "issueHistory": [],
            "inspectionHistory": [], "auditEvents": [], "sync": "synced",
            **payload,
        }
        item["auditEvents"] = [{"at": at, "action": f"Created ({code})" + (" via Voice-to-Note" if payload.get("voiceTranscript") else ""), "by": payload.get("createdBy")}]
        STATE["items"].insert(0, item)
        return item
    '''
).strip()


APPLY_ACTION_BLOCK = textwrap.dedent(
    '''
    def apply_action(item: dict[str, Any], action: str, body: dict[str, Any]) -> None:
        body = copy.deepcopy(body)

        if body.get("photo"):
            body["photo"] = maybe_upload_photo(
                body.get("photo"),
                folder=f"items/{item.get('id', 'unknown')}/{action}",
            )

        by = body.get("by") or STATE["settings"].get("preparedBy") or "Site Manager"
        at = now_iso()
        if action == "issue":
            target = body.get("to") or item.get("subcontractor")
            if not target or not item.get("trade"):
                raise ValueError("issuing requires a trade and subcontractor")
            reissue = bool(body.get("reissue"))
            item.update(status="issued", subcontractor=target)
            item.setdefault("issuedAt", at)
            item.setdefault("issueHistory", []).append({"at": at, "to": target, "by": by, "note": body.get("note"), "reissue": reissue})
            if not reissue: item.pop("rejectionReason", None)
            audit(item, f"{'Re-issued' if reissue else 'Issued'} to {target}", by, body.get("note"))
        elif action == "in-progress":
            item["status"] = "in_progress"; item.setdefault("inProgressAt", at); audit(item, "Marked in progress", by)
        elif action == "ready":
            item.update(status="ready_for_review", readyForReviewAt=at); audit(item, "Marked ready for review", by, body.get("note"))
        elif action == "inspect":
            item.update(status="under_inspection", underInspectionAt=at)
            item.setdefault("inspectionHistory", []).append({"at": at, "by": by, "action": "started"}); audit(item, "Inspection started", by)
        elif action == "reject":
            reason = str(body.get("reason", "")).strip()
            if not reason: raise ValueError("a rejection reason is required")
            item.update(status="rejected", rejectionReason=reason)
            item.setdefault("inspectionHistory", []).append({"at": at, "by": by, "action": "rejected", "reason": reason}); audit(item, "Rejected on inspection", by, reason)
        elif action == "rectification":
            if not body.get("photo") and not str(body.get("comment", "")).strip():
                raise ValueError("attach a photo or add a comment")
            item.setdefault("rectificationEvidence", []).append({"id": new_id(), "at": at, "photo": body.get("photo"), "photoMeta": body.get("photoMeta"), "comment": body.get("comment"), "by": by})
            if item["status"] == "issued": item.update(status="in_progress", inProgressAt=at)
            audit(item, "Rectification evidence added", by, body.get("comment"))
            if body.get("advanceToReady"):
                item.update(status="ready_for_review", readyForReviewAt=at); audit(item, "Marked ready for review", by)
        elif action == "close":
            if not body.get("confirmed"):
                raise ValueError("closeout confirmation is required")
            if item["type"] != "incomplete" and not body.get("photo"):
                raise ValueError("a closeout photo is required")
            item["status"] = "complete" if item["type"] == "incomplete" else "closed"
            item["closedAt"] = at
            if body.get("photo") or body.get("note"):
                item.setdefault("closeoutEvidence", []).append({"id": new_id(), "at": at, "photo": body.get("photo"), "photoMeta": body.get("photoMeta"), "by": by, "role": body.get("role", "Site Manager"), "note": body.get("note"), "confirmation": "I confirm the work is complete and acceptable." if body.get("confirmed") else None})
            if item.get("inspectionHistory") is not None and body.get("accepted", True):
                item["inspectionHistory"].append({"at": at, "by": by, "action": "accepted"})
            audit(item, "Closed with evidence" if item["type"] != "incomplete" else "Completed", by)
        elif action == "reopen":
            reason = str(body.get("reason", "")).strip()
            if not reason: raise ValueError("a reopen reason is required")
            item.update(status="in_progress", inProgressAt=at); item.pop("closedAt", None); audit(item, "Reopened", by, reason)
        elif action == "comment":
            text = str(body.get("text", "")).strip()
            if not text: raise ValueError("comment text is required")
            item.setdefault("comments", []).append({"id": new_id(), "at": at, "text": text, "by": by}); audit(item, "Comment added", by, text)
        else:
            raise ValueError("unknown action")
    '''
).strip()


def main() -> None:
    app_path = find_app_path()
    if app_path is None:
        return

    text = app_path.read_text(encoding="utf-8")
    original = text

    if "\nimport mimetypes\n" not in text:
        text = text.replace("\nimport json\n", "\nimport json\nimport mimetypes\n", 1)

    starts = [
        pos for pos in (
            text.find("\ndef storage_enabled()"),
            text.find("\ndef use_supabase_storage()"),
            text.find("\ndef create_item(payload: dict[str, Any]) -> dict[str, Any]:"),
        )
        if pos != -1
    ]
    end = text.find("\ndef is_overdue(item: dict[str, Any]) -> bool:")

    if starts and end != -1:
        start = min(starts)
        replacement = "\n\n" + HELPER_BLOCK + "\n\n\n" + CREATE_ITEM_BLOCK + "\n\n\n" + APPLY_ACTION_BLOCK + "\n"
        text = text[:start] + replacement + text[end:]

    text = re.sub(
        r'(?m)^ {20}previous_photos = len\(result\.get\("originalPhotos", \[\]\)\)\n.*?^ {20}added_photos =',
        '                    previous_photos = len(result.get("originalPhotos", []))\n'
        '                    result.update({k: v for k, v in body.items() if k in allowed})\n'
        '                    added_photos =',
        text,
        flags=re.DOTALL,
    )

    if text != original:
        app_path.write_text(text, encoding="utf-8")
        print("CleanRun sitecustomize patched app.py before startup", flush=True)


try:
    main()
except Exception as exc:
    print("CleanRun sitecustomize patch failed:", repr(exc), flush=True)
