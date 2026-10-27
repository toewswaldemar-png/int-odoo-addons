import io
import os

from lxml import etree

from odoo.tests.common import TransactionCase, new_test_user, tagged
from odoo.tools.safe_eval import safe_eval

from ..models.int_filemanager_document import PREVIEW_EXTENSIONS


def remove(path):
    if os.path.exists(path):
        os.unlink(path)


@tagged("post_install", "-at_install")
class TestDocumentAnalysis(TransactionCase):
    """The pivot and the graph add up the size of the documents, as far as a user sees them."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Folder = cls.env["int.filemanager.folder"]
        cls.Document = cls.env["int.filemanager.document"]
        cls.user = new_test_user(
            cls.env,
            login="analysis_user",
            groups="base.group_user,int_filemanager.int_filemanager_group_user",
        )
        cls.open = cls.Folder.create({"name": "Open", "access_mode": "open"})
        cls.hidden = cls.Folder.create({"name": "Hidden", "access_mode": "restricted"})

    def setUp(self):
        super().setUp()
        self.documents = self.Document

    def _document(self, name, content, folder):
        document = self.Document._create_from_stream(io.BytesIO(content), name, folder)
        self.addCleanup(remove, self.Document._blob_path(document.checksum))
        self.documents += document
        return document

    def _sums(self, Document, groupby):
        """What the views ask for: the size added up by the group, for the documents of the test
        (as far as the user of ``Document`` sees them)."""
        groups = Document.formatted_read_group(
            [("id", "in", self.documents.ids)], [groupby], ["size:sum"]
        )
        return {group[groupby]: group["size:sum"] for group in groups}

    # --- the sums ------------------------------------------------------------

    def test_the_size_is_added_up_by_type(self):
        self._document("a.txt", b"abc", self.open)
        self._document("b.txt", b"12345", self.open)
        self._document("c.png", b"\x89PNG\r\n\x1a\n\x00", self.open)
        sums = self._sums(self.Document, "mimetype")
        self.assertEqual(sums["text/plain"], 8)
        self.assertEqual(sums["image/png"], 9)

    def test_the_size_is_added_up_by_folder_and_by_tag(self):
        tag = self.env["int.filemanager.tag"].create({"name": "Invoice"})
        first = self._document("a.txt", b"abc", self.open)
        self._document("b.txt", b"12345", self.hidden)
        first.tag_ids = tag
        by_folder = self._sums(self.Document, "folder_id")
        self.assertEqual(
            {folder[0]: size for folder, size in by_folder.items()},
            {self.open.id: 3, self.hidden.id: 5},
        )
        by_tag = self._sums(self.Document, "tag_ids")
        self.assertEqual({tag_[0]: size for tag_, size in by_tag.items() if tag_}, {tag.id: 3})

    def test_a_user_adds_up_only_what_the_user_sees(self):
        self._document("a.txt", b"abc", self.open)
        self._document("b.txt", b"12345", self.hidden)
        as_user = self.Document.with_user(self.user)
        self.assertEqual(self._sums(as_user, "mimetype"), {"text/plain": 3})

    # --- the views -----------------------------------------------------------

    def test_the_views_and_the_groups_are_there(self):
        views = self.Document.with_user(self.user).get_views(
            [(False, "list"), (False, "pivot"), (False, "graph"), (False, "search")]
        )["views"]
        # The size is shown by the formatter of the module, not as a bare number of bytes.
        for view_type in ("pivot", "graph"):
            self.assertIn('widget="int_filemanager_size"', views[view_type]["arch"])
        self.assertIn('type="row"', views["pivot"]["arch"])
        for name in (
            "group_by_folder",
            "group_by_mimetype",
            "group_by_tag",
            "group_by_create_uid",
            "group_by_create_month",
        ):
            self.assertIn(f'name="{name}"', views["search"]["arch"])
        # The core shows the search panel in the list and the kanban only.
        self.assertIn('view_types="list,kanban,pivot,graph"', views["search"]["arch"])

    def test_the_action_offers_the_kanban_the_pivot_and_the_graph(self):
        action = self.env.ref("int_filemanager.int_filemanager_document_action")
        self.assertEqual(action.view_mode, "list,kanban,pivot,graph,form")

    # --- the filters of the search view --------------------------------------

    def _filter_domain(self, name):
        """The domain of a filter of the search view, as the web client evaluates it."""
        arch = self.Document.with_user(self.user).get_views([(False, "search")])["views"]["search"]["arch"]
        node = etree.fromstring(arch).xpath(f"//filter[@name='{name}']")[0]
        return safe_eval(node.get("domain"), {"uid": self.user.id})

    def test_the_filter_for_office_files_lists_the_types_that_get_a_preview(self):
        (condition,) = self._filter_domain("filter_office")
        self.assertEqual(set(condition[2]), set(PREVIEW_EXTENSIONS))

    def test_the_filters_for_the_kind_of_file_find_their_files(self):
        pdf = self._document("a.pdf", b"%PDF-1.4\n%%EOF\n", self.open)
        image = self._document("b.png", b"\x89PNG\r\n\x1a\n\x00", self.open)
        text = self._document("c.txt", b"abc", self.open)
        office = self._document("d.txt", b"abc", self.open)
        office.write({"mimetype": next(iter(PREVIEW_EXTENSIONS))})

        def found(name):
            return self.documents.filtered_domain(self._filter_domain(name))

        self.assertEqual(found("filter_pdf"), pdf)
        self.assertEqual(found("filter_images"), image)
        self.assertEqual(found("filter_office"), office)
        self.assertNotIn(text, found("filter_pdf") | found("filter_images") | found("filter_office"))

    def test_the_filter_for_my_uploads_leaves_the_uploads_of_others(self):
        mine = self.Document.with_user(self.user)._create_from_stream(
            io.BytesIO(b"mine"), "mine.txt", self.open.with_user(self.user)
        )
        self.documents += mine
        other = self._document("other.txt", b"other", self.open)
        self.assertEqual(self.documents.filtered_domain(self._filter_domain("filter_my_uploads")), mine)
        self.assertNotEqual(other.create_uid, self.user)

    def test_the_documents_are_grouped_by_creator_and_by_month(self):
        self._document("a.txt", b"abc", self.open)
        for groupby in ("create_uid", "create_date:month"):
            with self.subTest(groupby=groupby):
                groups = self.Document.formatted_read_group(
                    [("id", "in", self.documents.ids)], [groupby], ["__count"]
                )
                self.assertEqual(sum(group["__count"] for group in groups), 1)
