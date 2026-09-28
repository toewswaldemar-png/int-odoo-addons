"""The browser bundle builds (Schritt 4b): Odoo's own asset pipeline - JS transpiler and
SCSS compiler - accepts everything the module ships. Cheap insurance; what is wrong with
the code itself is found by tools/v2check/jscheck.sh and owlcheck.sh."""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestV2Assets(TransactionCase):
    def test_backend_bundle_contains_the_v2_explorer(self):
        bundle = self.env["ir.qweb"]._get_asset_bundle(
            "web.assets_backend", css=True, js=True, debug_assets=False
        )
        js = bundle.js().raw.decode()
        for module in (
            "@int_filemanager/int_filemanager/v2/list_view",
            "@int_filemanager/int_filemanager/v2/kanban_view",
            "@int_filemanager/int_filemanager/v2/uploads_service",
            "@int_filemanager/int_filemanager/v2/chunk_upload",
        ):
            self.assertIn(module, js)
        # Compiles the SCSS of the module, v2 upload panel included. Odoo swallows a
        # compile error into a stub stylesheet: look for that first (its text is huge).
        css = bundle.css().raw.decode()
        self.assertNotIn("A css error occured", css[:500], css[:1500])
        self.assertIn("o_int_filemanager_upload_panel", css)
