"""N1 is closed in v2: the value methods check the user's right themselves, so a
user cannot get around it by calling them over /web/dataset/call_kw or
/json/2 instead of the file manager's own routes."""

from odoo.tests.common import tagged

from .test_v2_access_http import AccessHttpCase


@tagged("post_install", "-at_install")
class TestV2FieldValueHttp(AccessHttpCase):
    def setUp(self):
        super().setUp()
        self.node.sudo().current_revision_id = self.revision
        self.field = (
            self.env["int_filemanager.extraction_field"]
            .sudo()
            .create({"name": "N1 number", "value_type": "number"})
        )
        self.values = [{"field_id": self.field.id, "text": "4711"}]

    def _stored(self):
        return (
            self.env["int_filemanager.field_value"]
            .sudo()
            .search_count([("node_id", "=", self.node.id)])
        )

    def test_call_kw_foreign_file_denied(self):
        self.authenticate("v2_http_outsider", "irrelevant")
        for method, args in (
            ("apply_field_values", [self.node.id, self.revision.id, self.values]),
            ("suggest_field_values", [self.node.id]),
        ):
            with self.subTest(method=method):
                payload = self._call_kw("int_filemanager.node", method, args).json()
                self.assertIn("error", payload)
                self.assertIn("AccessError", payload["error"]["data"]["name"])
        self.assertEqual(self._stored(), 0)

    def test_call_kw_reading_is_not_enough_to_store(self):
        self.authenticate("v2_http_reader", "irrelevant")
        payload = self._call_kw(
            "int_filemanager.node",
            "apply_field_values",
            [self.node.id, self.revision.id, self.values],
        ).json()
        self.assertIn("AccessError", payload["error"]["data"]["name"])
        self.assertEqual(self._stored(), 0)

    def test_json2_foreign_file_denied(self):
        key = self._api_key(self.outsider)
        resp = self._json2(
            "int_filemanager.node",
            "apply_field_values",
            {
                "node_id": self.node.id,
                "revision_id": self.revision.id,
                "values": self.values,
            },
            key,
        )
        self.assertEqual(resp.status_code, 403)
        resp = self._json2(
            "int_filemanager.node",
            "suggest_field_values",
            {"node_id": self.node.id},
            key,
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self._stored(), 0)

    def test_json2_values_cannot_be_written_directly(self):
        key = self._api_key(self.reader)
        resp = self._json2(
            "int_filemanager.field_value",
            "create",
            {
                "vals_list": [
                    {
                        "node_id": self.node.id,
                        "field_id": self.field.id,
                        "value_text": "1",
                    }
                ]
            },
            key,
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self._stored(), 0)
