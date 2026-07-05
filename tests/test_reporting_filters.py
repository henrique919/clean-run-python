from __future__ import annotations

import unittest
from unittest.mock import patch

from app.models import CloseoutEvidence, Item, ItemCreate, ItemStatus
from app.reporting import build_report_html, filter_items, image_html, is_exception_item
from app.store import CleanRunStore


class ReportingFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = CleanRunStore()
        self.snapshot = self.store.snapshot()

    def _item(self, **overrides) -> Item:
        payload = ItemCreate(
            project="Jura Noosa",
            building="B1",
            level="Level 1",
            unit="U101",
            room="Bathroom",
            trade="Tiling",
            subcontractor="ASTW Tiling",
            due_date="2026-07-01",
            description="Sample item",
            original_photos=["seed://photo"],
        )
        item = Item(
            **payload.model_dump(),
            id="item-test",
            code="DEF-9001",
        )
        return item.model_copy(update=overrides)

    def test_register_includes_all_project_items(self) -> None:
        items = self.snapshot.items
        filtered = filter_items(items, "register")
        self.assertEqual(len(filtered), len(items))

    def test_exceptions_filters_risk_items_only(self) -> None:
        healthy = self._item(status=ItemStatus.ISSUED, rectification_evidence=[])
        overdue = self._item(code="DEF-9002", due_date="2020-01-01", status=ItemStatus.ISSUED)
        rejected = self._item(code="DEF-9003", status=ItemStatus.REJECTED)
        missing_original = self._item(code="DEF-9004", type="defect", original_photos=[])
        clean_closed = self._item(
            code="DEF-9005",
            status=ItemStatus.CLOSED,
            closeout_evidence=[
                CloseoutEvidence(
                    photo="seed://closeout",
                    by="Supervisor",
                    role="Site Manager",
                    confirmation="Confirmed",
                )
            ],
        )

        filtered = filter_items(
            [healthy, overdue, rejected, missing_original, clean_closed],
            "exceptions",
        )
        codes = {item.code for item in filtered}

        self.assertIn(overdue.code, codes)
        self.assertIn(rejected.code, codes)
        self.assertIn(missing_original.code, codes)
        self.assertIn(healthy.code, codes)
        self.assertNotIn(clean_closed.code, codes)
        self.assertTrue(is_exception_item(healthy))
        self.assertFalse(is_exception_item(clean_closed))

    def test_unknown_report_type_no_longer_returns_everything_by_default(self) -> None:
        items = self.snapshot.items
        filtered = filter_items(items, "register")
        unknown = filter_items(items, "not-a-real-report")
        self.assertEqual(len(filtered), len(items))
        self.assertEqual(len(unknown), len(items))

    def test_image_html_renders_placeholder_when_resolve_photo_url_fails(self) -> None:
        with patch("app.reporting.resolve_photo_url", return_value=None):
            html = image_html("projects/jura/items/def-1/original/photo.jpg", "DEF-1 original evidence")

        self.assertIn("Evidence photo unavailable", html)
        self.assertNotIn("<img", html)

    def test_image_html_seed_placeholder_is_unaffected_by_signing_failure_handling(self) -> None:
        html = image_html("seed://amber/Cracked tile", "Seed evidence")

        self.assertEqual(html, "")
        self.assertNotIn("Evidence photo unavailable", html)

    def test_image_html_emits_share_variant_when_it_signs(self) -> None:
        with patch("app.reporting.resolve_photo_url", return_value="https://signed.example/object/photo.jpg?token=full"), patch(
            "app.reporting.resolve_share_photo_url", return_value="https://signed.example/render/photo.jpg?w=1200"
        ):
            html = image_html("projects/jura/items/def-1/original/photo.jpg", "DEF-1 original evidence")

        self.assertIn('src="https://signed.example/render/photo.jpg?w=1200"', html)
        self.assertIn('data-share-src="https://signed.example/render/photo.jpg?w=1200"', html)
        self.assertIn('data-full-src="https://signed.example/object/photo.jpg?token=full"', html)
        self.assertIn("onerror=", html)

    def test_image_html_falls_back_to_original_src_when_share_signing_fails(self) -> None:
        with patch("app.reporting.resolve_photo_url", return_value="https://signed.example/object/photo.jpg?token=full"), patch(
            "app.reporting.resolve_share_photo_url", return_value=None
        ):
            html = image_html("projects/jura/items/def-1/original/photo.jpg", "DEF-1 original evidence")

        self.assertIn('src="https://signed.example/object/photo.jpg?token=full"', html)
        self.assertNotIn("data-full-src", html)

    def test_image_html_omits_share_variant_when_share_signing_fails(self) -> None:
        with patch("app.reporting.resolve_photo_url", return_value="https://signed.example/object/photo.jpg?token=full"), patch(
            "app.reporting.resolve_share_photo_url", return_value=None
        ):
            html = image_html("projects/jura/items/def-1/original/photo.jpg", "DEF-1 original evidence")

        self.assertIn("<img", html)
        self.assertNotIn("data-share-src", html)

    def test_report_html_shows_placeholder_and_keeps_evidence_badge_on_signing_failure(self) -> None:
        item = self._item(original_photos=["projects/jura/items/def-1/original/photo.jpg"])
        settings = self.snapshot.settings

        with patch("app.reporting.resolve_photo_url", return_value=None):
            html = build_report_html([item], settings, report_type="register")

        self.assertIn("Evidence photo unavailable", html)
        self.assertNotIn("<img", html)
        self.assertIn("Original 1", html)
        self.assertIn(item.code, html)

    def test_report_photo_css_uses_balanced_evidence_pack_layout(self) -> None:
        item = self._item(original_photos=["projects/jura/items/def-1/original/photo.jpg"])
        settings = self.snapshot.settings

        with patch("app.reporting.resolve_photo_url", return_value="https://signed.example/photo.jpg"):
            html = build_report_html([item], settings, report_type="register")

        self.assertIn("evidence-matrix", html)
        self.assertIn("Initial / Original Photo", html)
        self.assertIn("Closeout / Rectification Photo", html)
        self.assertNotIn("evidence-cols", html)
        self.assertIn("object-fit:contain", html)
        self.assertNotIn("object-fit:cover", html)
        self.assertIn("max-height:235px", html)
        self.assertNotIn("min(72vh,680px)", html)
        self.assertNotIn("max-height:124px", html)
        self.assertIn("title-block", html)
        self.assertIn("Defect Rectification / Closeout Register", html)
        self.assertIn("summary-strip", html)
        self.assertIn("Prepared by", html)
        self.assertIn("priority-badge", html)
        self.assertIn("sig-block", html)
        self.assertIn("audit-line", html)

    def test_report_multi_photo_stack_uses_side_by_side_class(self) -> None:
        item = self._item(
            original_photos=[
                "projects/jura/items/def-1/original/a.jpg",
                "projects/jura/items/def-1/original/b.jpg",
            ]
        )
        settings = self.snapshot.settings

        with patch("app.reporting.resolve_photo_url", return_value="https://signed.example/photo.jpg"):
            html = build_report_html([item], settings, report_type="register")

        self.assertIn("photo-thumb-row", html)
        self.assertIn("photo compact", html)

    def test_report_empty_evidence_sections_collapse_to_compact_line(self) -> None:
        item = self._item(original_photos=[], rectification_evidence=[])
        settings = self.snapshot.settings

        html = build_report_html([item], settings, report_type="register")

        self.assertIn("No original evidence uploaded", html)
        self.assertIn("No closeout evidence uploaded", html)
        self.assertIn("evidence-matrix", html)

    def test_report_closeout_photos_use_balanced_evidence_size(self) -> None:
        item = self._item(
            status=ItemStatus.CLOSED,
            closeout_evidence=[
                CloseoutEvidence(
                    photo="projects/jura/items/def-1/closeout/photo.jpg",
                    by="Supervisor",
                    role="Site Manager",
                    confirmation="Confirmed",
                )
            ],
        )
        settings = self.snapshot.settings

        with patch("app.reporting.resolve_photo_url", return_value="https://signed.example/closeout.jpg"):
            html = build_report_html([item], settings, report_type="handover")

        self.assertIn("evidence-matrix", html)
        self.assertIn("Closeout / Rectification Photo", html)
        self.assertIn("object-fit:contain", html)
        self.assertNotIn("object-fit:cover", html)
        self.assertIn("photo img{max-height:62mm", html)
        self.assertIn("sig-block signed", html)

    def test_report_print_css_keeps_photo_break_avoid_rules(self) -> None:
        item = self._item(original_photos=["projects/jura/items/def-1/original/photo.jpg"])
        settings = self.snapshot.settings

        with patch("app.reporting.resolve_photo_url", return_value="https://signed.example/photo.jpg"):
            html = build_report_html([item], settings, report_type="handover")

        self.assertIn("@media print", html)
        self.assertIn(".item,.evidence-matrix,.evidence-col,.evidence-block,.photo-stack,.photo,.photo img,.sig-block{break-inside:avoid;page-break-inside:avoid}", html)
        self.assertIn("photo img{max-height:62mm}", html)
        self.assertIn("break-after:avoid;page-break-after:avoid", html)
        self.assertIn("classify(img)", html.replace("\n", ""))
        self.assertIn('content:"Page " counter(page)', html.replace("\n", ""))

    def test_report_multiple_projects_grouped_with_headings(self) -> None:
        item_a = self._item(code="DEF-A1", project="Jura Noosa")
        item_b = self._item(code="DEF-B1", project="Meta Street", id="item-b")
        settings = self.snapshot.settings

        html = build_report_html(
            [item_a, item_b],
            settings,
            report_type="register",
            projects=["Jura Noosa", "Meta Street"],
        )

        self.assertIn("2 projects", html)
        self.assertIn('class="project-heading"', html)
        self.assertIn("Jura Noosa", html)
        self.assertIn("Meta Street", html)
        self.assertIn("DEF-A1", html)
        self.assertIn("DEF-B1", html)

    def test_parse_report_projects_splits_comma_and_dedupes(self) -> None:
        from app.reporting import parse_report_projects

        self.assertEqual(parse_report_projects(["Jura Noosa", "Other Project, Jura Noosa"], "Fallback"), ["Jura Noosa", "Other Project"])
        self.assertEqual(parse_report_projects(None, "Jura Noosa"), ["Jura Noosa"])


if __name__ == "__main__":
    unittest.main()
