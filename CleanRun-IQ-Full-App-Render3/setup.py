from pathlib import Path
from setuptools import setup
import re
import textwrap


def patch_app_py() -> None:
    """Patch app.py during Render build before `python app.py` starts."""
    app_path = Path(__file__).resolve().with_name("app.py")
    if not app_path.exists():
        return

    text = app_path.read_text(encoding="utf-8")
    original = text

    if "\nimport mimetypes\n" not in text:
        text = text.replace("\nimport json\n", "\nimport json\nimport mimetypes\n", 1)

    helper_block = textwrap.dedent(
        '''
        def storage_enabled() -> bool:
            return os.environ.get("CLEANRUN_STORAGE", "local").lower() == "supabase"


        def use_supabase_storage() -> bool:
            return storage_enabled()


        def guess_image_mime_and_extension(value: str) -> tuple[str, str]:
            if value.startswith("data:"):
                header = value.split(",", 1)[0]
                mime_type = header.split(";")[0].replace("data:", "") or "image/jpeg"
            elif value.startswith("/9j/") or value.startswith("9j/"):
                mime_type = "image/jpeg"
            elif value.startswith("iVBOR"):
                mime_type = "image/png"
            elif value.startswith("UklGR"):
                mime_type = "image/webp"
            else:
                mime_type = "image/jpeg"

            extension_map = {
                "image/jpeg": ".jpg",
                "image/jpg": ".jpg",
                "image/png": ".png",
                "image/webp": ".webp",
            }
            return mime_type, extension_map.get(mime_type, ".jpg")


        def extract_base64_photo(value: str) -> str:
            if value.startswith("data:"):
                return value.split(",", 1)[1]
            return value.strip()


        def upload_photo_to_supabase_storage(photo: Any, folder: str = "evidence") -> Any:
            if not photo or not isinstance(photo, str):
                return photo

            if photo.startswith("http://") or photo.startswith("https://") or photo.startswith("seed://"):
                return photo

            if not storage_enabled():
                return photo

            try:
                bucket = os.environ.get("CLEANRUN_STORAGE_BUCKET", "cleanrun-evidence")
                mime_type, extension = guess_image_mime_and_extension(photo)
                encoded = extract_base64_photo(photo)
                raw_bytes = base64.b64decode(encoded, validate=False)

                max_bytes = int(os.environ.get("CLEANRUN_MAX_IMAGE_BYTES", "8000000"))
                if len(raw_bytes) > max_bytes:
                    raise ValueError("uploaded image is too large")

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

            except Exception as exc:
                print("Supabase photo upload failed:", repr(exc), flush=True)
                return photo


        def upload_data_url_to_supabase(data_url: str, folder: str = "evidence") -> str:
            uploaded = upload_photo_to_supabase_storage(data_url, folder=folder)
            return uploaded if isinstance(uploaded, str) else data_url


        def maybe_upload_photo(photo: Any, folder: str = "evidence") -> Any:
            return upload_photo_to_supabase_storage(photo, folder=folder)


        def upload_photo_list(photos: Any, folder: str = "evidence") -> list[Any]:
            if not photos:
                return []

            if not isinstance(photos, list):
                return []

            return [
                upload_photo_to_supabase_storage(photo, folder=folder)
                for photo in photos
            ]
        '''
    ).strip()

    helper_pattern = re.compile(
        r"\ndef (?:storage_enabled|use_supabase_storage)\(\) -> bool:.*?\n(?=def create_item\(payload: dict\[str, Any\]\) -> dict\[str, Any\]:)",
        re.DOTALL,
    )

    if helper_pattern.search(text):
        text = helper_pattern.sub("\n" + helper_block + "\n\n", text, count=1)
    elif "def create_item(payload: dict[str, Any]) -> dict[str, Any]:" in text:
        text = text.replace(
            "\ndef create_item(payload: dict[str, Any]) -> dict[str, Any]:",
            "\n" + helper_block + "\n\ndef create_item(payload: dict[str, Any]) -> dict[str, Any]:",
            1,
        )

    create_marker = (
        '    if payload["type"] in {"defect", "client"} and not payload.get("originalPhotos"):\n'
        '        raise ValueError("defects and client defects require at least one original photo")\n'
    )
    create_patch = create_marker + (
        '\n'
        '    payload["originalPhotos"] = upload_photo_list(\n'
        '        payload.get("originalPhotos", []),\n'
        '        folder=f"items/original/{payload.get(\'project\', \'unknown\')}",\n'
        '    )\n'
    )
    if 'payload["originalPhotos"] = upload_photo_list(' not in text and create_marker in text:
        text = text.replace(create_marker, create_patch, 1)

    if 'body["photo"] = upload_photo_to_supabase_storage(' not in text and 'body["photo"] = maybe_upload_photo(' not in text:
        action_marker = '    at = now_iso()\n'
        action_patch = (
            '    at = now_iso()\n'
            '    if body.get("photo"):\n'
            '        body["photo"] = upload_photo_to_supabase_storage(\n'
            '            body.get("photo"),\n'
            '            folder=f"items/{item.get(\'id\', \'unknown\')}/{action}",\n'
            '        )\n'
        )
        idx = text.find('def apply_action(item: dict[str, Any], action: str, body: dict[str, Any]) -> None:')
        if idx != -1:
            before = text[:idx]
            after = text[idx:].replace(action_marker, action_patch, 1)
            text = before + after

    old_patch_line = '                    result.update({k: v for k, v in body.items() if k in allowed})'
    new_patch_block = textwrap.dedent(
        '''
                            incoming = {k: v for k, v in body.items() if k in allowed}

                            if "originalPhotos" in incoming:
                                incoming["originalPhotos"] = upload_photo_list(
                                    incoming.get("originalPhotos", []),
                                    folder=f"items/{result.get('id', 'unknown')}/original",
                                )

                            result.update(incoming)
        '''
    ).rstrip()
    if old_patch_line in text and 'incoming["originalPhotos"] = upload_photo_list(' not in text:
        text = text.replace(old_patch_line, new_patch_block, 1)

    if text != original:
        app_path.write_text(text, encoding="utf-8")
        print("CleanRun build patch applied to app.py", flush=True)


patch_app_py()

setup(name="cleanrun-render-build-patch", version="0.0.1", py_modules=[])
