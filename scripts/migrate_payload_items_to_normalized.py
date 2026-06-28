from __future__ import annotations

import logging
from collections import Counter

from app.models import AppData, Item
from app.store import seed_settings
from app.store_supabase import SupabaseCleanRunStore
from app.supabase_client import get_supabase_client


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    client = get_supabase_client()
    store = SupabaseCleanRunStore()
    settings = store._read_settings()  # noqa: SLF001 - migration utility intentionally uses repository internals.
    if not settings:
        settings = seed_settings()

    rows = client.table("items").select("code,payload").not_.is_("payload", "null").execute().data or []
    counts: Counter[str] = Counter()

    for row in rows:
        code = row.get("code") or "unknown"
        payload = row.get("payload")
        if not payload:
            counts["skipped"] += 1
            logger.info("skipped %s: empty payload", code)
            continue
        try:
            item = Item.model_validate(payload)
            store._upsert_item(item, settings)  # noqa: SLF001 - idempotent normalized replay.
            counts["migrated"] += 1
            logger.info("migrated %s", item.code)
        except Exception:
            counts["failed"] += 1
            logger.exception("failed %s", code)

    summary = {
        "found": len(rows),
        "migrated": counts["migrated"],
        "skipped": counts["skipped"],
        "failed": counts["failed"],
    }
    print(summary)
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
