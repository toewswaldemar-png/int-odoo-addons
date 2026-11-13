import re

from odoo.tests.common import TransactionCase, tagged

DEFINE_REGEX = re.compile(r"odoo\.define\(\s*'([^']+)'\s*,\s*\[([^\]]*)\]")
MODULES = ("views/parameter_list",)


@tagged("post_install", "-at_install")
class TestAssets(TransactionCase):
    """The script is built into the backend bundle and imports what exists.

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

    def test_the_style_sheet_is_built_into_the_bundle_and_is_for_the_list_only(self):
        css = self.env["ir.qweb"]._get_asset_bundle("web.assets_backend", css=True, js=False).css().raw.decode()
        # the rules start with the class of the list: nothing else in Odoo changes
        self.assertIn(".o_int_workbench_parameter_list .o_list_table .o_list_number", css)

    def test_the_modules_are_in_the_bundle(self):
        for name in MODULES:
            self.assertIn(f"@int_workbench/{name}", self.modules)

    def test_what_the_modules_import_exists(self):
        for name, dependencies in self.modules.items():
            if not name.startswith("@int_workbench/"):
                continue
            for dependency in dependencies:
                if dependency.startswith("@odoo/owl"):
                    continue
                self.assertIn(dependency, self.modules, f"{name} imports {dependency}, which is not in the bundle")

    def test_there_is_nothing_but_the_list(self):
        """The module adds no page and no field widget: the views are made of what Odoo has, and the list controller is the one exception."""
        ours = [name for name in self.modules if name.startswith("@int_workbench/")]
        self.assertEqual(ours, [f"@int_workbench/{name}" for name in MODULES])

    def test_the_list_is_registered_as_a_view(self):
        self.assertIn("int_workbench.parameter_list", self.script)
