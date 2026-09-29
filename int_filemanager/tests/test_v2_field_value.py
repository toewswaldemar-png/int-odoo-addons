"""Data model of value recognition: fields, rules and confirmed values.

Values follow the rights of their node (read along the node's scope, no direct
write for anyone); fields and rules are read by every user and changed by
administrators only.
"""

import re

import psycopg2

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestV2FieldValue(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_group = cls.env.ref("int_filemanager.group_filemanager_user")
        cls.internal_group = cls.env.ref("base.group_user")
        cls.admin_group = cls.env.ref("int_filemanager.group_filemanager_admin")
        cls.reader_group = cls.env["res.groups"].create({"name": "FV Reader"})
        cls.scope = cls.env["int_filemanager.scope"].create(
            {"name": "FV Scope", "read_group_ids": [(4, cls.reader_group.id)]}
        )
        cls.node = cls.env["int_filemanager.node"].create(
            {"name": "invoice.pdf", "scope_id": cls.scope.id}
        )
        cls.field = cls.env["int_filemanager.extraction_field"].create(
            {"name": "FV Invoice number", "value_type": "number"}
        )
        cls.reader = cls._make_user("fv_reader", [cls.reader_group])
        cls.outsider = cls._make_user("fv_outsider", [])
        cls.manager = cls._make_user("fv_manager", [cls.admin_group])

    @classmethod
    def _make_user(cls, login, groups):
        return cls.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "group_ids": [
                    (
                        6,
                        0,
                        [g.id for g in groups]
                        + (cls.user_group | cls.internal_group).ids,
                    )
                ],
            }
        )

    def _make_value(self, field=None, **vals):
        return self.env["int_filemanager.field_value"].create(
            {
                "node_id": self.node.id,
                "field_id": (field or self.field).id,
                "value_text": "R-2024-001",
                **vals,
            }
        )

    # -- rights on values ---------------------------------------------------

    def test_value_follows_node_scope(self):
        value = self._make_value()
        values = self.env["int_filemanager.field_value"]
        self.assertFalse(
            values.with_user(self.outsider).search([("id", "=", value.id)])
        )
        self.assertEqual(
            values.with_user(self.reader).search([("id", "=", value.id)]), value
        )
        # Through the node too: that is how "files with invoice number X" is searched.
        self.assertFalse(
            self.env["int_filemanager.node"]
            .with_user(self.outsider)
            .search([("field_value_ids.value_text", "=", "R-2024-001")])
        )

    def test_nobody_writes_values_through_the_orm(self):
        """Values change only through the node's checked methods (N1)."""
        value = self._make_value()
        for user in (self.reader, self.manager):
            values = self.env["int_filemanager.field_value"].with_user(user)
            with self.assertRaises(AccessError):
                values.create(
                    {
                        "node_id": self.node.id,
                        "field_id": self.field.id,
                        "value_text": "x",
                    }
                )
            with self.assertRaises(AccessError):
                values.browse(value.id).write({"value_text": "forged"})
            with self.assertRaises(AccessError):
                values.browse(value.id).unlink()

    # -- rights on fields and rules ------------------------------------------

    def test_fields_and_rules_readable_by_users_changed_by_managers(self):
        fields_ = self.env["int_filemanager.extraction_field"]
        self.assertTrue(
            fields_.with_user(self.outsider).search([("id", "=", self.field.id)])
        )
        with self.assertRaises(AccessError):
            fields_.with_user(self.reader).create(
                {"name": "Mine", "value_type": "word"}
            )
        with self.assertRaises(AccessError):
            self.env["int_filemanager.extraction_rule"].with_user(self.reader).create(
                {"field_id": self.field.id, "keywords": "Nr."}
            )
        field = fields_.with_user(self.manager).create(
            {"name": "Order", "value_type": "number"}
        )
        rule = (
            self.env["int_filemanager.extraction_rule"]
            .with_user(self.manager)
            .create({"field_id": field.id, "keywords": "Bestellnummer\nBestell-Nr."})
        )
        self.assertEqual(rule._keyword_list(), ["Bestellnummer", "Bestell-Nr."])

    # -- consistency ----------------------------------------------------------

    def test_one_value_per_field_and_node(self):
        self._make_value()
        with mute_logger("odoo.sql_db"), self.assertRaises(psycopg2.IntegrityError):
            with self.env.cr.savepoint():
                self._make_value(value_text="other")

    def test_value_is_removed_with_its_node(self):
        value = self._make_value()
        self.node.unlink()
        self.assertFalse(value.exists())

    def test_field_with_values_can_be_archived_not_deleted(self):
        self._make_value()
        with mute_logger("odoo.sql_db"), self.assertRaises(psycopg2.IntegrityError):
            with self.env.cr.savepoint():
                self.field.unlink()
        self.field.active = False
        self.assertFalse(self.field.active)

    def test_type_cannot_change_once_values_exist(self):
        empty = self.env["int_filemanager.extraction_field"].create(
            {"name": "FV Empty", "value_type": "number"}
        )
        empty.value_type = "word"
        self._make_value()
        with self.assertRaises(UserError):
            self.field.value_type = "word"

    def test_field_names_are_unique_ignoring_case(self):
        fields_ = self.env["int_filemanager.extraction_field"]
        with self.assertRaises(ValidationError):
            fields_.create({"name": "fv invoice NUMBER", "value_type": "number"})
        # "_" is a wildcard for ilike and must not make a different name clash.
        fields_.create({"name": "FV_Invoice number", "value_type": "number"})

    def test_quantity_needs_unit(self):
        with self.assertRaises(ValidationError):
            self.env["int_filemanager.extraction_field"].create(
                {"name": "FV Consumption", "value_type": "quantity"}
            )

    def test_typed_column_must_fit_the_type(self):
        make = self.env["int_filemanager.extraction_field"].create
        date_field = make({"name": "FV Date", "value_type": "date"})
        period_field = make({"name": "FV Period", "value_type": "period"})
        amount_field = make({"name": "FV Amount", "value_type": "amount"})
        with self.assertRaises(ValidationError):
            self._make_value(date_field, value_text="01.02.2024")
        self._make_value(date_field, value_text="2024-02-01", value_date="2024-02-01")
        # A period is either two dates or a length with a unit.
        with self.assertRaises(ValidationError):
            self._make_value(period_field, value_text="x", value_date="2024-02-01")
        with self.assertRaises(ValidationError):
            self._make_value(
                period_field,
                value_text="x",
                value_date="2024-02-01",
                value_date_to="2024-01-01",
            )
        self._make_value(
            period_field, value_text="12 months", value_number=12, unit="months"
        )
        with self.assertRaises(ValidationError):
            self._make_value(amount_field, value_text="12.50", value_number=12.5)
        # No column beyond those of the type.
        eur = self.env.ref("base.EUR")
        with self.assertRaises(ValidationError):
            self._make_value(value_date="2024-02-01")
        with self.assertRaises(ValidationError):
            self._make_value(
                amount_field,
                value_text="12.50",
                value_number=12.5,
                currency_id=eur.id,
                unit="months",
            )
        self._make_value(
            amount_field, value_text="12.50", value_number=12.5, currency_id=eur.id
        )

    def test_revision_and_rule_must_belong_to_the_value(self):
        other = self.env["int_filemanager.node"].create(
            {"name": "other.pdf", "scope_id": self.scope.id}
        )
        blob = self.env["int_filemanager.blob"].create({"sha256": "f" * 64, "size": 0})
        foreign_revision = self.env["int_filemanager.revision"].create(
            {
                "node_id": other.id,
                "blob_id": blob.id,
                "revision_no": 1,
                "origin": "upload",
            }
        )
        with self.assertRaises(ValidationError):
            self._make_value(revision_id=foreign_revision.id)
        foreign_rule = self.env.ref("int_filemanager.extraction_rule_iban")
        with self.assertRaises(ValidationError):
            self._make_value(rule_id=foreign_rule.id, source="rule")
        own_rule = self.env["int_filemanager.extraction_rule"].create(
            {"field_id": self.field.id, "keywords": "Nr."}
        )
        self._make_value(rule_id=own_rule.id, source="rule")

    def test_rule_is_checked_when_saved(self):
        rules = self.env["int_filemanager.extraction_rule"]
        with self.assertRaises(ValidationError):
            rules.create({"field_id": self.field.id, "keywords": " \n  "})
        with self.assertRaises(ValidationError):
            rules.create(
                {"field_id": self.field.id, "mode": "regex", "pattern": "(unclosed"}
            )
        with self.assertRaises(ValidationError):
            rules.create(
                {
                    "field_id": self.field.id,
                    "mode": "regex",
                    "pattern": r"Nr\. (\d+)",
                    "group_index": 2,
                }
            )
        rule = rules.create(
            {
                "field_id": self.field.id,
                "mode": "regex",
                "pattern": r"Nr\. (\d+)",
                "group_index": 1,
            }
        )
        self.assertEqual(rule.group_index, 1)

    # -- starting set -----------------------------------------------------------

    def test_starting_set_is_complete(self):
        seeded = self.env["int_filemanager.extraction_field"].search(
            [
                (
                    "id",
                    "in",
                    [
                        self.env.ref(f"int_filemanager.extraction_field_{key}").id
                        for key in (
                            "invoice_number",
                            "total_amount",
                            "energy_price",
                            "price_guarantee",
                            "iban",
                            "vat",
                            "email",
                        )
                    ],
                )
            ]
        )
        self.assertEqual(len(seeded), 7)
        for field in seeded:
            self.assertTrue(field.rule_ids, field.name)
        amount = self.env.ref("int_filemanager.extraction_field_total_amount")
        self.assertEqual(amount.currency_id, self.env.ref("base.EUR"))
        # The mail rule also takes an address OCR split at the @.
        mail = self.env.ref("int_filemanager.extraction_rule_email")
        found = re.findall(mail.pattern, "an max @example.de oder info@example.de")
        self.assertEqual(found, ["max @example.de", "info@example.de"])
        rule = self.env.ref("int_filemanager.extraction_rule_customer_number")
        self.assertIn("Geschäftspartnernummer", rule._keyword_list())
