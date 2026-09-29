"""suggest_field_values on a node: rights, the text of the current revision, the own
company left out, and the sender and tags suggested alongside the fields."""

import json
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests.common import tagged

from .. import value_suggest
from .test_v2_derivative import DerivativeCase, FakeConverter
from .test_v2_derivative_kinds import text_result
from .test_v2_value_suggest import layout

OWN_IBAN = "DE89370400440532013000"
SUPPLIER_IBAN = "GB82WEST12345698765432"


def words_of(page):
    return {
        "version": 2,
        "ocr": "none",
        "pages": [{"width": 595.0, "height": 842.0, "rotation": 0}],
        "text": page.text,
        "words": page.words,
    }


class FieldValueCase(DerivativeCase):
    """Files with a word list from made-up pages, and fields of the tests only."""

    def setUp(self):
        super().setUp()
        # Files are read by internal users; the test users of DerivativeCase are not.
        self.writer.group_ids = [(4, self.env.ref("base.group_user").id)]
        Field = self.env["int_filemanager.extraction_field"].sudo()
        # The starting set is left out, so that each test knows every field.
        Field.search([]).active = False
        self.invoice = Field.create(
            {"name": "T Invoice number", "value_type": "number"}
        )
        self.iban = Field.create({"name": "T IBAN", "value_type": "iban"})
        Rule = self.env["int_filemanager.extraction_rule"].sudo()
        Rule.create({"field_id": self.invoice.id, "keywords": "Rechnungsnummer"})
        Rule.create({"field_id": self.iban.id, "keywords": "IBAN"})
        self.Node = self.env["int_filemanager.node"]

    def _pdf(self, name, page):
        node = self._file(name, b"%PDF-1.4 " + name.encode())
        data = json.dumps(words_of(page)).encode()
        self._run(
            FakeConverter(
                by_kind={"words": lambda sha256: text_result(data, "application/json")}
            )
        )
        return node

    def _suggest(self, node, user=None):
        return self.Node.with_user(user or self.writer).suggest_field_values(node.id)

    def _best(self, result, field):
        entry = next(f for f in result["fields"] if f["field_id"] == field.id)
        return entry["suggestions"][0] if entry["suggestions"] else None


@tagged("post_install", "-at_install")
class TestV2FieldValueSuggest(FieldValueCase):
    def test_suggestions_from_the_word_list(self):
        page = layout(
            (100, [(50, "Rechnungsnummer"), (200, "R-2024-001")]),
            (112, [(50, "IBAN: GB82 WEST 1234 5698 7654 32")]),
        )
        node = self._pdf("rechnung.pdf", page)
        result = self._suggest(node)
        self.assertEqual(result["state"], "ready")
        self.assertEqual(result["revision_id"], node.current_revision_id.id)
        best = self._best(result, self.invoice)
        self.assertEqual(best["value"]["value_text"], "R-2024-001")
        self.assertEqual((best["page"], best["x0"], best["top"]), (1, 200, 100))
        self.assertEqual(best["direction"], "left")
        self.assertEqual(
            self._best(result, self.iban)["value"]["value_text"], SUPPLIER_IBAN
        )
        self.assertFalse(
            next(f for f in result["fields"] if f["field_id"] == self.invoice.id)[
                "confirmed"
            ]
        )

    def test_nothing_is_stored(self):
        node = self._pdf("rechnung.pdf", layout((100, [(50, "Rechnungsnummer 4711")])))
        self._suggest(node)
        self.assertFalse(node.field_value_ids)

    def test_pending_until_the_text_is_read(self):
        node = self._file("neu.pdf", b"%PDF-1.4 new")
        self.assertEqual(self._suggest(node)["state"], "pending")
        self.Derivative._enqueue_missing()
        self.assertEqual(self._suggest(node)["state"], "pending")

    def test_no_text_for_a_picture(self):
        from .test_v2_derivative import JPEG

        node = self._file("foto.jpg", JPEG)
        self._run()
        self.assertEqual(self._suggest(node)["state"], "none")

    def test_text_of_a_text_file(self):
        node = self._file("notiz.txt", b"Rechnungsnummer: 4711")
        self._run(
            FakeConverter(
                by_kind={"text": lambda sha256: text_result(b"Rechnungsnummer: 4711")}
            )
        )
        best = self._best(self._suggest(node), self.invoice)
        self.assertEqual(best["value"]["value_text"], "4711")
        self.assertEqual(best["page"], 0)

    def test_only_who_may_read_the_file(self):
        node = self._pdf("rechnung.pdf", layout((100, [(50, "Rechnungsnummer 4711")])))
        with self.assertRaises(AccessError):
            self._suggest(node, self.outsider)

    def test_own_company_is_left_out_and_the_sender_found(self):
        company_partner = self.env.company.partner_id
        Bank = self.env["res.partner.bank"].sudo()
        Bank.create({"acc_number": OWN_IBAN, "partner_id": company_partner.id})
        supplier = (
            self.env["res.partner"]
            .sudo()
            .create({"name": "Supplier of tests", "is_company": True})
        )
        Bank.create({"acc_number": SUPPLIER_IBAN, "partner_id": supplier.id})
        page = layout(
            (100, [(50, "IBAN: DE89 3704 0044 0532 0130 00")]),
            (112, [(50, "IBAN: GB82 WEST 1234 5698 7654 32")]),
        )
        result = self._suggest(self._pdf("rechnung.pdf", page))
        suggested = next(f for f in result["fields"] if f["field_id"] == self.iban.id)
        self.assertEqual(
            [s["value"]["value_text"] for s in suggested["suggestions"]],
            [SUPPLIER_IBAN],
        )
        self.assertEqual(result["partner"]["id"], supplier.id)
        self.assertEqual(result["partner"]["via"], "iban")

    def test_sender_by_name_and_tags(self):
        supplier = (
            self.env["res.partner"]
            .sudo()
            .create({"name": "Muster Energie GmbH", "is_company": True})
        )
        tag = self.env["int_filemanager.tag"].sudo().create({"name": "Strom"})
        self.env["int_filemanager.tag"].sudo().create({"name": "Stromausfall"})
        page = layout((100, [(50, "Muster Energie GmbH Ihre Rechnung Strom 2024")]))
        result = self._suggest(self._pdf("brief.pdf", page))
        self.assertEqual(
            (result["partner"]["id"], result["partner"]["via"]), (supplier.id, "name")
        )
        self.assertEqual([t["id"] for t in result["tags"]], [tag.id])

    def test_a_confirmed_value_is_shown(self):
        node = self._pdf("rechnung.pdf", layout((100, [(50, "Rechnungsnummer 4711")])))
        self.env["int_filemanager.field_value"].create(
            {"node_id": node.id, "field_id": self.invoice.id, "value_text": "4711"}
        )
        entry = next(
            f for f in self._suggest(node)["fields"] if f["field_id"] == self.invoice.id
        )
        self.assertEqual(entry["confirmed"], "4711")

    def test_a_slow_rule_is_logged(self):
        self.env["int_filemanager.extraction_rule"].sudo().create(
            {
                "field_id": self.invoice.id,
                "mode": "regex",
                "pattern": r"Nr\. (\d+)",
                "group_index": 1,
            }
        )
        node = self._pdf("rechnung.pdf", layout((100, [(50, "Nr. 4711")])))
        with (
            patch.object(value_suggest, "SLOW_PATTERN_SECONDS", -1),
            self.assertLogs(
                "odoo.addons.int_filemanager.models.int_filemanager_node"
            ) as logs,
        ):
            self._suggest(node)
        self.assertIn("took", logs.output[0])

    # -- found when reviewed ------------------------------------------------

    def _hide_from_writer(self, partner):
        """A record rule hiding one contact from the writer, like a company rule."""
        group = self.env["res.groups"].sudo().create({"name": "Partner hidden"})
        self.writer.group_ids = [(4, group.id)]
        self.env["ir.rule"].sudo().create(
            {
                "name": "hide one contact",
                "model_id": self.env.ref("base.model_res_partner").id,
                "groups": [(4, group.id)],
                "domain_force": f"[('id', '!=', {partner.id})]",
            }
        )

    def test_a_company_the_user_may_not_read_is_not_suggested(self):
        Partner = self.env["res.partner"].sudo()
        company = Partner.create({"name": "Hidden Parent GmbH", "is_company": True})
        contact = Partner.create({"name": "Visible Contact", "parent_id": company.id})
        self.env["res.partner.bank"].sudo().create(
            {"acc_number": SUPPLIER_IBAN, "partner_id": contact.id}
        )
        self._hide_from_writer(company)
        page = layout(
            (100, [(50, "Hidden Parent GmbH")]),
            (112, [(50, "IBAN: GB82 WEST 1234 5698 7654 32")]),
        )
        self.assertFalse(self._suggest(self._pdf("brief.pdf", page))["partner"])

    def test_vat_stored_without_country_and_mail_of_the_same_domain(self):
        Partner = self.env["res.partner"].sudo()
        by_vat = Partner.create(
            {"name": "Vat Only", "is_company": True, "vat": "136695976"}
        )
        page = layout((100, [(50, "USt-IdNr.: DE136695976")]))
        result = self._suggest(self._pdf("a.pdf", page))
        self.assertEqual(
            (result["partner"]["id"], result["partner"]["via"]), (by_vat.id, "vat")
        )
        by_site = Partner.create(
            {
                "name": "Site Only",
                "is_company": True,
                "website": "https://www.vendor-t.de",
            }
        )
        page = layout((100, [(50, "Fragen an billing@vendor-t.de")]))
        result = self._suggest(self._pdf("b.pdf", page))
        self.assertEqual(
            (result["partner"]["id"], result["partner"]["via"]), (by_site.id, "email")
        )

    def test_phrases_and_the_limit_of_tags(self):
        Tag = self.env["int_filemanager.tag"].sudo()
        phrase = Tag.create({"name": "Strom Vertrag"})
        Tag.create({"name": "Vertrag Strom"})
        for i in range(12):
            Tag.create({"name": f"Wort{i}"})
        words = " ".join(f"Wort{i}" for i in range(12))
        page = layout((100, [(50, f"Ihr Strom Vertrag {words}")]))
        tags = self._suggest(self._pdf("c.pdf", page))["tags"]
        self.assertEqual(len(tags), 10)
        self.assertIn(phrase.id, [t["id"] for t in tags])
        self.assertNotIn("Vertrag Strom", [t["name"] for t in tags])

    def test_a_broken_word_list_gives_no_suggestions_instead_of_an_error(self):
        node = self._file("kaputt.pdf", b"%PDF-1.4 broken")
        data = json.dumps({"version": 2, "words": []}).encode()
        self._run(
            FakeConverter(
                by_kind={"words": lambda sha256: text_result(data, "application/json")}
            )
        )
        self.assertEqual(self._suggest(node)["state"], "none")
