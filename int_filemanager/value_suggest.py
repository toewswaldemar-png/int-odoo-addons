"""Suggesting field values for one document, without database access.

The recognition does not look for one keyword after the other. It first finds
every value on the page together with the text that labels it - the words in
front of it, the cell to its left, the text above or below it, the head of its
table column - and only then decides which field a label belongs to. That order
is the one base_import uses to map the column headers of an import file to
fields (_get_mapping_suggestion): a remembered mapping first, then an exact
match, then a fuzzy one (difflib, distance below 0.2), each only among the
fields whose type fits the value; one match per field.

The page is described by the word list of the converter: ``text`` with words
separated by a space, columns by a tab, lines by a newline and pages by a form
feed, and ``words`` as ``[page, x0, top, x1, bottom, start, end]``. A plain text
file has no words; then only the words in front of a value can label it.
"""

import bisect
import difflib
import re
import time
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache

from . import value_types

_NUMBER_WORDS = re.compile(r"(?<![^\W\d_])(?:nr|no|nummer|number)(?![^\W\d_])")
FUZZY_MATCH_DISTANCE = 0.2
_FUZZY_MIN_RATIO = 1 - FUZZY_MATCH_DISTANCE + 1e-9

# How far a label may be from its value (words, PDF points, rows). Set on the
# practice part of the test collection, as general rules only.
LABEL_WORDS_BEFORE = 6
MAX_LINE_GAP = 20.0
MAX_ROWS_ABOVE = 10
ALIGN_TOLERANCE = 6.0

# A keyword inside a longer label must make up this much of it; below, the label
# is a sentence that happens to mention the keyword ("Rechnungen werden für einen
# Zeitraum von 10 Jahren aufbewahrt").
MIN_CONTAINED_SHARE = 0.3
# A label may go on a little after the keyword ("Gesamtbetrag in Höhe von", "Ihre
# Kundennummer bei uns"); more words make it the subject of a sentence
# ("Auftragsbestätigung gilt gleichzeitig als Rechnung").
MAX_WORDS_AFTER_KEYWORD = 3
# The last part of a compound names what it is, but a short, general keyword there
# is narrowed to something else: a "Geburtsdatum" is no document date, a
# "Dauerauftrag" no order, an "Ehefrau" no addressee. A longer one keeps its
# meaning ("Fälligkeitszeitraum" is a period).
MIN_COMPOUND_KEYWORD = 8

# The address window of a letter, as shares of the first page's width and height:
# the value starts left of the first share, ends left of the second, and lies
# between the top and bottom ones. DIN 5008 puts it 27-90 mm from the top edge on
# the left; in the test collection the addressee's name sits there in three of four
# letters, and starts that far left in 370 of 374. Right of it, on the same lines,
# is the information block of the sender.
ADDRESS_WINDOW = (0.45, 0.6, 0.08, 0.33)
_A4 = (595.0, 842.0)

# A number of one digit is a position, a count or a footnote, not a reference.
MIN_NUMBER_DIGITS = 2

# Check digits prove what these values are, so they are suggested without a label
# too, after every labelled one. Not an IBAN: printed without a label, it is mostly
# the reader's own account ("wir buchen von Ihrem Konto ... ab").
SELF_EVIDENT_TYPES = ("vat",)

# Preference when a value is labelled from several sides, and how well a label
# names a field: learned for this sender, equal to a keyword, containing one,
# close to one, or no label at all.
_DIRECTION_RANK = {
    "hint": 0,
    "regex": 0,
    "before": 1,
    "left": 2,
    "above": 3,
    "below": 4,
    "unlabelled": 5,
}
TIER_HINT, TIER_EXACT, TIER_CONTAINS, TIER_FUZZY, TIER_UNLABELLED = 0, 1, 2, 3, 4

# A rule's pattern running longer than this on one document is reported.
SLOW_PATTERN_SECONDS = 1.0

MAX_ALTERNATIVES = 4
MAX_UNASSIGNED = 30


@lru_cache(maxsize=4096)
def normalize(label):
    """Compact form of a label or keyword: "Kunden-Nr.:" -> "kundennummer"."""
    text = unicodedata.normalize("NFKC", label).casefold().replace("ß", "ss")
    text = _NUMBER_WORDS.sub("nummer", text)
    return "".join(c for c in text if c.isalnum())


def _is_number(word):
    digits = sum(c.isdigit() for c in word)
    return digits > 0 and digits >= sum(c.isalpha() for c in word)


def _word_ends(label):
    """Offsets in normalize(label) at which a word of the label ends.

    A digit read into a word ("1Herrn") is a word of its own.
    """
    ends, length = set(), 0
    for word in re.split(r"[\s/-]+|(?<=\d)(?=[^\W\d_])|(?<=[^\W\d_])(?=\d)", label):
        length += len(normalize(word))
        ends.add(length)
    return ends


@dataclass
class FieldSpec:
    """A field as the recognition needs it; the caller builds it from the database."""

    id: int
    value_type: str
    keywords: list = field(default_factory=list)
    unit: str = None
    rule_id: int = None
    # (rule id, compiled pattern, group) of the rules in regex mode
    patterns: list = field(default_factory=list)
    # normalized label -> hint id, learned for the sender of this document
    hints: dict = field(default_factory=dict)
    # where on the page the value is printed: None anywhere, "address" in the
    # address window
    area: str = None


@dataclass
class _Segment:
    """Text between two tabs or line breaks: a cell, a label, a line of prose."""

    start: int
    end: int
    line: int
    page: int = 0
    x0: float = 0.0
    top: float = 0.0
    x1: float = 0.0
    bottom: float = 0.0


@dataclass
class Label:
    text: str
    direction: str
    start: int = 0
    end: int = 0
    rows_skipped: int = 0
    distance: float = 0.0


class Page:
    """The text of a document with the position of every word."""

    def __init__(self, text, words=None, pages=None):
        self.text = text
        # page number -> (width, height) in the unit of the word positions
        self.sizes = {}
        for number, size in enumerate(pages or [], 1):
            if isinstance(size, dict):
                width, height = size.get("width"), size.get("height")
                if isinstance(width, int | float) and isinstance(height, int | float):
                    self.sizes[number] = (float(width), float(height))
        self.words = sorted(words or [], key=lambda w: w[5])
        self._starts = [w[5] for w in self.words]
        self.segments = []
        line = start = 0
        for m in re.finditer(r"[\t\n\f]", text + "\n"):
            if text[start : m.start()].strip():
                seg = _Segment(start, m.start(), line)
                box = self.box(start, m.start())
                if box:
                    seg.page, seg.x0, seg.top, seg.x1, seg.bottom = box
                self.segments.append(seg)
            if m.group() != "\t":
                line += 1
            start = m.end()
        self._seg_starts = [s.start for s in self.segments]
        self._on_page = {}
        for seg in self.segments:
            self._on_page.setdefault(seg.page, []).append(seg)

    def words_between(self, start, end):
        i = max(bisect.bisect_right(self._starts, start) - 1, 0)
        found = []
        while i < len(self.words) and self.words[i][5] < end:
            if self.words[i][6] > start:
                found.append(self.words[i])
            i += 1
        return found

    def box(self, start, end):
        """(page, x0, top, x1, bottom) around text[start:end], or None without words."""
        words = self.words_between(start, end)
        if not words:
            return None
        return (
            words[0][0],
            min(w[1] for w in words),
            min(w[2] for w in words),
            max(w[3] for w in words),
            max(w[4] for w in words),
        )

    def in_area(self, start, end, area):
        """Whether text[start:end] is printed in area; without positions it is not."""
        if not area:
            return True
        box = self.box(start, end)
        if not box or box[0] != 1:
            return False
        width, height = self.sizes.get(1, _A4)
        start, end, top, bottom = ADDRESS_WINDOW
        return (
            box[1] <= start * width
            and box[3] <= end * width
            and box[2] >= top * height
            and box[4] <= bottom * height
        )

    def segment_at(self, pos):
        i = bisect.bisect_right(self._seg_starts, pos) - 1
        if i >= 0 and self.segments[i].start <= pos < self.segments[i].end:
            return self.segments[i]
        return None

    def labels_of(self, start, end, value_starts):
        """Every label of the value text[start:end], from all sides."""
        seg = self.segment_at(start)
        if seg is None:
            return []
        labels = []
        before = self._label_before(seg, start)
        if before:
            labels.append(before)
        box = self.box(start, end)
        if box:
            labels += self._labels_around(seg, box, value_starts)
        return labels

    def _label_before(self, seg, value_start):
        """The words in front of the value in its own segment: "Rechnungsnr.: 4711".

        Only the words after the last number count, the rest belongs to another
        value: "Rechnung vom 12.03. Kundennummer 4711" is labelled "Kundennummer".
        A word with a stray digit read into it ("1Herrn") is still a word.
        """
        words = list(re.finditer(r"\S+", self.text[seg.start : value_start]))
        words = words[-LABEL_WORDS_BEFORE:]
        numbers = [i for i, w in enumerate(words) if _is_number(w.group())]
        if numbers:
            words = words[numbers[-1] + 1 :]
        if not words:
            return None
        start = seg.start + words[0].start()
        text = self.text[start:value_start].strip(" :;-")
        if not any(c.isalpha() for c in text):
            return None
        return Label(text, "before", start, value_start)

    def _label(self, seg, direction, rows=0, distance=0.0):
        text = self.text[seg.start : seg.end].strip(" :;-")
        # A label is short; a longer segment is prose, not the name of a value.
        if any(c.isalpha() for c in text) and len(text.split()) <= LABEL_WORDS_BEFORE:
            return Label(text, direction, seg.start, seg.end, rows, distance)
        return None

    def _labels_around(self, seg, box, value_starts):
        page, x0, top, x1, bottom = box
        segments = self._on_page.get(page, [])
        labels = []
        left = [s for s in segments if s.line == seg.line and s.x1 <= seg.x0 + 1]
        if left:
            s = max(left, key=lambda s: s.x1)
            labels.append(self._label(s, "left", 0, seg.x0 - s.x1))
        # The value's column: segments aligned on its left edge or overlapping it.
        column = [
            s
            for s in segments
            if s.line != seg.line
            and (
                abs(s.x0 - seg.x0) <= ALIGN_TOLERANCE
                or min(s.x1, x1) - max(s.x0, x0) > -ALIGN_TOLERANCE
            )
        ]
        # Above: the nearest line; through rows that hold values themselves (a
        # table), up to the head of the column.
        above = sorted(
            (s for s in column if s.bottom <= top + 1), key=lambda s: -s.bottom
        )
        edge = top
        for rows, s in enumerate(above[:MAX_ROWS_ABOVE]):
            if edge - s.bottom > MAX_LINE_GAP:
                break
            i = bisect.bisect_left(value_starts, s.start)
            if i < len(value_starts) and value_starts[i] < s.end:
                edge = s.top
                continue
            labels.append(self._label(s, "above", rows, top - s.bottom))
            break
        below = sorted((s for s in column if s.top >= bottom - 1), key=lambda s: s.top)
        if below and below[0].top - bottom <= MAX_LINE_GAP:
            labels.append(self._label(below[0], "below", 0, below[0].top - bottom))
        return [label for label in labels if label]


def match_label(label, spec):
    """(tier, score) of how well label names the field, lower is better; or None."""
    return _match(normalize(label), spec, _word_ends(label))


def _contains(norm, keyword, ends):
    """How keyword stands in the longer label norm: True as its label, False in
    prose, None only inside a word.

    It has to end one of the label's words: the last part of a German compound
    names what it is ("Telekom-Kundennummer" is a customer number, a
    "Familienkasse" is no family, "angeboten" no offer), and few words may follow.
    """
    found = None
    start = norm.find(keyword)
    while start >= 0:
        end = start + len(keyword)
        whole = start == 0 or start in ends
        if end in ends:
            if (
                (whole or len(keyword) >= MIN_COMPOUND_KEYWORD)
                and len(keyword) >= MIN_CONTAINED_SHARE * len(norm)
                and sum(e > end for e in ends) <= MAX_WORDS_AFTER_KEYWORD
            ):
                return True
            # Not close either: an "Eilauftrag" is not a misread "Auftrag".
            found = False
        start = norm.find(keyword, start + 1)
    return found


def _match(norm, spec, ends):
    if not norm:
        return None
    best = None
    # A label learned for this sender, as the whole label or a part of it.
    for hint in spec.hints:
        if norm == hint:
            return TIER_HINT, 0.0
        if hint and hint in norm:
            found = (TIER_HINT, 1 - len(hint) / len(norm))
            best = found if best is None or found < best else best
    if best:
        return best
    for keyword in spec.keywords:
        kw = normalize(keyword)
        if not kw:
            continue
        if norm == kw:
            return TIER_EXACT, 0.0
        contained = _contains(norm, kw, ends) if kw in norm else None
        if contained is False:
            continue
        if contained:
            # The larger the part of the label the keyword covers, the better.
            found = (TIER_CONTAINS, 1 - len(kw) / len(norm))
        else:
            # An inflected or misread keyword ("Kundennummern", "Kundennumer") is
            # still close to it. A label shorter by more than a letter is not: a
            # bare "Nr." would be close to "Kd.-Nr.". The quick upper bounds of
            # difflib rule out most pairs before the exact ratio is worked out.
            # The limit is strict and kept clear of rounding: 1 - 0.8 is
            # 0.19999999999999996 in floating point, which would let "Betrag" (a
            # table column) pass as close to "Endbetrag".
            if len(norm) < len(kw) - 1:
                continue
            matcher = difflib.SequenceMatcher(None, norm, kw)
            if any(
                ratio() <= _FUZZY_MIN_RATIO
                for ratio in (
                    matcher.real_quick_ratio,
                    matcher.quick_ratio,
                    matcher.ratio,
                )
            ):
                continue
            found = (TIER_FUZZY, 1 - matcher.ratio())
        if best is None or found < best:
            best = found
    return best


@dataclass
class Suggestion:
    field_id: int
    value: dict
    source_text: str
    start: int
    end: int
    box: tuple
    label: str
    direction: str
    tier: int
    rule_id: int = None
    hint_id: int = None

    def as_dict(self):
        page, x0, top, x1, bottom = self.box or (0, 0.0, 0.0, 0.0, 0.0)
        return {
            "value": self.value,
            "source_text": self.source_text,
            "start": self.start,
            "end": self.end,
            "page": page,
            "x0": x0,
            "top": top,
            "x1": x1,
            "bottom": bottom,
            "label": self.label,
            "direction": self.direction,
            "tier": self.tier,
            "rule_id": self.rule_id,
            "hint_id": self.hint_id,
        }


def suggest(page, specs, skip=None, slow=None, **options):
    """Return the suggestions per field and the label-value pairs no field took.

    :param page: the document as a :class:`Page`
    :param specs: the active fields as :class:`FieldSpec`
    :param skip: callable(value_type, value) -> True for a value never to suggest
        (the own company's IBAN, VAT number and mail addresses)
    :param slow: callable(rule_id, seconds) for a pattern that ran too long
    :param options: passed on to value_types (currencies, default_currency, today ...)
    :returns: ``({field_id: [best, alternative, ...]}, [unassigned pair, ...])``
    """
    skip = skip or (lambda value_type, value: False)
    pairs, unassigned = [], []
    kinds = {
        (s.value_type, s.unit)
        for s in specs
        if s.keywords or s.hints or s.value_type in SELF_EVIDENT_TYPES
    }
    for value_type, unit in sorted(kinds, key=lambda k: (k[0], k[1] or "")):
        fitting = [s for s in specs if (s.value_type, s.unit) == (value_type, unit)]
        candidates = [
            c
            for c in value_types.find(value_type, page.text, unit=unit, **options)
            if not skip(value_type, c.value)
        ]
        _labelled_pairs(page, value_type, fitting, candidates, pairs, unassigned)
        # Without a label, the value could belong to any field of its type.
        if value_type in SELF_EVIDENT_TYPES and len({s.id for s in fitting}) == 1:
            rank = _DIRECTION_RANK["unlabelled"]
            for c in candidates:
                if not page.in_area(c.start, c.end, fitting[0].area):
                    continue
                key = (TIER_UNLABELLED, rank, 0, 0.0, 0.0, c.start)
                label = Label("", "unlabelled", c.start, c.start)
                pairs.append((key, fitting[0], c, label, None))
    for spec in specs:
        for rule_id, pattern, group in spec.patterns:
            started = time.perf_counter()
            pairs += _pattern_pairs(page, spec, rule_id, pattern, group, skip, options)
            seconds = time.perf_counter() - started
            if slow and seconds > SLOW_PATTERN_SECONDS:
                slow(rule_id, seconds)
    return _assign(page, pairs), _unassigned(unassigned)


def _labelled_pairs(page, value_type, fitting, candidates, pairs, unassigned):
    """Add a pair for every label of a candidate that names one of the fitting
    fields to pairs, and the labels no field took to unassigned."""
    cache = {}
    # Every line starts a word value, so for words the line above is the label
    # (no table of values to look through: "Herrn" above "Max Muster").
    starts = [] if value_type == "word" else [c.start for c in candidates]
    for c in candidates:
        if value_type == "number" and _digits(c) < MIN_NUMBER_DIGITS:
            continue
        # A name starts with a capital letter; "und Frau Muster" does not.
        if value_type == "word" and not c.source_text[:1].isupper():
            continue
        for label in page.labels_of(c.start, c.end, starts):
            # The same label stands next to many values: match it once.
            if label.text not in cache:
                norm, ends = normalize(label.text), _word_ends(label.text)
                cache[label.text] = [
                    (spec, _match(norm, spec, ends)) for spec in fitting
                ]
            matches = [(spec, m) for spec, m in cache[label.text] if m]
            for spec, (tier, score) in matches:
                if not page.in_area(c.start, c.end, spec.area):
                    continue
                key = (
                    tier,
                    _DIRECTION_RANK[label.direction],
                    label.rows_skipped,
                    score,
                    label.distance,
                    c.start,
                )
                rule_id = None if tier == TIER_HINT else spec.rule_id
                pairs.append((key, spec, c, label, rule_id))
            if not matches and value_type != "word":
                unassigned.append((label, value_type, c))


def _pattern_pairs(page, spec, rule_id, pattern, group, skip, options):
    """The pairs of a rule's regular expression: each match that is a whole value."""
    pairs = []
    for m in pattern.finditer(page.text):
        start, end = m.span(group)
        if start < 0:
            continue
        value = value_types.parse(
            spec.value_type, page.text[start:end], unit=spec.unit, **options
        )
        if (
            value is None
            or skip(spec.value_type, value)
            or not page.in_area(start, end, spec.area)
        ):
            continue
        c = value_types.Candidate(start, end, page.text[start:end], value)
        key = (TIER_EXACT, 0, 0, 0.0, 0.0, start)
        pairs.append((key, spec, c, Label("", "regex", start, start), rule_id))
    return pairs


def _assign(page, pairs):
    """Best pairs first. A value is the best suggestion of at most one field; it may
    still be an alternative of others. A field keeps up to MAX_ALTERNATIVES more."""
    pairs.sort(key=lambda p: p[0])
    taken = set()
    result = {}
    for key, spec, c, label, rule_id in pairs:
        chosen = result.setdefault(spec.id, [])
        span = (c.start, c.end)
        if len(chosen) > MAX_ALTERNATIVES or any(
            (s.start, s.end) == span for s in chosen
        ):
            continue
        if not chosen:
            if span in taken:
                continue
            taken.add(span)
        chosen.append(
            Suggestion(
                spec.id,
                c.value,
                c.source_text,
                c.start,
                c.end,
                page.box(c.start, c.end),
                label.text,
                label.direction,
                key[0],
                rule_id=rule_id,
                hint_id=_hint_of(normalize(label.text), spec)
                if key[0] == TIER_HINT
                else None,
            )
        )
    return {k: v for k, v in result.items() if v}


def _digits(candidate):
    return sum(c.isdigit() for c in candidate.value["value_text"])


def _unassigned(items):
    seen, result = set(), []
    for label, value_type, c in items:
        span = (c.start, c.end)
        if span in seen or len(label.text.split()) > 4:
            continue
        seen.add(span)
        result.append({"label": label.text, "value_type": value_type, **c.value})
        if len(result) >= MAX_UNASSIGNED:
            break
    return result


def _hint_of(norm, spec):
    """Id of the learned label that the (normalized) label is or contains."""
    for hint, hint_id in spec.hints.items():
        if hint and hint in norm:
            return hint_id
    return None


def label_of_value(page, value_type, value_text, near=None, **options):
    """The label next to a printed value, to learn from a confirmation; or None.

    The value is looked up in the text by what it reads as (the one closest to
    ``near`` if it is printed more than once), and labelled like any suggestion.
    """
    candidates = list(value_types.find(value_type, page.text, **options))
    matching = [c for c in candidates if c.value["value_text"] == value_text]
    if not matching:
        return None, None
    if near is not None:
        matching.sort(key=lambda c: abs(c.start - near))
    value = matching[0]
    labels = page.labels_of(value.start, value.end, [c.start for c in candidates])
    if not labels:
        return None, value
    return min(labels, key=lambda lb: _DIRECTION_RANK[lb.direction]), value
