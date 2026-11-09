import re

from odoo.tests.common import TransactionCase, tagged

DEFINE_REGEX = re.compile(r"odoo\.define\(\s*'([^']+)'\s*,\s*\[([^\]]*)\]")
MODULES = ("regler_client", "regler_poll", "regler_views", "regler_app")


@tagged("post_install", "-at_install")
class TestAssets(TransactionCase):
    """The scripts are built into the backend bundle and import what exists.

    There is no browser in the test run, so this is what can be checked here: a wrong path in an
    import is no error of the build, the module is just never loaded.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        bundle = cls.env["ir.qweb"]._get_asset_bundle("web.assets_backend", css=False, js=True)
        cls.script = bundle.js().raw.decode()
        cls.modules = {
            name: re.findall(r"'([^']+)'", dependencies) for name, dependencies in DEFINE_REGEX.findall(cls.script)
        }

    def test_the_modules_are_in_the_bundle(self):
        for name in MODULES:
            self.assertIn(f"@int_regler/{name}", self.modules)

    def test_what_the_modules_import_exists(self):
        for name, dependencies in self.modules.items():
            if not name.startswith("@int_regler/"):
                continue
            for dependency in dependencies:
                if dependency.startswith("@odoo/owl"):
                    continue
                self.assertIn(dependency, self.modules, f"{name} imports {dependency}, which is not in the bundle")

    def test_the_templates_are_in_the_bundle(self):
        for template in ("App", "Overview", "Errors", "ClampField"):
            self.assertIn(f"int_regler.{template}", self.script)
        # the process values and the clamps are the list of int.regler.parameter, not a part of the page
        self.assertNotIn("int_regler.Values", self.script)

    def test_the_page_is_registered_as_the_client_action(self):
        self.assertIn('"int_regler.app"', self.script.replace("'", '"'))
