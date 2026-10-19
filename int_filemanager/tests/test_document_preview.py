from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestDocumentPreview(TransactionCase):
    """The preview of the file: on the page of the document, and by a click on a card of the kanban."""

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

    def test_the_form_is_the_page_with_the_file_and_has_no_preview_of_the_mail_module(self):
        arch = self._views("form")["form"]["arch"]
        # The view class whose renderer puts the file beside the form.
        self.assertIn('js_class="int_filemanager_document_form"', arch)
        # The mail module's own preview and the button that stood for it are gone.
        self.assertNotIn("o_attachment_preview", arch)
        self.assertNotIn("int_filemanager_preview_button", arch)
        # The chatter is the renderer's to show, when the user asks for it.
        self.assertNotIn("<chatter", arch)
        # The renderer works out the file from these.
        for name in ("name", "mimetype", "checksum", "size"):
            self.assertIn(f'name="{name}"', arch)

    def test_the_kanban_shows_a_picture_and_has_the_form_in_the_menu_of_the_card(self):
        arch = self._views("kanban")["kanban"]["arch"]
        # The class whose controller shows the file by a click on the card.
        self.assertIn('js_class="int_filemanager_document_kanban"', arch)
        self.assertIn('widget="int_filemanager_document_thumbnail"', arch)
        self.assertIn('create="0"', arch)
        # The form and the download are in the menu of the card: a click on it shows the file.
        # The form opens by type="open" (the pager over the cards), not by the method of the model.
        self.assertIn('type="open"', arch)
        self.assertNotIn('name="action_open_form"', arch)
        self.assertIn('name="action_download"', arch)
        self.assertTrue(hasattr(self.Document, "action_download"))

    def test_the_list_keeps_the_button_that_the_controller_turns_into_a_click_on_a_row(self):
        # DocumentListController.beforeExecuteActionButton looks for the name of this method.
        arch = self._views("list")["list"]["arch"]
        self.assertIn('name="action_open_form"', arch)
        self.assertTrue(hasattr(self.Document, "action_open_form"))
