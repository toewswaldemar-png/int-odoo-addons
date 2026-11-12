from unittest import mock

import requests

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

REQUEST = "odoo.addons.int_workbench.models.int_workbench_device.requests.request"


def answer(body, status=200):
    """A response of the service as requests gives it."""
    response = mock.Mock()
    response.status_code = status
    response.json.return_value = body
    response.text = str(body)
    return response


PROJECT = {
    "id": "a" * 64,
    "added_at": "2026-11-10T08:15:30Z",
    "size": 1234,
    "file_count": 5,
    "loadable": True,
    "load_error": "",
    "rows": 120,
    "problem": "",
    "origins": [{"path": "BR 187/11HA35D/Pro_1", "imported_at": "2026-11-10T08:15:30Z"}],
}


@tagged("post_install", "-at_install")
class TestIntWorkbenchServiceData(TransactionCase):
    """What Odoo asks of the service (users, log, projects) and what the service reports in its snapshot (errors)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = new_test_user(cls.env, login="wb_data_svc", groups="int_workbench.int_workbench_group_service")
        cls.manager = new_test_user(cls.env, login="wb_data_manager", groups="base.group_user,int_workbench.int_workbench_group_manager")
        cls.reader = new_test_user(cls.env, login="wb_data_reader", groups="base.group_user,int_workbench.int_workbench_group_user")
        cls.operator = new_test_user(cls.env, login="wb_data_operator", groups="base.group_user,int_workbench.int_workbench_group_operator")
        cls.device = cls.env["int.workbench.device"].create(
            {"name": "Bench", "device_ref": "main", "service_user_id": cls.service.id, "service_url": "http://workbench:8080/", "service_token": "secret"}
        )

    def as_manager(self):
        return self.device.with_user(self.manager)

    # === errors (the snapshot) === #

    def test_the_active_errors_of_a_report_become_rows(self):
        Device = self.env["int.workbench.device"].with_user(self.service)
        report = {"status": {"connected": True}, "errors": {"active": [{"word": "F1", "bit": 3, "text": "Sensor"}, {"word": "F2", "bit": 0, "text": "Fan"}]}}
        Device.service_sync(device_ref="main", snapshot=report)
        self.assertEqual({(e.word, e.bit, e.text) for e in self.device.error_ids}, {("F1", 3, "Sensor"), ("F2", 0, "Fan")})
        self.assertNotIn("errors", self.device.snapshot, "the errors are rows, not a part of the Json")
        report = {"errors": {"active": [{"word": "F2", "bit": 0, "text": "Fan (new text)"}, {"word": "F3", "bit": 7, "text": "Door"}]}}
        Device.service_sync(device_ref="main", snapshot=report)
        self.assertEqual({(e.word, e.bit, e.text) for e in self.device.error_ids}, {("F2", 0, "Fan (new text)"), ("F3", 7, "Door")})
        Device.service_sync(device_ref="main", snapshot={"errors": {"active": []}})
        self.assertFalse(self.device.error_ids)

    def test_errors_that_are_not_shaped_as_errors_are_left_out(self):
        Device = self.env["int.workbench.device"].with_user(self.service)
        Device.service_sync(device_ref="main", snapshot={"errors": {"active": ["x", {"word": 1}, {"word": "F1", "bit": "3"}, {"word": "F1", "bit": 1}]}})
        self.assertEqual(self.device.error_ids.mapped("bit"), [1])
        Device.service_sync(device_ref="main", snapshot={"errors": "nothing"})
        self.assertFalse(self.device.error_ids)

    # === what Odoo asks of the service === #

    def test_the_call_carries_the_token_and_stops_at_the_address(self):
        with mock.patch(REQUEST, return_value=answer({"users": []})) as request:
            self.as_manager().action_fetch_users()
        args, kwargs = request.call_args
        self.assertEqual(args, ("GET", "http://workbench:8080/api/v1/users"), "the slash at the end of the address is dropped")
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer secret"})
        self.assertTrue(kwargs["timeout"])

    def test_a_controller_without_an_address_cannot_be_asked(self):
        self.device.service_url = False
        with self.assertRaises(UserError):
            self.as_manager().action_fetch_users()

    def test_an_address_must_be_http(self):
        with self.assertRaises(ValidationError):
            self.device.service_url = "file:///etc/passwd"

    def test_a_refusal_of_the_service_is_told_with_its_reason(self):
        with mock.patch(REQUEST, return_value=answer({"error": "needs the admin right"}, 403)), self.assertRaisesRegex(UserError, "needs the admin right"):
            self.as_manager().action_fetch_users()

    def test_a_service_that_does_not_answer_is_told(self):
        with mock.patch(REQUEST, side_effect=requests.ConnectionError("down")), self.assertRaisesRegex(UserError, "does not answer"):
            self.as_manager().action_fetch_users()

    def test_only_a_manager_asks_the_service(self):
        for user in (self.reader, self.operator):
            with self.assertRaises(AccessError), mock.patch(REQUEST, return_value=answer({"users": []})) as request:
                self.device.with_user(user).action_fetch_users()
            request.assert_not_called()

    def test_the_token_is_for_managers_only(self):
        with self.assertRaises(AccessError):
            self.device.with_user(self.reader).service_token  # noqa: B018

    # === users === #

    def test_users_are_brought_to_what_the_service_says(self):
        users = {
            "users": [
                {"name": "anna", "roles": ["read", "clamp"], "disabled": False, "created_at": "2026-11-01T10:00:00Z", "changed_at": "2026-11-02T10:00:00+01:00"},
                {"name": "bert", "roles": ["admin"], "disabled": True, "created_at": "2026-11-01T10:00:00Z", "changed_at": "2026-11-01T10:00:00Z"},
            ]
        }
        with mock.patch(REQUEST, return_value=answer(users)):
            self.as_manager().action_fetch_users()
        rows = {user.name: user for user in self.env["int.workbench.user"].search([("device_id", "=", self.device.id)])}
        self.assertEqual(rows["anna"].roles, "read, clamp")
        self.assertEqual(str(rows["anna"].changed_at), "2026-11-02 09:00:00", "the time is kept in UTC")
        self.assertTrue(rows["bert"].disabled)
        with mock.patch(REQUEST, return_value=answer({"users": [users["users"][0]]})):
            self.as_manager().action_fetch_users()
        self.assertEqual(self.env["int.workbench.user"].search([("device_id", "=", self.device.id)]).mapped("name"), ["anna"])

    def test_users_and_log_are_for_managers_to_read(self):
        with mock.patch(REQUEST, return_value=answer({"users": [{"name": "anna", "roles": []}]})):
            self.as_manager().action_fetch_users()
        self.assertTrue(self.env["int.workbench.user"].with_user(self.manager).search([]))
        for model in ("int.workbench.user", "int.workbench.log"):
            with self.assertRaises(AccessError):
                self.env[model].with_user(self.reader).search([])

    # === log === #

    def test_the_log_is_fetched_newest_first_and_an_entry_that_ended_is_updated(self):
        entry = {
            "id": 7, "started_at": "2026-11-12T10:00:00Z", "finished_at": None, "user": "anna", "roles": ["clamp"], "remote": "10.0.0.5",
            "device": "main", "route": "POST /api/v1/clamps/0016", "kind": "clamp", "input": {"code": "0016", "action": "set"},
            "outcome": "running", "status": 0, "detail": "",
        }
        with mock.patch(REQUEST, return_value=answer({"entries": [entry], "next_before": None})) as request:
            self.as_manager().action_fetch_log()
        self.assertEqual(request.call_args.kwargs["params"], {"limit": 1000})
        log = self.env["int.workbench.log"].with_user(self.manager).search([("device_id", "=", self.device.id)])
        self.assertEqual((log.entry_id, log.outcome, log.finished_at, log.kind), (7, "running", False, "clamp"))
        self.assertIn('"code": "0016"', log.input)
        finished = {**entry, "finished_at": "2026-11-12T10:00:01Z", "outcome": "done", "status": 200}
        with mock.patch(REQUEST, return_value=answer({"entries": [finished], "next_before": None})):
            self.as_manager().action_fetch_log()
        self.assertEqual(log.search_count([("device_id", "=", self.device.id)]), 1)
        log.invalidate_recordset()
        self.assertEqual((log.outcome, log.status, str(log.finished_at)), ("done", 200, "2026-11-12 10:00:01"))

    # === projects === #

    def test_the_versions_of_the_library_are_listed_with_vehicle_and_project(self):
        broken = {**PROJECT, "id": "b" * 64, "loadable": False, "load_error": "no KS.BIN", "rows": 0, "origins": []}
        with mock.patch(REQUEST, return_value=answer({"projects": [PROJECT, broken], "root_set": True, "loader_version": "1"})):
            self.as_manager().action_fetch_projects()
        versions = {p.checksum: p for p in self.env["int.workbench.project"].search([("device_id", "=", self.device.id)])}
        good = versions["a" * 64]
        self.assertEqual((good.vehicle, good.project, good.short_id, good.rows, good.loadable), ("BR 187/11HA35D", "Pro_1", "aaaaaaaa", 120, True))
        self.assertEqual(good.display_name, "Pro_1 aaaaaaaa")
        self.assertEqual((versions["b" * 64].loadable, versions["b" * 64].load_error), (False, "no KS.BIN"))

    def test_new_folders_are_taken_over_in_packages(self):
        folders = [{"path": f"V/P{n}", "state": "new"} for n in range(30)] + [{"path": "V/old", "state": "known"}, {"path": "V/bad", "state": "error"}]

        def route(method, url, **kwargs):
            if url.endswith("/projects/inventory"):
                return answer({"items": folders})
            if url.endswith("/projects/import"):
                paths = kwargs["json"]["paths"]
                return answer({"results": [{"path": path, "ok": path != "V/P3", "id": "c" * 64, "created": True, "loadable": path != "V/P4", "error": "no"} for path in paths]})
            return answer({"projects": [PROJECT], "root_set": True, "loader_version": "1"})

        wizard = self.env["int.workbench.project.import"].with_user(self.manager).create({"device_id": self.device.id})
        with mock.patch(REQUEST, side_effect=route) as request:
            wizard.action_import()
        imports = [call for call in request.call_args_list if call.args[1].endswith("/projects/import")]
        self.assertEqual([len(call.kwargs["json"]["paths"]) for call in imports], [25, 5], "30 new folders go in packages of 25")
        self.assertEqual(wizard.state, "done")
        self.assertIn("30 folders, 29 new versions, 1 turned away", wizard.result)
        self.assertIn("V/P3: turned away", wizard.result)
        self.assertIn("V/P4: brought in, does not load", wizard.result)
        self.assertEqual(self.env["int.workbench.project"].search_count([("device_id", "=", self.device.id)]), 1, "the library is fetched afresh")

    def test_without_new_folders_the_dialog_says_so(self):
        wizard = self.env["int.workbench.project.import"].with_user(self.manager).create({"device_id": self.device.id})
        with mock.patch(REQUEST, return_value=answer({"items": [{"path": "V/old", "state": "known"}]})), self.assertRaisesRegex(UserError, "no new folders"):
            wizard.action_import()

    def test_the_dialog_is_for_managers_only(self):
        with mock.patch(REQUEST, return_value=answer({"items": []})) as request, self.assertRaises(AccessError):
            self.env["int.workbench.project.import"].with_user(self.operator).create({"device_id": self.device.id})
        request.assert_not_called()
        # the call itself checks as well: a dialog made by somebody else (or by the server) is no way to the token
        wizard = self.env["int.workbench.project.import"].create({"device_id": self.device.id})
        with mock.patch(REQUEST, return_value=answer({"items": []})) as request, self.assertRaises(AccessError):
            wizard.with_user(self.operator).action_import()
        request.assert_not_called()

    # === clamping from the list === #

    def test_the_clamp_dialog_asks_for_a_value_and_makes_a_request(self):
        self.env["int.workbench.parameter"].sudo()._sync(
            self.device, {"values": {"entries": [{"code": "0016", "text": "0", "value": 0}]}, "clamps": {"rows": [{"code": "0016", "held": False, "analog": False, "state": {}}]}}
        )
        row = self.env["int.workbench.parameter"].with_user(self.operator).search([("device_id", "=", self.device.id)])
        action = row.action_clamp()
        self.assertEqual((action["res_model"], action["target"]), ("int.workbench.parameter.clamp", "new"))
        wizard = self.env["int.workbench.parameter.clamp"].with_user(self.operator).browse(action["res_id"])
        wizard.value = 1
        wizard.action_clamp()
        command = self.env["int.workbench.command"].search([("device_id", "=", self.device.id)])
        self.assertEqual((command.code, command.action, command.value, command.user_id), ("0016", "set", 1.0, self.operator))

    def test_release_asks_only_for_the_rows_that_are_clamped(self):
        Parameter = self.env["int.workbench.parameter"]
        clamps = {"rows": [{"code": "0016", "held": True, "analog": False, "state": {"clamped": True, "value": 1}}, {"code": "0017", "held": False, "state": {}}]}
        entries = [{"code": "0016", "text": "1", "value": 1}, {"code": "0017", "text": "0", "value": 0}]
        Parameter.sudo()._sync(self.device, {"values": {"entries": entries}, "clamps": clamps})
        rows = Parameter.with_user(self.operator).search([("device_id", "=", self.device.id)])
        rows.action_release()
        commands = self.env["int.workbench.command"].search([("device_id", "=", self.device.id)])
        self.assertEqual(commands.mapped("code"), ["0016"])
        self.assertEqual(commands.action, "release")
        with self.assertRaises(UserError):
            rows.filtered(lambda row: not row.clamped).action_release()

    def test_a_reader_cannot_ask_for_a_clamp(self):
        self.env["int.workbench.parameter"].sudo()._sync(self.device, {"values": {"entries": [{"code": "0016", "text": "0", "value": 0}]}})
        row = self.env["int.workbench.parameter"].with_user(self.reader).search([("device_id", "=", self.device.id)])
        with self.assertRaises(AccessError):
            row.action_clamp()
