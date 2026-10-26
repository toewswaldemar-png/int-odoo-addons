import re

from odoo.tests.common import TransactionCase, tagged

MODULE_PREFIX = "@int_filemanager_image_editor/"
# Owl and the other libraries are no modules of the bundle's list; the core's own are.
LIBRARY_PREFIX = "@odoo/"
DEFINE_REGEX = re.compile(r"odoo\.define\(\s*'([^']+)'\s*,\s*\[([^\]]*)\]")

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
    "int_filemanager_image_editor.DocumentImageEditor",
    "int_filemanager_image_editor.ImageEditorTools",
    "int_filemanager_image_editor.ImageEditorPanel",
    "int_filemanager_image_editor.ImageEditorPanelStyle",
    "int_filemanager_image_editor.ImageEditorPanelEdit",
    "int_filemanager_image_editor.ImageEditorPanelAdjust",
    "int_filemanager_image_editor.ImageEditorPanelCrop",
    "int_filemanager_image_editor.ImageEditorPanelView",
    "int_filemanager_image_editor.ImageEditorColorField",
    "int_filemanager_image_editor.ImageEditorSaveDialog",
)


@tagged("post_install", "-at_install")
class TestImageEditorAssets(TransactionCase):
    """The editor for pictures is a bundle of its own, loaded at the first click on "Edit"."""

    BUNDLE = "int_filemanager_image_editor.assets_image_editor"

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

    def test_the_service_that_opens_the_editor_is_a_service_of_the_backend(self):
        self.assertIn(
            f"{MODULE_PREFIX}backend/document_image_editor_service",
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
        self.assertRegex(self.script, rf'VERSION\s*=\s*"{re.escape(FABRIC_VERSION)}"')

    def test_the_parts_of_fabric_that_the_editor_relies_on_are_there(self):
        for piece in FABRIC_PARTS:
            self.assertIn(piece, self.script, f"{piece} is gone from Fabric")

    def test_the_styles_of_the_editor_compile(self):
        bundle = self.env["ir.qweb"]._get_asset_bundle(self.BUNDLE, css=True, js=False)
        css = bundle.css().raw.decode()
        self.assertEqual(bundle.css_errors, [])
        # The dialogs of Odoo (a `.modal` at 1055) must stay in front of the editor.
        self.assertRegex(css, r"\.o_int_filemanager_image_editor\.modal\s*\{\s*z-index:\s*1054")
