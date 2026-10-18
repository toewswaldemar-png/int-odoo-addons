import re

from odoo.tests.common import TransactionCase, tagged

MODULE_PREFIX = "@int_filemanager/"
# Owl and the other libraries are no modules of the bundle's list; the core's own are.
LIBRARY_PREFIX = "@odoo/"
DEFINE_REGEX = re.compile(r"odoo\.define\(\s*'([^']+)'\s*,\s*\[([^\]]*)\]")

TEMPLATES = (
    "int_filemanager.DocumentDropzone",
    "int_filemanager.DocumentKanbanView.Buttons",
    "int_filemanager.DocumentListContextMenu",
    "int_filemanager.DocumentListContextMenuRenderer",
    "int_filemanager.DocumentListRenderer",
    "int_filemanager.DocumentListView.Buttons",
    "int_filemanager.DocumentNameField",
    "int_filemanager.DocumentPreview",
    "int_filemanager.DocumentPreviewButton",
    "int_filemanager.DocumentThumbnailField",
    "int_filemanager.SizeField",
)

# What the module takes from the core without an extension point built for it (the name of the
# module and a piece of its source that the module's own code relies on). The bundle is
# minified: no spaces around the signs.
CORE_PARTS = {
    # DocumentFormRenderer: the preview beside the form is the mail module's layout with its
    # own component and `hasFile`.
    "@mail/chatter/web/form_renderer": ("mailComponents", "hasFile(", "mailLayout("),
    "@mail/chatter/web/form_compiler": ("div.o_attachment_preview", "AttachmentView"),
    # DocumentKanbanRecord: the click on a card (as the core's `product.document` takes it).
    "@web/views/kanban/kanban_record": ("onGlobalClick(", "CANCEL_GLOBAL_CLICK"),
    # DocumentKanbanController: the class on the root of the kanban, and the setting of the
    # user that keeps the size of the cards.
    "@web/views/kanban/kanban_controller": ("get className(", "headerButtons"),
    "@web/core/user": ("setUserSettings(", "user_settings"),
    # DocumentListRenderer: the click on the picture of a row; the rest of the row keeps the
    # core's click, which ends in `openRecord`.
    "@web/views/list/list_renderer": ("onCellClicked(", "openRecord("),
    # DocumentListContextMenu: the buttons of the head of the list run as the core's button of
    # the ticked rows does.
    "@web/views/view_button/multi_record_view_button": ("onClickViewButton(", "getResIds("),
    # DocumentListController: the button "Properties" opens the form as a click on a row does.
    "@web/views/list/list_controller": ("beforeExecuteActionButton(", "selectRecord("),
}


@tagged("post_install", "-at_install")
class TestAssets(TransactionCase):
    """The scripts of the module are built into the backend bundle and import what exists.

    There is no browser in the test run (the JS tests of Hoot need one), so this is the part
    of the interface that can be checked here: a wrong path in an import is no error of the
    build, the module is just never loaded.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        bundle = cls.env["ir.qweb"]._get_asset_bundle("web.assets_backend", css=False, js=True)
        cls.script = bundle.js().raw.decode()
        cls.modules = {
            name: re.findall(r"'([^']+)'", dependencies)
            for name, dependencies in DEFINE_REGEX.findall(cls.script)
        }

    def test_the_modules_are_in_the_bundle(self):
        ours = {name for name in self.modules if name.startswith(MODULE_PREFIX)}
        for name in (
            "dropzone/document_dropzone",
            "fields/content_hits/document_content_hits_field",
            "fields/name/document_name_field",
            "fields/size/size_field",
            "fields/thumbnail/document_thumbnail_field",
            "file_viewer/document_file_viewer",
            "file_viewer/document_preview",
            "file_viewer/document_preview_button",
            "file_viewer/file_viewer_frame_zoom_hook",
            "file_viewer/file_viewer_frames_hook",
            "file_viewer/file_viewer_swipe_hook",
            "touch/double_tap",
            "touch/momentum",
            "touch/pinch",
            "touch/swipe",
            "views/form/document_form_renderer",
            "views/form/document_form_view",
            "views/kanban/document_kanban_controller",
            "views/kanban/document_kanban_record",
            "views/kanban/document_kanban_renderer",
            "views/kanban/document_kanban_view",
            "views/kanban/document_tile_size",
            "views/list/document_list_context_menu",
            "views/list/document_list_context_menu_renderer",
            "views/list/document_list_controller",
            "views/list/document_list_renderer",
            "views/list/document_list_view",
        ):
            self.assertIn(f"{MODULE_PREFIX}int_filemanager/{name}", ours)

    def test_every_import_of_the_modules_exists(self):
        missing = {
            name: sorted(
                dependency
                for dependency in dependencies
                if not dependency.startswith(LIBRARY_PREFIX) and dependency not in self.modules
            )
            for name, dependencies in self.modules.items()
            if name.startswith(MODULE_PREFIX)
        }
        self.assertEqual({name: deps for name, deps in missing.items() if deps}, {})

    def _source(self, module):
        """The part of the bundle that defines ``module``."""
        start = self.script.index(f"odoo.define('{module}'")
        end = self.script.find("odoo.define(", start + 1)
        return self.script[start:end]

    def test_the_parts_of_the_core_that_the_module_relies_on_are_there(self):
        # A new Odoo may rename them; then the preview beside the form or the click on a card
        # would silently stop working (the build does not notice).
        for module, pieces in CORE_PARTS.items():
            source = self._source(module)
            for piece in pieces:
                self.assertIn(piece, source, f"{piece} is gone from {module}")

    def test_the_templates_are_in_the_bundle(self):
        # The name is also in the class that uses the template: look for the registration.
        for template in TEMPLATES:
            self.assertIn(f'registerTemplate("{template}"', self.script)
