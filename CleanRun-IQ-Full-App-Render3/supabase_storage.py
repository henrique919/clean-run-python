import base64
import mimetypes
import os
import uuid
from datetime import datetime, timezone

from supabase_client import get_supabase


BUCKET = os.getenv("CLEANRUN_STORAGE_BUCKET", "cleanrun-evidence")


def upload_data_url_to_supabase(data_url: str, folder: str = "evidence") -> str:
    """
    Converts browser data URL image into Supabase Storage object.
    Returns public URL if bucket is public.
    """

    if not data_url.startswith("data:"):
        return data_url

    header, encoded = data_url.split(",", 1)

    mime_type = header.split(";")[0].replace("data:", "") or "image/jpeg"
    extension = mimetypes.guess_extension(mime_type) or ".jpg"

    raw_bytes = base64.b64decode(encoded)

    now = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    file_path = f"{folder}/{now}/{uuid.uuid4().hex}{extension}"

    supabase = get_supabase()

    supabase.storage.from_(BUCKET).upload(
        path=file_path,
        file=raw_bytes,
        file_options={
            "content-type": mime_type,
            "upsert": "false",
        },
    )

    public_url = supabase.storage.from_(BUCKET).get_public_url(file_path)

    return public_url
