import base64
import io
import zipfile
from unittest import mock

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

from odoo.addons.int_workbench.models import project_check as check
from odoo.addons.int_workbench.tests.test_software import application, srec

TABLE = b"--------\r\n--BR186011 V01.1 20.03.2008 11:22 3EGM090644M2011 Grote               #\r\n0001 01  I0000.0  -- Klima Auto\r\n"
SCRIPT = b"CONFCAN\r\nBFGR001 V00.1 13.11.2007 15:10 3EGM090644M2001 Daisel                 #\r\n1\r\n03\r\n"


def project_files(extra=None):
    """The files of a project folder: the settings, a table, a script, error data (not part of a version)."""
    files = {"DEF.BIN": b"settings", "Ftab.txt": TABLE, "CANPROP.LAD": SCRIPT, "020701.fs2": b"error data"}
    files.update(extra or {})
    return list(files.items())


class TestProjectCheck(TransactionCase):
    """The rule of the version: the same files, the same checksum as in the service (projectlib)."""

    def test_the_checksum_of_a_fixed_example_is_the_one_of_the_service(self):
        # the value of projectlib TestPruefsummeFesterVektor: a.bin = "one" and B.TXT = "two"
        files = [("B.TXT", check.analyse("B.TXT", b"two").sha256), ("a.bin", check.analyse("a.bin", b"one").sha256)]
        want = "9a5ed0aac061fd9066868323b25f7247ca2f67c1ff6156721b9a1518433e3de1"
        self.assertEqual(check.checksum(files), want)
        # the order of the files and the case of the names do not matter
        self.assertEqual(check.checksum([(files[1][0].upper(), files[1][1]), (files[0][0].lower(), files[0][1])]), want)

    def test_error_data_is_no_part_of_a_version(self):
        version = check.build(project_files())
        self.assertEqual([info.name for info in version.files], ["CANPROP.LAD", "DEF.BIN", "Ftab.txt"])
        self.assertEqual(version.checksum, check.build(project_files({"other.fs2": b"more", "x.RPT": b"report"})).checksum)
        self.assertNotEqual(version.checksum, check.build(project_files({"Ftab.txt": TABLE + b"x"})).checksum)

    def test_a_file_is_told_by_its_content(self):
        kinds = {info.name: (info.kind, info.command) for info in check.build(project_files({"x.dwn": srec([(0x198000, application())])})).files}
        self.assertEqual(kinds["DEF.BIN"], ("settings", ""))
        self.assertEqual(kinds["Ftab.txt"], ("table", ""))
        self.assertEqual(kinds["CANPROP.LAD"], ("script", "confcan"))
        self.assertEqual(kinds["x.dwn"][0], "program")

    def test_the_version_line_is_read_and_the_tables_name_the_application(self):
        version = check.build(project_files())
        info = {info.name: info for info in version.files}
        self.assertEqual((info["Ftab.txt"].line_name, info["Ftab.txt"].line_version, info["Ftab.txt"].line_document), ("BR186011", "01.1", "090644"))
        self.assertEqual(info["CANPROP.LAD"].line_author, "Daisel")
        self.assertEqual((version.expected_document, version.expected_names), ("090644", "BFGR001, BR186011"))

    def test_what_is_no_project_is_refused_with_the_reason(self):
        cases = {
            "no_files": [("a.fs2", b"x")],
            "no_settings": [("Ftab.txt", TABLE)],
            "name_clash": [("DEF.BIN", b"a"), ("def.bin", b"b")],
            "bad_name": [("DEF.BIN", b"a"), ("a/b.txt", b"b")],
        }
        for code, files in cases.items():
            with self.assertRaises(check.VersionError, msg=code) as raised:
                check.build(files)
            self.assertEqual(raised.exception.code, code)
        with mock.patch.object(check, "MAX_FILE_BYTES", 4), self.assertRaises(check.VersionError) as raised:
            check.build([("DEF.BIN", b"12345")])
        self.assertEqual(raised.exception.code, "file_too_big")
        with mock.patch.object(check, "MAX_TOTAL_BYTES", 6), self.assertRaises(check.VersionError) as raised:
            check.build([("DEF.BIN", b"1234"), ("b.txt", b"1234")])
        self.assertEqual(raised.exception.code, "too_big")

    def test_a_zip_archive_of_a_project_folder_gives_its_files(self):
        def archive(entries):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as handle:
                for name, content in entries:
                    handle.writestr(name, content)
            return buffer.getvalue()

        flat = check.read_archive(archive([("DEF.BIN", b"a"), ("Ftab.txt", b"b")]))
        inside = check.read_archive(archive([("Pro_2/DEF.BIN", b"a"), ("Pro_2/Ftab.txt", b"b"), ("Pro_2/sub/deep.txt", b"c")]))
        self.assertEqual(sorted(name for name, _content in flat), ["DEF.BIN", "Ftab.txt"])
        self.assertEqual(sorted(name for name, _content in inside), ["DEF.BIN", "Ftab.txt"], "the folder that holds all is taken away, deeper ones are no part of it")
        with self.assertRaises(check.VersionError) as raised:
            check.read_archive(archive([("../DEF.BIN", b"a")]))
        self.assertEqual(raised.exception.code, "bad_name")
        with self.assertRaises(check.VersionError) as raised:
            check.read_archive(b"not a zip")
        self.assertEqual(raised.exception.code, "bad_archive")


@tagged("post_install", "-at_install")
class TestIntWorkbenchProjectVersion(TransactionCase):
    """The project management in Odoo: a version is a draft until a manager approves it, never changes, and is assigned to controllers."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Version = cls.env["int.workbench.project.version"]
        cls.technician = new_test_user(cls.env, login="wb_pv_tech", groups="base.group_user,int_workbench.int_workbench_group_technician")
        cls.manager = new_test_user(cls.env, login="wb_pv_mgr", groups="base.group_user,int_workbench.int_workbench_group_manager")
        cls.reader = new_test_user(cls.env, login="wb_pv_read", groups="base.group_user,int_workbench.int_workbench_group_user")
        cls.image = srec([(0x198000, application())])
        service = new_test_user(cls.env, login="wb_pv_svc", groups="int_workbench.int_workbench_group_service")
        cls.device = cls.env["int.workbench.device"].create({"name": "Bench", "device_ref": "main", "service_user_id": service.id})

    def bring_in(self, files=None, vehicle="BR186/Br186012", project="Pro_2", user=None, origin=""):
        return self.Version.with_user(user or self.technician)._from_files(vehicle, project, files or project_files(), origin)

    # === from files === #

    def test_the_files_of_a_folder_become_a_draft_with_the_files_and_the_expected_application(self):
        version, created = self.bring_in()
        self.assertTrue(created)
        self.assertEqual((version.state, version.vehicle, version.project, version.file_count), ("draft", "BR186/Br186012", "Pro_2", 3))
        self.assertEqual((version.expected_document, version.expected_names), ("090644", "BFGR001, BR186011"))
        self.assertEqual(version.checksum, check.build(project_files()).checksum)
        files = {file.name: file for file in version.file_ids}
        self.assertEqual(files["CANPROP.LAD"].command, "confcan")
        self.assertEqual(base64.b64decode(files["Ftab.txt"].data), TABLE)
        self.assertEqual(version.origins, "BR186/Br186012/Pro_2")
        self.assertNotIn("020701.fs2", files)

    def test_the_same_files_from_another_folder_are_the_same_version(self):
        first, _created = self.bring_in(origin="A/Pro_1")
        again, created = self.bring_in(vehicle="BR186/Copy", project="Pro_9", origin="B/Pro_9")
        self.assertEqual((again, created), (first, False))
        self.assertEqual(first.origins.splitlines(), ["A/Pro_1", "B/Pro_9"])
        self.assertFalse(self.env["int.workbench.project.folder"].search([("name", "=", "Pro_9")]), "no project for a version that was there already")

    def test_a_changed_file_is_a_new_version_of_the_same_project(self):
        first, _created = self.bring_in()
        second, created = self.bring_in(project_files({"Ftab.txt": TABLE + b"0002 01  I0000.1  -- Other\r\n"}))
        self.assertTrue(created)
        self.assertEqual(first.folder_id, second.folder_id)
        self.assertEqual(first.folder_id.version_count, 2)

    def test_a_program_in_the_folder_is_also_a_record_of_the_software(self):
        version, _created = self.bring_in(project_files({"BR186002.dwn": self.image}))
        file = version.file_ids.filtered(lambda file: file.name == "BR186002.dwn")
        self.assertEqual(file.kind, "program")
        self.assertEqual((file.software_id.kind, file.software_id.name), ("application", "BR186002"))
        # the six digits link the tables and the application: BR186002 is 090644
        self.assertEqual(file.software_id.document_number, "090644")
        self.assertIn(file.software_id, version.software_ids)

    def test_a_folder_that_is_no_project_is_refused(self):
        with self.assertRaises(UserError) as raised:
            self.bring_in([("Ftab.txt", TABLE)])
        self.assertIn("DEF.BIN", str(raised.exception))
        with self.assertRaises(UserError):
            self.bring_in(vehicle="", project="")

    # === states and rights === #

    def test_a_manager_approves_and_a_technician_does_not(self):
        version, _created = self.bring_in()
        with self.assertRaises(AccessError):
            version.with_user(self.technician).action_approve()
        with self.assertRaises(AccessError):
            version.with_user(self.technician).write({"state": "approved"})
        version.with_user(self.manager).action_approve()
        self.assertEqual((version.state, version.approved_by_id), ("approved", self.manager))

    def test_what_a_version_consists_of_cannot_be_changed(self):
        version, _created = self.bring_in()
        for values in ({"checksum": "0" * 64}, {"size": 1}, {"expected_document": "000000"}):
            with self.assertRaises(UserError, msg=str(values)):
                version.with_user(self.manager).write(values)

    def test_only_a_draft_is_deleted(self):
        draft, _created = self.bring_in()
        approved, _created = self.bring_in(project_files({"Ftab.txt": TABLE + b"x"}))
        approved.with_user(self.manager).action_approve()
        with self.assertRaises(UserError):
            approved.with_user(self.manager).unlink()
        draft.with_user(self.manager).unlink()
        self.assertFalse(draft.exists())

    def test_a_reader_sees_the_versions_and_brings_nothing_in(self):
        version, _created = self.bring_in()
        self.assertEqual(version.with_user(self.reader).file_count, 3)
        with self.assertRaises(AccessError):
            self.bring_in(project_files(), user=self.reader)

    # === the assignment === #

    def test_only_an_approved_version_is_assigned_and_the_chatter_keeps_it(self):
        version, _created = self.bring_in()
        with self.assertRaises(ValidationError):
            self.device.with_user(self.manager).write({"project_version_id": version.id})
        version.with_user(self.manager).action_approve()
        self.device.with_user(self.manager).write({"project_version_id": version.id})
        self.assertEqual(version.device_ids, self.device)
        self.assertIn("Assigned to the controller Bench", version.message_ids[0].body)
        other, _created = self.bring_in(project_files({"Ftab.txt": TABLE + b"y"}))
        other.with_user(self.manager).action_approve()
        self.device.with_user(self.manager).write({"project_version_id": other.id})
        self.assertIn("Taken away from the controller Bench", version.message_ids[0].body)
        self.assertEqual(other.device_ids, self.device)

    def test_a_version_that_a_controller_has_does_not_go_back_to_draft(self):
        version, _created = self.bring_in()
        version.with_user(self.manager).action_approve()
        self.device.with_user(self.manager).write({"project_version_id": version.id})
        with self.assertRaises(UserError):
            version.with_user(self.manager).action_draft()
        self.device.with_user(self.manager).write({"project_version_id": False})
        version.with_user(self.manager).action_draft()
        self.assertEqual(version.state, "draft")

    # === the public method for the tool, and the dialog === #

    def test_the_tool_brings_a_version_in_with_the_content_as_base64(self):
        files = [{"name": name, "data": base64.b64encode(content).decode()} for name, content in project_files()]
        answer = self.Version.with_user(self.manager).import_version("BR186/Br186012", "Pro_2", files, "stock/Pro_2")
        self.assertTrue(answer["created"])
        self.assertEqual(answer["checksum"], check.build(project_files()).checksum)
        again = self.Version.with_user(self.manager).import_version("X", "Y", files, "stock/Other")
        self.assertEqual((again["id"], again["created"]), (answer["id"], False))
        with self.assertRaises(UserError):
            self.Version.with_user(self.manager).import_version("X", "Y", [{"name": "DEF.BIN", "data": "***"}])
        with self.assertRaises(UserError):
            self.Version.with_user(self.manager).import_version("X", "Y", [{"name": "DEF.BIN"}])

    def test_the_dialog_brings_the_files_or_a_zip_archive_in(self):
        Attachment = self.env["ir.attachment"].with_user(self.technician)

        def attach(name, content):
            return Attachment.create({"name": name, "datas": base64.b64encode(content), "res_model": "int.workbench.project.upload", "res_id": 0})

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as handle:
            for name, content in project_files():
                handle.writestr("Pro_2/" + name, content)
        wizard = self.env["int.workbench.project.upload"].with_user(self.technician).create(
            {"vehicle": "BR186/Br186012", "project": "Pro_2", "attachment_ids": [(6, 0, [attach("Pro_2.zip", buffer.getvalue()).id])]}
        )
        wizard.action_upload()
        self.assertEqual(wizard.state, "done")
        self.assertEqual(wizard.version_id.checksum, check.build(project_files()).checksum)
        self.assertIn("New draft", wizard.result)
        # the same again with loose files: the version is there already
        loose = self.env["int.workbench.project.upload"].with_user(self.technician).create(
            {"vehicle": "Other", "project": "Pro_7", "attachment_ids": [(6, 0, [attach(name, content).id for name, content in project_files()])]}
        )
        loose.action_upload()
        self.assertEqual(loose.version_id, wizard.version_id)
        self.assertIn("already there", loose.result)
        two = self.env["int.workbench.project.upload"].with_user(self.technician).create(
            {"vehicle": "A", "project": "B", "attachment_ids": [(6, 0, [attach("a.zip", b"x").id, attach("DEF.BIN", b"y").id])]}
        )
        with self.assertRaises(UserError):
            two.action_upload()
