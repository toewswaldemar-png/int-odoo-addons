from unittest.mock import Mock, patch

import requests

from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tools import mute_logger

from odoo.addons.int_ui_showcase.controllers.icecast import demo_icestats, normalize_icestats


@tagged("post_install", "-at_install")
class TestUiShowcaseModel(TransactionCase):
    def test_state_buttons(self):
        record = self.env["int.ui.showcase"].create({"name": "Test"})
        self.assertEqual(record.state, "draft")
        record.action_confirm()
        self.assertEqual(record.state, "confirmed")
        record.action_done()
        self.assertEqual(record.state, "done")
        record.action_draft()
        self.assertEqual(record.state, "draft")
        record.action_cancel()
        self.assertEqual(record.state, "cancel")

    def test_totals(self):
        record = self.env["int.ui.showcase"].create(
            {
                "name": "Totals",
                "line_ids": [
                    (0, 0, {"name": "A", "quantity": 2, "price_unit": 10}),
                    (0, 0, {"name": "B", "quantity": 1, "price_unit": 5}),
                ],
            }
        )
        self.assertEqual(record.line_count, 2)
        self.assertEqual(record.amount_total, 25)

    def test_buttons_return_actions(self):
        record = self.env["int.ui.showcase"].create({"name": "Actions"})
        self.assertEqual(record.action_open_lines()["res_model"], "int.ui.showcase.line")
        self.assertEqual(record.action_notify()["tag"], "display_notification")
        self.assertEqual(record.action_rainbow()["effect"]["type"], "rainbow_man")

    def test_wizard_posts_message(self):
        record = self.env["int.ui.showcase"].create({"name": "Wizard"})
        wizard = (
            self.env["int.ui.showcase.wizard"]
            .with_context(active_id=record.id)
            .create({"message": "Hello"})
        )
        wizard.action_confirm()
        self.assertIn("Hello", record.message_ids[0].body)

    def test_properties_and_stage(self):
        category = self.env["int.ui.showcase.category"].create(
            {
                "name": "Category",
                "showcase_properties_definition": [
                    {"name": "serial", "type": "char", "string": "Serial"}
                ],
            }
        )
        stages = self.env["int.ui.showcase.stage"].search([])
        record = self.env["int.ui.showcase"].create(
            {
                "name": "Props",
                "category_id": category.id,
                "stage_id": stages[0].id,
                "properties": {"serial": "X1"},
            }
        )
        self.assertEqual(record.properties["serial"], "X1")
        record.stage_id = stages[1]
        self.assertTrue(record.duration_tracking)

    def test_report_html(self):
        record = self.env["int.ui.showcase"].create({"name": "Report"})
        html, _report_type = self.env["ir.actions.report"]._render_qweb_html(
            "int_ui_showcase.report_showcase", record.ids
        )
        self.assertIn(b"Report", html)


@tagged("post_install", "-at_install")
class TestUiShowcaseTours(HttpCase):
    def test_views_tour(self):
        self.start_tour(
            "/odoo/action-int_ui_showcase.int_ui_showcase_action?debug=1",
            "int_ui_showcase_views",
            login="admin",
        )

    def test_components_tour(self):
        self.start_tour(
            "/odoo/action-int_ui_showcase.int_ui_showcase_ui_components_action?debug=1",
            "int_ui_showcase_components",
            login="admin",
        )

    def test_portal_page(self):
        self.authenticate("admin", "admin")
        response = self.url_open("/my/ui-showcase")
        self.assertEqual(response.status_code, 200)
        self.assertIn("UI Showcase", response.text)


@tagged("post_install", "-at_install")
class TestUiShowcaseIcecast(HttpCase):
    def test_normalize_list_and_single_source(self):
        many = normalize_icestats(
            {
                "icestats": {
                    "server_id": "Icecast 2.4.4",
                    "source": [
                        {"listenurl": "http://host:8000/b", "listeners": 3, "listener_peak": 5, "title": "T"},
                        {"listenurl": "http://host:8000/a", "listeners": "2", "artist": "Choir", "title": "Song"},
                    ],
                }
            }
        )
        self.assertEqual([mount["mount"] for mount in many["mounts"]], ["/a", "/b"])
        self.assertEqual(many["listeners"], 5)
        self.assertEqual(many["peak"], 5)
        self.assertEqual(many["mounts"][0]["title"], "Choir - Song")
        single = normalize_icestats({"icestats": {"source": {"listenurl": "http://host/x", "listeners": 1}}})
        self.assertEqual(single["listeners"], 1)

    def test_normalize_without_source(self):
        for payload in (None, {}, {"icestats": {"server_id": "Icecast"}}):
            result = normalize_icestats(payload)
            self.assertEqual(result["mounts"], [])
            self.assertEqual(result["listeners"], 0)

    def test_demo_moves_with_time(self):
        first = normalize_icestats(demo_icestats(0))
        later = normalize_icestats(demo_icestats(50))
        self.assertEqual(len(first["mounts"]), 3)
        self.assertNotEqual(
            [mount["title"] for mount in first["mounts"]], [mount["title"] for mount in later["mounts"]]
        )

    def test_status_demo(self):
        self.authenticate("admin", "admin")
        result = self.make_jsonrpc_request("/int_ui_showcase/icecast/status")
        self.assertTrue(result["demo"])
        self.assertIsNone(result["error"])
        self.assertEqual(len(result["mounts"]), 3)

    def test_status_live_and_unreachable(self):
        self.env["ir.config_parameter"].set_param("int_ui_showcase.icecast_url", "http://icecast.test:8000/")
        self.authenticate("admin", "admin")
        response = Mock()
        response.json.return_value = {"icestats": {"source": {"listenurl": "http://icecast.test:8000/live", "listeners": 7}}}
        with patch("odoo.addons.int_ui_showcase.controllers.icecast.requests.get", return_value=response) as get:
            result = self.make_jsonrpc_request("/int_ui_showcase/icecast/status")
        self.assertEqual(get.call_args.args[0], "http://icecast.test:8000/status-json.xsl")
        self.assertFalse(result["demo"])
        self.assertEqual(result["listeners"], 7)
        with patch(
            "odoo.addons.int_ui_showcase.controllers.icecast.requests.get",
            side_effect=requests.ConnectionError("down"),
        ), mute_logger("odoo.addons.int_ui_showcase.controllers.icecast"):
            result = self.make_jsonrpc_request("/int_ui_showcase/icecast/status")
        self.assertEqual(result["error"], "Icecast is not reachable.")
        self.assertEqual(result["mounts"], [])
