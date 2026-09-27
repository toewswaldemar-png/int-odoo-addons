"""HTTP-level rights tests for the v2 side models (Konzept 12/16, Pruefbericht
A1/A2): the same access rules as test_v2_access.py, but exercised over the
TWO real reachable routes instead of the ORM directly -

    /web/dataset/call_kw   - auth="user": every logged-in internal user,
                              no API key needed (A2's core finding)
    /json/2/<model>/<method> - auth="bearer": needs an API key, scope "rpc"

Both dispatch through the same odoo.service.model.get_public_method /
ir.rule machinery, so a rule missing on a side model leaks over BOTH routes,
not just one - Konzept 16 requires testing both. Written before the v2
models exist (Kern 11, Schritt 3): expected to fail until they land."""

import datetime

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestV2AccessHttp(HttpCase):
    def setUp(self):
        super().setUp()
        base_group = self.env.ref("int_filemanager.group_filemanager_user")
        self.reader_group = (
            self.env["res.groups"].sudo().create({"name": "V2 HTTP Reader"})
        )
        self.scope = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {"name": "V2 HTTP Scope", "read_group_ids": [(4, self.reader_group.id)]}
            )
        )
        self.node = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": "http_test.txt", "scope_id": self.scope.id})
        )
        self.blob = (
            self.env["int_filemanager.blob"]
            .sudo()
            .create({"sha256": "5" * 64, "size": 0.0})
        )
        self.revision = (
            self.env["int_filemanager.revision"]
            .sudo()
            .create(
                {
                    "node_id": self.node.id,
                    "blob_id": self.blob.id,
                    "revision_no": 1,
                    "origin": "upload",
                }
            )
        )

        self.outsider = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "V2HttpOutsider",
                    "login": "v2_http_outsider",
                    "group_ids": [(6, 0, [base_group.id])],
                }
            )
        )
        self.reader = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "V2HttpReader",
                    "login": "v2_http_reader",
                    "group_ids": [(6, 0, [base_group.id, self.reader_group.id])],
                }
            )
        )
        # create_uid is set from the acting user at INSERT time and ignored by write()
        # afterwards, so ownership must be established via with_user(self.reader).
        upload_operation = (
            self.env["int_filemanager.operation"]
            .with_user(self.reader)
            .create({"key": "http-op-1"})
        )
        self.upload = (
            self.env["int_filemanager.upload"]
            .with_user(self.reader)
            .create({"operation_id": upload_operation.id})
        )
        self.operation = (
            self.env["int_filemanager.operation"]
            .with_user(self.reader)
            .create({"key": "http-op-key-1"})
        )

    def _api_key(self, user):
        return (
            self.env["res.users.apikeys"]
            .with_user(user)
            ._generate(
                scope="rpc",
                name="v2 access test",
                expiration_date=datetime.datetime.now() + datetime.timedelta(hours=1),
            )
        )

    def _call_kw(self, model, method, args=None, kwargs=None):
        return self.url_open(
            "/web/dataset/call_kw",
            json={
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "model": model,
                    "method": method,
                    "args": args or [],
                    "kwargs": kwargs or {},
                },
                "id": 1,
            },
        )

    def _json2(self, model, method, params, api_key):
        return self.url_open(
            f"/json/2/{model}/{method}",
            json=params,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    # -- call_kw: every model, as a plain logged-in user, no API key --------

    def test_call_kw_search_read_denied_models_return_nothing_for_outsider(self):
        # blob is excluded here: it has no ACL at all (see the dedicated blob test
        # below), so it fails with an "error" payload, not an empty "result" - a
        # structurally different denial from the row-level rules on the rest.
        self.authenticate("v2_http_outsider", "irrelevant")
        for model in (
            "int_filemanager.node",
            "int_filemanager.revision",
            "int_filemanager.upload",
            "int_filemanager.operation",
        ):
            with self.subTest(model=model):
                resp = self._call_kw(
                    model, "search_read", kwargs={"domain": [], "fields": ["id"]}
                )
                payload = resp.json()
                self.assertNotIn("error", payload, payload)
                self.assertEqual(
                    payload["result"],
                    [],
                    f"{model} leaked rows to an outsider via call_kw",
                )

    def test_call_kw_search_read_scope_reader_sees_node_and_revision(self):
        self.authenticate("v2_http_reader", "irrelevant")
        resp = self._call_kw(
            "int_filemanager.node",
            "search_read",
            kwargs={"domain": [], "fields": ["id"]},
        )
        ids = [r["id"] for r in resp.json()["result"]]
        self.assertIn(self.node.id, ids)

        resp = self._call_kw(
            "int_filemanager.revision",
            "search_read",
            kwargs={"domain": [], "fields": ["id"]},
        )
        ids = [r["id"] for r in resp.json()["result"]]
        self.assertIn(self.revision.id, ids)

    def test_call_kw_blob_never_readable_even_with_scope_group(self):
        """No group_id at all is granted access to blob (Konzept 12), so even a
        reader who can see the node/revision gets a hard error here, not an empty
        result - the ACL layer blocks it before any row-level rule even runs."""
        self.authenticate("v2_http_reader", "irrelevant")
        resp = self._call_kw(
            "int_filemanager.blob",
            "search_read",
            kwargs={"domain": [], "fields": ["sha256"]},
        )
        self.assertIn("error", resp.json())

    def test_call_kw_upload_and_operation_only_show_own_records(self):
        self.authenticate("v2_http_outsider", "irrelevant")
        resp = self._call_kw(
            "int_filemanager.upload",
            "search_read",
            kwargs={"domain": [], "fields": ["id"]},
        )
        self.assertEqual(resp.json()["result"], [])
        resp = self._call_kw(
            "int_filemanager.operation",
            "search_read",
            kwargs={"domain": [], "fields": ["id"]},
        )
        self.assertEqual(resp.json()["result"], [])

        self.authenticate("v2_http_reader", "irrelevant")
        resp = self._call_kw(
            "int_filemanager.upload",
            "search_read",
            kwargs={"domain": [], "fields": ["id"]},
        )
        ids = [r["id"] for r in resp.json()["result"]]
        self.assertIn(self.upload.id, ids)

    def test_call_kw_read_group_respects_scope(self):
        self.authenticate("v2_http_outsider", "irrelevant")
        resp = self._call_kw(
            "int_filemanager.node",
            "read_group",
            kwargs={"domain": [], "fields": ["scope_id"], "groupby": ["scope_id"]},
        )
        self.assertEqual(resp.json()["result"], [])

    def test_call_kw_write_denied_returns_error_not_silent_success(self):
        self.authenticate("v2_http_outsider", "irrelevant")
        resp = self._call_kw(
            "int_filemanager.revision",
            "write",
            args=[[self.revision.id], {"origin": "edit"}],
        )
        payload = resp.json()
        self.assertIn(
            "error", payload, "write on a foreign revision must not silently succeed"
        )

    # -- JSON-2: same rules must hold with a scoped API key, no session -----

    def test_json2_missing_bearer_is_unauthorized(self):
        resp = self.url_open(
            "/json/2/int_filemanager.node/search_read",
            json={"domain": [], "fields": ["id"]},
        )
        self.assertEqual(resp.status_code, 401)

    def test_json2_search_read_respects_same_rules_as_call_kw(self):
        outsider_key = self._api_key(self.outsider)
        resp = self._json2(
            "int_filemanager.node",
            "search_read",
            {"domain": [], "fields": ["id"]},
            outsider_key,
        )
        self.assertEqual(resp.json(), [])

        reader_key = self._api_key(self.reader)
        resp = self._json2(
            "int_filemanager.node",
            "search_read",
            {"domain": [], "fields": ["id"]},
            reader_key,
        )
        ids = [r["id"] for r in resp.json()]
        self.assertIn(self.node.id, ids)

    def test_json2_blob_never_readable(self):
        reader_key = self._api_key(self.reader)
        resp = self._json2(
            "int_filemanager.blob",
            "search_read",
            {"domain": [], "fields": ["sha256"]},
            reader_key,
        )
        self.assertEqual(resp.status_code, 403)

    def test_json2_upload_only_shows_own_records(self):
        outsider_key = self._api_key(self.outsider)
        resp = self._json2(
            "int_filemanager.upload",
            "search_read",
            {"domain": [], "fields": ["id"]},
            outsider_key,
        )
        self.assertEqual(resp.json(), [])

        reader_key = self._api_key(self.reader)
        resp = self._json2(
            "int_filemanager.upload",
            "search_read",
            {"domain": [], "fields": ["id"]},
            reader_key,
        )
        ids = [r["id"] for r in resp.json()]
        self.assertIn(self.upload.id, ids)
