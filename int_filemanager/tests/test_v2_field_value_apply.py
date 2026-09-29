"""apply_field_values: confirmed values are checked again, stored per field, noted
on the file, and teach the sender's labels to the next suggestion."""

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged

from .test_v2_field_value_suggest import FieldValueCase
from .test_v2_value_suggest import layout


@tagged("post_install", "-at_install")
class TestV2FieldValueApply(FieldValueCase):
    def setUp(self):
        super().setUp()
        Field = self.env["int_filemanager.extraction_field"].sudo()
        eur = self.env.ref("base.EUR")
        eur.active = True
        self.due = Field.create({"name": "T Due date", "value_type": "date"})
        self.total = Field.create(
            {"name": "T Total", "value_type": "amount", "currency_id": eur.id}
        )
        self.customer = Field.create({"name": "T Customer", "value_type": "number"})
        Rule = self.env["int_filemanager.extraction_rule"].sudo()
        self.due_rule = Rule.create({"field_id": self.due.id, "keywords": "Fällig am"})
        Rule.create({"field_id": self.customer.id, "keywords": "Kundennummer"})
        self.sender = (
            self.env["res.partner"]
            .sudo()
            .create({"name": "Stadtwerke Test", "is_company": True})
        )
        self.page = layout(
            (100, [(50, "Rechnungsnummer"), (200, "R-2024-001")]),
            (112, [(50, "Fällig am"), (200, "15.02.2024")]),
            (124, [(50, "Vertragskonto"), (200, "4711 0815")]),
        )
        self.node = self._pdf("rechnung.pdf", self.page)
        self.revision = self.node.current_revision_id

    def _apply(self, values, user=None, **kwargs):
        return self.Node.with_user(user or self.writer).apply_field_values(
            self.node.id, self.revision.id, values, **kwargs
        )

    def _value(self, field):
        return self.node.field_value_ids.filtered(lambda v: v.field_id == field)

    def test_an_accepted_suggestion_is_read_again_and_stored(self):
        start = self.page.text.index("15.02.2024")
        result = self._apply(
            [
                {
                    "field_id": self.due.id,
                    "text": "15.02.2024",
                    "source": "rule",
                    "rule_id": self.due_rule.id,
                    "start": start,
                }
            ]
        )
        self.assertEqual(result, {self.due.id: "2024-02-15"})
        value = self._value(self.due)
        self.assertEqual(str(value.value_date), "2024-02-15")
        self.assertEqual((value.source, value.rule_id), ("rule", self.due_rule))
        self.assertEqual(value.revision_id, self.revision)
        self.assertEqual((value.page, value.x0, value.top), (1, 200, 112))

    def test_a_text_that_is_no_value_of_the_type_is_refused(self):
        with self.assertRaises(UserError):
            self._apply([{"field_id": self.due.id, "text": "31.02.2024"}])
        self.assertFalse(self.node.field_value_ids)

    def test_typed_values_without_unit_or_currency(self):
        self._apply([{"field_id": self.total.id, "text": "231,60", "source": "manual"}])
        value = self._value(self.total)
        self.assertEqual((value.value_number, value.currency_id.name), (231.6, "EUR"))
        self.assertEqual(value.source, "manual")
        self._apply([{"field_id": self.total.id, "text": "231"}])
        self.assertEqual(self._value(self.total).value_number, 231.0)

    def test_only_the_fields_sent_are_replaced_and_an_empty_text_removes(self):
        self._apply(
            [
                {"field_id": self.due.id, "text": "15.02.2024"},
                {"field_id": self.invoice.id, "text": "R-2024-001"},
            ]
        )
        self._apply([{"field_id": self.due.id, "text": "16.02.2024"}])
        self.assertEqual(self._value(self.invoice).value_text, "R-2024-001")
        self.assertEqual(self._value(self.due).value_text, "2024-02-16")
        self._apply([{"field_id": self.invoice.id, "text": ""}])
        self.assertFalse(self._value(self.invoice))
        self.assertTrue(self._value(self.due))

    def test_values_of_an_old_revision_are_not_stored(self):
        self.Node.with_user(self.writer).create_new_revision(
            self.node.id, self.revision.id, b"%PDF-1.4 changed", "op-apply-new"
        )
        with self.assertRaises(UserError):
            self._apply([{"field_id": self.due.id, "text": "15.02.2024"}])
        self.assertFalse(self.node.field_value_ids)

    def test_reading_is_not_enough(self):
        group = self.env["res.groups"].sudo().create({"name": "Apply readers"})
        self.node.scope_id.sudo().read_group_ids = [(4, group.id)]
        reader = self.env["res.users"].sudo().create(
            {
                "name": "Apply reader",
                "login": "apply_reader",
                "group_ids": [
                    (6, 0, [group.id, self.env.ref("base.group_user").id,
                            self.env.ref("int_filemanager.group_filemanager_user").id])
                ],
            }
        )  # fmt: skip
        with self.assertRaises(AccessError):
            self._apply([{"field_id": self.due.id, "text": "15.02.2024"}], reader)
        with self.assertRaises(AccessError):
            self._apply(
                [{"field_id": self.due.id, "text": "15.02.2024"}], self.outsider
            )
        self.assertFalse(self.node.field_value_ids)

    def test_sender_tags_and_a_note_on_the_file(self):
        tag = self.env["int_filemanager.tag"].sudo().create({"name": "Strom"})
        self._apply(
            [{"field_id": self.due.id, "text": "15.02.2024"}],
            partner_id=self.sender.id,
            tag_ids=[tag.id],
        )
        self.assertEqual(self.node.partner_id, self.sender)
        self.assertIn(tag, self.node.tag_ids)
        note = self.node.message_ids[0]
        self.assertIn("T Due date", note.body)
        self.assertIn("2024-02-15", note.body)
        self.assertEqual(note.author_id, self.writer.partner_id)

    def test_the_sender_s_label_is_learned_and_used_next_time(self):
        # "Vertragskonto" is no keyword of the customer number: typed by hand, then
        # learned from the label next to the value.
        self.assertFalse(self._best(self._suggest(self.node), self.customer))
        self._apply(
            [{"field_id": self.customer.id, "text": "4711 0815"}],
            partner_id=self.sender.id,
        )
        hint = (
            self.env["int_filemanager.extraction_hint"]
            .sudo()
            .search([("partner_id", "=", self.sender.id)])
        )
        self.assertEqual((hint.label, hint.field_id), ("vertragskonto", self.customer))
        self.assertEqual(hint.direction, "left")
        other = self._pdf(
            "zweite.pdf", layout((100, [(50, "Ihr Vertragskonto"), (200, "5555 1234")]))
        )
        other.partner_id = self.sender
        best = self._best(self._suggest(other), self.customer)
        self.assertEqual(best["value"]["value_text"], "55551234")
        self.assertEqual((best["tier"], best["hint_id"]), (0, hint.id))

    def test_users_cannot_read_the_learned_labels(self):
        self._apply(
            [{"field_id": self.customer.id, "text": "4711 0815"}],
            partner_id=self.sender.id,
        )
        with self.assertRaises(AccessError):
            self.env["int_filemanager.extraction_hint"].with_user(self.writer).search(
                []
            )

    def test_the_last_confirmation_wins(self):
        self._apply(
            [{"field_id": self.customer.id, "text": "4711 0815"}],
            partner_id=self.sender.id,
        )
        self._apply(
            [{"field_id": self.invoice.id, "text": "4711 0815"}],
            partner_id=self.sender.id,
        )
        hint = (
            self.env["int_filemanager.extraction_hint"]
            .sudo()
            .search(
                [("partner_id", "=", self.sender.id), ("label", "=", "vertragskonto")]
            )
        )
        self.assertEqual((hint.field_id, hint.hit_count), (self.invoice, 1))

    def test_nothing_is_learned_for_the_own_company(self):
        self._apply(
            [{"field_id": self.customer.id, "text": "4711 0815"}],
            partner_id=self.env.company.partner_id.id,
        )
        self.assertFalse(
            self.env["int_filemanager.extraction_hint"].sudo().search_count([])
        )
