import re

from odoo.tests.common import TransactionCase, tagged

DEFINE_REGEX = re.compile(r"odoo\.define\(\s*'([^']+)'\s*,\s*\[([^\]]*)\]")
MODULES = (
    "cog/service_cog_item",
    "connection/connection_banner",
    "connection/connection_menu",
    "connection/connection_service",
    "views/clamp_banner",
    "views/command_form",
    "views/parameter_list",
)


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

    def test_the_compact_rows_are_a_class_of_the_lists_of_the_module_only(self):
        css = self.env["ir.qweb"]._get_asset_bundle("web.assets_backend", css=True, js=False).css().raw.decode()
        self.assertIn(".o_int_workbench_compact .o_list_table .o_data_row > td", css)
        self.assertNotIn("\n.o_data_row > td {\n  padding-top: 0.125rem", css, "the rule starts with the class, it is not for every list")

    def test_a_clamped_row_and_the_strip_of_the_clamps_are_in_the_bundle(self):
        css = self.env["ir.qweb"]._get_asset_bundle("web.assets_backend", css=True, js=False).css().raw.decode()
        self.assertIn(".o_int_workbench_parameter_list .o_list_table .o_data_row.o_int_workbench_clamped > td:first-child", css)
        self.assertIn("o_int_workbench_clamped", self.script)
        self.assertIn("int_workbench.ClampBanner", self.script)
        self.assertIn(".o_int_workbench_parameter_list .o_list_renderer .o_int_workbench_clamp_banner", css)
        self.assertIn("position: sticky", css.split(".o_int_workbench_clamp_banner")[1][:200], "the strip stays at the top like the headings")

    def test_the_selection_list_is_registered_as_a_view(self):
        self.assertIn("int_workbench.selection_list", self.script)

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
        """The module adds no page and no field widget: the views are made of what Odoo has; it adds the list controller, the state of the connection (service, systray item, banner), the form of a request and the entry \"Service\" of the gear menu of a device."""
        ours = [name for name in self.modules if name.startswith("@int_workbench/")]
        self.assertEqual(ours, [f"@int_workbench/{name}" for name in MODULES])

    def test_the_list_is_registered_as_a_view(self):
        self.assertIn("int_workbench.parameter_list", self.script)

    def test_the_list_of_errors_is_registered_as_a_view_too(self):
        self.assertIn("int_workbench.error_list", self.script)

    def test_the_list_of_errors_takes_its_controller_from_the_same_script(self):
        """It is one script with two lists, not a second one: the module still adds no more than the list controller."""
        self.assertEqual(self.script.count("@int_workbench/views/parameter_list'"), 1)

    def test_the_banner_template_extends_the_renderer_of_odoo_where_odoo_has_the_place(self):
        """The template adds to the top of web.ListRenderer: if Odoo changes that place, the banner would be lost without an error."""
        self.assertIn('t-name="int_workbench.ListRenderer"', self.script)
        self.assertIn('t-inherit="web.ListRenderer"', self.script)
        start = self.script.index('t-name="web.ListRenderer"')
        core = self.script[start : self.script.index("t-name=", start + 1)]
        self.assertIn("o_list_renderer", core)
        self.assertIn("showNoContentHelper", core)
        self.assertIn("int_workbench.ConnectionBanner", self.script)
        self.assertIn("int_workbench.ConnectionMenu", self.script)
        self.assertIn("int_workbench.connection_menu", self.script)
