"""Reading typed values out of document text: tables of printed text and the
value it must give (or None when it must not give one).

The cases come from real scanned and digital documents: OCR errors, numbers
printed in groups, units before or after the number, IBANs followed by the BIC.
"""

from datetime import date

from odoo.tests.common import BaseCase, tagged

from .. import value_types

TODAY = date(2026, 9, 29)


def first(value_type, text, pos=0, **options):
    options.setdefault("today", TODAY)
    for candidate in value_types.find(value_type, text, pos, **options):
        return candidate
    return None


@tagged("post_install", "-at_install")
class TestV2ValueTypes(BaseCase):
    def check(self, value_type, cases, **options):
        for text, expected in cases:
            with self.subTest(text=text):
                candidate = first(value_type, text, **options)
                got = candidate and candidate.value
                if expected is None:
                    self.assertIsNone(got)
                else:
                    self.assertIsNotNone(got)
                    self.assertEqual({k: got.get(k) for k in expected}, expected)

    def test_parse_number(self):
        for text, expected in [
            ("1.234,56", 1234.56),
            ("1,234.56", 1234.56),
            ("1234,5", 1234.5),
            ("12.50", 12.5),
            ("3.000", 3000),
            ("1.234.567", 1234567),
            ("1,234,567", 1234567),
            ("1'234.50", 1234.5),
            ("1\u00a0234,56", 1234.56),
            ("-12,50", -12.5),
            ("12,50-", -12.5),
            ("1.234.56", None),
            ("12.34.567", None),
            ("1234.567,8", None),
            ("12,", None),
        ]:
            with self.subTest(text=text):
                self.assertEqual(value_types.parse_number(text), expected)

    def test_number(self):
        self.check(
            "number",
            [
                ("R-2024-001.", {"value_text": "R-2024-001"}),
                ("4711/2 vom", {"value_text": "4711/2"}),
                # Printed in groups; stored without the spaces.
                ("836 585 797 780", {"value_text": "836585797780"}),
                ("44 450 7-5 148 621", {"value_text": "444507-5148621"}),
                # A label's next word is no number without a digit.
                ("an.", None),
                ("29.01.2019", None),
                ("2019-01-29", None),
                ("Kunde", None),
                # A value never crosses a column or line break.
                ("4711\t12", {"value_text": "4711"}),
            ],
        )

    def test_number_right_after_a_label(self):
        # "Nr.4711" is one token; searched from the end of the label it is the number.
        self.assertEqual(first("number", "Nr.4711").value["value_text"], "Nr.4711")
        self.assertEqual(first("number", "Nr.4711", 3).value["value_text"], "4711")

    def test_a_word_value_may_start_at_every_word(self):
        found = [
            c.value["value_text"] for c in value_types.find("word", "Herrn Max Muster")
        ]
        self.assertEqual(found, ["Herrn Max Muster", "Max Muster", "Muster"])

    def test_word(self):
        self.check(
            "word",
            [
                (
                    "Ökostrom Plus 24\tFälligkeitstag",
                    {"value_text": "Ökostrom Plus 24"},
                ),
                ("Basis.", {"value_text": "Basis"}),
                ("12345", None),
            ],
        )

    def test_date(self):
        self.check(
            "date",
            [
                ("01.02.24", {"value_date": date(2024, 2, 1)}),
                ("1.2.2024", {"value_date": date(2024, 2, 1)}),
                ("01/02/2024", {"value_date": date(2024, 2, 1)}),
                ("2024-02-01", {"value_date": date(2024, 2, 1)}),
                ("1. Februar 2024", {"value_date": date(2024, 2, 1)}),
                ("01. Feb. 2024", {"value_date": date(2024, 2, 1)}),
                ("3. März 2025", {"value_date": date(2025, 3, 3)}),
                ("3 mar 2025", {"value_date": date(2025, 3, 3)}),
                ("1 June 2024", {"value_date": date(2024, 6, 1)}),
                ("am 15.01.2025.", {"value_text": "2025-01-15"}),
                # Two-digit years far ahead are the last century.
                ("01.02.60", {"value_date": date(1960, 2, 1)}),
                # Not a date, or not a plausible one.
                ("31.02.2024", None),
                ("01.02.1850", None),
                ("01.02.2099", None),
                ("27.0'1 .2025", None),
                ("01.02-2024", None),
                ("Version 1.2.3", None),
            ],
        )

    def test_period(self):
        self.check(
            "period",
            [
                (
                    "01.01.2024 - 31.12.2024",
                    {
                        "value_date": date(2024, 1, 1),
                        "value_date_to": date(2024, 12, 31),
                    },
                ),
                (
                    "01.01.2024 bis zum 31.12.2024",
                    {
                        "value_date": date(2024, 1, 1),
                        "value_date_to": date(2024, 12, 31),
                    },
                ),
                # The first date takes its year from the second.
                (
                    "01.01. - 31.12.2024",
                    {
                        "value_date": date(2024, 1, 1),
                        "value_date_to": date(2024, 12, 31),
                    },
                ),
                (
                    "01.12.–28.02.2025",
                    {
                        "value_date": date(2024, 12, 1),
                        "value_date_to": date(2025, 2, 28),
                    },
                ),
                (
                    "12 Monate ab Lieferbeginn",
                    {"value_number": 12.0, "unit": "months", "value_text": "12 months"},
                ),
                ("4 Wochen", {"value_number": 4.0, "unit": "weeks"}),
                ("1 Jahr", {"value_number": 1.0, "unit": "years"}),
                ("31.12.2024 bis 01.01.2024", None),
                ("12 Monatsraten", None),
            ],
        )

    def test_amount(self):
        self.check(
            "amount",
            [
                ("1.234,56 €", {"value_number": 1234.56, "currency_code": "EUR"}),
                ("1,234.56 EUR", {"value_number": 1234.56}),
                ("€12,50", {"value_number": 12.5, "value_text": "12.50 EUR"}),
                ("1234,5 €", {"value_number": 1234.5}),
                ("1.234 €", {"value_number": 1234.0}),
                # A bare number counts only with cents; the default currency applies.
                ("231,60", {"value_number": 231.6, "currency_code": "EUR"}),
                ("1234,5", None),
                ("2024", None),
                # Unit before the number, or a per-month suffix after the currency.
                ("EUR/Monat 10,90", {"value_number": 10.9}),
                ("13,40 €/Monat", {"value_number": 13.4}),
                # Credits: a leading or trailing minus.
                ("-12,50 €", {"value_number": -12.5}),
                ("12,50- Gutschrift", {"value_number": -12.5}),
                # OCR garbage does not give a value.
                ("152/0 €", None),
                # A position number is not merged into the amount.
                ("Pos. 3 250,00", {"value_number": 250.0}),
            ],
        )

    def test_amount_currency_from_the_database(self):
        self.check(
            "amount",
            [
                ("$ 12.50", {"value_number": 12.5, "currency_code": "USD"}),
                ("12,50 CHF", {"currency_code": "CHF"}),
                ("12,50", {"currency_code": "CHF"}),
            ],
            currencies={"$": "USD", "USD": "USD", "CHF": "CHF", "€": "EUR"},
            default_currency="CHF",
        )

    def test_quantity(self):
        self.check(
            "quantity",
            [
                ("3.000 kWh", {"value_number": 3000.0, "unit": "kWh"}),
                ("3000kWh", {"value_number": 3000.0}),
                ("kWh 12.345", {"value_number": 12345.0}),
                ("13,40 ct/kWh", None),
                ("2.500", None),
            ],
            unit="kWh",
        )
        self.check(
            "quantity",
            [
                ("28,53 ct/kWh", {"value_number": 28.53, "value_text": "28.53 ct/kWh"}),
                ("Cent/kWh 28,5", {"value_number": 28.5}),
                ("28,5 Ct / kWh", {"value_number": 28.5}),
                ("28,5 kWh", None),
            ],
            unit="ct/kWh",
        )

    def test_iban(self):
        iban = "DE89370400440532013000"
        self.check(
            "iban",
            [
                ("DE89 3704 0044 0532 0130 00", {"value_text": iban}),
                (iban, {"value_text": iban}),
                # Some letterheads put a space after the country code.
                ("DE 89 3704 0044 0532 0130 00", {"value_text": iban}),
                # OCR read a letter where the format demands a digit.
                ("DE89 37O4 0044 0532 0130 00", {"value_text": iban}),
                ("DE89 3704 0044 O532 Ol30 00", {"value_text": iban}),
                # The BIC after it is cut off.
                ("DE89 3704 0044 0532 0130 00 BIC COBADEFFXXX", {"value_text": iban}),
                # Letters that belong there stay letters.
                ("NL91 ABNA 0417 1643 00", {"value_text": "NL91ABNA0417164300"}),
                # Wrong check digits, masked, or a creditor identifier.
                ("DE89 3704 0044 0532 0130 01", None),
                ("DE** 5625 **** **** **** 12", None),
                ("DE98ZZZ09999999999", None),
            ],
        )

    def test_iban_is_cut_where_it_ends(self):
        text = "IBAN: DE89 3704 0044 0532 0130 00 BIC COBADEFFXXX"
        candidate = first("iban", text)
        self.assertEqual(candidate.source_text, "DE89 3704 0044 0532 0130 00")

    def test_vat(self):
        self.check(
            "vat",
            [
                ("DE136695976", {"value_text": "DE136695976"}),
                ("DE 136 695 976", {"value_text": "DE136695976"}),
                # Without country prefix the default country applies.
                ("136695976", {"value_text": "DE136695976"}),
                ("DE l36695976", {"value_text": "DE136695976"}),
                ("ATU13585627", {"value_text": "ATU13585627"}),
                ("DE136695976 HRB 1234", {"value_text": "DE136695976"}),
                ("DE136695977", None),
                ("RECHNUNG", None),
            ],
        )

    def test_email(self):
        self.check(
            "email",
            [
                ("max.muster@example.de", {"value_text": "max.muster@example.de"}),
                ("Max.Muster @Example.DE", {"value_text": "max.muster@example.de"}),
                ("Mail an: info@firma-x.de.", {"value_text": "info@firma-x.de"}),
                ("info at firma.de", None),
            ],
        )

    def test_candidates_come_left_to_right_within_the_range(self):
        text = "Datum 01.02.2024\tFällig 15.02.2024\nLieferung 03.02.2024"
        found = list(value_types.find("date", text, today=TODAY))
        self.assertEqual(
            [c.value["value_date"] for c in found],
            [date(2024, 2, 1), date(2024, 2, 15), date(2024, 2, 3)],
        )
        self.assertEqual(text[found[1].start : found[1].end], "15.02.2024")
        start = text.index("Fällig")
        found = list(
            value_types.find("date", text, start, text.index("\n"), today=TODAY)
        )
        self.assertEqual([c.value["value_date"] for c in found], [date(2024, 2, 15)])

    def test_parse_takes_only_a_whole_value(self):
        parse = value_types.parse
        self.assertEqual(
            parse("amount", " 1.234,56  € ", today=TODAY)["value_number"], 1234.56
        )
        self.assertIsNone(parse("amount", "ca. 1.234,56 €", today=TODAY))
        self.assertEqual(
            parse("iban", "DE89 3704 0044 0532 0130 00")["value_text"],
            "DE89370400440532013000",
        )
        self.assertIsNone(parse("iban", "DE89 3704 0044 0532 0130 00 BIC"))
        self.assertIsNone(parse("date", "31.02.2024", today=TODAY))
        with self.assertRaises(ValueError):
            parse("quantity", "3000 kWh")

    # -- found when reviewed ------------------------------------------------

    def test_window_never_cuts_a_value_short(self):
        found = list(value_types.find("number", "12345", 0, 3))
        self.assertEqual([c.value["value_text"] for c in found], ["12345"])
        found = list(value_types.find("date", "01.02.20245 x", 0, 10, today=TODAY))
        self.assertEqual(found, [])
        # Only values that start inside the window.
        self.assertEqual(list(value_types.find("number", "ab 12 34x 56", 0, 2)), [])

    def test_parse_does_not_join_columns_or_lines(self):
        self.assertIsNone(value_types.parse("quantity", "12\tkWh", unit="kWh"))
        self.assertIsNone(value_types.parse("number", "4711\n12"))
        self.assertEqual(
            value_types.parse("quantity", " 12  kWh ", unit="kWh")["value_number"], 12
        )

    def test_no_date_inside_a_dashed_identifier(self):
        self.check(
            "date",
            [
                ("INV-01-02-2024-A", None),
                ("abc2024-02-01xyz", {"value_date": date(2024, 2, 1)}),
                ("01.02.2024Seite 1", {"value_date": date(2024, 2, 1)}),
                ("2024-01-01T12:00", {"value_date": date(2024, 1, 1)}),
                ("01-02-2024-A", None),
                ("(01.02.2024)", {"value_date": date(2024, 2, 1)}),
                ("01.01.2024-31.12.2024", {"value_date": date(2024, 1, 1)}),
                # Unusual capitals do not crash the month lookup.
                ("1. MA\u0130 2024", None),
            ],
        )
        self.check("period", [("INV-01.01.2024-31.12.2024-A", None)])

    def test_leap_day_takes_the_year_before(self):
        self.check(
            "period",
            [
                (
                    "29.02. - 28.02.2025",
                    {
                        "value_date": date(2024, 2, 29),
                        "value_date_to": date(2025, 2, 28),
                    },
                )
            ],
        )

    def test_unit_is_not_part_of_a_compound_unit(self):
        self.check(
            "quantity",
            [
                ("12 kWh/Tag", None),
                ("Tag/kWh 12", None),
                ("12 kWh.", {"value_number": 12}),
            ],
            unit="kWh",
        )

    def test_email_syntax(self):
        # An invalid address gives no value rather than a guessed part of it.
        self.check(
            "email",
            [
                (".abc@example.com", None),
                ("a..b@example.com", None),
                ("a@-example.com", None),
                ("a@example-.com", None),
            ],
        )

    def test_no_endless_numbers(self):
        self.check("amount", [("9" * 400 + " EUR", None)])
        self.assertIsNone(value_types.parse_number("1" * 16))
