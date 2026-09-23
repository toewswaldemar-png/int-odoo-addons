import unittest

from odoo.addons.int_filemanager.fulltext import _build_indexed_text, _decode_form_field_value, _locate_span


def _word(text, x0, top, x1, bottom):
    return {"text": text, "x0": x0, "top": top, "x1": x1, "bottom": bottom}


class TestBuildIndexedText(unittest.TestCase):
    """Reine Offset-Buchhaltung, keine Odoo-Umgebung noetig - _build_indexed_text/_locate_span
    sind der Kern von Phase B (docs/int_filemanager_ocr_selbstdefinierte_felder.md): ein
    Regex-Treffer im zusammengesetzten Text muss sich verlustfrei auf die zugrundeliegenden
    pdfplumber-Wort-Boxen zurueckfuehren lassen."""

    def test_single_page_offsets_match_text(self):
        words = [_word("Rechnung", 10, 20, 60, 30), _word("Nr.", 65, 20, 80, 30), _word("12345", 85, 20, 120, 30)]
        text, word_index = _build_indexed_text([words])
        self.assertEqual(text, "Rechnung Nr. 12345 \n")
        # Jeder Eintrag muss exakt sein eigenes Token im zusammengesetzten Text treffen.
        for w, entry in zip(words, word_index):
            self.assertEqual(text[entry["start"]:entry["end"]], w["text"])
            self.assertEqual(entry["page"], 1)

    def test_multi_page_offsets_and_page_numbers(self):
        page1 = [_word("Seite", 0, 0, 10, 10), _word("eins", 12, 0, 20, 10)]
        page2 = [_word("Seite", 0, 0, 10, 10), _word("zwei", 12, 0, 20, 10)]
        text, word_index = _build_indexed_text([page1, page2])
        pages = [w["page"] for w in word_index]
        self.assertEqual(pages, [1, 1, 2, 2])
        for w, entry in zip(page1 + page2, word_index):
            self.assertEqual(text[entry["start"]:entry["end"]], w["text"])

    def test_locate_span_single_word(self):
        words = [_word("Betrag", 0, 0, 30, 10), _word("129,90", 35, 0, 70, 10)]
        text, word_index = _build_indexed_text([words])
        start = text.index("129,90")
        box = _locate_span(word_index, start, start + len("129,90"))
        self.assertEqual(box, {"page": 1, "x0": 35, "y0": 0, "x1": 70, "y1": 10})

    def test_locate_span_union_of_multiple_words(self):
        # Ein Treffer kann mehrere Woerter umfassen, z.B. eine mit Leerzeichen erkannte
        # Rechnungsnummer - die Box muss dann die Vereinigung aller beteiligten Wort-Boxen sein.
        words = [_word("RE", 0, 0, 20, 10), _word("2024", 22, 0, 50, 10), _word("0042", 52, 0, 80, 10)]
        text, word_index = _build_indexed_text([words])
        start = text.index("RE")
        end = text.index("0042") + len("0042")
        box = _locate_span(word_index, start, end)
        self.assertEqual(box, {"page": 1, "x0": 0, "y0": 0, "x1": 80, "y1": 10})

    def test_locate_span_across_page_boundary_returns_none(self):
        page1 = [_word("Ende", 0, 0, 20, 10)]
        page2 = [_word("Anfang", 0, 0, 30, 10)]
        text, word_index = _build_indexed_text([page1, page2])
        box = _locate_span(word_index, 0, len(text))
        self.assertIsNone(box)

    def test_locate_span_no_overlap_returns_none(self):
        words = [_word("Wort", 0, 0, 20, 10)]
        _, word_index = _build_indexed_text([words])
        self.assertIsNone(_locate_span(word_index, 1000, 1010))

    def test_locate_span_empty_word_index_returns_none(self):
        self.assertIsNone(_locate_span([], 0, 5))


class TestDecodeFormFieldValue(unittest.TestCase):
    """AcroForm-Feldwerte (2026-09-19, live an einem echten Behoerdenformular gefunden - eine
    Kindergeldnummer existierte nur als Formularfeld-Wert, nicht im normalen Seitentext, siehe
    docs/int_filemanager_ocr_selbstdefinierte_felder.md) - beide in freier Wildbahn beobachteten
    Kodierungen pruefen."""

    def test_utf16be_with_bom(self):
        value = "﻿006FK405328".encode("utf-16-be")
        self.assertEqual(_decode_form_field_value(value), "006FK405328")

    def test_utf16be_with_umlaut(self):
        value = "﻿Töws Clemens".encode("utf-16-be")
        self.assertEqual(_decode_form_field_value(value), "Töws Clemens")

    def test_plain_utf8_without_bom(self):
        self.assertEqual(_decode_form_field_value(b"006FK405328"), "006FK405328")

    def test_already_str(self):
        self.assertEqual(_decode_form_field_value("006FK405328"), "006FK405328")

    def test_empty_returns_none(self):
        self.assertIsNone(_decode_form_field_value(b""))
        self.assertIsNone(_decode_form_field_value(""))
        self.assertIsNone(_decode_form_field_value(None))


if __name__ == "__main__":
    unittest.main()
