#!/usr/bin/env python3
"""Phase 2.2 performance measurements (read-only, no app behaviour changes)."""

from __future__ import annotations

import json
import os
import statistics
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

PRODUCTION_BASE = "https://app.cleanruniq.com"


def measure_frontend(base: str = PRODUCTION_BASE) -> dict:
    assets = ["/", "/assets/enhancements.js", "/assets/enhancements.css", "/assets/format-dates.js"]
    out: dict = {}
    for path in assets:
        t0 = time.perf_counter()
        with urllib.request.urlopen(f"{base}{path}", timeout=60) as res:
            body = res.read()
        out[path] = {
            "bytes": len(body),
            "kb": round(len(body) / 1024, 1),
            "ms": round((time.perf_counter() - t0) * 1000, 1),
        }
    out["total_initial_kb"] = round(sum(v["bytes"] for v in out.values() if isinstance(v, dict)) / 1024, 1)
    out["blocks_first_render"] = (
        "index.html boot() awaits reload() -> GET /api/state before painting UI; "
        "large inline CSS + Google Fonts @import in <head>; enhancements.js loads after inline boot script"
    )
    return out


def measure_health(base: str = PRODUCTION_BASE, runs: int = 5) -> dict:
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        with urllib.request.urlopen(f"{base}/health", timeout=60) as res:
            res.read()
        times.append((time.perf_counter() - t0) * 1000)
    return {
        "warm_health_ms": [round(t, 1) for t in times],
        "warm_health_avg_ms": round(statistics.mean(times), 1),
        "note": "Warm instance only; cold spin-down wake not measurable without 15+ min idle or Render Events log",
    }


def measure_supabase_sign_roundtrip() -> dict:
    cfg = json.loads(urllib.request.urlopen(f"{PRODUCTION_BASE}/api/auth/config", timeout=30).read())
    url = cfg["supabase_url"]
    key = cfg["supabase_publishable_key"]
    endpoint = f"{url}/storage/v1/object/sign/cleanrun-evidence/cleanrun/public/perf-probe/fake.jpg"
    body = json.dumps({"expiresIn": 604800}).encode()
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    times = []
    for _ in range(5):
        req = urllib.request.Request(endpoint, data=body, method="POST", headers=headers)
        t0 = time.perf_counter()
        try:
            urllib.request.urlopen(req, timeout=30).read()
        except urllib.error.HTTPError:
            pass
        times.append((time.perf_counter() - t0) * 1000)
    return {
        "probe": "POST create_signed_url on non-existent path (400 expected)",
        "roundtrip_ms": [round(t, 1) for t in times],
        "roundtrip_avg_ms": round(statistics.mean(times), 1),
        "roundtrip_p50_ms": round(statistics.median(times), 1),
    }


def _patch_signing(track):
    """Patch storage signing so probes work without Supabase credentials."""
    from contextlib import contextmanager
    from unittest.mock import MagicMock

    mock_client = MagicMock()

    def mock_signed(client, path: str, *, transform: dict | None = None):
        return track(path, transform=transform)

    @contextmanager
    def ctx():
        with patch("app.storage._client_for_storage_path", return_value=mock_client):
            with patch("app.storage._signed_url", side_effect=mock_signed):
                yield

    return ctx


def count_sign_calls_for_items(items) -> dict:
    """Mirror legacy_state signing (camel_item only) without network I/O."""
    from app.main import camel_item

    calls = 0

    def track(path, *, transform=None):
        nonlocal calls
        calls += 1
        return f"https://mock/{'thumb' if transform else 'full'}/{calls}"

    with _patch_signing(track)():
        for item in items:
            camel_item(item)
    originals = sum(len(i.original_photos) for i in items)
    rect = sum(len(i.rectification_evidence) for i in items)
    closeout = sum(len(i.closeout_evidence) for i in items)
    return {
        "item_count": len(items),
        "original_photo_slots": originals,
        "rectification_evidence_slots": rect,
        "closeout_evidence_slots": closeout,
        "create_signed_url_calls": calls,
        "expected_formula": "per item: originals×2 (full+thumb) + rect photos + closeout photos",
        "signing_sequential": True,
    }


def build_synthetic_items(count: int = 44):
    from app.models import Item, ItemStatus, ItemType, Priority, SyncState, now_iso

    now = now_iso()
    items = []
    for i in range(count):
        path = f"cleanrun/public/projects/jura-noosa/items/def-{i:03d}/original/{i:08x}.jpg"
        items.append(
            Item(
                id=f"synthetic-{i}",
                code=f"DEF-{i:03d}",
                type=ItemType.DEFECT,
                status=ItemStatus.OPEN,
                project="Jura Noosa",
                building="Block A",
                level="L01",
                unit="A-101",
                room="Kitchen",
                trade="Tiling",
                subcontractor="Demo Sub",
                priority=Priority.HIGH,
                due_date="2026-07-15",
                description=f"Synthetic defect {i} for perf probe",
                raised_by="Site Manager",
                created_by="perf-probe",
                original_photos=[path],
                created_at=now,
                updated_at=now,
                sync=SyncState.SYNCED,
            )
        )
    return items


def measure_instrumented_api_state(items, *, sign_delay_ms: float = 0) -> dict:
    from app import main as app_main
    from app.store import CleanRunStore
    from tests.test_auth_permissions import AsgiClient, bearer

    sign_calls: list[dict] = []
    t_start = time.perf_counter()

    def track(path, *, transform=None):
        if sign_delay_ms:
            time.sleep(sign_delay_ms / 1000)
        sign_calls.append(
            {
                "path": path,
                "transform": bool(transform),
                "at_ms": round((time.perf_counter() - t_start) * 1000, 2),
            }
        )
        return f"https://mock/sign/{len(sign_calls)}?t={'thumb' if transform else 'full'}"

    with tempfile.TemporaryDirectory() as tmp:
        store = CleanRunStore(Path(tmp) / "cleanrun.json")
        store._write(type(store.snapshot())(items=items, settings=store.snapshot().settings))
        with patch.object(app_main, "store", store):
            with _patch_signing(track)():
                client = AsgiClient(app_main.app)
                t_db = time.perf_counter()
                store.snapshot()
                db_ms = (time.perf_counter() - t_db) * 1000
                t_req = time.perf_counter()
                res = client.get("/api/state", headers=bearer("dev-site-manager"))
                total_ms = (time.perf_counter() - t_req) * 1000

    gaps = [sign_calls[i + 1]["at_ms"] - sign_calls[i]["at_ms"] for i in range(len(sign_calls) - 1)]
    return {
        "db_snapshot_ms_local_json": round(db_ms, 1),
        "api_state_total_ms": round(total_ms, 1),
        "signing_ms": round(total_ms - db_ms, 1) if sign_delay_ms == 0 else round(sign_delay_ms * len(sign_calls), 1),
        "serialization_estimate_ms": round(max(0, total_ms - db_ms - sign_delay_ms * len(sign_calls)), 1) if sign_delay_ms else None,
        "create_signed_url_calls": len(sign_calls),
        "transform_calls": sum(1 for c in sign_calls if c["transform"]),
        "full_photo_calls": sum(1 for c in sign_calls if not c["transform"]),
        "sign_call_gap_ms_first_10": [round(g, 2) for g in gaps[:10]],
        "signing_sequential": all(g >= 0 for g in gaps) if gaps else True,
        "response_bytes": len(res.body),
        "response_kb": round(len(res.body) / 1024, 1),
        "sign_delay_ms_per_call": sign_delay_ms,
    }


def measure_production_supabase_read() -> dict | None:
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        return None
    os.environ.setdefault("CLEANRUN_STORAGE", "supabase")
    os.environ.setdefault("CLEANRUN_ENV", "production")
    from app.store_supabase import SupabaseCleanRunStore

    store = SupabaseCleanRunStore()
    times = []
    item_count = 0
    for _ in range(3):
        t0 = time.perf_counter()
        data = store._read()
        times.append((time.perf_counter() - t0) * 1000)
        item_count = len(data.items)
    return {
        "item_count": item_count,
        "db_read_ms": [round(t, 1) for t in times],
        "db_read_avg_ms": round(statistics.mean(times), 1),
        "queries": "items + item_photos + item_comments + item_audit_events + app_settings",
    }


def live_login(base: str, email: str, password: str) -> str:
    cfg = json.loads(urllib.request.urlopen(f"{base}/api/auth/config", timeout=30).read())
    req = urllib.request.Request(
        f"{cfg['supabase_url']}/auth/v1/token?grant_type=password",
        data=json.dumps({"email": email, "password": password}).encode(),
        headers={"Content-Type": "application/json", "apikey": cfg["supabase_publishable_key"]},
        method="POST",
    )
    data = json.loads(urllib.request.urlopen(req, timeout=30).read())
    token = data.get("access_token")
    if not token:
        raise RuntimeError(data)
    return token


def measure_live_state(base: str, token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    times = []
    bodies = []
    for i in range(4):
        req = urllib.request.Request(f"{base}/api/state", headers=headers)
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=180) as res:
            body = res.read()
        times.append((time.perf_counter() - t0) * 1000)
        bodies.append(body)
    raw = bodies[0]
    payload = json.loads(raw)
    items = payload.get("items", [])
    active = payload.get("settings", {}).get("activeProject")
    active_items = [i for i in items if i.get("project") == active]
    signed = raw.count(b"/storage/v1/object/sign") + raw.count(b"/storage/v1/render/image/sign")
    originals = sum(len(i.get("originalPhotos") or []) for i in items)
    thumbs = sum(len(i.get("originalPhotoThumbnails") or []) for i in items)
    deploy = json.loads(urllib.request.urlopen(f"{base}/api/deploy", timeout=30).read())
    return {
        "deploy": deploy,
        "item_count_all": len(items),
        "item_count_active_project": len(active_items),
        "active_project": active,
        "original_photo_refs": originals,
        "thumbnail_url_count": thumbs,
        "api_state_cold_ms": round(times[0], 1),
        "api_state_warm_avg_ms": round(statistics.mean(times[1:]), 1),
        "api_state_all_ms": [round(t, 1) for t in times],
        "response_kb": round(len(raw) / 1024, 1),
        "signed_url_strings_in_json": signed,
        "estimated_create_signed_url_calls": signed,
    }


def analyze_save_path() -> dict:
    return {
        "walk_mode_save_plus_next": {
            "POST_/api/items": "uploads photos via normalize_photo per image (sequential), upserts item; returns Item (unsigned storage paths)",
            "server_create_item": "calls _read() full snapshot before write (extra DB round-trip on every save)",
            "client_mergeSavedItem": "merges POST response into local state immediately (walk mode)",
            "client_reload_after_save": "YES — walk mode: reload() in background after Save+Next; non-walk: await reload() before navigate",
            "reload_cost": "full GET /api/state re-signs ALL visible items",
        },
        "signed_urls_regenerated_per_save": "All items on every reload(); ≈ originals×2 + rect + closeout per item (sequential create_signed_url)",
        "save_plus_next_perceived_latency": "POST /api/items only blocks UI until item write completes; background reload may contend with next capture",
    }


def hosting_notes(base: str = PRODUCTION_BASE) -> dict:
    deploy = json.loads(urllib.request.urlopen(f"{base}/api/deploy", timeout=30).read())
    return {
        "render_yaml_plan": "starter (repo render.yaml — confirm in Render dashboard; may differ)",
        "dashboard_plan_truth": "NOT verified by agent API — check Render dashboard → clean-run-python → Instance type",
        "uvicorn_workers": "1 process — app.py: uvicorn.run(app) with no workers arg",
        "spin_down": "Starter web services spin down after ~15 min idle (Render docs); confirm Events tab for 'Service spun down' / wake",
        "production_deploy": deploy,
        "cold_start": "Not measured (instance was warm during probe); use Render Events or idle-then-refresh test",
    }


def extrapolate_production(sign_calls: int, db_ms: float, sign_ms_per_call: float, payload_kb: float) -> dict:
    signing_ms = sign_calls * sign_ms_per_call
    serial_ms = db_ms + signing_ms + 50  # ~50ms serialization estimate for JSON encode
    return {
        "assumed_db_read_ms": db_ms,
        "assumed_sign_ms_per_call": sign_ms_per_call,
        "sign_calls": sign_calls,
        "estimated_signing_ms": round(signing_ms, 0),
        "estimated_total_ms_sequential": round(serial_ms, 0),
        "estimated_payload_kb": payload_kb,
        "note": "Extrapolation from measured Supabase round-trip + synthetic 44-item call count; run with CLEANRUN_LIVE_* for ground truth",
    }


def main() -> None:
    import logging

    logging.disable(logging.CRITICAL)
    synthetic = build_synthetic_items(44)
    sign_meta = count_sign_calls_for_items(synthetic)
    local_zero = measure_instrumented_api_state(synthetic, sign_delay_ms=0)
    sign_probe = measure_supabase_sign_roundtrip()
    extrap = extrapolate_production(
        sign_calls=sign_meta["create_signed_url_calls"],
        db_ms=800,
        sign_ms_per_call=sign_probe["roundtrip_avg_ms"],
        payload_kb=local_zero["response_kb"],
    )

    report = {
        "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "save_path_analysis": analyze_save_path(),
        "hosting": hosting_notes(),
        "frontend": measure_frontend(),
        "health": measure_health(),
        "supabase_sign_probe": sign_probe,
        "synthetic_44_items": {
            "sign_call_analysis": sign_meta,
            "local_instrumented_zero_latency": local_zero,
            "production_extrapolation": extrap,
        },
        "production_supabase_read": measure_production_supabase_read(),
    }

    base = os.getenv("CLEANRUN_LIVE_BASE_URL", PRODUCTION_BASE).rstrip("/")
    email = os.getenv("CLEANRUN_LIVE_EMAIL", "")
    password = os.getenv("CLEANRUN_LIVE_PASSWORD", "")
    if email and password:
        token = live_login(base, email, password)
        report["live_production"] = measure_live_state(base, token)
    else:
        report["live_production"] = {
            "skipped": "Set CLEANRUN_LIVE_BASE_URL, CLEANRUN_LIVE_EMAIL, CLEANRUN_LIVE_PASSWORD for authenticated /api/state timings",
        }

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
