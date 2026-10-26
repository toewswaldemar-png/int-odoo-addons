from odoo.fields import Domain
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.int_filemanager.tests.test_folder_access import AccessCase

from ..models.int_filemanager_folder import SHARE_ROOT_KEY

FOLDER = "int.filemanager.folder"
DOCUMENT = "int.filemanager.document"


@tagged("post_install", "-at_install")
class TestShareScope(AccessCase, TransactionCase):
    """What the guests of a share reach: exactly the expected folders and files, whatever they ask."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.Share = cls.env["int.filemanager.share"]
        cls.company2 = cls.env["res.company"].create({"name": "Other company"})

    def _folder(self, name, parent, **values):
        return self.Folder.create({"name": name, "parent_id": parent.id, **values})

    def setUp(self):
        super().setUp()
        # shared (open) > deep, a > a1, hidden (restricted) > hidden1 > reopened (open),
        # archived, foreign (other company); other: a top folder beside it
        self.a = self._folder("a", self.shared)
        self.a1 = self._folder("a1", self.a)
        self.hidden = self._folder("hidden", self.shared, access_mode="restricted")
        self.hidden1 = self._folder("hidden1", self.hidden)
        self.reopened = self._folder("reopened", self.hidden1, access_mode="open")
        self.archived = self._folder("archived", self.shared)
        self.foreign = self._folder("foreign", self.shared)
        self.other = self.Folder.create({"name": "other", "access_mode": "open"})
        self.documents = {
            folder: self._document(folder, f"{folder.name}.txt", folder.name.encode())
            for folder in (
                self.shared, self.deep, self.a, self.a1, self.hidden, self.hidden1,
                self.reopened, self.archived, self.foreign, self.other,
            )
        }
        self._legacy_company(self.foreign, self.company2)
        self.gone = self._document(self.a, "gone.txt", b"gone")
        self.gone.active = False
        self.archived.active = False  # with its file, as the archiving of a folder does
        self.share = self.Share.create({"folder_id": self.shared.id})

    def _legacy_company(self, folder, company):
        """A subfolder of another company: the folders have the company of their parent now, data
        from before may still hold one, and the share must not reach it."""
        self.env.flush_all()
        self.env.cr.execute("UPDATE int_filemanager_folder SET company_id = %s WHERE id = %s", (company.id, folder.id))
        self.env.cr.execute("UPDATE int_filemanager_document SET company_id = %s WHERE folder_id = %s", (company.id, folder.id))
        self.env.invalidate_all()

    def _scope(self, share, model):
        return self.env[model].with_context(active_test=True).search(share._scope_domain(model))

    def _files(self, *folders):
        return self.env[DOCUMENT].browse([self.documents[folder].id for folder in folders])

    # --- the folders and the files ------------------------------------------------------------

    def test_the_folders_are_the_shared_tree_without_the_hidden_the_archived_and_other_companies(self):
        expected = self.shared + self.deep + self.a + self.a1
        self.assertEqual(self._scope(self.share, FOLDER), expected)

    def test_the_files_are_those_of_these_folders_that_are_active(self):
        expected = self._files(self.shared, self.deep, self.a, self.a1)
        self.assertEqual(self._scope(self.share, DOCUMENT), expected)

    def test_a_folder_that_is_open_again_below_a_hidden_one_stays_hidden(self):
        self.assertNotIn(self.reopened, self._scope(self.share, FOLDER))
        self.assertNotIn(self.documents[self.reopened], self._scope(self.share, DOCUMENT))

    def test_what_is_beside_and_above_is_not_reached(self):
        self.assertNotIn(self.other, self._scope(self.share, FOLDER))
        parent = self.Folder.create({"name": "parent", "access_mode": "open"})
        child = self._folder("child", parent)
        share = self.Share.create({"folder_id": child.id})
        self.assertEqual(self._scope(share, FOLDER), child)

    def test_a_share_without_a_company_reaches_every_company_below(self):
        top = self.Folder.create({"name": "top", "access_mode": "open", "company_id": False})
        inner = self._folder("inner", top, company_id=self.company2.id)
        share = self.Share.create({"folder_id": top.id})
        self.assertFalse(share.company_id)
        self.assertEqual(self._scope(share, FOLDER), top + inner)

    def test_a_restricted_folder_that_is_shared_is_seen_itself(self):
        share = self.Share.create({"folder_id": self.secret.id})
        self.assertEqual(self._scope(share, FOLDER), self.secret + self.inner)
        self.assertFalse(share._hidden_folders())

    # --- the folder for the uploads -----------------------------------------------------------

    def test_the_folder_for_the_uploads_is_hidden_from_everybody_also_when_opened(self):
        top = self.Folder.create({"name": "top", "access_mode": "open"})
        mid = self._folder("mid", top)
        uploading = self.Share.create({"folder_id": mid.id, "can_upload": True})
        above = self.Share.create({"folder_id": top.id})
        upload = uploading.upload_folder_id
        self.assertEqual(self._scope(uploading, FOLDER), mid)
        self.assertEqual(self._scope(above, FOLDER), top + mid)
        upload.access_mode = "open"  # somebody opens it for his colleagues: still no guest sees it
        self.assertEqual(self._scope(uploading, FOLDER), mid)
        self.assertEqual(self._scope(above, FOLDER), top + mid)
        self.assertEqual(above._hidden_folders(), upload)

    def test_the_folder_for_the_uploads_of_a_blocked_share_stays_hidden(self):
        top = self.Folder.create({"name": "top", "access_mode": "open"})
        uploading = self.Share.create({"folder_id": self._folder("mid", top).id, "can_upload": True})
        upload = uploading.upload_folder_id
        upload.access_mode = "open"
        uploading.action_archive()
        above = self.Share.create({"folder_id": top.id})
        self.assertNotIn(upload, self._scope(above, FOLDER))

    def test_the_documents_of_the_uploads_are_hidden_too(self):
        top = self.Folder.create({"name": "top", "access_mode": "open"})
        uploading = self.Share.create({"folder_id": self._folder("mid", top).id, "can_upload": True})
        uploading.upload_folder_id.access_mode = "open"
        uploaded = self._document(uploading.upload_folder_id, "g.txt", b"from a guest")
        above = self.Share.create({"folder_id": top.id})
        self.assertNotIn(uploaded, self.Document.search(above._scope_domain(DOCUMENT)))

    # --- a file ---------------------------------------------------------------------------------

    def test_the_share_of_a_file_reaches_that_file_only(self):
        document = self.documents[self.a]
        share = self.Share.create({"document_id": document.id})
        self.assertEqual(self._scope(share, DOCUMENT), document)
        self.assertFalse(self._scope(share, FOLDER))
        document.active = False
        self.assertFalse(self._scope(share, DOCUMENT))

    # --- what the guests ask for ----------------------------------------------------------------

    def test_a_domain_of_the_guests_never_widens_the_scope(self):
        scope = self.share._scope_domain(DOCUMENT)
        inside = self._scope(self.share, DOCUMENT)
        everything = self.env[DOCUMENT].search([])
        self.assertGreater(len(everything), len(inside))
        hostile = [
            [("id", ">", 0)],
            ["|", ("id", ">", 0), ("name", "!=", "x")],
            [(1, "=", 1)],
            ["!", ("id", "=", -1)],
            [("folder_id", "not in", [])],
            ["|", "|", ("folder_id", "=", self.other.id), ("folder_id", "=", self.hidden.id), (1, "=", 1)],
            [("folder_id", "child_of", self.other.id)],
        ]
        for client in hostile:
            with self.subTest(client=client):
                found = self.env[DOCUMENT].search(Domain.AND([scope, Domain(client)]))
                self.assertFalse(found - inside)

    # --- the parent of the shared folder --------------------------------------------------------

    def test_the_guests_do_not_see_the_parent_of_the_shared_folder(self):
        parent = self.Folder.create({"name": "Parent of the shared", "access_mode": "restricted"})
        child = self._folder("child", parent)
        grandchild = self._folder("grandchild", child)
        Folder = self.env[FOLDER]
        read = {r["id"]: r["parent_id"] for r in Folder.browse([child.id, grandchild.id]).read(["parent_id"])}
        self.assertEqual(read[child.id][0], parent.id)
        guest = Folder.with_context(**{SHARE_ROOT_KEY: child.id})
        read = {r["id"]: r["parent_id"] for r in guest.browse([child.id, grandchild.id]).read(["parent_id"])}
        self.assertFalse(read[child.id])
        self.assertEqual(read[grandchild.id][0], child.id)
        found = guest.search_read([("id", "in", [child.id, grandchild.id])], ["parent_id", "display_name"])
        self.assertEqual({r["id"]: bool(r["parent_id"]) for r in found}, {child.id: False, grandchild.id: True})

    def test_the_search_panel_of_the_guests_keeps_a_root_that_has_a_parent(self):
        parent = self.Folder.create({"name": "Parent of the shared", "access_mode": "open"})
        child = self._folder("child", parent)
        grandchild = self._folder("grandchild", child)
        share = self.Share.create({"folder_id": child.id})
        arguments = {
            "comodel_domain": list(share._scope_domain(FOLDER)),
            "expand": True,
            "limit": 0,
        }
        Document = self.env[DOCUMENT]
        # Without the mask the chain of the root leads outside the result: the panel is empty.
        self.assertFalse(Document.search_panel_select_range("folder_id", **arguments)["values"])
        guest = Document.with_context(**{SHARE_ROOT_KEY: child.id})
        values = guest.search_panel_select_range("folder_id", **arguments)["values"]
        self.assertEqual({value["id"] for value in values}, {child.id, grandchild.id})
        self.assertFalse(next(value for value in values if value["id"] == child.id)["parent_id"])
