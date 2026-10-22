import re

from odoo.tests.common import TransactionCase, tagged

DEFINE_REGEX = re.compile(r"odoo\.define\(\s*'([^']+)'\s*,\s*\[([^\]]*)\]")


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
            name: re.findall(r"'([^']+)'", dependencies)
            for name, dependencies in DEFINE_REGEX.findall(cls.script)
        }

    def test_the_modules_are_in_the_bundle(self):
        for name in ("keepass_header", "keepass_client", "keepass_unlock"):
            self.assertIn(f"@int_keepass/{name}", self.modules)

    def test_what_the_modules_import_exists(self):
        for name, dependencies in self.modules.items():
            if not name.startswith("@int_keepass/"):
                continue
            for dependency in dependencies:
                if dependency.startswith("@odoo/owl"):
                    continue
                self.assertIn(dependency, self.modules, f"{name} imports {dependency}, which is not in the bundle")

    def test_the_template_is_in_the_bundle(self):
        self.assertIn("int_keepass.Unlock", self.script)

    def test_the_core_still_offers_what_the_patch_relies_on(self):
        rpc = self.modules.get("@web/core/network/rpc")
        self.assertIsNotNone(rpc)
        # the hook for tests that the module wraps, and the setting that carries a header
        squeezed = re.sub(r"\s+", "", self.script)
        for part in ("rpc._rpc=function", 'RPC_SETTINGS=new Set(["cache","silent","xhr","headers"])'):
            self.assertIn(re.sub(r"\s+", "", part), squeezed)
