from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


def history_item(code, text, count=0, time="2026-11-14T09:57:18", z="K", p="A", raw=""):
    return {"code": code, "text": text, "count": count, "time": time, "z": z, "p": p, "class": 5, "raw": raw or f"{code:04d}"}


def status_item(index, code, text="", count=0, active=False, newest=False, rank=-1, level=0, wprio=0, lmzus=0, quit=False, reported=None):
    return {
        "index": index,
        "code": code,
        "text": text,
        "count": count,
        "active": active,
        "newest": newest,
        "rank": rank,
        "level": level,
        "wprio": wprio,
        "lmzus": lmzus,
        "sig_f": active,
        "sig": active,
        "quit": quit,
        "bit9": False,
        "reported": active or level != 0 if reported is None else reported,
        "z": "K" if active else "G",
        "p": "A" if level == 5 else "",
        "extra": False,
        "raw": f"{index:04x}",
    }


def memory(history, status, read_at="2026-11-14T09:57:18+01:00", **extra):
    return {
        "errors_memory": {
            "status": "ok",
            "read_at": read_at,
            "connected": True,
            "stale": False,
            "clear_enabled": False,
            "history_count": len(history),
            "status_total": len(status),
            "active_count": sum(1 for item in status if isinstance(item, dict) and item.get("active")),
            "history": history,
            "status_all": status,
            **extra,
        }
    }


@tagged("post_install", "-at_install")
class TestIntWorkbenchErrorMemory(TransactionCase):
    """The error memory of a controller (history and status records) as the report of the service carries it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = new_test_user(cls.env, login="wb_mem_svc", groups="int_workbench.int_workbench_group_service")
        cls.reader = new_test_user(cls.env, login="wb_mem_reader", groups="base.group_user,int_workbench.int_workbench_group_user")
        cls.device = cls.env["int.workbench.device"].create({"name": "Bench", "device_ref": "main", "service_user_id": cls.service.id})

    def report(self, snapshot):
        self.env["int.workbench.device"].with_user(self.service).service_sync(device_ref="main", snapshot=snapshot)

    # === history === #

    def test_the_history_of_a_report_becomes_rows(self):
        self.report(memory([history_item(9998, "Initialization"), history_item(1000, "CAN bus", z="K"), history_item(1000, "CAN bus", 1, z="G", p="C")], []))
        rows = self.device.error_history_ids.sorted("entry")
        self.assertEqual(rows.mapped("entry"), [1, 2, 3])
        self.assertEqual(rows.mapped("code"), [9998, 1000, 1000])
        self.assertEqual(rows.mapped("event"), ["coming", "coming", "going"])
        self.assertEqual((rows[2].text, rows[2].count, rows[2].priority, rows[2].controller_time), ("CAN bus", 1, "C", "2026-11-14T09:57:18"))
        self.assertEqual(rows[1].raw, "1000")

    def test_a_new_reading_changes_and_removes_entries(self):
        self.report(memory([history_item(1000, "A"), history_item(1001, "B"), history_item(1003, "C")], []))
        self.report(memory([history_item(9999, "Cleared"), history_item(1001, "B2")], [], read_at="2026-11-14T09:58:18+01:00"))
        rows = self.device.error_history_ids.sorted("entry")
        self.assertEqual([(row.entry, row.code, row.text) for row in rows], [(1, 9999, "Cleared"), (2, 1001, "B2")])

    def test_the_rows_stay_when_the_memory_was_not_read_again(self):
        self.report(memory([history_item(1000, "A")], [status_item(0, 1000, "A", active=True, rank=0)]))
        self.report(memory([history_item(1001, "B")], [status_item(0, 1001, "B")]))  # the same read_at: nothing new was read
        self.assertEqual(self.device.error_history_ids.mapped("code"), [1000])
        self.assertEqual(self.device.error_status_ids.mapped("code"), [1000])

    def test_an_unreadable_memory_leaves_the_rows_as_they_are(self):
        self.report(memory([history_item(1000, "A")], [status_item(0, 1000, "A", active=True, rank=0)]))
        self.report({"errors_memory": {"status": "error", "error": "no answer", "read_at": "2026-11-14T10:00:00+01:00"}})
        self.assertEqual(self.device.error_history_ids.mapped("code"), [1000])
        self.assertEqual(self.device.error_status_ids.mapped("code"), [1000])
        self.assertEqual(self.device.snapshot["errors_memory"], {"status": "error", "error": "no answer", "read_at": "2026-11-14T10:00:00+01:00"})

    def test_items_that_are_not_shaped_as_entries_are_left_out(self):
        self.report(memory(["x", {"code": "1000"}, history_item(1001, "B")], ["y", {"index": "0"}, {"index": True}, status_item(2, 1002, "C")]))
        self.assertEqual(self.device.error_history_ids.mapped("code"), [1001])
        self.assertEqual(self.device.error_status_ids.mapped("element"), [3])
        self.report({"errors_memory": "nothing"})
        self.assertEqual(self.device.error_history_ids.mapped("code"), [1001], "a part that is no object changes nothing")

    # === status records === #

    def test_the_status_records_of_a_report_become_rows(self):
        status = [
            status_item(53, 9050, "Heartbeat", count=3, active=True, newest=True, rank=0, level=5, wprio=2, lmzus=2),
            status_item(16, 1003, "CAN stop", count=3, active=True, rank=1, level=5, wprio=1, lmzus=2),
            status_item(1, 1301, "Flap", rank=4),
        ]
        self.report(memory([], status))
        rows = self.device.error_status_ids.sorted("rank")
        self.assertEqual(rows.mapped("element"), [54, 17, 2], "the element counts from 1, the index from 0")
        self.assertEqual(rows.mapped("present"), [True, True, False])
        self.assertEqual(rows.mapped("newest"), [True, False, False])
        self.assertEqual((rows[0].wprio, rows[0].lmzus, rows[0].level, rows[0].count), (2, 2, 5, 3))
        self.assertEqual(rows.mapped("reported"), [True, True, False])
        self.assertEqual(len(self.env["int.workbench.error.status"].search([("device_id", "=", self.device.id)])), 3, "a record that is not there is not hidden")

    def test_a_service_without_status_all_gives_only_the_records_the_original_lists(self):
        old = memory([], [])
        del old["errors_memory"]["status_all"]
        old["errors_memory"]["status_records"] = [status_item(0, 1000, "A", active=True, rank=0)]
        self.report(old)
        self.assertEqual(self.device.error_status_ids.mapped("element"), [1])
        self.assertEqual(self.device.error_status_ids.rank, 0)

    def test_a_record_that_went_is_changed_not_added(self):
        self.report(memory([], [status_item(0, 1000, "A", count=1, active=True, newest=True, rank=0, level=5, wprio=2, lmzus=2)]))
        row = self.device.error_status_ids
        self.report(memory([], [status_item(0, 1000, "A", count=1, level=1, rank=0)], read_at="2026-11-14T09:58:18+01:00"))
        self.assertEqual(self.device.error_status_ids, row)
        self.assertEqual((row.present, row.newest, row.level, row.wprio, row.reported), (False, False, 1, 0, True))

    # === the Json and the rights === #

    def test_the_json_keeps_how_the_memory_was_read_not_what_it_holds(self):
        self.report(memory([history_item(1000, "A")], [status_item(0, 1000, "A")]))
        kept = self.device.snapshot["errors_memory"]
        self.assertEqual((kept["status"], kept["read_at"], kept["history_count"], kept["status_total"]), ("ok", "2026-11-14T09:57:18+01:00", 1, 1))
        self.assertFalse({"history", "status_all", "status_records"} & set(kept))

    def test_a_reader_may_look_but_not_change(self):
        self.report(memory([history_item(1000, "A")], [status_item(0, 1000, "A")]))
        history = self.env["int.workbench.error.history"].with_user(self.reader)
        status = self.env["int.workbench.error.status"].with_user(self.reader)
        self.assertEqual(history.search([]).mapped("code"), [1000])
        self.assertEqual(status.search([]).mapped("code"), [1000])
        with self.assertRaises(AccessError):
            history.search([]).write({"text": "x"})
        with self.assertRaises(AccessError):
            status.create({"device_id": self.device.id, "element": 9})
