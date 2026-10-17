import json
from unittest.mock import patch

from odoo.tests.common import HttpCase, TransactionCase, tagged

from ..models.int_filemanager_share import ShareBadRequest, ShareForbidden
from ..tools import share_gateway
from ..tools.share_gateway import ShareGateway
from .test_folder_access import AccessCase

DOCUMENT = "int.filemanager.document"
FOLDER = "int.filemanager.folder"
TAG = "int.filemanager.tag"


class GatewayCase(AccessCase):
    """A shared folder with a hidden folder, a folder beside it, files and tags."""

    @classmethod
    def _set_up_gateway(cls):
        cls._set_up_access()
        cls.Share = cls.env["int.filemanager.share"]
        cls.Tag = cls.env[TAG]
        # parent (open) > root (shared) > sub; root > hidden (restricted); beside: other (open)
        cls.parent = cls.Folder.create({"name": "Parent", "access_mode": "open"})
        cls.root = cls.Folder.create({"name": "Root", "parent_id": cls.parent.id})
        cls.sub = cls.Folder.create({"name": "Sub", "parent_id": cls.root.id})
        cls.hidden = cls.Folder.create({"name": "Hidden", "parent_id": cls.root.id, "access_mode": "restricted"})
        cls.other = cls.Folder.create({"name": "Other", "access_mode": "open"})
        cls.visible_tag = cls.Tag.create({"name": "Invoice"})
        cls.secret_tag = cls.Tag.create({"name": "Secret"})

    def _make_documents(self):
        self.in_root = self._document(self.root, "in_root.txt", b"1")
        self.in_sub = self._document(self.sub, "in_sub.txt", b"2")
        self.in_hidden = self._document(self.hidden, "in_hidden.txt", b"3")
        self.in_other = self._document(self.other, "in_other.txt", b"4")
        self.archived = self._document(self.root, "archived.txt", b"5")
        self.archived.active = False
        self.in_root.tag_ids = self.visible_tag
        self.in_hidden.tag_ids = self.secret_tag
        self.visible = self.in_root + self.in_sub


@tagged("post_install", "-at_install")
class TestShareGateway(GatewayCase, TransactionCase):
    """What a guest can ask the gateway: the attacks of the spike, and what the plan adds."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_gateway()

    def setUp(self):
        super().setUp()
        self._make_documents()
        self.share = self.Share.create({"folder_id": self.root.id})
        self.gateway = ShareGateway(self.share)

    def _call(self, model, method, *args, **kwargs):
        return self.gateway.call(model, method, list(args), kwargs)

    def _search(self, domain, model=DOCUMENT, **kwargs):
        result = self._call(model, "web_search_read", domain=domain, specification={"name": {}}, **kwargs)
        return result["records"]

    def _names(self, domain, model=DOCUMENT, **kwargs):
        return sorted(record["name"] for record in self._search(domain, model, **kwargs))

    def assertRefused(self, *call, kind=ShareForbidden, **kwargs):
        with self.assertRaises(kind):
            self._call(*call, **kwargs)

    # --- the list of calls ----------------------------------------------------------------------

    def test_only_the_reading_methods_of_the_table_are_open(self):
        for method in (
            "write", "unlink", "create", "search_read", "read", "action_archive", "web_save", "copy",
            "check_access", "with_user", "_search", "sudo", "export_data", "name_create", "message_post",
            "search", "search_count", "read_group", "browse",
        ):  # fmt: skip
            with self.subTest(method):
                self.assertRefused(DOCUMENT, method)
        for model in (
            "res.users", "ir.config_parameter", "ir.attachment", "int.filemanager.text.page",
            "int.filemanager.link", "int.filemanager.share", "res.partner", "ir.model.data",
        ):  # fmt: skip
            with self.subTest(model):
                self.assertRefused(model, "web_search_read")
        self.assertRefused(DOCUMENT, "get_views", views=[[False, "form"]])

    # --- the scope ------------------------------------------------------------------------------

    def test_a_search_finds_the_files_of_the_scope_only(self):
        self.assertEqual(self._names([]), ["in_root.txt", "in_sub.txt"])
        self.assertEqual(self._names([], FOLDER), ["Root", "Sub"])

    def test_no_domain_widens_the_scope(self):
        for domain in (
            ["|", ("id", ">", 0), ("name", "=", "x")],
            [(1, "=", 1)],
            ["!", ("id", "=", 0)],
            [("folder_id", "in", [self.other.id, self.hidden.id])],
            [("id", "in", [self.in_other.id, self.in_hidden.id, self.archived.id])],
            [("folder_id", "=", self.hidden.id)],
        ):
            with self.subTest(domain):
                found = set(self._names(domain))
                self.assertLessEqual(found, {"in_root.txt", "in_sub.txt"})
        self.assertFalse(self._search([("folder_id", "=", self.hidden.id)]))
        self.assertFalse(self._search([("id", "in", [self.in_other.id])]))

    def test_the_context_of_the_guest_is_not_used(self):
        self.assertEqual(
            self._names([], context={"active_test": False}), ["in_root.txt", "in_sub.txt"]
        )

    def test_child_of_takes_only_the_folders_that_the_share_shows(self):
        self.assertEqual(self._names([("folder_id", "child_of", self.root.id)]), ["in_root.txt", "in_sub.txt"])
        self.assertEqual(self._names([("folder_id", "child_of", [self.sub.id])]), ["in_sub.txt"])
        for folder in (self.parent, self.hidden, self.other):
            with self.subTest(folder.name):
                self.assertRefused(DOCUMENT, "web_search_read", domain=[("folder_id", "child_of", folder.id)])
        self.assertRefused(DOCUMENT, "web_search_read", domain=[("folder_id", "parent_of", self.sub.id)])
        self.assertRefused(FOLDER, "web_search_read", domain=[("id", "parent_of", self.sub.id)])
        self.assertRefused(FOLDER, "web_search_read", domain=[("id", "child_of", self.other.id)])
        self.assertEqual(self._names([("id", "child_of", self.sub.id)], FOLDER), ["Sub"])

    def test_fields_operators_and_values_outside_the_list_are_refused(self):
        for expression in (
            "folder_id.access_user_ids.login", "folder_id.access_user_ids", "create_uid", "create_uid.login",
            "active", "origin_path", "content_search", "checksum", "ocr_checksum", "content", "company_id",
            "message_ids", "folder_id.create_uid",
        ):  # fmt: skip
            with self.subTest(expression):
                self.assertRefused(DOCUMENT, "web_search_read", domain=[(expression, "ilike", "a")])
        self.assertRefused(DOCUMENT, "web_search_read", domain=[("name", "=?", "a")])
        self.assertRefused(DOCUMENT, "web_search_read", domain=[("folder_id", "any", [("create_uid", "=", 1)])])
        self.assertRefused(
            DOCUMENT, "web_search_read", domain=[("folder_id", "any", [("access_user_ids.login", "=", "a")])]
        )

    def test_a_domain_that_is_not_one_is_a_bad_request(self):
        for domain in ("name = a", {"a": 1}, [("name", "sqli", "a")], [("name", "=", {"a": 1})], [("name",)]):
            with self.subTest(domain):
                self.assertRefused(DOCUMENT, "web_search_read", domain=domain, kind=ShareBadRequest)
        for value in (["Invoice"], "Root"):  # a text would be looked up by name, as superuser
            with self.subTest(value):
                self.assertRefused(
                    DOCUMENT, "web_search_read", domain=[("folder_id", "in", value)], kind=ShareBadRequest
                )
        self.assertRefused(
            DOCUMENT, "web_search_read", domain=[("name", "in", list(range(300)))], kind=ShareBadRequest
        )
        # an any inside an any: the folders have no relation of the list to follow
        nested = [("folder_id", "any", [("parent_id", "any", [("id", ">", 0)])])]
        self.assertRefused(DOCUMENT, "web_search_read", domain=nested)
        self.assertRefused(
            DOCUMENT, "web_search_read", domain=[("name", "=", "x" * share_gateway.MAX_DOMAIN_LENGTH)],
            kind=ShareBadRequest,
        )  # fmt: skip

    def test_paths_of_one_step_and_an_any_inside_the_list_work(self):
        self.assertEqual(self._names([("folder_id.name", "=", "Sub")]), ["in_sub.txt"])
        self.assertEqual(self._names([("tag_ids.name", "=", "Invoice")]), ["in_root.txt"])
        self.assertEqual(self._names([("folder_id", "any", [("name", "=", "Sub")])]), ["in_sub.txt"])
        self.assertRefused(DOCUMENT, "web_search_read", domain=[("folder_id.parent_id.name", "=", "a")])

    # --- the parent of the shared folder ----------------------------------------------------------

    def test_the_guest_does_not_learn_what_lies_above_the_shared_folder(self):
        records = self._call(
            FOLDER, "web_search_read", domain=[], specification={"name": {}, "parent_id": {}}
        )["records"]
        parents = {record["name"]: record["parent_id"] for record in records}
        self.assertFalse(parents["Root"])
        self.assertTrue(parents["Sub"])
        self.assertRefused(
            FOLDER, "web_search_read", domain=[],
            specification={"parent_id": {"fields": {"display_name": {}}}},
        )  # fmt: skip
        self.assertFalse(self._search([("parent_id", "=", self.parent.id)], FOLDER))
        self.assertRefused(FOLDER, "web_search_read", domain=[("parent_id.name", "ilike", "Parent")])
        self.assertRefused(FOLDER, "web_search_read", domain=[("parent_id", "any", [("name", "=", "a")])])
        self.assertRefused(FOLDER, "web_search_read", domain=[], order="parent_id")
        self.assertRefused(FOLDER, "formatted_read_group", domain=[], groupby=["parent_id"], aggregates=["__count"])
        self.assertEqual(self._names([("parent_id", "=", self.root.id)], FOLDER), ["Sub"])

    # --- what is read -----------------------------------------------------------------------------

    def test_a_specification_names_fields_of_the_list_only(self):
        for name in (
            "create_uid", "message_ids", "origin_path", "content", "thumbnail", "activity_ids", "company_id",
            "access_user_ids", "write_uid", "message_follower_ids",
        ):  # fmt: skip
            with self.subTest(name):
                self.assertRefused(DOCUMENT, "web_search_read", specification={name: {}})
        self.assertRefused(
            DOCUMENT, "web_search_read", specification={"folder_id": {"fields": {"access_user_ids": {}}}}
        )
        self.assertRefused(
            DOCUMENT, "web_search_read", specification={"tag_ids": {"fields": {"create_uid": {}}}}
        )
        self.assertRefused(
            DOCUMENT, "web_search_read", specification={"tag_ids": {"foo": 1}}, kind=ShareBadRequest
        )
        records = self._call(
            DOCUMENT, "web_search_read", domain=[],
            specification={"tag_ids": {"fields": {"name": {}}, "context": {"x": 1}, "domain": [(1, "=", 1)]}},
        )["records"]  # fmt: skip
        self.assertEqual(len(records), 2)

    def test_the_checksum_is_asked_for_by_the_widgets_and_never_given(self):
        spec = {"name": {}, "checksum": {}, "ocr_checksum": {}}
        records = self._call(DOCUMENT, "web_search_read", domain=[], specification=spec)["records"]
        for record in records:
            self.assertIs(record["checksum"], False)
            self.assertIs(record["ocr_checksum"], False)
        records = self._call(DOCUMENT, "web_read", [self.in_root.id], specification=spec)
        self.assertEqual((records[0]["checksum"], records[0]["ocr_checksum"]), (False, False))
        self.assertIn("checksum", self._call(DOCUMENT, "fields_get"))
        self.assertIn(self.in_root.checksum, self.Document.search([]).mapped("checksum"))  # it is there; not given
        result = self._call(
            DOCUMENT, "web_read_group", domain=[], groupby=["folder_id"], aggregates=["__count"],
            auto_unfold=True, unfold_read_specification=spec,
        )  # fmt: skip
        for group in result["groups"]:
            for record in group.get("__records", []):
                self.assertIs(record["checksum"], False)

    def test_the_order_the_groups_and_the_aggregates_name_fields_of_the_list_only(self):
        self.assertRefused(DOCUMENT, "web_search_read", order="create_uid")
        self.assertRefused(DOCUMENT, "web_search_read", order="checksum")
        self.assertRefused(DOCUMENT, "web_search_read", order="name asc, create_uid desc")
        for order in ("name; select pg_sleep(5)", "(select 1)", "folder_id.name"):
            with self.subTest(order):
                self.assertRefused(DOCUMENT, "web_search_read", order=order, kind=ShareBadRequest)
        self._call(DOCUMENT, "web_search_read", order="name desc nulls last")
        for groupby in (["create_uid"], ["folder_id.name"], ["checksum"]):
            with self.subTest(groupby):
                self.assertRefused(DOCUMENT, "formatted_read_group", groupby=groupby, aggregates=["__count"])
        self.assertRefused(
            DOCUMENT, "formatted_read_group", groupby=["name", "mimetype", "folder_id", "tag_ids"],
            aggregates=["__count"], kind=ShareBadRequest,
        )  # fmt: skip
        self.assertRefused(DOCUMENT, "formatted_read_group", groupby=["write_date:evil"], aggregates=["__count"])
        for aggregates in (["create_uid:count"], ["size:evil"], ["id:array_agg"], ["(select 1):sum"]):
            with self.subTest(aggregates):
                self.assertRefused(DOCUMENT, "formatted_read_group", groupby=["mimetype"], aggregates=aggregates)
        self.assertRefused(DOCUMENT, "formatted_read_group", groupby=["mimetype"], aggregates=["__count"], having=[1])
        groups = self._call(DOCUMENT, "formatted_read_group", domain=[], groupby=["folder_id"], aggregates=["__count"])
        self.assertEqual(sorted(group["__count"] for group in groups), [1, 1])
        groups = self._call(DOCUMENT, "formatted_read_group", domain=[], groupby=["mimetype"], aggregates=["size:sum"])
        self.assertEqual(len(groups), 1)

    def test_limit_and_offset_are_bounded(self):
        for limit in (100000, -1, "abc", None, True):
            with self.subTest(limit):
                self.assertLessEqual(self.gateway.limit(limit), share_gateway.MAX_LIMIT)
        self.assertEqual(self.gateway.limit(2), 2)
        self.assertEqual(self.gateway.offset(-5), 0)
        self.assertEqual(self.gateway.offset(10**12), share_gateway.MAX_OFFSET)
        self.assertFalse(self._search([], offset=10**12))
        self.assertEqual(len(self._search([], limit=1)), 1)

    def test_a_file_is_read_by_its_id_only_inside_the_scope(self):
        ids = [self.in_root.id, self.in_hidden.id, self.in_other.id, self.archived.id]
        records = self._call(DOCUMENT, "web_read", ids, specification={"name": {}})
        self.assertEqual([record["name"] for record in records], ["in_root.txt"])
        self.assertRefused(DOCUMENT, "web_read", ["1"], specification={}, kind=ShareBadRequest)
        self.assertRefused(DOCUMENT, "web_read", list(range(1000)), specification={}, kind=ShareBadRequest)
        self.assertEqual(self._call(FOLDER, "web_read", [self.parent.id, self.hidden.id], specification={}), [])

    def test_the_open_groups_of_a_reload_are_cut_down(self):
        group = {"value": self.root.id, "folded": False, "offset": 0, "limit": 10**9}
        group["progressbar_domain"] = [(1, "=", 1)]
        result = self._call(
            DOCUMENT, "web_read_group", domain=[], groupby=["folder_id"], aggregates=["__count"],
            opening_info=[group], unfold_read_specification={"name": {}},
        )  # fmt: skip
        self.assertTrue(result["groups"])
        self.assertEqual(self.gateway.opening_info([group])[0].keys(), {"value", "folded", "offset", "limit"})
        self.assertEqual(self.gateway.opening_info([group])[0]["limit"], share_gateway.MAX_LIMIT)
        for info in ("x", [1], [{"value": {"a": 1}}], [{"value": [1, 2, 3, 4]}]):
            with self.subTest(info):
                with self.assertRaises(ShareBadRequest):
                    self.gateway.opening_info(info)

    # --- the search panel --------------------------------------------------------------------------

    def _panel(self, model, field, method="search_panel_select_range", **kwargs):
        kwargs.setdefault("expand", True)
        kwargs.setdefault("limit", 0)
        return self._call(model, method, field, **kwargs)

    def test_the_panel_of_folders_shows_the_scope_and_the_root_has_no_parent(self):
        values = self._panel(DOCUMENT, "folder_id", comodel_domain=[])["values"]
        self.assertEqual({value["display_name"] for value in values}, {"Root", "Sub"})
        root = next(value for value in values if value["display_name"] == "Root")
        self.assertFalse(root["parent_id"])
        self.assertFalse(self._panel(DOCUMENT, "folder_id", comodel_domain=[("id", "=", self.other.id)])["values"])
        self.assertFalse(
            self._panel(
                DOCUMENT, "folder_id", search_domain=[("folder_id", "=", self.other.id)], expand=False
            )["values"]
        )

    def test_the_panel_of_tags_shows_the_tags_of_the_files_that_the_guest_sees(self):
        values = self._panel(DOCUMENT, "tag_ids", "search_panel_select_multi_range", enable_counters=True)["values"]
        self.assertEqual([value["display_name"] for value in values], ["Invoice"])
        self.assertEqual(self._names([], TAG), ["Invoice"])
        self.assertFalse(self._call(TAG, "name_search", "Secret"))
        self.assertEqual(len(self._call(TAG, "name_search", "Inv")), 1)
        self.assertEqual(self._call(TAG, "web_read", [self.secret_tag.id], specification={}), [])

    def test_the_panel_refuses_what_is_not_the_list(self):
        self.assertRefused(DOCUMENT, "search_panel_select_range", "create_uid")
        self.assertRefused(DOCUMENT, "search_panel_select_range", "folder_id", group_by="create_uid")
        self.assertRefused(DOCUMENT, "search_panel_select_range", "folder_id", comodel_domain=[("create_uid", "=", 1)])
        self.assertRefused(DOCUMENT, "search_panel_select_range", "folder_id", category_domain=[("checksum", "=", "a")])

    # --- the other models, the fields, the views ---------------------------------------------------

    def test_folders_and_tags_are_found_inside_the_scope_only(self):
        self.assertFalse(self._call(FOLDER, "name_search", "Hidden"))
        self.assertFalse(self._call(FOLDER, "name_search", "Other"))
        self.assertEqual([name for __, name in self._call(FOLDER, "name_search", "Sub")], ["Sub"])
        self.assertEqual(self._call(FOLDER, "web_name_search", "Sub")[0]["display_name"], "Sub")
        self.assertRefused(FOLDER, "web_search_read", specification={"access_user_ids": {}})
        self.assertRefused(FOLDER, "name_search", "a", operator="~")

    def test_fields_get_gives_the_list_and_nothing_else(self):
        names = set(self._call(DOCUMENT, "fields_get"))
        self.assertEqual(names, share_gateway.FIELDS[DOCUMENT] | {"checksum", "ocr_checksum"})
        self.assertRefused(DOCUMENT, "fields_get", ["create_uid"])

    def test_the_views_are_those_of_the_guests_without_a_checksum(self):
        result = self._call(DOCUMENT, "get_views", views=[[False, "list"], [False, "kanban"], [False, "search"]])
        self.assertEqual(set(result["views"]), {"list", "kanban", "search"})
        self.assertEqual(set(result["models"]), {DOCUMENT, FOLDER, TAG} & set(result["models"]))
        for info in result["models"].values():
            self.assertFalse({"create_uid", "origin_path", "content", "company_id"} & set(info["fields"]))
        for view in result["views"].values():
            self.assertNotIn("checksum", view["arch"])
        self.assertIn("int_filemanager_guest_list", result["views"]["list"]["arch"])

    def test_the_call_must_have_the_shape_of_a_call(self):
        with self.assertRaises(ShareBadRequest):
            self.gateway.call(DOCUMENT, "fields_get", {}, [])
        with self.assertRaises(ShareForbidden):
            self.gateway.call(None, None, [], {})


@tagged("post_install", "-at_install")
class TestShareGatewayRoute(GatewayCase, HttpCase):
    """The route: statuses, no traceback, who gets in."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_gateway()

    def setUp(self):
        super().setUp()
        self._make_documents()
        self.share = self.Share.create({"folder_id": self.root.id})
        self.env.registry._int_filemanager_share_brake = None  # the counters start empty

    def _rpc(self, share=None, **body):
        share = share or self.share
        body.setdefault("model", DOCUMENT)
        body.setdefault("method", "web_search_read")
        body.setdefault("kwargs", {"domain": [], "specification": {"name": {}}})
        return self.url_open(
            f"/int_filemanager/share/{share.token}/rpc",
            data=json.dumps(body),
            headers={"Content-Type": "application/json"},
        )

    def test_a_call_gives_json_and_sets_no_cookie(self):
        response = self._rpc()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sorted(r["name"] for r in response.json()["records"]), ["in_root.txt", "in_sub.txt"])
        self.assertNotIn("session_id", response.cookies)
        self.assertNotIn("Set-Cookie", response.headers)
        self.assertEqual(response.headers["Cache-Control"], "private, no-cache")

    def test_a_logged_in_user_is_a_guest_there(self):
        self.authenticate("access_alice", "access_alice")
        response = self._rpc()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["records"]), 2)

    def test_what_is_refused_is_a_status_and_a_short_text_without_a_traceback(self):
        cases = (
            (self._rpc(method="unlink"), 403),
            (self._rpc(model="res.users"), 403),
            (self._rpc(kwargs={"domain": [("create_uid", "=", 1)]}), 403),
            (self._rpc(kwargs={"domain": "x"}), 400),
            (self.url_open(f"/int_filemanager/share/{self.share.token}/rpc", data="no json"), 400),
            (self.url_open(f"/int_filemanager/share/{self.share.token}/rpc", data="[1]"), 400),
            (self.url_open(f"/int_filemanager/share/{self.share.token}/rpc", data=" "), 400),
        )
        for response, status in cases:
            with self.subTest(status=status, text=response.text[:60]):
                self.assertEqual(response.status_code, status)
                self.assertNotIn("Traceback", response.text)
                self.assertNotIn("/usr/lib", response.text)

    def test_an_unexpected_error_is_a_500_without_the_error(self):
        def boom(gateway, model, args, kwargs):
            raise RuntimeError("secret detail /usr/lib/python3/odoo")

        with patch.dict(share_gateway.METHODS, {(DOCUMENT, "web_search_read"): boom}):
            response = self._rpc()
        self.assertEqual(response.status_code, 500)
        for text in ("secret detail", "RuntimeError", "Traceback", "/usr/lib"):
            self.assertNotIn(text, response.text)

    def test_a_body_over_a_megabyte_is_not_read(self):
        self.assertEqual(self._rpc(kwargs={"domain": [("name", "=", "x" * 1_100_000)]}).status_code, 413)

    def test_who_gets_in(self):
        # unknown, blocked
        self.assertEqual(self.url_open("/int_filemanager/share/unknown/rpc", data="{}").status_code, 404)
        # only uploading: nothing to read; a file: no gateway
        upload_only = self.Share.create({"folder_id": self.root.id, "can_view": False, "can_download": False, "can_upload": True})
        self.assertEqual(self._rpc(upload_only).status_code, 403)
        self.assertEqual(self._rpc(self.Share.create({"document_id": self.in_root.id})).status_code, 403)
        # download alone is enough to read the list
        self.assertEqual(self._rpc(self.Share.create({"folder_id": self.root.id, "can_view": False})).status_code, 200)
        self.share.action_archive()
        self.assertEqual(self._rpc().status_code, 410)

    def test_the_password_key_is_needed_and_checked(self):
        share = self.Share.create({"folder_id": self.root.id, "password": "a long password"})
        self.assertEqual(self._rpc(share).status_code, 403)
        self.assertEqual(self._rpc(share, k="wrong").status_code, 403)
        self.assertEqual(self._rpc(share, k=5).status_code, 403)
        key = share._unlock_key()
        self.assertEqual(self._rpc(share, k=key).status_code, 200)
        self.assertEqual(self._rpc(self.share, k=key).status_code, 200)  # no password there: not needed

    def test_the_key_of_one_share_opens_no_other(self):
        first = self.Share.create({"folder_id": self.root.id, "password": "a long password"})
        second = self.Share.create({"folder_id": self.other.id, "password": "a long password"})
        self.assertEqual(self._rpc(second, k=first._unlock_key()).status_code, 403)

    def test_the_brake_on_requests_holds(self):
        self.env["ir.config_parameter"].set_param("int_filemanager.share_requests_per_minute", "2")
        statuses = [self._rpc().status_code for __ in range(3)]
        self.assertEqual(statuses, [200, 200, 429])
