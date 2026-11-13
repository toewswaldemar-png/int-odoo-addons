from unittest import mock

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

from odoo.addons.int_workbench.models.int_workbench_device import VALUES_MESSAGE_IDS
from odoo.addons.int_workbench.models.int_workbench_parameter import SEQUENCE_PER_DEVICE


def entry(code, text="0", value=0, name=None, status="ok", unit="", pages=(6,), stale=False, time="t1"):
    """A row as the service reports it (the key ``time`` changes with every read and does not count)."""
    return {"id": int(code), "code": code, "name": name or f"Row {code}", "pages": list(pages), "status": status, "value": value,
            "text": text, "unit": unit, "stale": stale, "time": time, "clamp": {"state": "autom.", "clamped": False}}


def report(entries, clamps=()):
    return {"status": {"connected": True}, "values": {"entries": entries}, "clamps": {"rows": list(clamps)}}


def clamp_row(code, held=False, value=0, analog=False):
    return {"code": code, "held": held, "analog": analog, "state": {"clamped": held, "value": value}}


@tagged("post_install", "-at_install")
class TestIntWorkbenchParameter(TransactionCase):
    """The rows of a controller are ordinary records, brought to each report of the service; only what changed is written."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = new_test_user(cls.env, login="regler_svc", groups="int_workbench.int_workbench_group_service")
        cls.reader = new_test_user(cls.env, login="regler_reader", groups="base.group_user,int_workbench.int_workbench_group_user")
        cls.device = cls.env["int.workbench.device"].create({"name": "Bench", "device_ref": "main", "service_user_id": cls.service.id})
        cls.other = cls.env["int.workbench.device"].create({"name": "Other", "device_ref": "second", "service_user_id": cls.service.id})
        cls.Parameter = cls.env["int.workbench.parameter"]

    def sync(self, entries, clamps=(), device=None):
        """The rows that were created or changed."""
        return self.Parameter.sudo()._sync(device or self.device, report(entries, clamps))[0]

    def structure(self, entries, device=None):
        """Whether rows were created or removed."""
        return self.Parameter.sudo()._sync(device or self.device, report(entries))[1]

    def rows(self, device=None):
        return {row.code: row for row in self.Parameter.search([("device_id", "=", (device or self.device).id)])}

    def test_the_rows_of_a_report_become_records(self):
        self.sync([entry("0001", "1", 1), entry("0005", "22.3°C", 22.3, unit="°C", pages=(6, 7))])
        rows = self.rows()
        self.assertEqual(set(rows), {"0001", "0005"})
        self.assertEqual((rows["0005"].text, rows["0005"].value, rows["0005"].unit, rows["0005"].pages), ("22.3°C", 22.3, "°C", "6,7"))

    def test_the_same_report_again_writes_nothing(self):
        self.sync([entry("0001", "1", 1), entry("0002", "0", 0)])
        with mock.patch.object(type(self.Parameter), "write", autospec=True, side_effect=type(self.Parameter).write) as write:
            # only the time of the read differs
            changed = self.sync([entry("0001", "1", 1, time="t2"), entry("0002", "0", 0, time="t2")])
        self.assertFalse(changed)
        write.assert_not_called()

    def test_only_the_row_that_changed_is_written(self):
        self.sync([entry("0001", "1", 1), entry("0005", "22.3°C", 22.3, unit="°C")])
        with mock.patch.object(type(self.Parameter), "write", autospec=True, side_effect=type(self.Parameter).write) as write:
            changed = self.sync([entry("0001", "1", 1, time="t2"), entry("0005", "22.4°C", 22.4, unit="°C", time="t2")])
        self.assertEqual(changed.mapped("code"), ["0005"])
        self.assertEqual(write.call_count, 1)
        self.assertEqual(self.rows()["0005"].text, "22.4°C")
        self.assertEqual(self.rows()["0001"].text, "1")

    def test_a_row_that_is_no_longer_reported_is_removed_and_a_new_one_is_added(self):
        self.sync([entry("0001"), entry("0002")])
        changed = self.sync([entry("0002"), entry("0003")])
        self.assertEqual(set(self.rows()), {"0002", "0003"})
        self.assertEqual(changed.mapped("code"), ["0003"])

    def test_clamp_state_comes_from_the_clamp_rows(self):
        self.sync([entry("0016"), entry("0017")], clamps=[clamp_row("0016", held=True, value=1), clamp_row("0017")])
        rows = self.rows()
        self.assertEqual((rows["0016"].can_clamp, rows["0016"].clamped, rows["0016"].clamp_value), (True, True, 1.0))
        self.assertEqual((rows["0017"].can_clamp, rows["0017"].clamped), (True, False))
        self.sync([entry("0016"), entry("0017")], clamps=[clamp_row("0016"), clamp_row("0017")])
        self.assertFalse(self.rows()["0016"].clamped)

    def test_a_row_without_a_clamp_row_cannot_be_clamped(self):
        self.sync([entry("0001")])
        self.assertFalse(self.rows()["0001"].can_clamp)

    def test_rows_of_two_controllers_do_not_mix(self):
        self.sync([entry("0001", "1", 1)])
        self.sync([entry("0001", "0", 0)], device=self.other)
        self.assertEqual(self.rows()["0001"].text, "1")
        self.assertEqual(self.rows(self.other)["0001"].text, "0")

    def test_what_is_not_shaped_as_a_row_is_left_out(self):
        self.sync(["x", {"name": "no code"}, {"code": 7}, entry("0001")])
        self.assertEqual(set(self.rows()), {"0001"})
        self.assertFalse(self.Parameter.sudo()._sync(self.device, "nonsense")[0])

    def test_the_call_of_the_service_keeps_the_rows_and_tells_the_page(self):
        Device = self.env["int.workbench.device"]

        def sync(entries):
            return Device.with_user(self.service).service_sync(device_ref="main", snapshot=report(entries))

        with mock.patch.object(type(Device), "_bus_send", autospec=True) as bus:
            sync([entry("0001", "0", 0)])
            self.assertEqual(bus.call_count, 0, "nobody looks, so nobody is told")
            self.device.watch()
            sync([entry("0001", "0", 0), entry("0002")])
            self.assertEqual(bus.call_args.args[1:], ("int_workbench/values", {"ids": [], "reload": True}), "a row came: load the list afresh")
            sync([entry("0001", "1", 1), entry("0002")])
            ids = [self.rows()["0001"].id]
            self.assertEqual(bus.call_args.args[1:], ("int_workbench/values", {"ids": ids, "reload": False}), "a row changed: its id")
            calls = bus.call_count
            sync([entry("0001", "1", 1, time="t2"), entry("0002")])
            self.assertEqual(bus.call_count, calls, "nothing changed, so nothing is told")
            sync([entry("0001", "1", 1)])
            self.assertEqual(bus.call_args.args[1:], ("int_workbench/values", {"ids": [], "reload": True}), "a row went: load the list afresh")
        self.assertEqual(self.rows()["0001"].text, "1")

    def test_many_changed_rows_are_not_listed_in_the_message(self):
        Device = self.env["int.workbench.device"]
        many = VALUES_MESSAGE_IDS + 1
        Device.with_user(self.service).service_sync(device_ref="main", snapshot=report([entry(f"{n:04d}", "0", 0) for n in range(1, many + 1)]))
        self.device.watch()
        with mock.patch.object(type(Device), "_bus_send", autospec=True) as bus:
            Device.with_user(self.service).service_sync(device_ref="main", snapshot=report([entry(f"{n:04d}", "1", 1) for n in range(1, many + 1)]))
        self.assertEqual(bus.call_args.args[1:], ("int_workbench/values", {"ids": [], "reload": True}))

    def test_rows_created_or_removed_are_told_as_structure(self):
        self.assertTrue(self.structure([entry("0001")]))
        self.assertFalse(self.structure([entry("0001", "5", 5)]), "a changed row is no change of the structure")
        self.assertTrue(self.structure([]))

    def test_a_reader_reads_the_rows_and_changes_nothing(self):
        self.sync([entry("0001")])
        row = self.Parameter.with_user(self.reader).search([("device_id", "=", self.device.id)])
        self.assertTrue(row)
        row.read(["code", "text"])
        for action in (lambda: row.write({"text": "x"}), lambda: self.Parameter.with_user(self.reader).create({"device_id": self.device.id, "code": "9"}), row.unlink):
            with self.assertRaises(AccessError):
                action()

    def test_the_rows_are_searched_filtered_and_grouped_like_any_records(self):
        self.sync([entry("0001", "1", 1, unit=""), entry("0005", "22.3°C", 22.3, unit="°C"), entry("0006", "5.1°C", 5.1, unit="°C", status="fault")])
        Parameter = self.Parameter
        self.assertEqual(Parameter.search([("device_id", "=", self.device.id), ("unit", "=", "°C")]).mapped("code"), ["0005", "0006"])
        self.assertEqual(Parameter.search([("device_id", "=", self.device.id), ("value", ">", 10)]).mapped("code"), ["0005"])
        groups = Parameter._read_group([("device_id", "=", self.device.id)], ["status"], ["__count"])
        self.assertEqual(dict(groups), {"ok": 2, "fault": 1})

    def test_a_removed_controller_takes_its_rows_with_it(self):
        self.sync([entry("0001")])
        device_id = self.device.id
        self.device.unlink()
        self.assertFalse(self.Parameter.search([("device_id", "=", device_id)]))

    def test_a_clamp_request_points_to_its_row(self):
        self.sync([entry("0016")])
        operator = new_test_user(self.env, login="regler_operator", groups="base.group_user,int_workbench.int_workbench_group_operator")
        Command = self.env["int.workbench.command"].with_user(operator)
        known = Command.create({"device_id": self.device.id, "code": "0016", "action": "set", "value": 1})
        unknown = Command.create({"device_id": self.device.id, "code": "0099", "action": "release"})
        self.assertEqual(known.parameter_id, self.rows()["0016"])
        self.assertFalse(unknown.parameter_id)
        self.assertEqual(self.rows()["0016"].command_ids, known)
        self.rows()["0016"].unlink()
        self.assertFalse(known.parameter_id, "a row that is gone leaves the request in the log")

    def test_the_list_of_the_rows_is_a_view_of_its_own_that_a_reader_can_load(self):
        views = self.Parameter.with_user(self.reader).get_views([(False, "list"), (False, "search")])
        self.assertIn('js_class="int_workbench.parameter_list"', views["views"]["list"]["arch"])
        self.assertIn("by_device", views["views"]["search"]["arch"])

    # ---- the star and the order ----

    def test_a_star_is_the_users_own(self):
        self.sync([entry("0001"), entry("0002")])
        other = new_test_user(self.env, login="regler_reader2", groups="base.group_user,int_workbench.int_workbench_group_user")
        Mine = self.Parameter.with_user(self.reader)
        scope = [("device_id", "=", self.device.id)]
        mine = Mine.search(scope + [("code", "=", "0001")])
        mine.write({"is_favorite": True})
        self.assertTrue(mine.is_favorite)
        self.assertFalse(self.Parameter.with_user(other).browse(mine.id).is_favorite, "another user has no star there")
        self.assertEqual(Mine.search(scope + [("is_favorite", "=", True)]).mapped("code"), ["0001"])
        self.assertEqual(Mine.search(scope + [("is_favorite", "=", False)]).mapped("code"), ["0002"])
        self.assertFalse(self.Parameter.with_user(other).search(scope + [("is_favorite", "=", True)]))
        mine.write({"is_favorite": False})
        self.assertFalse(mine.is_favorite)

    def test_a_star_is_not_a_right_to_change_the_row(self):
        self.sync([entry("0001")])
        row = self.Parameter.with_user(self.reader).search([("device_id", "=", self.device.id)])
        with self.assertRaises(AccessError):
            row.write({"is_favorite": True, "text": "x"})

    def test_a_report_keeps_stars_and_order(self):
        self.sync([entry("0001"), entry("0002")])
        rows = self.rows()
        rows["0001"].with_user(self.reader).write({"is_favorite": True})
        rows["0002"].write({"sequence": -5})
        self.sync([entry("0001", "1", 1), entry("0002", "1", 1)])
        self.assertTrue(self.rows()["0001"].with_user(self.reader).is_favorite)
        self.assertEqual(self.rows()["0002"].sequence, -5)

    def test_new_rows_come_in_the_order_of_the_report_a_controller_after_the_other(self):
        self.sync([entry("0007"), entry("0003")])
        self.sync([entry("0001")], device=self.other)
        rows = self.rows()
        base = self.device.id * SEQUENCE_PER_DEVICE
        self.assertEqual([rows["0007"].sequence, rows["0003"].sequence], [base, base + 1])
        self.assertEqual(self.rows(self.other)["0001"].sequence, self.other.id * SEQUENCE_PER_DEVICE)

    def test_an_operator_arranges_the_rows_a_reader_does_not(self):
        self.sync([entry("0001"), entry("0002"), entry("0003")])
        operator = new_test_user(self.env, login="regler_operator2", groups="base.group_user,int_workbench.int_workbench_group_operator")
        rows = self.Parameter.with_user(operator).search([("device_id", "=", self.device.id)])
        # what the list does when a row is dragged: web_resequence, which writes the sequence of each row
        rows.sorted(key=lambda r: r.code, reverse=True).web_resequence({"code": {}}, "sequence", 0)
        self.assertEqual(self.Parameter.search([("device_id", "=", self.device.id)], order="sequence").mapped("code"), ["0003", "0002", "0001"])
        with self.assertRaises(AccessError):
            rows.with_user(self.reader).write({"sequence": 99})
        with self.assertRaises(AccessError):
            rows.write({"sequence": 1, "text": "x"})

    def test_the_list_can_be_starred_by_a_reader_and_dragged_by_an_operator(self):
        operator = new_test_user(self.env, login="regler_operator3", groups="base.group_user,int_workbench.int_workbench_group_operator")

        def arch(user):
            return self.Parameter.with_user(user).get_views([(False, "list")])["views"]["list"]["arch"]

        reader_arch, operator_arch = arch(self.reader), arch(operator)
        # nobody may write the model, and the server would make the list read-only: the view says edit="1", so the star is not grey
        self.assertIn('edit="1"', reader_arch)
        self.assertIn('widget="boolean_favorite"', reader_arch)
        self.assertNotIn('widget="handle"', reader_arch, "a reader cannot arrange the rows, so there is no handle")
        self.assertIn('widget="handle"', operator_arch)
        self.assertIn('edit="1"', operator_arch)
        # the operator edits the list in place (switch, value, several ticked rows); the reader sees the state of the clamp
        for part in ('name="clamp_toggle"', 'name="clamp_input"', 'widget="boolean_toggle"'):
            self.assertIn(part, operator_arch)
            self.assertNotIn(part, reader_arch)
        # (the state field itself stays in both: the value is marked by it)
        self.assertIn('string="Clamped to"', reader_arch)
        self.assertNotIn('string="Clamped to"', operator_arch)
        for arch_of_user in (operator_arch, reader_arch):
            # the row says how it stands: clamped, could not be read, out of date
            for part in ('decoration-warning="clamped"', "decoration-danger=\"status != 'ok'\"", 'decoration-muted="stale"'):
                self.assertIn(part, arch_of_user)
            self.assertIn('editable="bottom"', arch_of_user)
            self.assertIn('multi_edit="1"', arch_of_user)
        self.assertNotIn('name="action_clamp"', operator_arch, "the dialog is gone")
