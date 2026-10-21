import re

from odoo.tests.common import TransactionCase, tagged

MODULE_PREFIX = "@int_filemanager/"
# Owl and the other libraries are no modules of the bundle's list; the core's own are.
LIBRARY_PREFIX = "@odoo/"
DEFINE_REGEX = re.compile(r"odoo\.define\(\s*'([^']+)'\s*,\s*\[([^\]]*)\]")

TEMPLATES = (
    "int_filemanager.DocumentDropzone",
    "int_filemanager.DocumentKanbanView.Buttons",
    "int_filemanager.DocumentListContextMenuRenderer",
    "int_filemanager.DocumentListRenderer",
    "int_filemanager.DocumentListView.Buttons",
    "int_filemanager.DocumentNameField",
    "int_filemanager.DocumentFileViewer",
    "int_filemanager.DocumentFormController",
    "int_filemanager.DocumentPreview",
    "int_filemanager.DocumentThumbnailField",
    "int_filemanager.SearchPanel.Category",
    "int_filemanager.SizeField",
)

# What the module takes from the core without an extension point built for it (the name of the
# module and a piece of its source that the module's own code relies on). The bundle is
# minified: no spaces around the signs.
CORE_PARTS = {
    # DocumentPreview: the viewer of the core without its modal frame, with one file.
    "@web/core/file_viewer/file_viewer": (
        "modal",
        "startIndex",
        "files",
        # DocumentFileViewer: the ground of the viewer is the surface of a picture; it drives
        # the core's own drag of the picture from there (and the click that closes it).
        "onMousedownImage(",
        "onMouseupImage(",
        "onMousemoveView(",
        "isDragging",
        "dragStartX",
    ),
    # DocumentImageEditor (the bundle of the editor): the loader of the bundles that the hook
    # starts, and the events of the upload that the editor waits for.
    "@web/core/assets": ("lazy_components", "bundle"),
    "@web/core/file_upload/file_upload_service": (
        "FILE_UPLOAD_LOADED",
        "FILE_UPLOAD_ERROR",
        "buildFormData",
    ),
    # The picture editor: the palette of the colours, the state of a dropdown, the dialog of the
    # choices before the picture is stored, and the bus of the router that takes the editor away.
    "@web/core/color_picker/color_picker": ("DEFAULT_COLORS",),
    "@web/core/dropdown/dropdown_hooks": ("useDropdownState",),
    "@web/core/dialog/dialog": ("contentClass", "modalRef"),
    "@web/core/browser/router": ("routerBus", "ROUTE_CHANGE"),
    # DocumentFormController: the panel at the side of the file can be pulled to another width.
    "@web/core/resizable_panel/resizable_panel": (
        "handleSide",
        "initialWidth",
        "minWidth",
        "onResize",
    ),
    # DocumentFormController: the chatter of the mail module as a component of its own, given
    # the record it belongs to by model and id; it reads `env.chatter` that mail puts into the
    # form controller and takes `has_activities` from the arch that mail's parser extends.
    "@mail/chatter/web_portal/chatter": ("threadModel", "threadId", "changeThread("),
    "@mail/chatter/web/form_controller": ("fetchThreadData", "MAIL:RELOAD-THREAD"),
    "@mail/chatter/web/form_arch_parser": ("has_activities",),
    # DocumentKanbanRecord: the click on a card (as the core's `product.document` takes it).
    "@web/views/kanban/kanban_record": ("onGlobalClick(", "CANCEL_GLOBAL_CLICK"),
    # DocumentKanbanController: the class on the root of the kanban, and the setting of the
    # user that keeps the size of the cards.
    "@web/views/kanban/kanban_controller": ("get className(", "headerButtons"),
    "@web/core/user": ("setUserSettings(", "user_settings"),
    # DocumentListRenderer: the click on the picture of a row; the rest of the row keeps the
    # core's click, which ends in `openRecord`. The rows are dragged to a folder from the root of
    # the renderer (`rootRef`).
    "@web/views/list/list_renderer": ("onCellClicked(", "openRecord(", "rootRef"),
    "@web/views/kanban/kanban_renderer": ("rootRef",),
    # The ticked rows go together when one of them is dragged to a folder.
    "@web/model/relational_model/dynamic_list": ("get selection(",),
    # The drag to a folder: the drag of the core, that does not move the dragged element
    # (`followCursor`, as the block selection of the calendar sets it in `onComputeParams`), whose
    # `preventDrag` and `ignore` keep it off the buttons and the rows that cannot move.
    "@web/core/utils/draggable_hook_builder": (
        "followCursor",
        "onComputeParams",
        "preventDrag",
        "ignoreSelector",
        "pe-none",
    ),
    # DocumentSearchPanel: the view names the panel as it names the control panel, and the panel
    # names the template of the folders (and keeps which of them are open).
    "@web/search/layout": ("params.SearchPanel",),
    "@web/search/search_panel/search_panel": ("subTemplates", "expanded"),
    # DocumentListController: the item "Move to..." runs as the `ActionMenus` of the core runs an
    # action (the ticked rows and the keys `active_*` in the context), in a group of the menu.
    "@web/search/action_menus/action_menus": (
        "executeAction(",
        "additionalContext",
        "active_ids",
        "STATIC_ACTIONS_GROUP_NUMBER",
    ),
    # The static items bring their own `groupNumber` into the items of the menu.
    "@web/views/list/list_controller": ("getStaticActionMenuItems(", "get actionMenuItems("),
    # The buttons of the head of the list run as the core's `MultiRecordViewButton` runs them
    # (the ticked rows, the call of the controller).
    "@web/views/view_button/multi_record_view_button": ("onClickViewButton(", "getResIds("),
    "@web/views/view_button/view_button_hook": ("onClickViewButton(", "beforeExecuteAction"),
    # DocumentSearchModel: the method that turns the folder of the panel into a condition (the
    # core takes ``child_of`` there; the module takes ``=``). If it is renamed, the override is
    # never called and a folder shows the documents of the folders below it again.
    "@web/search/search_model": ("_getCategoryDomain(", "child_of", "parentField"),
    # DocumentListController: the menu "New" restores the view after the dialog of the new
    # folder (the client action of the core; the panel does not reload its tree).
    "@web/webclient/actions/client_actions": ("soft_reload",),
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
            "fields/content_hits/document_content_hit_count_field",
            "fields/content_hits/document_content_hits_field",
            "fields/content_hits/document_content_hits_popover",
            "fields/name/document_name_field",
            "fields/size/size_field",
            "fields/thumbnail/document_thumbnail_field",
            "file_viewer/document_file_viewer",
            "file_viewer/document_image_editor_service",
            "file_viewer/document_preview",
            "file_viewer/file_viewer_frame_zoom_hook",
            "file_viewer/file_viewer_frames_hook",
            "file_viewer/file_viewer_swipe_hook",
            "touch/double_tap",
            "touch/momentum",
            "touch/pinch",
            "touch/swipe",
            "views/document_open_mode",
            "views/document_search_model",
            "views/drag/document_drag_ghost",
            "views/drag/document_drag_source_hook",
            "views/drag/document_drag_state",
            "views/drag/document_move",
            "views/form/document_form_controller",
            "views/form/document_form_view",
            "views/kanban/document_kanban_controller",
            "views/kanban/document_kanban_record",
            "views/kanban/document_kanban_renderer",
            "views/kanban/document_kanban_view",
            "views/kanban/document_tile_size",
            "views/list/document_list_context_menu_renderer",
            "views/list/document_list_controller",
            "views/list/document_list_renderer",
            "views/list/document_list_view",
            "views/list/document_new_folder",
            "views/search_panel/document_search_panel",
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

    def test_the_styles_of_the_module_compile(self):
        # A style that does not compile (a `min()` with % and rem, say) breaks the whole bundle of
        # the web client: the user sees an error at every load. The build only logs it.
        for name in ("web.assets_backend", "web.assets_web"):
            bundle = self.env["ir.qweb"]._get_asset_bundle(name, css=True, js=False)
            bundle.css()
            self.assertEqual(bundle.css_errors, [], name)

    def test_the_templates_of_the_core_have_the_places_the_page_of_a_document_uses(self):
        # DocumentFormController inherits the template of the form view: it puts its buttons into
        # the slot next to the pager (the list does the same) in front of the slot of the cog menu,
        # and wraps the renderer in the layout of the page; a new Odoo may change them.
        for template, pieces in (
            (
                "web.FileViewer",
                (
                    "o-FileViewer-headerButton",
                    "fa-times",
                    "props.modal",
                    # DocumentFileViewer moves the handlers of the wheel and of the mouse from the
                    # picture to the ground (`o-FileViewer-main`).
                    "o-FileViewer-main",
                    "o-FileViewer-viewImage",
                    't-on-wheel="onWheelImage"',
                    't-on-mousedown.stop="onMousedownImage"',
                    't-on-mouseup.stop="onMouseupImage"',
                    # DocumentFileViewer puts the button "Edit" after the one of the printer.
                    'role="toolbar"',
                    'title="Print"',
                ),
            ),
            # The folders of the search panel get the mark of a drop (the place of the xpath); the
            # rows of the list and the cards of the kanban carry `data-id` (the drag finds them).
            ("web.SearchPanel.Category", ("<header", "t-on-click")),
            ("web.ListRenderer.RecordRow", ("o_data_row", "t-att-data-id")),
            ("web.KanbanRecord", ("t-att-data-id",)),
            ("web.FormView", ("control-panel-additional-actions", "props.Renderer", "<Layout")),
            ("web.ControlPanel", ("control-panel-navigation-additional", "o_cp_pager")),
        ):
            start = self.script.index(f'registerTemplate("{template}"')
            end = self.script.find("registerTemplate(", start + 1)
            for piece in pieces:
                self.assertIn(piece, self.script[start:end], f"{piece} is gone from {template}")


# What the editor takes from Fabric (the library of the bundle of the editor): the version it was
# written for, and the names of what it calls. The bundle is minified, but the names of methods and
# of the exports stay.
FABRIC_VERSION = "7.4.0"
FABRIC_PARTS = (
    # the canvas
    "getScenePoint",
    "getViewportPoint",
    "setViewportTransform",
    "toCanvasElement",
    "toSVG",
    "enlivenObjects",
    "classRegistry",
    "freeDrawingBrush",
    "text:editing:exited",
    "path:created",
    "after:render",
    # objects and what the marks are made of
    "setPositionByOrigin",
    "triggerLayout",
    "removeAll",
    "bringObjectToFront",
    "applyTransformToObject",
    "multiplyTransformMatrices",
    "groupSVGElements",
    "loadSVGFromString",
    "Textbox",
    "Polyline",
    "Gradient",
    "Pattern",
    "SprayBrush",
    "CircleBrush",
    "PatternBrush",
    # the filters
    "Convolute",
    "BlendColor",
    "RemoveColor",
    "HueRotation",
    "Vibrance",
    "Pixelate",
    "Kodachrome",
    "Technicolor",
)
EDITOR_MODULES = (
    "arrange",
    "color_field",
    "constants",
    "controls",
    "crop_tool",
    "document_image_editor",
    "drawing",
    "edit_state",
    "export",
    "filters",
    "geometry",
    "history",
    "import_image",
    "marks",
    "overlay",
    "picture",
    "redact_mark",
    "save_dialog",
    "scene_ops",
    "snapping",
    "viewport",
)
EDITOR_TEMPLATES = (
    "int_filemanager.DocumentImageEditor",
    "int_filemanager.ImageEditorTools",
    "int_filemanager.ImageEditorPanel",
    "int_filemanager.ImageEditorPanelStyle",
    "int_filemanager.ImageEditorPanelEdit",
    "int_filemanager.ImageEditorPanelAdjust",
    "int_filemanager.ImageEditorPanelCrop",
    "int_filemanager.ImageEditorPanelView",
    "int_filemanager.ImageEditorColorField",
    "int_filemanager.ImageEditorSaveDialog",
)


@tagged("post_install", "-at_install")
class TestImageEditorAssets(TransactionCase):
    """The editor for pictures is a bundle of its own, loaded at the first click on "Edit"."""

    BUNDLE = "int_filemanager.assets_image_editor"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.script = (
            cls.env["ir.qweb"]._get_asset_bundle(cls.BUNDLE, css=False, js=True).js().raw.decode()
        )
        backend = (
            cls.env["ir.qweb"]
            ._get_asset_bundle("web.assets_backend", css=False, js=True)
            .js()
            .raw.decode()
        )
        cls.modules = {
            name: re.findall(r"'([^']+)'", dependencies)
            for name, dependencies in DEFINE_REGEX.findall(cls.script)
        }
        cls.backend_script = backend
        cls.backend_modules = {name for name, _ in DEFINE_REGEX.findall(backend)}

    def test_the_editor_and_fabric_are_in_the_bundle(self):
        for name in EDITOR_MODULES:
            self.assertIn(f"{MODULE_PREFIX}image_editor/{name}", self.modules)
            # The editor is no part of the backend bundle: it would be loaded with every page.
            self.assertNotIn(f"{MODULE_PREFIX}image_editor/{name}", self.backend_modules)
        for template in EDITOR_TEMPLATES:
            self.assertIn(f'registerTemplate("{template}"', self.script)
        self.assertIn("fabric", self.script)

    def test_the_editor_is_not_in_the_bundle_of_the_guests(self):
        guest = self.env["ir.qweb"]._get_asset_bundle(
            "int_filemanager.assets_guest", css=False, js=True
        )
        script = guest.js().raw.decode()
        # Neither the editor nor the service that opens it: without the service the viewer of a
        # guest has no button "Edit".
        self.assertNotIn("document_image_editor", script)

    def test_the_service_that_opens_the_editor_is_a_service_of_the_backend(self):
        self.assertIn(
            f"{MODULE_PREFIX}int_filemanager/file_viewer/document_image_editor_service",
            self.backend_modules,
        )
        self.assertIn("int_filemanager.image_editor", self.backend_script)

    def test_every_import_of_the_editor_exists(self):
        known = set(self.modules) | self.backend_modules
        missing = {
            name: sorted(
                dependency
                for dependency in dependencies
                if not dependency.startswith(LIBRARY_PREFIX) and dependency not in known
            )
            for name, dependencies in self.modules.items()
            if name.startswith(MODULE_PREFIX)
        }
        self.assertEqual({name: deps for name, deps in missing.items() if deps}, {})

    def test_the_version_of_fabric_is_the_one_the_editor_was_written_for(self):
        # A newer Fabric may change what the editor calls; replacing the file is a decision to
        # check the editor against it (and to change this number).
        self.assertIn(f"`{FABRIC_VERSION}`", self.script)

    def test_the_parts_of_fabric_that_the_editor_relies_on_are_there(self):
        for piece in FABRIC_PARTS:
            self.assertIn(piece, self.script, f"{piece} is gone from Fabric")

    def test_the_styles_of_the_editor_compile(self):
        bundle = self.env["ir.qweb"]._get_asset_bundle(self.BUNDLE, css=True, js=False)
        css = bundle.css().raw.decode()
        self.assertEqual(bundle.css_errors, [])
        # The dialogs of Odoo (a `.modal` at 1055) must stay in front of the editor.
        self.assertRegex(css, r"\.o_int_filemanager_image_editor\.modal\s*\{\s*z-index:\s*1054")
