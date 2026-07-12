"""Regenerate static HTML report samples under reports/samples/."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from app.models import AppData, Item
from app.reporting import build_report_html
from app.store import _normalize_app_data_payload

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports" / "samples"

SAMPLE_REDIRECTS = (
    ("Jura-Noosa-Defect-Register-sample.html", "reports/samples/Jura-Noosa-Defect-Register-sample.html"),
    ("Jura-Noosa-Handover-Evidence-sample.html", "reports/samples/Jura-Noosa-Handover-Evidence-sample.html"),
)

SEED_COLORS = {
    "amber": "#C27803",
    "red": "#B42318",
    "navy": "#1A2332",
    "sky": "#1D4ED8",
    "green": "#18A94F",
}


def demo_photo(seed_url: str) -> str:
    rest = seed_url.replace("seed://", "")
    parts = rest.split("/", 1)
    color = SEED_COLORS.get(parts[0], "#52606D")
    label = parts[1] if len(parts) > 1 else "Evidence"
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">'
        f'<rect width="480" height="360" fill="{color}"/>'
        f'<text x="240" y="180" text-anchor="middle" fill="#fff" font-size="20" '
        f'font-family="Arial,sans-serif" font-weight="700">{label}</text></svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def hydrate(value: str | None) -> str | None:
    if value and value.startswith("seed://"):
        return demo_photo(value)
    return value


def redirect_html(target: str) -> str:
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\" />"
        f'<meta http-equiv="refresh" content="0;url={target}" />'
        f"<title>Redirecting…</title></head><body>"
        f'<p>Redirecting to <a href="{target}">{target}</a>…</p></body></html>'
    )


def write_preview_redirects() -> None:
    for filename, target in SAMPLE_REDIRECTS:
        (REPO / filename).write_text(redirect_html(target), encoding="utf-8")


def hydrate_item(item: Item) -> Item:
    return item.model_copy(
        update={
            "original_photos": [hydrate(photo) or photo for photo in item.original_photos],
            "rectification_evidence": [
                evidence.model_copy(update={"photo": hydrate(evidence.photo) or evidence.photo})
                for evidence in item.rectification_evidence
            ],
            "closeout_evidence": [
                evidence.model_copy(update={"photo": hydrate(evidence.photo) or evidence.photo})
                for evidence in item.closeout_evidence
            ],
        }
    )


def main() -> None:
    payload = json.loads((REPO / "cleanrun_data.json").read_text(encoding="utf-8"))
    data = AppData.model_validate(_normalize_app_data_payload(payload))
    items = [hydrate_item(item) for item in data.items]
    jura = [item for item in items if item.project == "Jura Noosa"]

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "Jura-Noosa-Defect-Register-sample.html").write_text(
        build_report_html(jura, data.settings, "register", projects=["Jura Noosa"]),
        encoding="utf-8",
    )
    (OUT / "Jura-Noosa-Handover-Evidence-sample.html").write_text(
        build_report_html(jura, data.settings, "handover", projects=["Jura Noosa"]),
        encoding="utf-8",
    )

    write_preview_redirects()

    register = (OUT / "Jura-Noosa-Defect-Register-sample.html").read_text(encoding="utf-8")
    handover = (OUT / "Jura-Noosa-Handover-Evidence-sample.html").read_text(encoding="utf-8")
    print(f"register: {len(jura)} items, {register.count('<img')} images")
    print(f"handover: {handover.count('<img')} images")
    print("preview: http://localhost:8765/Jura-Noosa-Defect-Register-sample.html")


if __name__ == "__main__":
    main()
