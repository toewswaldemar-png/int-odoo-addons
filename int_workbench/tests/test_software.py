import base64
import os

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

from odoo.addons.int_workbench.models import software_check as check

DATA = os.path.join(os.path.dirname(__file__), "data")


def srec(parts, end=True):
    """The text of an S-Record file with the given ``[(address, bytes)]`` (S2 records of 32 bytes, an S0 header and an S8 end record)."""

    def record(kind, address, data):
        body = bytes([len(data) + 4]) + address.to_bytes(3, "big") + data
        return ("S%s%s%02X" % (kind, body.hex().upper(), (sum(body) & 0xFF) ^ 0xFF)).encode()

    lines = [record("0", 0, b"HDR")]
    for address, data in parts:
        for offset in range(0, len(data), 32):
            lines.append(record("2", address + offset, data[offset : offset + 32]))
    if end:
        lines.append(record("8", 0, b""))
    return b"\r\n".join(lines) + b"\r\n"


def field(text, length=32):
    return text.encode().ljust(length, b"\x00")


def application(name="BR186002", resource="R090644", document="3EGM090644E2002", expected="3EGM009880E9210", other_order=False):
    mark = b"\x05\x06\xfe\xff" if other_order else b"\x05\x06\xff\xfe"
    prefix = b"\xb3\x8f\x00\xf0\x00\xf0" if other_order else b"\x00\x04\x8b\xd5\xb3\x8f\x01\x5a\x01\x5a"
    return prefix + mark + field(name) + field(resource) + b"RES-GLOBAL".ljust(40, b"\x00") + document.encode() + b"\x00" + expected.encode() + b"\x00" * 20


def operating_system(identity="3EGM 0098 80 E0310"):
    return b"\x00\x40\x24\x1c" * 8 + identity.encode() + b"\x00" * 30


APPLICATION_TEXT = (
    b"\r\n\r\n#dl 1\r\n#PLC  Applikation: CANTAUFE, Resource: 64EX_A00, Byteanz. = 8\r\n"
    b"Erstelldatum Resource (GMT+1) = 21.01.2003  15:34:37  \r\n> \r\n*1A44F0 75B3 8F00\r\n*1A44F8 0001 0002\r\n#PLC  Ende\r\n\r\n> \r\n"
)


class TestSoftwareCheck(TransactionCase):
    """What reading a file says about it: by the content, never by the name."""

    def test_an_operating_system_is_told_by_where_it_starts_and_says_its_version(self):
        result = check.check_file("anything.bin", srec([(0, operating_system())]))
        self.assertEqual((result.kind, result.hardware, result.os_version), ("os", "ha3x", "3.10"))
        self.assertEqual(result.ranges[0][0], 0)
        self.assertEqual(len(result.sha256), 64)

    def test_an_application_says_its_name_resource_document_and_the_operating_system_it_is_made_for(self):
        result = check.check_file("BR186002.dwn", srec([(0x198000, application()), (0x2B8000, b"\x01" * 64)]))
        self.assertEqual((result.kind, result.hardware), ("application", "ha3x"))
        self.assertEqual((result.app_name, result.resource), ("BR186002", "R090644"))
        # the number of the operating system (009880) is not the number of the application
        self.assertEqual((result.document, result.expected_os), ("3EGM090644E2002", "2.10"))
        self.assertEqual(result.warnings, [])

    def test_operating_system_and_application_in_one_file_is_a_combined_image(self):
        result = check.check_file("x.m00", srec([(0, operating_system("3EGM 0098 80 E0211")), (0x198000, application("ALP45010", "ALP45010"))]))
        self.assertEqual((result.kind, result.hardware, result.os_version, result.app_name), ("combined", "ha3x", "2.11", "ALP45010"))

    def test_family_b_starts_at_0x4d000_and_has_the_header_with_the_other_byte_order(self):
        result = check.check_file("R2016010.DWN", srec([(0x4D000, application("R2016010", "RS090189", "3EGM090189E2010", other_order=True))]))
        self.assertEqual((result.kind, result.hardware, result.app_name, result.resource), ("combined", "family_b", "R2016010", "RS090189"))

    def test_the_bootstrap_and_the_block_of_parameters_are_told_by_their_place(self):
        boot = check.check_file("b.dwn", srec([(0xFF8000, b"\x01\x02" * 40)]))
        self.assertEqual((boot.kind, boot.hardware), ("bootloader", "ha3x"))
        parameters = check.check_file("hsi.dwn", srec([(0x3B385C, b"3EGM 0098 80 E0205\x00hsi_frm.c ver: 1.00")]))
        self.assertEqual((parameters.kind, parameters.os_version), ("parameter", "2.05"))

    def test_a_real_block_of_parameters_and_a_real_bootstrap(self):
        with open(os.path.join(DATA, "hsiRNK0100.dwn"), "rb") as handle:
            parameters = check.check_file("hsiRNK0100.dwn", handle.read())
        self.assertEqual((parameters.kind, parameters.hardware, parameters.os_version), ("parameter", "ha3x", "2.05"))
        with open(os.path.join(DATA, "bot.dwn"), "rb") as handle:
            boot = check.check_file("bot.dwn", handle.read())
        self.assertEqual((boot.kind, boot.hardware, boot.ranges[0][0]), ("bootloader", "ha3x", 0xFF8000))

    def test_a_program_text_is_read_by_its_header(self):
        result = check.check_file("CANTAUFE.LAD", APPLICATION_TEXT)
        self.assertEqual((result.kind, result.app_name, result.resource, result.created), ("text", "CANTAUFE", "64EX_A00", "21.01.2003 15:34:37"))
        self.assertEqual(result.data_size, 8)

    def test_a_memory_range_that_is_nobody_s_is_unknown_with_a_warning(self):
        result = check.check_file("x.dwn", srec([(0x500000, b"\x01" * 16)]))
        self.assertEqual(result.kind, "unknown")
        self.assertEqual([code for code, _values in result.warnings], ["unknown_ranges"])

    def test_the_name_is_no_proof(self):
        result = check.check_file("B1852010.dwn", srec([(0x198000, application("B1852006", "R090622", "3EGM090622E2004"))]))
        self.assertEqual(result.app_name, "B1852006")
        self.assertEqual([code for code, _values in result.warnings], ["name_differs"])

    def test_files_that_are_no_programs_are_refused_with_the_reason(self):
        bad = bytearray(srec([(0, operating_system())]))
        bad[40] = ord("1") if bad[40] != ord("1") else ord("2")  # one digit of one record, still a hexadecimal digit
        cases = {
            "empty": b"",
            "not_a_program": b"CONFCAN\r\n# nothing\r\n",
            "bad_checksum": bytes(bad),
            "no_data": b"S0030000FC\r\nS9030000FC\r\n",
            "text_no_data": b"#PLC  Applikation: X, Resource: Y\r\n",
        }
        for code, content in cases.items():
            with self.assertRaises(check.ImageError, msg=code) as raised:
                check.check_file("x", content)
            self.assertEqual(raised.exception.code, code)


@tagged("post_install", "-at_install")
class TestIntWorkbenchSoftware(TransactionCase):
    """The programs in Odoo: one record for each content, approved by a manager, never changed."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Software = cls.env["int.workbench.software"]
        cls.technician = new_test_user(cls.env, login="wb_sw_tech", groups="base.group_user,int_workbench.int_workbench_group_technician")
        cls.manager = new_test_user(cls.env, login="wb_sw_mgr", groups="base.group_user,int_workbench.int_workbench_group_manager")
        cls.reader = new_test_user(cls.env, login="wb_sw_read", groups="base.group_user,int_workbench.int_workbench_group_user")
        cls.image = srec([(0x198000, application())])

    def bring_in(self, name="BR186002.dwn", content=None, user=None):
        return (self.Software.with_user(user or self.technician))._from_file(name, content or self.image)

    # === from a file === #

    def test_a_file_becomes_a_draft_that_says_what_it_is(self):
        software, created = self.bring_in()
        self.assertTrue(created)
        self.assertEqual(
            (software.state, software.kind, software.hardware, software.name, software.os_version, software.document, software.expected_os),
            ("draft", "application", "ha3x", "BR186002", "", "3EGM090644E2002", "2.10"),
        )
        self.assertEqual(software.sources, "BR186002.dwn")
        self.assertEqual(base64.b64decode(software.data), self.image)
        self.assertIn("0x198000", software.ranges)

    def test_the_same_content_under_another_name_is_the_same_program(self):
        first, _created = self.bring_in("BR186002.dwn")
        again, created = self.bring_in("kopie_von_br186002.m00")
        self.assertEqual((again, created), (first, False))
        self.assertEqual(first.sources.splitlines(), ["BR186002.dwn", "kopie_von_br186002.m00"])
        self.assertEqual(self.Software.search_count([("sha256", "=", first.sha256)]), 1)

    def test_a_file_that_is_no_program_is_refused_with_its_name_and_the_reason(self):
        with self.assertRaises(UserError) as raised:
            self.bring_in("notes.txt", b"just words")
        self.assertIn("notes.txt", str(raised.exception))
        self.assertIn("neither an S-Record image", str(raised.exception))
        self.assertFalse(self.Software.search([("filename", "=", "notes.txt")]))

    def test_the_name_of_an_operating_system_says_its_version(self):
        software, _created = self.bring_in("v310.dwn", srec([(0, operating_system())]))
        self.assertEqual((software.kind, software.name, software.os_version), ("os", "Operating system 3.10", "3.10"))

    def test_the_warning_of_a_name_that_differs_is_kept_on_the_record(self):
        software, _created = self.bring_in("B1852010.dwn", srec([(0x198000, application("B1852006", "R090622", "3EGM090622E2004"))]))
        self.assertIn("B1852010.dwn", software.warnings)
        self.assertIn("B1852006", software.warnings)

    # === states and rights === #

    def test_a_manager_approves_and_a_technician_does_not(self):
        software, _created = self.bring_in()
        with self.assertRaises(AccessError):
            software.with_user(self.technician).action_approve()
        with self.assertRaises(AccessError):
            software.with_user(self.technician).write({"state": "approved"})
        software.with_user(self.manager).action_approve()
        self.assertEqual((software.state, software.approved_by_id), ("approved", self.manager))
        self.assertTrue(software.approved_at)

    def test_a_program_is_retired_and_approved_again_and_set_back_to_draft(self):
        software, _created = self.bring_in()
        manager = software.with_user(self.manager)
        manager.action_approve()
        manager.action_retire()
        self.assertEqual(software.state, "retired")
        manager.action_approve()
        manager.action_draft()
        self.assertEqual((software.state, software.approved_by_id.id, software.approved_at), ("draft", False, False))

    def test_a_program_in_no_known_memory_is_not_approved(self):
        software, _created = self.bring_in("x.dwn", srec([(0x500000, b"\x01" * 16)]))
        self.assertEqual(software.kind, "unknown")
        with self.assertRaises(UserError):
            software.with_user(self.manager).action_approve()

    def test_what_the_file_contains_cannot_be_changed(self):
        software, _created = self.bring_in()
        for values in ({"kind": "os"}, {"sha256": "0" * 64}, {"data": base64.b64encode(b"x")}, {"app_name": "Other"}):
            with self.assertRaises(UserError, msg=str(values)):
                software.with_user(self.manager).write(values)

    def test_only_a_draft_is_deleted(self):
        software, _created = self.bring_in()
        approved, _created = self.bring_in("v310.dwn", srec([(0, operating_system())]))
        approved.with_user(self.manager).action_approve()
        with self.assertRaises(UserError):
            approved.with_user(self.manager).unlink()
        with self.assertRaises(AccessError):
            software.with_user(self.technician).unlink()
        software.with_user(self.manager).unlink()
        self.assertFalse(software.exists())

    def test_a_reader_sees_the_programs_and_brings_nothing_in(self):
        software, _created = self.bring_in()
        self.assertEqual(software.with_user(self.reader).name, "BR186002")
        with self.assertRaises(AccessError):
            self.bring_in("v310.dwn", srec([(0, operating_system())]), user=self.reader)

    # === the dialog === #

    def test_the_dialog_brings_files_in_and_names_what_it_did_to_each(self):
        # the user brings the files in, so they are his attachments
        Attachment = self.env["ir.attachment"].with_user(self.technician)

        def attach(name, content):
            return Attachment.create({"name": name, "datas": base64.b64encode(content), "res_model": "int.workbench.software.upload", "res_id": 0})

        first, _created = self.bring_in("old.dwn", self.image)
        os_image = srec([(0, operating_system())])
        wizard = (
            self.env["int.workbench.software.upload"]
            .with_user(self.technician)
            .create({"attachment_ids": [(6, 0, [attach("v310.dwn", os_image).id, attach("BR186002_copy.dwn", self.image).id, attach("words.txt", b"words").id])]})
        )
        attachments = wizard.attachment_ids
        wizard.action_upload()
        self.assertEqual(wizard.state, "done")
        lines = wizard.result.splitlines()
        self.assertEqual([line[0] for line in lines], ["+", "=", "×"])
        self.assertIn("v310.dwn", lines[0])
        self.assertIn("words.txt", lines[2])
        self.assertEqual(len(wizard.software_ids), 2)
        self.assertIn(first, wizard.software_ids)
        self.assertFalse(attachments.exists(), "the uploads are not kept as files of their own")
        action = wizard.action_show()
        self.assertEqual(action["domain"], [("id", "in", wizard.software_ids.ids)])

    def test_the_dialog_wants_a_file(self):
        wizard = self.env["int.workbench.software.upload"].with_user(self.technician).create({})
        with self.assertRaises(UserError):
            wizard.action_upload()
