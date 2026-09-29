"""Reading typed values (dates, amounts, IBANs ...) out of a document's text.

Pure functions without database access, so that they can be tested with plain
tables and reused wherever a value is suggested or confirmed. The text is the
one of the word list: words are separated by a space, columns by a tab, lines
by a newline and pages by a form feed. A value never crosses a tab, newline or
form feed.

find() yields every candidate of a type in a text, left to right; parse()
reads a text that must be exactly one value. Both return the columns of
int_filemanager.field_value (value_text plus the columns of the type), with
the currency as its ISO code.
"""

import os
import re
from dataclasses import dataclass
from datetime import date
from functools import cache

from babel.dates import get_month_names
from stdnum import numdb
from stdnum.eu import vat as stdnum_vat

from odoo.tools.mail import email_normalize

# Years outside this window are reading errors, not dates.
MIN_YEAR = 1900
MAX_YEARS_AHEAD = 30

DEFAULT_CURRENCIES = {"€": "EUR", "EUR": "EUR", "Euro": "EUR"}

# Characters OCR confuses with digits. Only used where the format demands a
# digit, and only kept when a check digit confirms the result.
_DIGIT_LOOKALIKES = str.maketrans("OoDQIl|SsBZG", "000011155826")

# Units written in more than one way; the first spelling is the canonical one.
_UNIT_SPELLINGS = [
    ("ct", "cent", "cents", "ct."),
    ("eur", "€", "euro"),
    ("kwh",),
    ("m³", "m3", "cbm"),
    ("monat", "mon.", "mtl.", "month"),
    ("jahr", "a", "year"),
]

_DURATION_UNITS = {
    "days": ("tag", "tage", "tagen", "day", "days"),
    "weeks": ("woche", "wochen", "week", "weeks"),
    "months": ("monat", "monate", "monaten", "month", "months"),
    "years": ("jahr", "jahre", "jahren", "year", "years"),
}


@dataclass(frozen=True)
class Candidate:
    start: int
    end: int
    source_text: str
    value: dict


# -- numbers ------------------------------------------------------------------

# A group separator is "." or "," (or a non-breaking/thin space in digital
# documents), never a plain space: in tables a plain space stands between two
# numbers as often as inside one.
_NUMBER = r"\d{1,3}(?:[.,\u00a0\u202f']\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
_MINUS = "-\u2212"


def parse_number(text):
    """Return the number written in text, or None.

    Two different separators: the last one is the decimal separator (the rule
    of base_import's _infer_separators). One kind used several times: it
    groups thousands. A single "," is decimal (German); a single "." followed
    by exactly three digits groups thousands, otherwise it is decimal.
    """
    text = text.strip()
    sign = -1 if text[:1] in _MINUS or text[-1:] in _MINUS else 1
    text = text.strip(_MINUS + "+").replace("\u00a0", "").replace("\u202f", "")
    text = text.replace("'", "")
    if not re.fullmatch(r"\d[\d.,]*", text) or not text[-1].isdigit():
        return None
    # More digits than a float holds exactly are no amount or quantity.
    if sum(c.isdigit() for c in text) > 15:
        return None
    seps = [c for c in text if c in ".,"]
    group = decimal = None
    if len(set(seps)) == 2:
        decimal = seps[-1]
        if seps.count(decimal) != 1:
            return None
        group = "," if decimal == "." else "."
    elif len(seps) > 1:
        group = seps[0]
    elif seps == [","] or (seps == ["."] and len(text.split(".")[1]) != 3):
        decimal = seps[0]
    elif seps:
        group = "."
    integer = text.split(decimal)[0] if decimal else text
    if group:
        # Groups of three after the first, or it is no grouping at all.
        parts = integer.split(group)
        if not 1 <= len(parts[0]) <= 3 or any(len(p) != 3 for p in parts[1:]):
            return None
        text = text.replace(group, "")
    if decimal:
        text = text.replace(decimal, ".")
    return sign * float(text)


def _format_number(number, decimals=0):
    """Plain decimal notation without exponent, keeping at least decimals."""
    text = f"{number:.6f}".rstrip("0")
    head, _dot, tail = text.partition(".")
    tail = tail.ljust(decimals, "0")
    return f"{head}.{tail}" if tail else head


# -- dates --------------------------------------------------------------------


def _month_names():
    names = {}
    for locale in ("de", "en"):
        for width, context in (
            ("wide", "format"),
            ("abbreviated", "format"),
            ("abbreviated", "stand-alone"),
        ):
            for month, name in get_month_names(width, context, locale).items():
                names[name.casefold().rstrip(".")] = month
    return names


_MONTHS = _month_names()
_MONTH_RE = "|".join(sorted(map(re.escape, _MONTHS), key=len, reverse=True))

# Day and month first (German order); the year may be missing in the first
# date of a period ("01.01. - 31.12.2024").
_NUMERIC_DATE = (
    r"(?P<d{n}>\d{{1,2}})(?P<s{n}>[./-])(?P<m{n}>\d{{1,2}})(?P=s{n})"
    r"(?P<y{n}>\d{{4}}|\d{{2}}){opt}"
)
_ISO_DATE = r"(?P<iy{n}>\d{{4}})-(?P<im{n}>\d{{2}})-(?P<id{n}>\d{{2}})"
_NAMED_DATE = (
    r"(?P<nd{n}>\d{{1,2}})\.?[ ]?(?P<nm{n}>" + _MONTH_RE + r")\.?[ ]?(?P<ny{n}>\d{{4}})"
)


def _date_re(n, year_optional=False):
    numeric = _NUMERIC_DATE.format(n=n, opt="?" if year_optional else "")
    return f"(?:{_ISO_DATE.format(n=n)}|{_NAMED_DATE.format(n=n)}|{numeric})"


def _year(text, today):
    year = int(text)
    if len(text) == 2:
        year += 2000 if 2000 + year <= today.year + 10 else 1900
    return year


def _date_from(match, n, today, year=None):
    """The date of the n-th date group of match, or None when it is no date."""
    group = match.groupdict()
    try:
        if group.get(f"iy{n}"):
            day, month = int(group[f"id{n}"]), int(group[f"im{n}"])
            year = int(group[f"iy{n}"])
        elif group.get(f"nm{n}"):
            day, month = int(group[f"nd{n}"]), _MONTHS.get(group[f"nm{n}"].casefold())
            year = int(group[f"ny{n}"])
        else:
            day, month = int(group[f"d{n}"]), int(group[f"m{n}"])
            if group.get(f"y{n}"):
                year = _year(group[f"y{n}"], today)
            elif year is None:
                return None
        result = date(year, month, day)
    except (TypeError, ValueError):
        return None
    if not MIN_YEAR <= result.year <= today.year + MAX_YEARS_AHEAD:
        return None
    return result


# -- units --------------------------------------------------------------------


def _unit_re(unit):
    """Pattern for unit in any of its spellings ("ct/kWh" also as "Cent / kWh")."""
    parts = []
    for part in unit.split("/"):
        key = part.strip().lower()
        spellings = next((s for s in _UNIT_SPELLINGS if key in s), (key,))
        parts.append(
            "(?:"
            + "|".join(sorted(map(re.escape, spellings), key=len, reverse=True))
            + ")"
        )
    return r"[ ]?/[ ]?".join(parts)


def _duration_unit(word):
    word = word.lower()
    return next(
        (unit for unit, words in _DURATION_UNITS.items() if word in words), None
    )


_DURATION = (
    r"(?P<n>\d{1,3})[ ]?(?P<u>"
    + "|".join(
        sorted(
            (re.escape(w) for words in _DURATION_UNITS.values() for w in words),
            key=len,
            reverse=True,
        )
    )
    + r")(?![\w])"
)


# -- check-digit types --------------------------------------------------------


@cache
def _iban_formats():
    """Country code -> structure of the account part, e.g. "DE" -> "8!n10!n".

    stdnum.iban cannot be used inside Odoo: Odoo's import hook for stdnum
    (odoo/_monkeypatches) replaces the package's loader, and importlib.resources
    then fails to open the iban.dat that stdnum.iban reads on import. The same
    file is read here by its path.
    """
    path = os.path.join(os.path.dirname(numdb.__file__), "iban.dat")
    with open(path, encoding="utf-8") as f:
        db = numdb.read(f)
    formats = {}
    for length, low, _high, props, _children in db.prefixes:
        if length == 2 and "bban" in props:
            formats[low] = props["bban"]
    return formats


def _iban_structure(country):
    """(length, kind) parts of the account part; kind n = digit, a = letter."""
    spec = _iban_formats().get(country.upper(), "")
    return [(int(n), kind) for n, kind in re.findall(r"(\d+)!?([nac])", spec)]


def _iban_is_valid(number):
    """Same checks as stdnum.iban.is_valid: country format and check digits."""
    structure = _iban_structure(number[:2])
    if not structure or not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]+", number):
        return False
    kinds = {"n": "[0-9]", "a": "[A-Z]", "c": "[A-Z0-9]"}
    bban = "".join(f"{kinds[kind]}{{{n}}}" for n, kind in structure)
    if not re.fullmatch(bban, number[4:]):
        return False
    return int("".join(str(int(c, 36)) for c in number[4:] + number[:4])) % 97 == 1


def _iban_digit_positions(country):
    """Positions of an IBAN of country (counted from 0) that must be digits."""
    positions, index = {2, 3}, 4
    for length, kind in _iban_structure(country):
        if kind == "n":
            positions.update(range(index, index + length))
        index += length
    return positions


def _repair_iban(compact):
    digits = _iban_digit_positions(compact[:2])
    return "".join(
        c.translate(_DIGIT_LOOKALIKES) if i in digits else c
        for i, c in enumerate(compact)
    )


def _prefixes(text):
    """text and its prefixes at spaces, longest first: a value followed by an
    unrelated word ("DE89 3704 ... 00 BIC") is found once that word is cut."""
    cut = len(text)
    while cut > 0:
        yield text[:cut]
        cut = text.rfind(" ", 0, cut)


# -- the types ----------------------------------------------------------------


class _Context:
    def __init__(self, unit, currencies, default_currency, default_country, today):
        self.unit = unit
        self.currencies = currencies or DEFAULT_CURRENCIES
        self.default_currency = default_currency
        self.default_country = default_country
        self.today = today or date.today()


# Every finder yields (start, end, value) for the valid matches in
# text[pos:endpos]. The boundaries keep a value from starting or ending in the
# middle of a word or number.
_LEFT = r"(?<![\w,/-])(?<!\d\.)"


def _find_number(text, pos, endpos, ctx):
    # Numbers printed in groups ("6 357 507 591", "44 450 7-5 148 621") before
    # single tokens ("R-2024-001", "4711/2"); every value holds a digit.
    pattern = re.compile(
        _LEFT
        + r"(?:\d{1,4}(?:-\d{1,4})?(?:[ ]\d{1,4}(?:-\d{1,4})?){1,6}(?![\w,]|[.,]\d)"
        + r"|(?=[\w\-/.]*\d)[A-Za-z0-9](?:[A-Za-z0-9\-/.]*[A-Za-z0-9])?(?![\w\-/]))"
    )
    for m in pattern.finditer(text, pos, endpos):
        # A date is not a number, though it looks like one ("29.01.2019").
        if _DATE_TOKEN.fullmatch(m.group()):
            continue
        yield m.start(), m.end(), {"value_text": m.group().replace(" ", "")}


_DATE_TOKEN = re.compile(_date_re(1))


def _find_word(text, pos, endpos, ctx):
    # Up to five words of one line and column, starting with a letter: a
    # name such as a tariff or a person. Longer or freer texts need a regular
    # expression. A value may start at every word, so that the words in front
    # of it stay free to be its label ("Herrn Max Muster": "Herrn", "Max Muster").
    pattern = re.compile(r"(?<!\w)(?=([^\W\d_][\w\-&+.']*(?:[ ][\w\-&+.']+){0,4}))")
    for m in pattern.finditer(text, pos, endpos):
        value = m.group(1).rstrip(".")
        yield m.start(), m.start() + len(value), {"value_text": value}


# A date is not part of an identifier joined by dashes ("INV-01-02-2024-A"). A
# letter right next to it is allowed: text taken from PDFs often runs a date into
# the next word ("01.02.2024Seite 1") or a time ("2024-01-01T12:00").
_DATE_LEFT = r"(?<![\d./,])(?<![A-Za-z]-)"
_DATE_RIGHT = r"(?!\d|[-/][A-Za-z]|[.,]\d)"


def _find_date(text, pos, endpos, ctx):
    pattern = re.compile(_DATE_LEFT + _date_re(1) + _DATE_RIGHT, re.IGNORECASE)
    for m in pattern.finditer(text, pos, endpos):
        value = _date_from(m, 1, ctx.today)
        if value:
            yield (
                m.start(),
                m.end(),
                {
                    "value_text": value.isoformat(),
                    "value_date": value,
                },
            )


def _find_period(text, pos, endpos, ctx):
    range_re = (
        _DATE_LEFT
        + _date_re(1, year_optional=True)
        + r"[ ]?(?:-|–|bis(?:[ ]zum)?|to|until)[ ]?"
        + _date_re(2)
        + _DATE_RIGHT
    )
    pattern = re.compile(f"(?:{range_re})|(?<![\\w.,])(?:{_DURATION})", re.IGNORECASE)
    for m in pattern.finditer(text, pos, endpos):
        if m.group("n"):
            yield (
                m.start(),
                m.end(),
                {
                    "value_text": f"{int(m.group('n'))} {_duration_unit(m.group('u'))}",
                    "value_number": float(m.group("n")),
                    "unit": _duration_unit(m.group("u")),
                },
            )
            continue
        end = _date_from(m, 2, ctx.today)
        start = end and _date_from(m, 1, ctx.today, year=end.year)
        # Without its own year the start lies before the end: in the year before
        # when it would come later (01.12. - 28.02.) or does not exist (29.02.).
        if end and not m.group("y1") and m.group("d1") and (not start or start > end):
            start = _date_from(m, 1, ctx.today, year=end.year - 1)
        if start and end and start <= end:
            yield (
                m.start(),
                m.end(),
                {
                    "value_text": f"{start.isoformat()} - {end.isoformat()}",
                    "value_date": start,
                    "value_date_to": end,
                },
            )


def _find_amount(text, pos, endpos, ctx):
    markers = "|".join(sorted(map(re.escape, ctx.currencies), key=len, reverse=True))
    pattern = re.compile(
        r"(?<![\w.,/])"
        rf"(?:(?P<c1>{markers})(?:/\w+\.?)?[ ]?)?"
        rf"(?P<neg>[{_MINUS}])?(?P<num>{_NUMBER})(?P<neg2>-(?![\d]))?"
        rf"(?:[ ]?(?P<c2>{markers}))?"
        r"(?![\w]|[.,]\d)"
    )
    for m in pattern.finditer(text, pos, endpos):
        marker = m.group("c1") or m.group("c2")
        number = parse_number(m.group("num"))
        decimals = re.search(r"[.,](\d+)$", m.group("num"))
        # A bare number counts only with cents, or it would take any count
        # or reference printed near the label.
        if number is None or not (marker or (decimals and len(decimals.group(1)) == 2)):
            continue
        if m.group("neg") or m.group("neg2"):
            number = -number
        currency = ctx.currencies.get(marker) if marker else ctx.default_currency
        if not currency:
            continue
        yield (
            m.start(),
            m.end(),
            {
                "value_text": f"{_format_number(number, 2)} {currency}",
                "value_number": number,
                "currency_code": currency,
            },
        )


def _find_quantity(text, pos, endpos, ctx):
    unit = _unit_re(ctx.unit)
    pattern = re.compile(
        rf"(?<![\w.,/])(?:(?P<u1>{unit})[ ]?)?(?P<num>[{_MINUS}]?(?:{_NUMBER}))"
        rf"(?:[ ]?(?P<u2>{unit}))?(?![\w]|[.,]\d|[ ]?/)",
        re.IGNORECASE,
    )
    for m in pattern.finditer(text, pos, endpos):
        number = parse_number(m.group("num"))
        if number is None or not (m.group("u1") or m.group("u2")):
            continue
        yield (
            m.start(),
            m.end(),
            {
                "value_text": f"{_format_number(number)} {ctx.unit}",
                "value_number": number,
                "unit": ctx.unit,
            },
        )


def _find_iban(text, pos, endpos, ctx):
    # Letters stand in for digits where OCR misread them; the check digits
    # decide which reading is an IBAN. One character per repetition, so that a
    # long run of letters cannot be split in many ways.
    pattern = re.compile(
        r"(?<![A-Za-z0-9])[A-Z]{2}[ ]?[0-9OoIlSB]{2}(?:[ ]?[0-9A-Za-z]){11,30}"
        r"(?![A-Za-z0-9])"
    )
    for m in pattern.finditer(text, pos, endpos):
        for prefix in _prefixes(m.group()):
            compact = prefix.replace(" ", "")
            if len(compact) < 15:
                break
            for number in (compact.upper(), _repair_iban(compact).upper()):
                if _iban_is_valid(number):
                    yield m.start(), m.start() + len(prefix), {"value_text": number}
                    break
            else:
                continue
            break


def _find_vat(text, pos, endpos, ctx):
    pattern = re.compile(
        r"(?<![A-Za-z0-9])(?:[A-Z]{2}[ ]?)?[0-9A-Zloi]"
        r"(?:[0-9A-Zloi]|[ .](?=[0-9A-Zloi])){6,16}"
        r"(?![A-Za-z0-9])"
    )
    for m in pattern.finditer(text, pos, endpos):
        for prefix in _prefixes(m.group()):
            number = _vat_value(prefix, ctx)
            if number:
                yield m.start(), m.start() + len(prefix), {"value_text": number}
                break


def _vat_value(text, ctx):
    compact = re.sub(r"[ .]", "", text)
    if len(compact) < 8 or not any(c.isdigit() for c in compact):
        return None
    if not compact[:2].isalpha():
        compact = ctx.default_country + compact
    head, body = compact[:2].upper(), compact[2:]
    # Austria prefixes its digits with a U, which must stay a letter.
    keep = 1 if head == "AT" else 0
    repaired = head + body[:keep] + body[keep:].translate(_DIGIT_LOOKALIKES)
    for number in (head + body.upper(), repaired.upper()):
        if stdnum_vat.is_valid(number):
            return stdnum_vat.compact(number)
    return None


def _find_email(text, pos, endpos, ctx):
    # OCR sometimes puts a space on either side of the @.
    pattern = re.compile(
        r"(?<![\w.%+-])[\w%+-]+(?:\.[\w%+-]+)*[ ]?@[ ]?"
        r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}"
        r"(?![\w-])"
    )
    for m in pattern.finditer(text, pos, endpos):
        address = email_normalize(m.group().replace(" ", ""))
        if address:
            yield m.start(), m.end(), {"value_text": address}


# No value is longer than this (a period with month names is about 45).
_LONGEST_VALUE = 200

_FINDERS = {
    "number": _find_number,
    "word": _find_word,
    "date": _find_date,
    "period": _find_period,
    "amount": _find_amount,
    "quantity": _find_quantity,
    "iban": _find_iban,
    "vat": _find_vat,
    "email": _find_email,
}


def find(
    value_type,
    text,
    pos=0,
    endpos=None,
    *,
    unit=None,
    currencies=None,
    default_currency="EUR",
    default_country="DE",
    today=None,
):
    """Yield the valid candidates of value_type that start in text[pos:endpos].

    A candidate may end after endpos: the window only says where to look, so
    that a value is never cut short where the window happens to end.

    :param unit: the field's unit, required for a quantity
    :param currencies: currency marker as printed (symbol or code) -> ISO code
    :param default_currency: ISO code of an amount printed without currency
    :param default_country: country of a VAT number printed without prefix
    :param today: reference for two-digit years and implausible dates
    """
    if value_type == "quantity" and not unit:
        raise ValueError("a quantity needs a unit")
    ctx = _Context(unit, currencies, default_currency, default_country, today)
    endpos = len(text) if endpos is None else endpos
    # Look a little beyond the window; a value touching that limit might go on.
    limit = min(len(text), endpos + _LONGEST_VALUE)
    for start, end, value in _FINDERS[value_type](text, pos, limit, ctx):
        if start >= endpos:
            break
        if end < limit or limit == len(text):
            yield Candidate(start, end, text[start:end], value)


def parse(value_type, text, **options):
    """Return the value when all of text is one value of value_type, else None.

    Used to check again on the server what a user confirmed or typed.
    """
    # Only spaces are tidied: a tab or line break inside means two values.
    text = re.sub(r"[ \u00a0]+", " ", text).strip(" \u00a0")
    for candidate in find(value_type, text, **options):
        if candidate.start == 0 and candidate.end == len(text):
            return candidate.value
    return None
