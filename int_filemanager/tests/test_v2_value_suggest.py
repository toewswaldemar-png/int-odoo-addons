"""Suggesting field values: labels found from every side of a value, and matched to
fields like base_import matches column headers - exact, containing, fuzzy.

The pages are built from rows of cells with made-up positions, one case per layout
seen in real documents: label before the value, in the cell to its left, above it,
below it (the information block of a business letterhead), a table column head.
"""

import re
from datetime import date
from unittest.mock import patch

from odoo.tests.common import BaseCase, tagged

from .. import value_suggest as vs

TODAY = date(2026, 9, 29)
CHAR_WIDTH = 5.0
LINE_HEIGHT = 9.0


def layout(*rows, page=1):
    """A word list of ``(top, [(x0, cell), ...])`` rows; cells are tab-separated."""
    text, words = "", []
    for r, (top, cells) in enumerate(rows):
        if r:
            text += "\n"
        for c, (x0, cell) in enumerate(cells):
            if c:
                text += "\t"
            x = x0
            for i, word in enumerate(cell.split(" ")):
                if i:
                    text += " "
                    x += CHAR_WIDTH
                start = len(text)
                text += word
                width = CHAR_WIDTH * len(word)
                words.append(
                    [page, x, top, x + width, top + LINE_HEIGHT, start, len(text)]
                )
                x += width
    return vs.Page(text, words)


def spec(field_id, value_type, *keywords, unit=None):
    return vs.FieldSpec(
        field_id, value_type, list(keywords), unit=unit, rule_id=field_id * 10
    )


INVOICE = spec(1, "number", "Rechnungsnummer", "Rechnungsnr.")
CUSTOMER = spec(2, "number", "Kundennummer", "Kunden-Nr.")
BASE_PRICE = spec(3, "amount", "Grundpreis")
INSTALMENT = spec(4, "amount", "Abschlag")
CONSUMPTION = spec(5, "quantity", "Jahresverbrauch", unit="kWh")
DOCUMENT_DATE = spec(6, "date", "Datum", "Anfrage")
AMOUNT = spec(7, "amount", "Betrag")
INQUIRY = spec(9, "number", "Anfragenummer", "Anfrage")


def run(page, specs, **options):
    found, unassigned = vs.suggest(page, specs, today=TODAY, **options)
    return found, unassigned


def texts(found):
    return {k: [s.value["value_text"] for s in v] for k, v in found.items()}


@tagged("post_install", "-at_install")
class TestV2ValueSuggest(BaseCase):
    def test_normalize(self):
        self.assertEqual(vs.normalize("Kunden-Nr.:"), "kundennummer")
        self.assertEqual(vs.normalize("Rechnungs No"), "rechnungsnummer")
        self.assertEqual(vs.normalize("Straße"), "strasse")
        # Only a whole "Nr" is spelled out, not the letters inside a word.
        self.assertEqual(vs.normalize("Nummernschild"), "nummernschild")
        self.assertEqual(vs.normalize("Monr"), "monr")

    def test_label_before_the_value(self):
        found, _ = run(vs.Page("Rechnungsnummer: R-2024-001\n"), [INVOICE])
        self.assertEqual(texts(found), {1: ["R-2024-001"]})
        best = found[1][0]
        self.assertEqual((best.direction, best.tier), ("before", vs.TIER_EXACT))
        self.assertEqual(best.rule_id, 10)

    def test_label_in_the_cell_to_the_left(self):
        page = layout((100, [(50, "Rechnungsnr."), (200, "4711")]))
        found, _ = run(page, [INVOICE])
        self.assertEqual(texts(found), {1: ["4711"]})
        self.assertEqual(found[1][0].direction, "left")
        self.assertEqual(found[1][0].box, (1, 200, 100, 220, 109))

    def test_labels_above_their_values_side_by_side(self):
        page = layout(
            (100, [(50, "Grundpreis"), (200, "Abschlag")]),
            (112, [(50, "13,40 €"), (200, "50,00 €")]),
        )
        found, _ = run(page, [BASE_PRICE, INSTALMENT])
        self.assertEqual(texts(found)[3][0], "13.40 EUR")
        self.assertEqual(texts(found)[4][0], "50.00 EUR")

    def test_label_above_wins_over_the_next_label_below(self):
        page = layout(
            (100, [(50, "Grundpreis")]),
            (112, [(50, "13,40 €")]),
            (124, [(50, "Abschlag")]),
            (136, [(50, "50,00 €")]),
        )
        found, _ = run(page, [BASE_PRICE, INSTALMENT])
        self.assertEqual(texts(found)[3][0], "13.40 EUR")
        self.assertEqual(texts(found)[4][0], "50.00 EUR")
        self.assertEqual(found[4][0].direction, "above")

    def test_label_below_the_value_as_in_a_letterhead(self):
        page = layout(
            (100, [(350, "Fax"), (450, "e-mail")]),
            (112, [(350, "18249"), (450, "Seite : 1 von 1")]),
            (124, [(350, "unsere Kundennummer bei Ihnen")]),
        )
        found, _ = run(page, [CUSTOMER])
        self.assertEqual(texts(found)[2][0], "18249")
        best = found[2][0]
        self.assertEqual((best.direction, best.tier), ("below", vs.TIER_CONTAINS))

    def test_head_of_a_table_column(self):
        page = layout(
            (100, [(50, "Pos"), (200, "Betrag")]),
            (112, [(50, "1"), (200, "12,50 €")]),
            (124, [(50, "2"), (200, "13,00 €")]),
        )
        found, _ = run(page, [AMOUNT])
        self.assertEqual(texts(found)[7], ["12.50 EUR", "13.00 EUR"])
        self.assertEqual(found[7][1].direction, "above")

    def test_the_type_decides_which_field_a_label_can_name(self):
        page = layout((100, [(50, "Jahresverbrauch")]), (112, [(50, "13,40 €")]))
        self.assertEqual(run(page, [CONSUMPTION])[0], {})
        page = layout((100, [(50, "Jahresverbrauch")]), (112, [(50, "3.000 kWh")]))
        self.assertEqual(texts(run(page, [CONSUMPTION])[0]), {5: ["3000 kWh"]})

    def test_close_and_containing_labels(self):
        found, _ = run(vs.Page("Kundennumer: 4711"), [CUSTOMER])
        self.assertEqual(
            (texts(found), found[2][0].tier), ({2: ["4711"]}, vs.TIER_FUZZY)
        )
        found, _ = run(vs.Page("Ihre Kundennummer bei uns: 4711"), [CUSTOMER])
        self.assertEqual(found[2][0].tier, vs.TIER_CONTAINS)
        self.assertEqual(run(vs.Page("Kontonummer: 4711"), [CUSTOMER])[0], {})

    def test_the_fuzzy_limit_is_strict(self):
        # "Betrag" heads a column of single items; its ratio to "Endbetrag" is
        # exactly 0.8, on the limit, and must not count as close.
        total = spec(17, "amount", "Endbetrag")
        page = layout((100, [(50, "Betrag")]), (112, [(50, "12,50 €")]))
        self.assertEqual(run(page, [total])[0], {})

    def test_a_business_letter_head(self):
        page = layout((100, [(350, "ANFRAGE 190023"), (527, "29.01.2019")]))
        found, _ = run(page, [DOCUMENT_DATE, INQUIRY])
        self.assertEqual(texts(found)[6], ["2019-01-29"])
        self.assertEqual(texts(found)[9], ["190023"])
        self.assertEqual(found[9][0].tier, vs.TIER_EXACT)

    def test_a_value_is_the_suggestion_of_one_field(self):
        first, second = spec(11, "number", "Nummer"), spec(12, "number", "Nummer")
        found, _ = run(vs.Page("Nummer: 4711"), [first, second])
        best = [v[0].value["value_text"] for v in found.values() if v]
        self.assertEqual(best, ["4711"])

    def test_own_values_are_skipped(self):
        iban = spec(13, "iban", "IBAN")
        page = vs.Page("IBAN: DE89 3704 0044 0532 0130 00")
        self.assertEqual(texts(run(page, [iban])[0]), {13: ["DE89370400440532013000"]})
        own = {"DE89370400440532013000"}
        found, _ = run(page, [iban], skip=lambda t, v: v["value_text"] in own)
        self.assertEqual(found, {})

    def test_regex_rules(self):
        pattern = vs.FieldSpec(
            14, "number", patterns=[(140, re.compile(r"Vorgang (\S+)"), 1)]
        )
        found, _ = run(vs.Page("Vorgang A-17 vom 01.02.2024"), [pattern])
        self.assertEqual(texts(found), {14: ["A-17"]})
        self.assertEqual((found[14][0].direction, found[14][0].rule_id), ("regex", 140))
        # The group must be a whole value of the type.
        found, _ = run(vs.Page("Vorgang offen"), [pattern])
        self.assertEqual(found, {})

    def test_a_slow_pattern_is_reported(self):
        pattern = vs.FieldSpec(15, "number", patterns=[(150, re.compile(r"(\d+)"), 1)])
        slow = []
        with patch.object(vs, "SLOW_PATTERN_SECONDS", -1):
            run(vs.Page("4711"), [pattern], slow=lambda rule, s: slow.append(rule))
        self.assertEqual(slow, [150])

    def test_pairs_no_field_took_are_listed(self):
        _found, unassigned = run(vs.Page("Vorgangsnummer: 4711"), [INVOICE])
        self.assertEqual(
            [(u["label"], u["value_text"]) for u in unassigned],
            [("Vorgangsnummer", "4711")],
        )

    def test_learned_label_of_the_sender_comes_first(self):
        learned = spec(16, "number", "Kundennummer")
        learned.hints = {vs.normalize("Vertragskonto"): 7}
        found, _ = run(vs.Page("Vertragskonto: 1234\nKundennummer: 5678"), [learned])
        self.assertEqual(texts(found)[16], ["1234", "5678"])
        self.assertEqual((found[16][0].tier, found[16][0].hint_id), (vs.TIER_HINT, 7))
        self.assertIsNone(found[16][0].rule_id)

    def test_a_keyword_counts_as_the_last_part_of_a_compound(self):
        found, _ = run(vs.Page("Telekom-Kundennummer: 4711"), [CUSTOMER])
        self.assertEqual(found[2][0].tier, vs.TIER_CONTAINS)
        # At the start of a word, the keyword is part of something else.
        order = spec(18, "number", "Auftrag")
        self.assertEqual(run(vs.Page("Auftragsbestandsliste: 4711"), [order])[0], {})
        family = spec(19, "number", "Familie")
        self.assertEqual(run(vs.Page("Familienkasse: 4711"), [family])[0], {})

    def test_a_sentence_mentioning_a_keyword_is_no_label(self):
        # The keyword is too small a part of the line below the value.
        page = layout(
            (100, [(50, "12,50 €")]), (112, [(50, "Der offene Betrag wird abgebucht")])
        )
        self.assertEqual(run(page, [AMOUNT])[0], {})
        page = layout((100, [(50, "12,50 €")]), (112, [(50, "Offener Betrag")]))
        self.assertEqual(texts(run(page, [AMOUNT])[0]), {7: ["12.50 EUR"]})
        # A few words after the keyword still make a label, a sentence does not.
        page = vs.Page("Den Betrag in Höhe von 12,50 €")
        self.assertEqual(texts(run(page, [AMOUNT])[0]), {7: ["12.50 EUR"]})
        page = layout(
            (100, [(50, "4711")]),
            (112, [(50, "Auftragsbestätigung gilt gleichzeitig als Rechnung")]),
        )
        order = spec(18, "number", "Auftragsbestätigung")
        self.assertEqual(run(page, [order])[0], {})

    def test_the_label_in_front_starts_after_the_last_number(self):
        found, _ = run(vs.Page("Rechnung vom 12.03.2024 Kundennummer 4711"), [CUSTOMER])
        best = found[2][0]
        self.assertEqual((best.label, best.tier), ("Kundennummer", vs.TIER_EXACT))
        page = vs.Page("Zurückzuzahlender Gesamtbetrag: 359. 642,08 €")
        self.assertEqual(run(page, [spec(17, "amount", "Gesamtbetrag")])[0], {})

    def test_a_number_of_one_digit_is_no_reference(self):
        order = spec(18, "number", "Auftragsnummer")
        self.assertEqual(run(vs.Page("Auftragsnummer: 4"), [order])[0], {})
        self.assertEqual(
            texts(run(vs.Page("Auftragsnummer: 42"), [order])[0]), {18: ["42"]}
        )

    def test_a_vat_number_needs_no_label(self):
        vat = spec(21, "vat", "USt-IdNr.")
        page = vs.Page("Eingetragen unter DE136695976")
        found, _ = run(page, [vat])
        self.assertEqual(texts(found), {21: ["DE136695976"]})
        best = found[21][0]
        self.assertEqual(
            (best.direction, best.tier), ("unlabelled", vs.TIER_UNLABELLED)
        )
        self.assertIsNone(best.rule_id)
        # A labelled one comes first.
        page = vs.Page("Eingetragen unter DE136695976\nUSt-IdNr.: DE811569869")
        self.assertEqual(texts(run(page, [vat])[0])[21], ["DE811569869", "DE136695976"])
        # With two fields of the type, a value without label could be either.
        other = spec(22, "vat", "USt-IdNr. des Empfängers")
        self.assertEqual(
            run(vs.Page("Eingetragen unter DE136695976"), [vat, other])[0], {}
        )

    def test_prose_is_not_close_to_its_keyword_either(self):
        term = spec(23, "period", "Mindestvertragslaufzeit")
        self.assertIsNone(vs.match_label("Mindestvertragslaufzeit s. u. a. O.", term))
        # An inflected keyword is.
        self.assertEqual(vs.match_label("Kundennummern", CUSTOMER)[0], vs.TIER_FUZZY)

    def test_a_vat_field_with_a_pattern_only_gets_unlabelled_numbers(self):
        pattern = vs.FieldSpec(
            24, "vat", patterns=[(240, re.compile(r"Steuer-ID (\S+)"), 1)]
        )
        found, _ = run(vs.Page("Eingetragen unter DE136695976"), [pattern])
        self.assertEqual(texts(found), {24: ["DE136695976"]})

    def test_a_short_keyword_ending_a_compound_names_something_else(self):
        found, _ = run(vs.Page("Geburtsdatum: 04.02.1986"), [DOCUMENT_DATE])
        self.assertEqual(found, {})
        found, _ = run(vs.Page("Rg.-Datum: 12.03.2024"), [DOCUMENT_DATE])
        self.assertEqual(texts(found), {6: ["2024-03-12"]})
        period = spec(25, "period", "Zeitraum")
        found, _ = run(
            vs.Page("Fälligkeitszeitraum: 01.01.2024 - 31.12.2024"), [period]
        )
        self.assertEqual(found[25][0].tier, vs.TIER_CONTAINS)

    def test_a_compound_with_another_meaning_is_not_close_either(self):
        order = spec(28, "number", "Auftrag")
        self.assertIsNone(vs.match_label("Eilauftrag", order))
        # A digit read into a word is no part of a compound.
        salutation = spec(29, "word", "Herrn")
        self.assertEqual(vs.match_label("1Herrn", salutation)[0], vs.TIER_CONTAINS)

    def test_a_bare_number_word_is_not_close_to_a_keyword(self):
        short = spec(26, "number", "Kd.-Nr.")
        self.assertEqual(run(vs.Page("Nr. 4711"), [short])[0], {})

    def test_the_addressee_only_in_the_address_window(self):
        recipient = spec(27, "word", "Herrn", "Herr", "Frau", "Herrn und Frau")
        recipient.area = "address"
        page = layout(
            (150, [(57, "Herrn")]),
            (162, [(57, "Max Muster")]),
            (400, [(57, "Herr"), (150, "Paul Beispiel")]),
        )
        found, _ = run(page, [recipient])
        self.assertEqual(found[27][0].value["value_text"], "Max Muster")
        self.assertNotIn("Paul Beispiel", texts(found)[27])
        # A name starts with a capital letter: "und Frau Max Muster" is none.
        page = layout((150, [(57, "Herrn und Frau Max Muster")]))
        self.assertEqual(texts(run(page, [recipient])[0])[27][0], "Max Muster")
        # Without positions nothing is known to be in the window.
        self.assertEqual(run(vs.Page("Herrn Max Muster"), [recipient])[0], {})

    def test_an_iban_needs_a_label(self):
        # Without one it is mostly the reader's own account.
        iban = spec(13, "iban", "IBAN")
        page = vs.Page("Wir buchen von Ihrem Konto DE89 3704 0044 0532 0130 00 ab")
        self.assertEqual(run(page, [iban])[0], {})

    def test_a_value_never_crosses_a_column(self):
        page = layout((100, [(50, "Rechnungsnummer"), (200, "4711"), (300, "12")]))
        self.assertEqual(texts(run(page, [INVOICE])[0]), {1: ["4711"]})
