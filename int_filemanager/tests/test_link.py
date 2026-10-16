import time
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from .test_folder_access import AccessCase


@tagged("post_install", "-at_install")
class TestLink(AccessCase, TransactionCase):
    """A document is also seen through the records it is linked to."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.Link = cls.env["int.filemanager.link"]
        cls.Partner = cls.env["res.partner"]
        # alice may change contacts: she is the one who ties documents to them
        cls.alice.write({"group_ids": [(4, cls.env.ref("base.group_partner_manager").id)]})
        cls.company2 = cls.env["res.company"].create({"name": "Other company"})

    def setUp(self):
        super().setUp()
        self.secret_doc = self._document(self.secret, "s.txt", b"secret")
        self.shared_doc = self._document(self.shared, "o.txt", b"open")
        self.p1 = self.Partner.create({"name": "P1"})
        self.p2 = self.Partner.create({"name": "P2"})
        self.link = self._link(self.secret_doc, self.p1)

    def _link(self, document, record, user=None):
        return self.Link.with_user(user or self.env.user).create(
            {"document_id": document.id, "record_ref": f"{record._name},{record.id}"}
        )

    def _docs(self, user):
        return self.Document.with_user(user).search([])

    # --- reading through the record ---------------------------------------------------------

    def test_a_reader_of_the_record_sees_the_document(self):
        self.assertEqual(self._docs(self.outsider), self.secret_doc)

    def test_without_a_link_the_user_sees_nothing(self):
        # The right to read and no rule that applies would show every document.
        self.link.unlink()
        self.assertFalse(self._docs(self.outsider))

    def test_the_record_path_is_for_reading_only(self):
        document = self.secret_doc.with_user(self.outsider)
        document.check_access("read")
        self.assertEqual(document.name, "s.txt")
        self.assertEqual(document.folder_id.display_name, "Secret")
        for operation in ("write", "unlink"):
            with self.assertRaises(AccessError):
                document.check_access(operation)
        with self.assertRaises(AccessError):
            document.write({"name": "x.txt"})

    def test_a_folder_user_sees_what_the_folder_shows_and_what_is_linked(self):
        self.assertEqual(self._docs(self.alice), self.shared_doc + self.secret_doc)

    def test_a_record_that_the_user_cannot_read_shows_nothing(self):
        hidden = self._document(self.secret, "h.txt", b"hidden")
        foreign = self.Partner.create({"name": "Foreign", "company_id": self.company2.id})
        self._link(hidden, foreign)
        self.assertNotIn(hidden, self._docs(self.outsider))
        self.assertNotIn(hidden, self._docs(self.alice))
        self.assertIn(hidden, self._docs(self.boss))

    def test_the_company_rule_cuts_the_record_path_too(self):
        other = self.Folder.create(
            {"name": "Other", "company_id": self.company2.id, "access_mode": "open"}
        )
        document = self._document(other, "c2.txt", b"c2")
        self._link(document, self.p1)
        self.assertNotIn(document, self._docs(self.outsider))

    def test_the_administrators_see_everything(self):
        self.assertEqual(self._docs(self.boss), self.secret_doc + self.shared_doc)

    def test_moving_the_document_keeps_the_link_and_the_access(self):
        self.secret_doc.folder_id = self.shared
        self.assertTrue(self.link.exists())
        self.assertEqual(self._docs(self.outsider), self.secret_doc)

    def test_a_new_link_is_seen_at_once(self):
        # A rule with the ids of the readable records inside would be remembered by the
        # core and miss this one.
        self.assertEqual(self._docs(self.outsider), self.secret_doc)
        self._link(self.shared_doc, self.Partner.create({"name": "P3"}))
        self.assertEqual(self._docs(self.outsider), self.secret_doc + self.shared_doc)

    # --- tying and untying ------------------------------------------------------------------

    def test_a_user_who_does_not_see_the_folder_cannot_pass_the_document_on(self):
        with self.assertRaises(AccessError):
            self._link(self.secret_doc, self.p2, self.outsider)
        # alice sees it through the contact only
        with self.assertRaises(AccessError):
            self._link(self.secret_doc, self.p2, self.alice)
        self._invite(self.secret, self.alice)
        self.assertTrue(self._link(self.secret_doc, self.p2, self.alice).exists())

    def test_the_record_must_be_one_the_user_may_change(self):
        foreign = self.Partner.create({"name": "Foreign", "company_id": self.company2.id})
        with self.assertRaises(AccessError):
            self._link(self.shared_doc, foreign, self.alice)
        self.assertTrue(self._link(self.shared_doc, self.p2, self.alice).exists())

    def test_untying_needs_the_same(self):
        with self.assertRaises(AccessError):
            self.link.with_user(self.alice).unlink()
        self._invite(self.secret, self.alice)
        self.link.with_user(self.alice).unlink()
        self.assertFalse(self.link.exists())

    def test_a_document_is_linked_once_to_a_record(self):
        with self.assertRaises(Exception), self.cr.savepoint():  # noqa: B017
            self._link(self.secret_doc, self.p1)

    def test_only_models_with_the_mixin_can_be_linked(self):
        country = self.env.ref("base.de")
        with self.assertRaises(UserError):
            self._link(self.shared_doc, country)

    def test_a_link_needs_a_record(self):
        with self.assertRaises(UserError):
            self.Link.create({"document_id": self.shared_doc.id})

    # --- counts, actions, search ------------------------------------------------------------

    def test_the_count_is_what_the_user_sees(self):
        self.assertEqual(self.p1.with_user(self.outsider).document_count, 1)
        self.assertEqual(self.p2.with_user(self.outsider).document_count, 0)
        self.assertEqual(self.p1.with_user(self.alice).document_count, 1)

    def test_the_action_shows_the_documents_of_the_record(self):
        self._link(self.shared_doc, self.p2)
        action = self.p1.with_user(self.outsider).action_open_documents()
        for user in (self.outsider, self.alice):
            # alice sees both documents, the action shows those of the record
            found = self.Document.with_user(user).search(action["domain"])
            self.assertEqual(found, self.secret_doc)

    def test_the_record_is_found_by_the_words_of_its_documents(self):
        document = self._document(self.shared, "t.txt", b"the invoice of the plumber")
        self._link(document, self.p2)
        Text = self.env["int.filemanager.text"]
        with patch.object(self.env.cr, "commit"):
            Text._create_rows(1000)
            for row in Text.search([("state", "=", "pending")]):
                row._read_text(time.monotonic() + 120)
        Text.flush_model()
        as_outsider = self.Partner.with_user(self.outsider)
        self.assertEqual(as_outsider.search([("document_search", "ilike", "plumber")]), self.p2)
        self.assertEqual(as_outsider.search([("document_search", "ilike", "secret")]), self.p1)
        self.assertFalse(as_outsider.search([("document_search", "ilike", "nothinghere")]))
        # without the link the secret document shows nothing
        self.link.unlink()
        self.assertFalse(as_outsider.search([("document_search", "ilike", "secret")]))

    # --- the chatter ------------------------------------------------------------------------

    def test_linking_and_unlinking_leave_a_note_on_both_sides(self):
        notes = lambda record: " ".join(record.message_ids.mapped("body"))  # noqa: E731
        self.assertIn("s.txt", notes(self.p1))
        self.assertIn("linked", notes(self.p1))
        self.assertIn("P1", notes(self.secret_doc))
        self.link.unlink()
        self.assertIn("unlinked", notes(self.p1))
        self.assertIn("Unlinked from", notes(self.secret_doc))

    # --- clean-up ---------------------------------------------------------------------------

    def test_deleting_the_record_removes_its_links(self):
        self.p1.unlink()
        self.assertFalse(self.link.exists())

    def test_deleting_the_document_removes_its_links(self):
        self.secret_doc.unlink()
        self.assertFalse(self.link.exists())

    def test_the_autovacuum_removes_links_of_records_deleted_by_sql(self):
        p3 = self.Partner.create({"name": "P3"})
        link = self._link(self.shared_doc, p3)
        self.env.flush_all()
        self.env.cr.execute("DELETE FROM res_partner WHERE id = %s", [p3.id])
        self.env.invalidate_all()
        self.assertTrue(link.exists())
        self.Link._gc_orphan_links()
        self.assertFalse(link.exists())
