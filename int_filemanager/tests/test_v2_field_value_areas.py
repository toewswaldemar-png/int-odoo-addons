"""suggest_field_values with boxes, and read_selection: the marked text of a file as
a value of a field."""

from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged

from ..models import int_filemanager_value_recognition
from ..models.int_filemanager_value_recognition import MAX_AREAS, MAX_SELECTION_CHARS
from .test_v2_derivative import FakeConverter
from .test_v2_derivative_kinds import text_result
from .test_v2_field_value_suggest import FieldValueCase
from .test_v2_value_suggest import layout

BOTTOM = {"page": 1, "x0": 0.0, "top": 0.5, "x1": 1.0, "bottom": 1.0}


@tagged("post_install", "-at_install")
class TestV2FieldValueAreas(FieldValueCase):
    def setUp(self):
        super().setUp()
        self.date = (
            self.env["int_filemanager.extraction_field"]
            .sudo()
            .create({"name": "T Date", "value_type": "date"})
        )
        self.page = layout(
            (100, [(50, "Rechnungsnummer"), (200, "1111")]),
            (110, [(50, "Vorgangsnummer"), (200, "4711")]),
            (500, [(50, "Rechnungsnummer"), (200, "2222")]),
            (510, [(50, "Objektnummer"), (200, "6900")]),
            (520, [(50, "Datum"), (200, "29.01.2019")]),
        )
        self.node = self._pdf("bescheid.pdf", self.page)

    def _suggest_in(self, areas, user=None):
        return self.Node.with_user(user or self.writer).suggest_field_values(
            self.node.id, areas=areas
        )

    def _read(self, field, start, end, user=None, revision_id=None):
        return self.Node.with_user(user or self.writer).read_selection(
            self.node.id,
            revision_id or self.node.current_revision_id.id,
            field.id,
            start,
            end,
        )

    def _offsets(self, text):
        start = self.page.text.index(text)
        return start, start + len(text)

    def test_without_boxes_the_answer_has_none(self):
        result = self._suggest(self.node)
        self.assertEqual(result["areas"], [])
        self.assertEqual(result["page_sizes"], {"1": [595.0, 842.0]})
        best = self._best(result, self.invoice)
        self.assertEqual(
            (best["value"]["value_text"], best["in_area"]), ("1111", False)
        )

    def test_values_of_a_box_go_first_and_are_counted(self):
        result = self._suggest_in([BOTTOM])
        best = self._best(result, self.invoice)
        self.assertEqual((best["value"]["value_text"], best["in_area"]), ("2222", True))
        (box,) = result["areas"]
        self.assertEqual(box["index"], 0)
        self.assertEqual([u["label"] for u in box["unassigned"]], ["Objektnummer"])
        self.assertEqual(box["unassigned"][0]["area"], 0)
        self.assertEqual(box["values"], 2)
        # The pairs outside a box stay in the list of the file.
        self.assertEqual([u["label"] for u in result["unassigned"]], ["Vorgangsnummer"])

    def test_boxes_must_be_valid(self):
        for area in (
            {**BOTTOM, "x1": 0.0},
            {**BOTTOM, "top": 0.9, "bottom": 0.5},
            {**BOTTOM, "x1": 1.5},
            {**BOTTOM, "x0": -0.1},
            {**BOTTOM, "page": 0},
            {**BOTTOM, "page": "1"},
            {**BOTTOM, "page": True},
            {**BOTTOM, "x0": "a"},
            {"page": 1},
            None,
        ):
            with self.subTest(area=area), self.assertRaises(UserError):
                self._suggest_in([area])
        with self.assertRaises(UserError):
            self._suggest_in([BOTTOM] * (MAX_AREAS + 1))
        self.assertEqual(
            len(self._suggest_in([BOTTOM] * MAX_AREAS)["areas"]), MAX_AREAS
        )

    def test_only_who_may_read_the_file_can_use_boxes(self):
        with self.assertRaises(AccessError):
            self._suggest_in([BOTTOM], self.outsider)

    def test_a_marking_is_read_with_the_type_of_the_field(self):
        start, end = self._offsets("29.01.2019")
        result = self._read(self.date, start, end)
        self.assertEqual(result["state"], "ready")
        suggestion = result["suggestion"]
        self.assertEqual(suggestion["value"]["value_text"], "2019-01-29")
        self.assertEqual(
            (suggestion["source_text"], suggestion["start"], suggestion["end"]),
            ("29.01.2019", start, end),
        )
        self.assertEqual(
            (suggestion["page"], suggestion["x0"], suggestion["top"]), (1, 200, 520)
        )
        self.assertEqual(suggestion["direction"], "selection")
        self.assertFalse(self.node.sudo().field_value_ids)

    def test_a_marking_that_cuts_a_word_takes_the_whole_word(self):
        start, end = self._offsets("29.01.2019")
        result = self._read(self.date, start + 3, end - 2)
        self.assertEqual(result["suggestion"]["source_text"], "29.01.2019")
        self.assertEqual(result["suggestion"]["start"], start)
        self.assertEqual(result["suggestion"]["end"], end)

    def test_a_marking_that_is_no_value_says_so(self):
        start, end = self._offsets("Datum")
        result = self._read(self.date, start, end)
        self.assertFalse(result["suggestion"])
        self.assertIn("Datum", result["message"])
        self.assertIn("Date", result["message"])

    def test_a_marking_over_several_words_is_one_text(self):
        start, _end = self._offsets("Rechnungsnummer")
        _start, end = self._offsets("1111")
        result = self._read(self.invoice, start, end)
        self.assertFalse(result["suggestion"])
        self.assertIn("Rechnungsnummer 1111", result["message"])

    def test_marking_errors(self):
        length = len(self.page.text)
        for start, end in (
            (5, 5),
            (6, 5),
            (-1, 3),
            (0, length + 1),
            ("0", 3),
            (0, 1.5),
        ):
            with self.subTest(start=start, end=end), self.assertRaises(UserError):
                self._read(self.date, start, end)
        with (
            patch.object(int_filemanager_value_recognition, "MAX_SELECTION_CHARS", 10),
            self.assertRaises(UserError),
        ):
            self._read(self.date, 0, length)  # longer than a value can be
        gone = self.date.id
        self.date.sudo().unlink()
        with self.assertRaises(UserError):
            self.Node.with_user(self.writer).read_selection(
                self.node.id, self.node.current_revision_id.id, gone, 0, 3
            )

    def test_a_changed_or_unread_file_reads_nothing(self):
        start, end = self._offsets("29.01.2019")
        stale = self._read(self.date, start, end, revision_id=-1)
        self.assertEqual(stale["state"], "changed")
        self.assertNotIn("suggestion", stale)
        fresh = self._file("neu.pdf", b"%PDF-1.4 new")
        answer = self.Node.with_user(self.writer).read_selection(
            fresh.id, fresh.current_revision_id.id, self.date.id, 0, 3
        )
        self.assertEqual(answer["state"], "pending")

    def test_only_who_may_read_the_file_can_read_a_marking(self):
        start, end = self._offsets("29.01.2019")
        with self.assertRaises(AccessError):
            self._read(self.date, start, end, user=self.outsider)

    def _words(self, page_number, user=None, revision_id=None, node=None):
        node = node or self.node
        return self.Node.with_user(user or self.writer).page_words(
            node.id, revision_id or node.current_revision_id.id, page_number
        )

    def test_the_words_of_a_page_come_with_their_places(self):
        result = self._words(1)
        self.assertEqual(result["state"], "ready")
        words = {self.page.text[w[4] : w[5]]: w for w in result["words"]}
        self.assertEqual(words["Objektnummer"][:2], [50, 510])
        self.assertEqual(len(result["words"]), len(self.page.words))
        self.assertEqual(self._words(2)["words"], [])

    def test_the_words_of_a_page_are_limited_and_checked(self):
        with patch.object(int_filemanager_value_recognition, "MAX_PAGE_WORDS", 3):
            self.assertEqual(len(self._words(1)["words"]), 3)
        for page_number in ("1", 1.5, True, None):
            with self.subTest(page=page_number), self.assertRaises(UserError):
                self._words(page_number)
        self.assertEqual(self._words(1, revision_id=-1)["state"], "changed")
        with self.assertRaises(AccessError):
            self._words(1, user=self.outsider)

    def test_an_iban_none_of_the_accounts_of_the_sender_has_is_warned_about(self):
        self.env["int_filemanager.extraction_rule"].sudo().create(
            {"field_id": self.iban.id, "keywords": "IBAN"}
        )
        sender = (
            self.env["res.partner"]
            .sudo()
            .create({"name": "Vendor T", "is_company": True, "vat": "DE136695976"})
        )
        page = layout(
            (100, [(50, "USt-IdNr.: DE136695976")]),
            (112, [(50, "IBAN: GB82 WEST 1234 5698 7654 32")]),
        )
        node = self._pdf("iban.pdf", page)
        self.assertEqual(self._suggest(node)["warnings"], [])  # no known account
        bank = self.env["res.partner.bank"].sudo()
        bank.create({"acc_number": "DE89370400440532013000", "partner_id": sender.id})
        warnings = self._suggest(node)["warnings"]
        self.assertEqual([w["type"] for w in warnings], ["iban_differs"])
        self.assertEqual(warnings[0]["field_id"], self.iban.id)
        self.assertIn("Vendor T", warnings[0]["message"])
        bank.create({"acc_number": "GB82WEST12345698765432", "partner_id": sender.id})
        self.assertEqual(self._suggest(node)["warnings"], [])

    def _text_file(self, content):
        node = self._file("notiz.txt", content.encode())
        self._run(
            FakeConverter(
                by_kind={"text": lambda sha256: text_result(content.encode())}
            )
        )
        return node

    def _read_in(self, node, field, start, end):
        return self.Node.with_user(self.writer).read_selection(
            node.id, node.current_revision_id.id, field.id, start, end
        )

    def test_a_marking_that_cuts_a_word_of_a_plain_text_takes_the_whole_word(self):
        text = "Rechnungsnummer: 4711 vom 29.01.2019"
        node = self._text_file(text)
        start = text.index("4711")
        result = self._read_in(node, self.invoice, start + 1, start + 3)
        self.assertEqual(result["suggestion"]["source_text"], "4711")
        self.assertEqual(
            (result["suggestion"]["start"], result["suggestion"]["end"]),
            (start, start + 4),
        )

    def test_a_marking_over_a_page_break_is_refused(self):
        node = self._text_file("Alice\fSmith")
        word = (
            self.env["int_filemanager.extraction_field"]
            .sudo()
            .create({"name": "T Word", "value_type": "word"})
        )
        with self.assertRaises(UserError):
            self._read_in(node, word, 0, 11)

    def test_a_long_range_of_blanks_is_refused_before_it_is_worked_on(self):
        node = self._text_file("4711" + " " * (5 * MAX_SELECTION_CHARS))
        with self.assertRaises(UserError):
            self._read_in(node, self.invoice, 0, 5 * MAX_SELECTION_CHARS)

    def test_too_many_boxes_are_refused_only_after_the_right_to_read(self):
        many = [BOTTOM] * (MAX_AREAS + 1)
        with self.assertRaises(AccessError):
            self._suggest_in(many, self.outsider)
        with self.assertRaises(UserError):
            self._suggest_in(many)
