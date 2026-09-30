"""Suggesting field values with boxes the user drew: their values go first, the
others stay, and the pairs no field took carry their place and their box."""

from odoo.tests.common import BaseCase, tagged

from .. import value_suggest as vs
from .test_v2_value_suggest import INVOICE, TODAY, layout, spec, texts

BOTTOM_HALF = (1, 0.0, 0.5, 1.0, 1.0)
WHOLE_PAGE = (1, 0.0, 0.0, 1.0, 1.0)


def run_in(page, specs, areas):
    return vs.suggest(page, specs, today=TODAY, areas=areas)


@tagged("post_install", "-at_install")
class TestV2ValueSuggestAreas(BaseCase):
    def _two_numbers(self):
        return layout(
            (100, [(50, "Rechnungsnummer"), (200, "1111")]),
            (500, [(50, "Rechnungsnummer"), (200, "2222")]),
        )

    def test_without_a_box_nothing_changes(self):
        found, _ = run_in(self._two_numbers(), [INVOICE], None)
        self.assertEqual(texts(found), {1: ["1111", "2222"]})
        self.assertFalse(any(s.in_area for s in found[1]))
        again, _ = run_in(self._two_numbers(), [INVOICE], [])
        self.assertEqual(texts(again), texts(found))

    def test_a_value_in_a_box_goes_first_and_the_others_stay(self):
        found, _ = run_in(self._two_numbers(), [INVOICE], [BOTTOM_HALF])
        self.assertEqual(texts(found), {1: ["2222", "1111"]})
        self.assertEqual([s.in_area for s in found[1]], [True, False])
        self.assertTrue(found[1][0].as_dict()["in_area"])

    def test_every_box_counts_when_there_are_several(self):
        top = (1, 0.0, 0.0, 1.0, 0.2)
        found, _ = run_in(self._two_numbers(), [INVOICE], [top, BOTTOM_HALF])
        self.assertEqual(texts(found), {1: ["1111", "2222"]})
        self.assertEqual([s.in_area for s in found[1]], [True, True])

    def test_a_learned_label_of_the_sender_still_comes_first(self):
        learned = spec(16, "number", "Kundennummer")
        learned.hints = {vs.normalize("Vertragskonto"): 7}
        page = layout(
            (100, [(50, "Vertragskonto"), (200, "1234")]),
            (500, [(50, "Kundennummer"), (200, "5678")]),
        )
        found, _ = run_in(page, [learned], [BOTTOM_HALF])
        self.assertEqual(texts(found)[16], ["1234", "5678"])
        self.assertEqual(found[16][0].tier, vs.TIER_HINT)

    def test_among_learned_labels_the_one_in_the_box_goes_first(self):
        learned = spec(16, "number", "Kundennummer")
        learned.hints = {vs.normalize("Vertragskonto"): 7}
        page = layout(
            (100, [(50, "Vertragskonto"), (200, "1234")]),
            (500, [(50, "Vertragskonto"), (200, "5678")]),
        )
        self.assertEqual(texts(run_in(page, [learned], None)[0])[16], ["1234", "5678"])
        found, _ = run_in(page, [learned], [BOTTOM_HALF])
        self.assertEqual(texts(found)[16], ["5678", "1234"])

    def test_a_box_on_another_page_or_without_positions_holds_nothing(self):
        other_page = (2, 0.0, 0.5, 1.0, 1.0)
        found, _ = run_in(self._two_numbers(), [INVOICE], [other_page])
        self.assertEqual(texts(found), {1: ["1111", "2222"]})
        self.assertFalse(any(s.in_area for s in found[1]))
        found, _ = run_in(vs.Page("Rechnungsnummer: 4711"), [INVOICE], [WHOLE_PAGE])
        self.assertFalse(found[1][0].in_area)

    def test_half_of_a_value_inside_is_enough(self):
        page = layout((100, [(50, "Wort")]))  # 50 to 70 wide, 100 to 109 high
        self.assertFalse(page.in_box(0, 4, (1, 0.0, 0.0, 0.1, 1.0)))
        self.assertTrue(page.in_box(0, 4, (1, 0.0, 0.0, 0.11, 1.0)))
        self.assertFalse(page.in_box(0, 4, BOTTOM_HALF))
        self.assertIsNone(page.area_of(0, 4, [BOTTOM_HALF]))
        self.assertEqual(page.area_of(0, 4, [BOTTOM_HALF, WHOLE_PAGE]), 1)

    def test_the_size_of_the_page_comes_from_the_word_list(self):
        words = [[1, 50.0, 100.0, 70.0, 109.0, 0, 4]]
        small = vs.Page("Wort", words, [{"width": 100.0, "height": 200.0}])
        self.assertTrue(small.in_box(0, 4, (1, 0.4, 0.4, 0.8, 0.6)))
        self.assertFalse(small.in_box(0, 4, (1, 0.0, 0.0, 0.3, 1.0)))

    def test_unassigned_pairs_carry_their_place_and_their_box(self):
        page = layout(
            (100, [(50, "Rechnungsnummer"), (200, "1111")]),
            (110, [(50, "Vorgangsnummer"), (200, "4711")]),
            (500, [(50, "Objektnummer"), (200, "6900")]),
        )
        found, unassigned = run_in(page, [INVOICE], [BOTTOM_HALF])
        self.assertEqual(texts(found), {1: ["1111"]})
        by_label = {u["label"]: u for u in unassigned}
        self.assertEqual(set(by_label), {"Vorgangsnummer", "Objektnummer"})
        self.assertIsNone(by_label["Vorgangsnummer"]["area"])
        self.assertEqual(by_label["Objektnummer"]["area"], 0)
        outside = by_label["Vorgangsnummer"]
        self.assertEqual(
            (outside["page"], outside["x0"], outside["top"]), (1, 200, 110)
        )
        self.assertEqual(
            page.text[outside["start"] : outside["end"]], outside["value_text"]
        )

    def test_a_value_a_field_took_is_no_unassigned_pair(self):
        page = layout((100, [(50, "Rechnungsnummer"), (200, "1111")]))
        self.assertEqual(run_in(page, [INVOICE], None)[1], [])

    def test_many_pairs_in_a_box_are_kept_but_few_outside(self):
        rows = [
            (10 + i * 12, [(50, "Ablage"), (200, str(1000 + i))]) for i in range(60)
        ]
        page = layout(*rows)
        _found, outside = run_in(page, [INVOICE], None)
        self.assertEqual(len(outside), vs.MAX_UNASSIGNED)
        _found, inside = run_in(page, [INVOICE], [WHOLE_PAGE])
        self.assertEqual(len(inside), 60)
        self.assertEqual({u["area"] for u in inside}, {0})
