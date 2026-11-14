from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


def file_item(name, count=3, date="11.05.2010", time="10:20:30", wagon="110", train="T1", kind="history", mode=1, device="11HA30"):
    return {"name": name, "count": count, "date": date, "time": time, "wagon": wagon, "train": train, "kind": kind, "mode": mode, "device": device}


def files_part(*items, write_enabled=True):
    return {"write_enabled": write_enabled, "files": list(items), "rejected": [], "wagons": ["110"]}


def row(index, code, text="Fehler", count=0, z="K", p="A", iso="2010-05-11T10:20:30"):
    return {"index": index, "kind": "history", "wagon": "110", "train": "T1", "date": "11.05.10", "time": "10:20:30", "iso": iso, "code": code, "text": text, "p": p, "count": count, "z": z, "class": 5}


@tagged("post_install", "-at_install")
class TestIntWorkbenchFs2(TransactionCase):
    """The saved error files of a controller: the list comes with the report, the records when Odoo asks for them."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.technician = new_test_user(cls.env, login="wb_fs2_tech", groups="base.group_user,int_workbench.int_workbench_group_technician")
        cls.operator = new_test_user(cls.env, login="wb_fs2_op", groups="base.group_user,int_workbench.int_workbench_group_operator")
        cls.reader = new_test_user(cls.env, login="wb_fs2_reader", groups="base.group_user,int_workbench.int_workbench_group_user")
        cls.service = new_test_user(cls.env, login="wb_fs2_svc", groups="int_workbench.int_workbench_group_service")
        cls.device = cls.env["int.workbench.device"].create({"name": "Bench", "device_ref": "main", "service_user_id": cls.service.id})
        cls.device.capability_ids = cls.env["int.workbench.capability"]._get_or_create(["clamps", "error_files"])

    def report(self, snapshot=None):
        return self.env["int.workbench.device"].with_user(self.service).service_sync(device_ref="main", snapshot=snapshot)

    # === the list of the files and what Odoo asks for === #

    def test_the_files_of_a_report_become_rows_and_odoo_asks_for_their_records(self):
        answer = self.report({"fs2_files": files_part(file_item("110501.fs2"), file_item("110502.fs2", kind="status"))})
        files = self.device.fs2_file_ids.sorted("name")
        self.assertEqual([(f.name, f.count, f.wagon, f.kind, f.controller_type) for f in files], [("110501.fs2", 3, "110", "history", "11HA30"), ("110502.fs2", 3, "110", "status", "11HA30")])
        self.assertEqual(self.device.snapshot["fs2_files"], {"write_enabled": True}, "the files are rows, the Json keeps only whether files may be written")
        self.assertEqual(sorted(answer["want"]["fs2_records"]), ["110501.fs2", "110502.fs2"])

    def test_the_records_come_for_the_files_asked_for_and_then_nothing_is_wanted(self):
        self.report({"fs2_files": files_part(file_item("110501.fs2"))})
        answer = self.report({"fs2_files": files_part(file_item("110501.fs2")), "fs2_records": {"files": {"110501.fs2": {"rows": [row(0, 1000, "CAN", 1), row(1, 1000, "CAN", 1, z="G", p="C")]}}}})
        records = self.device.fs2_file_ids.record_ids.sorted("entry")
        self.assertEqual([(r.entry, r.code, r.event, r.priority, r.iso) for r in records], [(0, 1000, "coming", "A", "2010-05-11T10:20:30"), (1, 1000, "going", "C", "2010-05-11T10:20:30")])
        self.assertEqual(records.mapped("device_id"), self.device, "the records know the controller of their file")
        self.assertEqual(answer["want"], {}, "a file whose records are here is not asked for again")

    def test_a_file_that_changed_is_asked_for_again_and_a_file_that_went_takes_its_records(self):
        self.report({"fs2_files": files_part(file_item("110501.fs2"), file_item("110502.fs2"))})
        self.report({"fs2_files": files_part(file_item("110501.fs2"), file_item("110502.fs2")),
                     "fs2_records": {"files": {"110501.fs2": {"rows": [row(0, 1000)]}, "110502.fs2": {"rows": [row(0, 1001)]}}}})
        answer = self.report({"fs2_files": files_part(file_item("110501.fs2", count=4))})  # 110502 is gone, 110501 has a record more
        self.assertEqual(self.device.fs2_file_ids.mapped("name"), ["110501.fs2"])
        self.assertEqual(self.env["int.workbench.fs2.record"].search_count([("device_id", "=", self.device.id)]), 1, "the records of a file that is gone are gone")
        self.assertEqual(answer["want"], {"fs2_records": ["110501.fs2"]})

    def test_at_most_three_files_are_asked_for_at_a_time(self):
        answer = self.report({"fs2_files": files_part(*[file_item(f"11050{n}.fs2") for n in range(1, 6)])})
        self.assertEqual(len(answer["want"]["fs2_records"]), 3)

    def test_things_that_are_not_shaped_as_files_or_records_are_left_out(self):
        self.report({"fs2_files": files_part("x", {"name": ""}, {"name": 5}, file_item("a.fs2"))})
        self.assertEqual(self.device.fs2_file_ids.mapped("name"), ["a.fs2"])
        self.report({"fs2_files": files_part(file_item("a.fs2")), "fs2_records": {"files": {"a.fs2": {"rows": ["y", {"index": "0"}, {"index": True}, row(2, 1002)]}, "zzz.fs2": {"rows": [row(0, 1)]}}}})
        self.assertEqual(self.device.fs2_file_ids.record_ids.mapped("entry"), [2])

    # === saving and deleting === #

    def test_a_technician_asks_for_saving_and_deleting_the_files(self):
        Command = self.env["int.workbench.command"].with_user(self.technician)
        save = Command.create({"device_id": self.device.id, "action": "fs2_save", "payload": {"wagon": " 110 ", "train": "T1", "complete": True, "extra": 1}})
        self.assertEqual(save._payload_dict(), {"wagon": "110", "train": "T1", "complete": True})
        self.assertEqual(save.detail, "110 T1")
        delete = Command.create({"device_id": self.device.id, "action": "fs2_delete", "payload": {"names": ["110501.fs2"]}})
        self.assertEqual(delete.detail, "110501.fs2")

    def test_the_button_of_the_list_asks_for_the_selected_files_of_each_controller(self):
        self.report({"fs2_files": files_part(file_item("110501.fs2"), file_item("110502.fs2"), file_item("110503.fs2"))})
        files = self.device.fs2_file_ids.filtered(lambda f: f.name in ("110501.fs2", "110503.fs2"))
        files.with_user(self.technician).action_delete()
        command = self.env["int.workbench.command"].search([("device_id", "=", self.device.id), ("action", "=", "fs2_delete")])
        self.assertEqual(sorted(command._payload_dict()["names"]), ["110501.fs2", "110503.fs2"])
        self.assertEqual(command.user_id, self.technician)
        with self.assertRaises(AccessError):
            files.with_user(self.operator).action_delete()
        with self.assertRaises(UserError):
            self.env["int.workbench.fs2.file"].with_user(self.technician).action_delete()

    def test_the_payload_of_saving_and_deleting_is_checked(self):
        Command = self.env["int.workbench.command"].with_user(self.technician)
        for action, payload in (
            ("fs2_save", {"wagon": "", "train": "", "complete": True}),
            ("fs2_save", {"wagon": "110", "train": "", "complete": "yes"}),
            ("fs2_save", {"wagon": "x" * 13, "train": "", "complete": True}),
            ("fs2_save", {"wagon": "110", "train": "Tisch", "complete": True}),
            ("fs2_delete", {"names": []}),
            ("fs2_delete", {"names": ["../secrets.key"]}),
            ("fs2_delete", {"names": "110501.fs2"}),
            ("fs2_delete", {"names": [f"{n}.fs2" for n in range(101)]}),
        ):
            with self.assertRaises(ValidationError, msg=f"{action} {payload}"):
                Command.create({"device_id": self.device.id, "action": action, "payload": payload})

    def test_a_controller_without_error_files_refuses_and_an_operator_may_not(self):
        bare = self.env["int.workbench.device"].create({"name": "Bare", "device_ref": "bare", "service_user_id": self.service.id})
        bare.capability_ids = self.env["int.workbench.capability"]._get_or_create(["clamps"])
        with self.assertRaisesRegex(UserError, "cannot do this"):
            self.env["int.workbench.command"].with_user(self.technician).create({"device_id": bare.id, "action": "fs2_delete", "payload": {"names": ["a.fs2"]}})
        with self.assertRaises(AccessError):
            self.env["int.workbench.command"].with_user(self.operator).create({"device_id": self.device.id, "action": "fs2_delete", "payload": {"names": ["a.fs2"]}})

    def test_a_reader_looks_at_the_files_but_changes_nothing(self):
        self.report({"fs2_files": files_part(file_item("a.fs2"))})
        files = self.env["int.workbench.fs2.file"].with_user(self.reader)
        self.assertEqual(files.search([]).mapped("name"), ["a.fs2"])
        with self.assertRaises(AccessError):
            files.search([]).write({"wagon": "x"})
