import re

from odoo.tests.common import TransactionCase, tagged

MODULE_PREFIX = "@int_filemanager/"
# Owl and the other libraries are no modules of the bundle's list; the core's own are.
LIBRARY_PREFIX = "@odoo/"
DEFINE_REGEX = re.compile(r"odoo\.define\(\s*'([^']+)'\s*,\s*\[([^\]]*)\]")

TEMPLATES = (
    "int_filemanager.DocumentDropzone",
    "int_filemanager.DocumentListRenderer",
    "int_filemanager.DocumentListView.Buttons",
    "int_filemanager.DocumentNameField",
    "int_filemanager.SizeField",
)


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
            "document_dropzone",
            "document_list_controller",
            "document_list_renderer",
            "document_list_view",
            "size_field",
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

    def test_the_templates_are_in_the_bundle(self):
        # The name is also in the class that uses the template: look for the registration.
        for template in TEMPLATES:
            self.assertIn(f'registerTemplate("{template}"', self.script)
