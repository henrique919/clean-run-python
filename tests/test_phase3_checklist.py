"""Phase 3 checklist — issue=notify offers, mid-size report photos, field-first Home (cards51)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import main as app_main
from app.store import CleanRunStore
from tests.test_auth_permissions import AsgiClient, bearer

ROOT = Path(__file__).resolve().parents[1]
ENHANCEMENTS = ROOT / "CleanRun-IQ-Full-App-Render3" / "assets" / "enhancements.js"
CSS = ROOT / "CleanRun-IQ-Full-App-Render3" / "assets" / "enhancements.css"


class Phase3NotifyChecklist(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.enh = ENHANCEMENTS.read_text(encoding="utf-8")
        cls.css = CSS.read_text(encoding="utf-8")

    def test_notify_module_markers(self) -> None:
        for marker in [
            "offerIssueNotification",
            "queueIssueNotification",
            "shareNotifyOffer",
            "addNotifyContact",
            "Notify subs ·",
            "Add contact details",
            "Not now",
            "navigator.share",
            "mailto:",
        ]:
            self.assertIn(marker, self.enh, marker)

    def test_notify_offer_hooks_all_issue_paths(self) -> None:
        # capture walk queue, capture issue-now, detail, card, command
        self.assertIn('if(mode==="issue")queueIssueNotification(item)', self.enh)
        self.assertIn('if(mode==="issue"&&item.sync!=="queued")offerIssueNotification(item)', self.enh)
        self.assertIn("applyItemActionResult(updated,act,id,body)", self.enh)
        self.assertIn('if(act==="issue")offerIssueNotification(findItemById(id)||updated)', self.enh)
        self.assertIn('openDashboardSearch(item.code,"Issued");offerIssueNotification(', self.enh)

    def test_detail_issue_skips_full_reload(self) -> None:
        self.assertIn("function applyItemActionResult(updated,act,id,body)", self.enh)
        self.assertIn("mergeSavedItem(updated)", self.enh)
        self.assertIn('const app=$("#app"),nav=$("#nav")', self.enh)
        self.assertIn("if(!app||!nav)return", self.enh)
        item_action_at = self.enh.index("itemAction=async function")
        item_action_block = self.enh[item_action_at : item_action_at + 2200]
        self.assertIn("applyItemActionResult(updated,act,id,body)", item_action_block)
        self.assertNotIn("await reload();showItem(id)", item_action_block)

    def test_notify_audit_uses_comment_endpoint(self) -> None:
        self.assertIn("async function recordNotificationPrepared(sub,ids,via)", self.enh)
        self.assertIn("Notification prepared for ${sub} via ${via}", self.enh)
        self.assertIn("/api/items/${id}/actions/comment", self.enh)
        self.assertIn('await recordNotificationPrepared(sub,ids,"share")', self.enh)
        self.assertIn('await recordNotificationPrepared(sub,ids,"email")', self.enh)
        self.assertIn('err.name==="AbortError"', self.enh)

    def test_notify_message_includes_app_link(self) -> None:
        self.assertIn("View in CleanRun IQ: https://app.cleanruniq.com", self.enh)

    def test_card_notify_badge_on_meta_line(self) -> None:
        for marker in [
            "function itemWasNotified(item)",
            "function cardNotifyBadge(i)",
            "NOT NOTIFIED",
            "NOTIFIED",
            "window.cardNotify=function",
            "cr-notify-badge",
            "cr-card-assignment",
        ]:
            self.assertIn(marker, self.enh, marker)
        self.assertNotIn("Notify again", self.enh)
        self.assertNotIn("cr-notify-action", self.enh)
        self.assertNotIn("cr-card-actions", self.enh[self.enh.index("function cardNotifyBadge"): self.enh.index("function cardNotifyBadge") + 900])

    def test_item_id_alias_reconciliation(self) -> None:
        for marker in [
            "const itemIdAliases=new Map()",
            "function rememberItemIdAlias(fromId,toId)",
            "function resolveItemIdKey(id)",
            "rememberItemIdAlias(replacesId,serverId)",
        ]:
            self.assertIn(marker, self.enh, marker)

    def test_show_item_resolves_server_id(self) -> None:
        show_at = self.enh.index("showItem=function(id)")
        block = self.enh[show_at : show_at + 700]
        self.assertIn("const i=findItemById(id)", block)
        self.assertIn("originalShowItem(i.id)", block)
        self.assertNotIn("state.items.find(x=>x.id===id)", block)

    def test_bulk_notify_subcontractor_mode(self) -> None:
        for marker in [
            "openBulkNotifyPicker",
            "openBulkNotifyList",
            "startBulkNotify",
            "issuedItemsForSub",
            "bulk-notify-row",
            "Notify subcontractor",
        ]:
            self.assertIn(marker, self.enh, marker)

    def test_create_then_issue_requires_server_id(self) -> None:
        """Server ignores client capture ids; issue must target the returned id."""
        client_id = "clientcaptureid123"
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CleanRunStore(Path(temp_dir) / "cleanrun.json")
            with patch.object(app_main, "store", store):
                client = AsgiClient(app_main.app)
                created = client.post(
                    "/api/items",
                    headers=bearer("dev-site-manager"),
                    json={
                        "id": client_id,
                        "type": "incomplete",
                        "project": "Jura Noosa",
                        "building": "Block A",
                        "level": "L01",
                        "unit": "101",
                        "room": "Kitchen",
                        "trade": "Painting",
                        "subcontractor": "Coastline Painting",
                        "priority": "high",
                        "dueDate": "2026-07-15",
                        "description": "Detail issue id regression",
                        "createdBy": "Site Manager",
                    },
                )
                self.assertEqual(created.status_code, 201)
                server_id = created.json()["id"]
                self.assertNotEqual(server_id, client_id)

                stale = client.post(
                    f"/api/items/{client_id}/actions/issue",
                    headers=bearer("dev-site-manager"),
                    json={"to": "Coastline Painting", "by": "Site Manager"},
                )
                self.assertEqual(stale.status_code, 404)

                issued = client.post(
                    f"/api/items/{server_id}/actions/issue",
                    headers=bearer("dev-site-manager"),
                    json={"to": "Coastline Painting", "by": "Site Manager"},
                )
                self.assertEqual(issued.status_code, 200)
                self.assertEqual(issued.json()["status"], "issued")

    def test_notify_prompt_mobile_layout(self) -> None:
        self.assertIn("body[data-route=\"capture\"] .notify-prompt", self.css)
        self.assertIn("@media (max-width:480px)", self.css)
        self.assertIn(".notify-actions .btn{flex:1", self.css)
        self.assertIn("min-height:44px", self.css)

    def test_notify_never_auto_sends(self) -> None:
        # The notify flow must only prefill share/mailto; no POST to any send endpoint.
        self.assertNotIn("/api/notify", self.enh)
        self.assertIn("nothing sends until you choose", self.enh)

    def test_create_issue_reconciles_client_request_id(self) -> None:
        for marker in [
            "function findItemById",
            "function mergeSavedItem(item,replacesId)",
            "mergeSavedItem(item,clientRequestId)",
            "rememberItemIdAlias(replacesId,serverId)",
            'data.dueDate=defaultCaptureDueDate()',
            'Item still syncing — wait a moment and try again.',
        ]:
            self.assertIn(marker, self.enh, marker)

    def test_walk_end_surfaces_queue_once(self) -> None:
        self.assertIn("if(wasWalk&&!walkMode&&notifyQueue.length)openNotifyQueue()", self.enh)

    def test_notify_prompt_styles_exist(self) -> None:
        self.assertIn(".notify-prompt", self.css)
        self.assertIn(".notify-chip", self.css)


class Phase3HomeChecklist(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.enh = ENHANCEMENTS.read_text(encoding="utf-8")

    def test_field_first_order(self) -> None:
        template_at = self.enh.index('const commandBar=(typeof commandHomeBar==="function"')
        home = self.enh[template_at : template_at + 4000]
        capture = home.index("capture-cta")
        kpis = home.index("dashboard-kpis")
        next_block = home.index("Next to deal with")
        insights = home.index("${insights}")
        self.assertLess(capture, kpis)
        self.assertLess(kpis, next_block)
        self.assertLess(next_block, insights)

    def test_insights_preserve_all_modules(self) -> None:
        for module in [
            "Closeout control room",
            "Subcontractor performance",
            "Trade pressure",
            "Today's schedule",
            "Quick focus",
        ]:
            self.assertIn(module, self.enh, module)
        self.assertIn("Project insights", self.enh)
        self.assertIn("toggleHomeInsights", self.enh)

    def test_command_search_is_desktop_only_on_home(self) -> None:
        self.assertIn(
            'matchMedia("(min-width:1024px)").matches)?commandHomeBar():""', self.enh
        )
        # The old mobile strip-then-re-add ordering bug must not return.
        self.assertNotIn(
            'return html.includes("command-home")?html:html.replace(`</div></section><div class="dashboard-kpis">`',
            self.enh,
        )


if __name__ == "__main__":
    unittest.main()
