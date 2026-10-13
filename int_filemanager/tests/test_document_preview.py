from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestDocumentPreview(TransactionCase):
    """The preview of the file: beside the form, and by a click on a card of the kanban."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env["int.filemanager.document"]
        cls.user = new_test_user(
            cls.env,
            login="preview_user",
            groups="base.group_user,int_filemanager.int_filemanager_group_user",
        )

    def _views(self, *view_types):
        views = self.Document.with_user(self.user).get_views([(False, t) for t in view_types])
        return views["views"]

    def test_the_form_has_the_preview_beside_it_and_the_button_below_the_width_xxl(self):
        arch = self._views("form")["form"]["arch"]
        # The class that makes the core's form compiler build the layout with a preview, and the
        # view class that puts the component of the module in the place of the core's one.
        self.assertIn('js_class="int_filemanager_document_form"', arch)
        self.assertIn('<div class="o_attachment_preview"/>', arch)
        # The core docks the preview from the width XXL on; below it the button shows the file.
        self.assertIn('widget name="int_filemanager_preview_button"', arch)
        self.assertIn("d-xxl-none", arch)
        # The renderer works out whether there is a file from these.
        for name in ("name", "mimetype", "checksum", "size"):
            self.assertIn(f'name="{name}"', arch)

    def test_the_preview_comes_after_the_sheet_and_before_the_chatter(self):
        arch = self._views("form")["form"]["arch"]
        self.assertLess(arch.index("</sheet>"), arch.index("o_attachment_preview"))
        self.assertLess(arch.index("o_attachment_preview"), arch.index("<chatter"))

    def test_the_kanban_shows_a_picture_and_has_the_form_in_the_menu_of_the_card(self):
        arch = self._views("kanban")["kanban"]["arch"]
        # The class whose controller shows the file by a click on the card.
        self.assertIn('js_class="int_filemanager_document_kanban"', arch)
        self.assertIn('widget="int_filemanager_document_thumbnail"', arch)
        self.assertIn('create="0"', arch)
        # The form and the download are in the menu of the card: a click on it shows the file.
        for method in ("action_open_form", "action_download"):
            self.assertIn(f'name="{method}"', arch)
            self.assertTrue(hasattr(self.Document, method))
