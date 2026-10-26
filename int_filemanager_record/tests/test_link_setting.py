from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.int_filemanager.tests.test_folder_access import AccessCase

RULES = (
    "int_filemanager_record.int_filemanager_document_rule_record",
    "int_filemanager_record.int_filemanager_link_rule_record",
)
ACCESSES = (
    "int_filemanager_record.access_int_filemanager_document_internal",
    "int_filemanager_record.access_int_filemanager_link_internal",
)


@tagged("post_install", "-at_install")
class TestLinkSetting(AccessCase, TransactionCase):
    """The way over the linked records is a setting; the folders decide while it is off."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.Settings = cls.env["res.config.settings"]
        cls.partner = cls.env["res.partner"].create({"name": "P1"})

    def setUp(self):
        super().setUp()
        self.document = self._document(self.secret, "s.txt", b"secret")
        self.env["int.filemanager.link"].create(
            {"document_id": self.document.id, "record_ref": f"res.partner,{self.partner.id}"}
        )

    def _set(self, value):
        settings = self.Settings.create({"int_filemanager_access_via_record": value})
        settings.set_values()

    def _switches(self):
        return [self.env.ref(name).active for name in RULES + ACCESSES]

    def test_the_way_is_off_at_first(self):
        self.assertEqual(self._switches(), [False] * 4)
        self.assertFalse(self.Settings.create({}).int_filemanager_access_via_record)

    def test_while_it_is_off_a_user_of_the_record_sees_no_document(self):
        for model in ("int.filemanager.document", "int.filemanager.link"):
            with self.assertRaises(AccessError):
                self.env[model].with_user(self.outsider).search([])

    def test_while_it_is_off_the_folders_decide_for_the_filemanager_users(self):
        self.assertEqual(self.Document.with_user(self.alice).search([]), self.env["int.filemanager.document"])
        self._invite(self.secret, self.alice)
        self.assertEqual(self.Document.with_user(self.alice).search([]), self.document)

    def test_while_it_is_off_the_contact_loads_for_a_user_without_the_group(self):
        self.assertEqual(self.partner.with_user(self.outsider).document_count, 0)

    def test_while_it_is_off_the_count_of_a_contact_is_what_the_folders_show(self):
        self.assertEqual(self.partner.with_user(self.alice).document_count, 0)
        self._invite(self.secret, self.alice)
        self.env.invalidate_all()
        self.assertEqual(self.partner.with_user(self.alice).document_count, 1)

    def test_the_setting_switches_the_rule_and_both_accesses_together(self):
        self._set(True)
        self.assertEqual(self._switches(), [True] * 4)
        self.assertTrue(self.Settings.create({}).get_values()["int_filemanager_access_via_record"])
        self.assertEqual(self.Document.with_user(self.outsider).search([]), self.document)
        self.assertEqual(self.partner.with_user(self.outsider).document_count, 1)
        self._set(False)
        self.assertEqual(self._switches(), [False] * 4)
        with self.assertRaises(AccessError):
            self.Document.with_user(self.outsider).search([])

    def test_switching_on_twice_changes_nothing(self):
        self._set(True)
        self._set(True)
        self.assertEqual(self._switches(), [True] * 4)
