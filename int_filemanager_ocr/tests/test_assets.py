import re

from odoo.tests.common import TransactionCase, tagged

MODULE_PREFIX = "@int_filemanager_ocr/"
# Owl and the other libraries are no modules of the bundle's list; the core's own are.
LIBRARY_PREFIX = "@odoo/"
DEFINE_REGEX = re.compile(r"odoo\.define\(\s*'([^']+)'\s*,\s*\[([^\]]*)\]")

TEMPLATES = (
    "int_filemanager_ocr.DocumentContentHitCountField",
    "int_filemanager_ocr.DocumentContentHitsField",
    "int_filemanager_ocr.DocumentContentHitsPopover",
)


@tagged("post_install", "-at_install")
class TestAssets(TransactionCase):
    """The widgets of the hits are built into the backend bundle and import what exists."""

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
        for name in (
            "content_hits/document_content_hit_count_field",
            "content_hits/document_content_hits_field",
            "content_hits/document_content_hits_popover",
        ):
            self.assertIn(f"{MODULE_PREFIX}{name}", self.modules)

    def test_the_templates_are_in_the_bundle(self):
        for template in TEMPLATES:
            self.assertIn(f'registerTemplate("{template}"', self.script)

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

    def test_the_styles_of_the_module_compile(self):
        # A style that does not compile breaks the whole bundle of the web client.
        for name in ("web.assets_backend", "web.assets_web"):
            bundle = self.env["ir.qweb"]._get_asset_bundle(name, css=True, js=False)
            bundle.css()
            self.assertEqual(bundle.css_errors, [], name)
