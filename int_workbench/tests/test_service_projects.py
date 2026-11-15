import base64
import hashlib

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

from odoo.addons.int_workbench.tests.images import operating_system, srec
from odoo.addons.int_workbench.tests.test_project_version import project_files


@tagged("post_install", "-at_install")
class TestIntWorkbenchServiceProjects(TransactionCase):
    """What the service asks about projects: which version its controller is to have, the files of it, and what it reports back."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = new_test_user(cls.env, login="wb_sp_mgr", groups="base.group_user,int_workbench.int_workbench_group_manager")
        cls.service = new_test_user(cls.env, login="wb_sp_svc", groups="int_workbench.int_workbench_group_service")
        cls.other_service = new_test_user(cls.env, login="wb_sp_svc2", groups="int_workbench.int_workbench_group_service")
        Device = cls.env["int.workbench.device"]
        cls.device = Device.create({"name": "Bench", "device_ref": "main", "service_user_id": cls.service.id})
        cls.other = Device.create({"name": "Other", "device_ref": "other", "service_user_id": cls.other_service.id})
        Version = cls.env["int.workbench.project.version"]
        cls.version, _created = Version._from_files("BR186/Br186012", "Pro_2", project_files())
        cls.second, _created = Version._from_files("BR186/Br186012", "Pro_3", project_files({"Ftab.txt": b"changed"}))
        cls.draft, _created = Version._from_files("BR186/Br186012", "Pro_4", project_files({"Ftab.txt": b"a draft"}))
        (cls.version | cls.second).with_user(cls.manager).action_approve()

    def call(self, method, *args, user=None, **kwargs):
        return getattr(self.env["int.workbench.device"].with_user(user or self.service), method)(*args, **kwargs)

    # === what the controller is to have === #

    def test_nothing_is_wanted_while_nothing_is_assigned(self):
        self.assertEqual(self.call("service_projects", "main"), {"wanted": None})

    def test_the_assigned_version_is_handed_out_with_its_files_and_their_checksums(self):
        self.device.with_user(self.manager).write({"project_version_id": self.version.id})
        wanted = self.call("service_projects", "main")["wanted"]
        self.assertEqual((wanted["checksum"], wanted["vehicle"], wanted["project"]), (self.version.checksum, "BR186/Br186012", "Pro_2"))
        names = {item["name"]: item for item in wanted["files"]}
        self.assertEqual(sorted(names), ["CANPROP.LAD", "DEF.BIN", "Ftab.txt"])
        self.assertEqual(names["DEF.BIN"], {"name": "DEF.BIN", "sha256": hashlib.sha256(b"settings").hexdigest(), "size": 8})

    def test_every_approved_version_is_listed_on_request_and_no_draft(self):
        approved = self.call("service_projects", "main", everything=True)["approved"]
        self.assertEqual({item["checksum"] for item in approved}, {self.version.checksum, self.second.checksum})
        self.assertNotIn("approved", self.call("service_projects", "main"))

    def test_a_service_reaches_its_own_controller_only(self):
        with self.assertRaises(UserError):
            self.call("service_projects", "other")
        with self.assertRaises(AccessError):
            self.call("service_projects", "main", user=self.manager)

    # === the files === #

    def test_a_file_comes_as_base64_with_its_checksum(self):
        answer = self.call("service_project_file", "main", self.version.checksum, "Ftab.txt")
        content = base64.b64decode(answer["data"])
        self.assertEqual(hashlib.sha256(content).hexdigest(), answer["sha256"])
        self.assertEqual((answer["name"], answer["size"]), ("Ftab.txt", len(content)))

    def test_a_draft_and_a_file_that_is_not_there_are_not_handed_out(self):
        with self.assertRaises(UserError):
            self.call("service_project_file", "main", self.draft.checksum, "Ftab.txt")
        with self.assertRaises(UserError):
            self.call("service_project_file", "main", self.version.checksum, "nothing.txt")

    # === what the service reports === #

    def test_the_report_fills_the_mirror_and_the_state_of_the_project(self):
        self.assertEqual(self.device.project_state, "none")
        self.device.with_user(self.manager).write({"project_version_id": self.version.id})
        self.assertEqual(self.device.project_state, "unknown", "assigned, but the service has not said what it uses")
        projects = [
            {"id": self.version.checksum, "size": 100, "file_count": 3, "rows": 71, "loadable": True, "origins": [{"path": "BR186/Br186012/Pro_2"}]},
            {"id": self.second.checksum, "size": 90, "file_count": 3, "loadable": False, "load_error": "no entries", "origins": []},
        ]
        self.call("service_projects_report", "main", projects=projects, active=self.version.checksum)
        self.assertEqual(self.device.project_state, "same")
        self.assertEqual(self.device.project_active_checksum, self.version.checksum)
        mirror = self.env["int.workbench.project"].search([("device_id", "=", self.device.id)])
        self.assertEqual(len(mirror), 2)
        self.assertEqual(mirror.filtered(lambda row: row.checksum == self.version.checksum).rows, 71)
        self.assertEqual(mirror.filtered(lambda row: row.checksum == self.second.checksum).load_error, "no entries")
        # another version is in use: it differs
        self.call("service_projects_report", "main", projects=projects, active=self.second.checksum)
        self.assertEqual(self.device.project_state, "differs")
        # the report of another service does not touch this controller
        self.assertEqual(self.env["int.workbench.project"].search_count([("device_id", "=", self.other.id)]), 0)

    def test_a_report_with_nonsense_is_taken_as_far_as_it_makes_sense(self):
        self.call("service_projects_report", "main", projects="nothing", active=12)
        self.assertFalse(self.device.project_active_checksum)
        self.call("service_projects_report", "main", projects=[{"id": 5}, "x", {"id": self.version.checksum}], active="x" * 100)
        self.assertFalse(self.device.project_active_checksum)
        self.assertEqual(self.env["int.workbench.project"].search_count([("device_id", "=", self.device.id)]), 1)

    # === the programs === #

    def test_an_approved_program_is_handed_out_with_its_content_and_nothing_else(self):
        Software = self.env["int.workbench.software"]
        image = srec([(0, operating_system())])
        software, _created = Software._from_file("v310.dwn", image)
        with self.assertRaises(UserError):
            self.call("service_software", "main", software.sha256)  # a draft
        software.with_user(self.manager).action_approve()
        answer = self.call("service_software", "main", software.sha256)
        self.assertEqual((answer["kind"], answer["hardware"], answer["size"], answer["name"]), ("os", "ha3x", len(image), "v310.dwn"))
        self.assertEqual(base64.b64decode(answer["data"]), image)
        software.with_user(self.manager).action_retire()
        with self.assertRaises(UserError):
            self.call("service_software", "main", software.sha256)
        with self.assertRaises(UserError):
            self.call("service_software", "main", "0" * 64)
        with self.assertRaises(AccessError):
            self.call("service_software", "main", software.sha256, user=self.manager)
