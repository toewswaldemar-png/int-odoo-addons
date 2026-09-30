"""Searching the text that was read from the documents (``node.content``).

The text lives in ``int_filemanager.derivative.text`` (kinds "text" and "words"),
which no user may read. A search only answers "found or not", filtered by the
caller's rights on the node, and never returns any text.
"""

import hashlib

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import SQL

from .. import derivative_plan as plan
from ..models.int_filemanager_node import MAX_SEARCH_TERM_CHARS, MAX_SEARCH_TERMS
from .test_v2_access_http import AccessHttpCase

INVOICE = "Rechnungsnummer 300/0154989/5/25 vom 3. Maerz, Wasserverbrauch 42 m3"
OTHER = "Wasserverbrauch und Mietvertrag, Zinsen 5% p.a., Kennung a_b"


def make_content(env, node, text, kind="words", state="done", revision_no=1):
    """Give ``node`` a revision whose blob has the text as a finished derivative."""
    sha256 = hashlib.sha256(f"{node.id}/{revision_no}".encode()).hexdigest()
    blob = env["int_filemanager.blob"].sudo().create({"sha256": sha256, "size": 1.0})
    revision = (
        env["int_filemanager.revision"]
        .sudo()
        .create(
            {
                "node_id": node.id,
                "blob_id": blob.id,
                "revision_no": revision_no,
                "origin": "upload",
            }
        )
    )
    node.sudo().current_revision_id = revision
    add_derivative(env, blob, text, kind, state)
    return blob


def add_derivative(env, blob, text, kind="words", state="done"):
    spec = plan.WORDS_SPEC if kind == "words" else plan.TEXT_SPEC
    return (
        env["int_filemanager.derivative"]
        .sudo()
        .create(
            {
                "source_blob_id": blob.id,
                "kind": kind,
                "spec": spec,
                "state": state,
                "text": text,
            }
        )
    )


@tagged("post_install", "-at_install")
class TestV2ContentSearch(TransactionCase):
    def setUp(self):
        super().setUp()
        base_group = self.env.ref("int_filemanager.group_filemanager_user")
        self.group = self.env["res.groups"].sudo().create({"name": "V2 Content Group"})
        self.scope = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {"name": "V2 Content Scope", "read_group_ids": [(4, self.group.id)]}
            )
        )
        self.hidden_scope = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create({"name": "V2 Content Hidden Scope"})
        )
        self.user = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "V2ContentUser",
                    "login": "v2_content_user",
                    "group_ids": [(6, 0, [base_group.id, self.group.id])],
                }
            )
        )
        self.invoice = self._file("invoice.pdf", INVOICE)
        self.other = self._file("other.txt", OTHER, kind="text")
        self.Node = self.env["int_filemanager.node"].with_user(self.user)

    def _file(self, name, text, kind="words", scope=None, **kwargs):
        node = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": name, "scope_id": (scope or self.scope).id})
        )
        make_content(self.env, node, text, kind=kind, **kwargs)
        return node

    def _found(self, value, operator="ilike"):
        return self.Node.search([("content", operator, value)])

    def test_word_only_in_the_document_finds_it(self):
        self.assertEqual(self._found("Maerz"), self.invoice)
        self.assertEqual(self._found("Mietvertrag"), self.other)
        self.assertFalse(self._found("Zwirbelquark"))

    def test_both_kinds_are_searched(self):
        # invoice.pdf has "words", other.txt has "text".
        self.assertEqual(self._found("Wasserverbrauch"), self.invoice | self.other)

    def test_case_does_not_matter(self):
        self.assertEqual(self._found("wasserVERBRAUCH mietvertrag"), self.other)

    def test_several_words_must_all_be_there(self):
        self.assertEqual(self._found("Wasserverbrauch Mietvertrag"), self.other)
        self.assertEqual(
            self._found("  Wasserverbrauch   Rechnungsnummer "), self.invoice
        )
        self.assertFalse(self._found("Mietvertrag Rechnungsnummer"))

    def test_numbers_with_separators_and_parts_of_them(self):
        for term in ("300/0154989/5/25", "154989", "0154989/5", "9/5/2", "300/"):
            with self.subTest(term=term):
                self.assertEqual(self._found(term), self.invoice)

    def test_wildcard_characters_are_plain_characters(self):
        self.assertEqual(self._found("5%"), self.other)
        self.assertEqual(self._found("%"), self.other)
        self.assertEqual(self._found("a_b"), self.other)
        self.assertFalse(self._found("a_c"))
        self.assertEqual(self._found("_"), self.other)

    def test_a_search_with_too_many_or_too_long_words_is_refused(self):
        with self.assertRaises(UserError):
            self._found(" ".join(["wort"] * (MAX_SEARCH_TERMS + 1)))
        with self.assertRaises(UserError):
            self._found("x" * (MAX_SEARCH_TERM_CHARS + 1))
        self.assertFalse(self._found(" ".join(["wort"] * MAX_SEARCH_TERMS)))

    def test_only_the_current_revision_counts(self):
        node = self._file("versions.pdf", "alteswort zwischenwort")
        make_content(self.env, node, "neueswort", revision_no=2)
        self.assertEqual(self._found("neueswort"), node)
        self.assertFalse(self._found("alteswort"))

    def test_text_that_is_not_done_or_of_another_kind_is_not_searched(self):
        self._file("running.pdf", "laufendwort", state="running")
        node = self._file("preview.pdf", "vorschauwort")
        # A derived picture never has text, but the field exists on every row.
        add_derivative(
            self.env, node.sudo().current_revision_id.blob_id, "kachelwort", "tile"
        )
        self.assertFalse(self._found("laufendwort"))
        self.assertFalse(self._found("kachelwort"))

    def test_the_spec_of_the_text_does_not_matter(self):
        # Whatever version of the reader made the text, it is the text of the file.
        node = self._file("older.pdf", "altspecwort")
        self.env["int_filemanager.derivative"].sudo().search(
            [("source_blob_id", "=", node.sudo().current_revision_id.blob_id.id)]
        ).spec = "v0-older"
        self.assertEqual(self._found("altspecwort"), node)

    def test_two_files_with_the_same_content_are_both_found_once(self):
        blob = self.invoice.sudo().current_revision_id.blob_id
        twin = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": "twin.pdf", "scope_id": self.scope.id})
        )
        revision = (
            self.env["int_filemanager.revision"]
            .sudo()
            .create(
                {
                    "node_id": twin.id,
                    "blob_id": blob.id,
                    "revision_no": 1,
                    "origin": "upload",
                }
            )
        )
        twin.sudo().current_revision_id = revision
        # A "text" row next to the "words" row of the same blob must not double it.
        add_derivative(self.env, blob, INVOICE, kind="text")
        found = self._found("154989")
        self.assertEqual(found, self.invoice | twin)
        self.assertEqual(len(found), 2)

    def test_trash_follows_the_usual_search_rules(self):
        self.invoice.sudo().write({"active": False, "removal_reason": "trash"})
        self.assertFalse(self._found("154989"))
        with_trash = self.Node.with_context(active_test=False)
        self.assertEqual(
            with_trash.search([("content", "ilike", "154989")]), self.invoice
        )

    def test_folders_never_match(self):
        folder = (
            self.env["int_filemanager.node"]
            .sudo()
            .create(
                {"name": "Wasserverbrauch", "scope_id": self.scope.id, "is_dir": True}
            )
        )
        self.assertNotIn(folder, self._found("Wasserverbrauch"))

    def test_combines_with_other_conditions_and_the_folder(self):
        folder = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": "inbox", "scope_id": self.scope.id, "is_dir": True})
        )
        self.other.sudo().parent_id = folder
        found = self.Node.search(
            [("content", "ilike", "Wasserverbrauch"), ("parent_id", "=", folder.id)]
        )
        self.assertEqual(found, self.other)
        found = self.Node.search(
            [("content", "ilike", "Wasserverbrauch"), ("name", "ilike", "invoice")]
        )
        self.assertEqual(found, self.invoice)

    def test_not_ilike_finds_files_without_the_word(self):
        found = self._found("Mietvertrag", operator="not ilike")
        self.assertEqual(found, self.invoice)

    def test_empty_search_value(self):
        self.assertEqual(self._found("   "), self.invoice | self.other)
        self.assertFalse(self._found("   ", operator="not ilike"))

    def test_other_operators_are_refused(self):
        for operator in ("=", "!=", "in"):
            with self.subTest(operator=operator), self.assertRaises(UserError):
                self.Node.search([("content", operator, "x")])

    def test_files_of_a_scope_the_user_cannot_read_are_not_found(self):
        self._file("secret.pdf", "geheimwort Wasserverbrauch", scope=self.hidden_scope)
        self.assertFalse(self._found("geheimwort"))
        self.assertEqual(self._found("Wasserverbrauch"), self.invoice | self.other)
        # The rule is not what the test depends on: the administrator sees it.
        self.assertTrue(
            self.env["int_filemanager.node"]
            .sudo()
            .search([("content", "ilike", "geheimwort")])
        )

    def test_the_text_is_never_returned(self):
        self.assertFalse(self.invoice.with_user(self.user).content)
        rows = self.Node.search_read(
            [("content", "ilike", "154989")], ["name", "content"]
        )
        self.assertEqual(
            rows, [{"id": self.invoice.id, "name": "invoice.pdf", "content": False}]
        )
        self.assertFalse(self.Node.search_read([], ["content"], limit=1)[0]["content"])

    def test_the_search_can_use_the_trigram_index(self):
        if not self.env.registry.has_trigram:
            self.skipTest("pg_trgm is not available in this database")
        cr = self.env.cr
        cr.execute(
            "SELECT indexdef FROM pg_indexes WHERE tablename ="
            " 'int_filemanager_derivative' AND indexdef ILIKE '%trgm%'"
        )
        self.assertTrue(cr.fetchall(), "no trigram index on the derivative table")
        # Only the trigram index can answer this: the planner may not read the table.
        query = (
            self.env["int_filemanager.derivative"]
            .sudo()
            ._search([("text", "ilike", "Zwirbelquark")])
        )
        cr.execute("SET LOCAL enable_seqscan = off")
        cr.execute(SQL("EXPLAIN %s", query.select()))
        plan_text = " ".join(row[0] for row in cr.fetchall())
        self.assertIn("int_filemanager_derivative__text_index", plan_text)


@tagged("post_install", "-at_install")
class TestV2ContentSearchHttp(AccessHttpCase):
    """The same answers over both RPC routes: no text, no foreign files."""

    def setUp(self):
        super().setUp()
        self.node.sudo().write({"name": "http_content.pdf"})
        blob = self.revision.blob_id
        self.node.sudo().current_revision_id = self.revision
        add_derivative(self.env, blob, "Zwirbelquark Wasserverbrauch 154989")

    def test_call_kw_search_read_finds_only_readable_files_and_no_text(self):
        domain = [("content", "ilike", "zwirbelquark")]
        kwargs = {"fields": ["name", "content"], "domain": domain}
        self.authenticate("v2_http_outsider", "irrelevant")
        payload = self._call_kw(
            "int_filemanager.node", "search_read", [], kwargs
        ).json()
        self.assertEqual(payload["result"], [])
        self.authenticate("v2_http_reader", "irrelevant")
        payload = self._call_kw(
            "int_filemanager.node", "search_read", [], kwargs
        ).json()
        self.assertEqual(
            payload["result"],
            [{"id": self.node.id, "name": "http_content.pdf", "content": False}],
        )
        self.assertNotIn("Wasserverbrauch", str(payload))

    def test_call_kw_web_search_read_returns_no_text(self):
        self.authenticate("v2_http_reader", "irrelevant")
        payload = self._call_kw(
            "int_filemanager.node",
            "web_search_read",
            [],
            {
                "domain": [("content", "ilike", "154989")],
                "specification": {"name": {}, "content": {}},
            },
        ).json()
        self.assertEqual(payload["result"]["length"], 1)
        self.assertFalse(payload["result"]["records"][0]["content"])

    def test_json2_search_read_finds_only_readable_files_and_no_text(self):
        body = {"domain": [["content", "ilike", "Zwirbelquark"]], "fields": ["content"]}
        resp = self._json2(
            "int_filemanager.node", "search_read", body, self._api_key(self.outsider)
        )
        self.assertEqual((resp.status_code, resp.json()), (200, []))
        resp = self._json2(
            "int_filemanager.node", "search_read", body, self._api_key(self.reader)
        )
        self.assertEqual(
            (resp.status_code, resp.json()),
            (200, [{"id": self.node.id, "content": False}]),
        )
