import time
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import Form, TransactionCase, tagged

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

    def test_the_record_of_a_link_can_be_changed(self):
        self._invite(self.secret, self.alice)
        self.link.with_user(self.alice).write({"record_ref": f"res.partner,{self.p2.id}"})
        self.assertEqual((self.link.res_model, self.link.res_id), ("res.partner", self.p2.id))
        self.assertEqual(self.link.document_id, self.secret_doc)
        self.assertIn("unlinked", " ".join(self.p1.message_ids.mapped("body")))
        self.assertIn("linked", " ".join(self.p2.message_ids.mapped("body")))
        self.assertEqual(self._docs(self.outsider), self.secret_doc)  # p2 is readable too
        self.assertEqual(self.p1.with_user(self.outsider).document_count, 0)

    def test_changing_a_link_has_the_same_rules(self):
        new = {"record_ref": f"res.partner,{self.p2.id}"}
        # alice sees the document through the contact only
        with self.assertRaises(AccessError):
            self.link.with_user(self.alice).write(new)
        with self.assertRaises(AccessError):
            self.link.with_user(self.outsider).write(new)
        self._invite(self.secret, self.alice)
        foreign = self.Partner.create({"name": "Foreign", "company_id": self.company2.id})
        with self.assertRaises(AccessError):
            self.link.with_user(self.alice).write({"record_ref": f"res.partner,{foreign.id}"})
        self.assertEqual(self.link.res_id, self.p1.id)

    def test_only_the_record_of_a_link_can_be_changed(self):
        self._invite(self.secret, self.alice)
        with self.assertRaises(UserError):
            self.link.with_user(self.alice).write({"document_id": self.shared_doc.id})
        with self.assertRaises(UserError):
            self.link.with_user(self.alice).write({"record_ref": f"res.country,{self.env.ref('base.de').id}"})

    def test_the_record_of_a_line_is_changed_in_the_form(self):
        self._invite(self.secret, self.alice)
        form = Form(self.secret_doc.with_user(self.alice))
        with form.link_ids.edit(0) as line:
            line.record_ref = self.p2
        form.save()
        self.assertEqual(self.link.res_id, self.p2.id)

    def test_a_document_is_linked_once_to_a_record(self):
        with self.assertRaises(Exception), self.cr.savepoint():  # noqa: B017
            self._link(self.secret_doc, self.p1)

    def test_only_models_with_the_mixin_can_be_linked(self):
        country = self.env.ref("base.de")
        with self.assertRaises(UserError):
            self._link(self.shared_doc, country)

    def test_the_context_of_another_screen_gives_a_new_line_no_record(self):
        # The keys of the attachments (a work centre is open, say): the new line of the list
        # must not take them, and the list must not fail on a record it does not offer.
        Link = self.Link.with_context(default_res_model="res.country", default_res_id=1)
        defaults = Link.default_get(["res_model", "res_model_id", "res_id", "record_ref"])
        self.assertFalse(defaults)
        line = self.Link.new({"res_model": "res.country", "res_id": 1})
        self.assertFalse(line.record_ref)
        line = self.Link.new({"res_model": "res.partner", "res_id": self.p1.id})
        self.assertEqual(line.record_ref, self.p1)

    def test_the_choice_of_a_new_line_is_computed_with_that_context(self):
        # Odoo fills what a new line lacks with default_get(): with the keys of another screen
        # the line got a record that the list does not offer, and its choice failed.
        Link = self.Link.with_context(default_res_model="res.country", default_res_id=1)
        self.assertFalse(Link.new({}).record_ref)

    def test_a_line_added_in_the_form_with_that_context_is_linked_to_the_chosen_record(self):
        # The form of the document as the browser fills it, with the keys of another screen.
        document = self._document(self.shared, "f.txt", b"form")
        self._invite(self.shared, self.alice)
        form = Form(document.with_user(self.alice).with_context(
            default_res_model="res.country", default_res_id=1
        ))
        with form.link_ids.new() as line:
            line.record_ref = self.p2
        form.save()
        link = document.link_ids
        self.assertEqual((link.res_model, link.res_id), ("res.partner", self.p2.id))

    def test_a_link_needs_a_record(self):
        with self.assertRaises(UserError):
            self.Link.create({"document_id": self.shared_doc.id})

    # --- what the user of the record loads --------------------------------------------------

    def test_the_views_of_the_record_load_without_the_group(self):
        action = self.p1.with_user(self.outsider).action_open_documents()
        self.assertEqual(action["context"]["int_filemanager_link_id"], self.p1.id)
        views = self.Document.with_user(self.outsider).get_views(
            [(False, "list"), (False, "kanban"), (False, "form"), (action["search_view_id"][0], "search")]
        )
        # no panel of the folders: the user cannot read them
        self.assertNotIn("searchpanel", views["views"]["search"]["arch"])
        self.assertNotIn("folder_id", views["views"]["search"]["arch"])

    def test_the_dialog_of_a_link_offers_the_choice_of_the_record_only(self):
        arch = self.Link.with_user(self.alice).get_views([(False, "form")])["views"]["form"]["arch"]
        self.assertIn("record_ref", arch)
        for raw in ("res_model_id", "res_model\"", "res_id"):
            self.assertNotIn(raw, arch)

    def test_the_list_and_the_form_of_the_record_load_without_the_group(self):
        documents = self.Document.with_user(self.outsider).search([])
        self.assertEqual(documents, self.secret_doc)
        documents.web_read(
            {
                "name": {},
                "folder_id": {"fields": {"display_name": {}}},
                "size": {},
                "mimetype": {},
                "write_date": {},
                "checksum": {},
                "ocr_checksum": {},
                "active": {},
                "tag_ids": {"fields": {"display_name": {}, "color": {}}},
                "link_ids": {
                    "fields": {
                        "record_ref": {},
                        "create_uid": {"fields": {"display_name": {}}},
                        "create_date": {},
                    }
                },
            }
        )

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
