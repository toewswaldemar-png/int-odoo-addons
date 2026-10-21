import re
from bisect import bisect_left, bisect_right
from itertools import accumulate

from odoo import api, fields, models
from odoo.tools import SQL

# The hit that the list shows in the row of a file; the others are loaded in blocks (see the document).
HITS_PER_FILE = 1
SNIPPET_RADIUS = 70
# Words of a page handed to the PDF viewer to mark, and the longest one.
TERMS_PER_PAGE = 8
TERM_LENGTH = 60
# Around a hit word in ``ts_headline``: control characters, so a page with them gets no excerpt.
MARK_START, MARK_END = "\x02", "\x03"
MARKED = re.compile(f"{MARK_START}(.*?){MARK_END}", re.DOTALL)
FOLDED_CAPITALS = {"Ä": "Ae", "Ö": "Oe", "Ü": "Ue"}
FOLDED_SMALL = (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"))


def folded(expression):
    """Fold umlauts in SQL for index and search alike; capitals first as ``lower`` follows ``LC_CTYPE``."""
    capitals = f"replace(replace(replace({expression}, 'Ä', 'Ae'), 'Ö', 'Oe'), 'Ü', 'Ue')"
    return (
        f"replace(replace(replace(replace(lower({capitals}), 'ä', 'ae'), 'ö', 'oe'), 'ü', 'ue'),"
        " 'ß', 'ss')"
    )


def _folded_length(char):
    """How many characters ``folded`` makes of one character, in Python."""
    text = FOLDED_CAPITALS.get(char, char).lower()
    for small, plain in FOLDED_SMALL:
        text = text.replace(small, plain)
    return len(text)


def _strip_marks(headline):
    """The text of a headline without the marks, and ``[(start, end)]`` of the marked words in it."""
    pieces, spans, length, last = [], [], 0, 0
    for match in MARKED.finditer(headline):
        before, word = headline[last : match.start()], match.group(1)
        pieces += [before, word]
        spans.append((length + len(before), length + len(before) + len(word)))
        length += len(before) + len(word)
        last = match.end()
    pieces.append(headline[last:])
    return "".join(pieces), spans


def _excerpt(content, headline):
    """The page text and the places of the found words in it (the headline's are of the folded text).

    :return: ``(text, [(start, end)])``; the folded text if the foldings of database and Python
        differ, no spans if the marks cannot be told from the text
    """
    if MARK_START in content or MARK_END in content:
        return "", []
    plain, spans = _strip_marks(headline)
    ends = list(accumulate(1 if char < "\x80" else _folded_length(char) for char in content))
    if not ends or ends[-1] != len(plain):
        return plain, spans
    # ``ends[i]`` is where the folded text of character ``i`` stops.
    return content, [(bisect_right(ends, start), bisect_left(ends, end) + 1) for start, end in spans]


def _snippet(text, spans):
    """The part of ``text`` around its first marked word, as ``[[string, is_match], ...]``."""
    if not spans:
        return []
    first_start, first_end = spans[0]
    start = max(first_start - SNIPPET_RADIUS, 0)
    end = min(first_end + SNIPPET_RADIUS, len(text))
    while 0 < start < first_start and not text[start - 1].isspace():
        start += 1
    while first_end < end < len(text) and not text[end].isspace():
        end -= 1
    parts, position = [], start
    for span_start, span_end in spans:
        if span_start >= start and span_end <= end:
            parts += [[text[position:span_start], 0], [text[span_start:span_end], 1]]
            position = span_end
    parts.append([text[position:end], 0])
    parts = [[re.sub(r"\s+", " ", string), is_match] for string, is_match in parts]
    if start > 0:
        parts[0][0] = "… " + parts[0][0].lstrip()
    if end < len(text):
        parts[-1][0] = parts[-1][0].rstrip() + " …"
    return [part for part in parts if part[0]]


def _terms(text, spans):
    """The marked words as they are written, once each: what the PDF viewer is asked to mark."""
    terms, seen = [], set()
    for start, end in spans:
        word = text[start:end]
        if word.casefold() in seen or len(word) > TERM_LENGTH or not word.strip():
            continue
        seen.add(word.casefold())
        terms.append(word)
        if len(terms) == TERMS_PER_PAGE:
            break
    return terms


class IntFilemanagerTextPage(models.Model):
    """The text of one page of a file; users have no access right, documents reach it by checksum."""

    _name = "int.filemanager.text.page"
    _description = "Filemanager text of a page"
    _order = "text_id, page"
    # Millions of rows.
    _log_access = False

    text_id = fields.Many2one("int.filemanager.text", required=True, ondelete="cascade")
    page = fields.Integer(required=True)
    content = fields.Text(prefetch=False)
    # A picture and (almost) no text; only the recognition reads these pages.
    scan = fields.Boolean()

    _page_per_text = models.UniqueIndex(
        "(text_id, page)", "A text has one entry per page."
    )
    _scan_index = models.Index("(text_id, page) WHERE scan")
    _content_index = models.Index(f"USING gin (to_tsvector('german', {folded('content')}))")

    @api.model
    def _content_hits(self, checksums, words, offset=0, limit=HITS_PER_FILE):
        """Pages with a hit, with an excerpt of each, for the words (as the document search finds them).

        Does not check access: the caller passes the checksums of the files the user may read.

        :param words: what the user typed; each is a ``websearch`` expression
        :param offset: how many of the pages with a hit (by page number) are skipped
        :param limit: how many pages are given, per file
        :return: ``{checksum: {"hits": [{"page", "parts", "terms"}], "total": n}}``, ``total`` = all
            pages of the file with a hit
        """
        checksums = tuple(set(checksums))
        if not checksums or not words:
            return {}
        Text = self.env["int.filemanager.text"]
        self.flush_model()
        Text.flush_model(["checksum"])
        Text._use_search_memory()
        # In brackets: ``@@`` and ``||`` bind equally strong, from the left.
        query = SQL(
            "(%s)",
            SQL(" || ").join(
                SQL("websearch_to_tsquery('german', %s)", SQL(folded("%s::text"), word))
                for word in words
            ),
        )
        # For a word on nearly every page PostgreSQL prefers a table scan to the index (20 s for
        # 50,000 pages instead of 0.3 s); keep this query off it.
        cr = self.env.cr
        cr.execute(SQL("SELECT current_setting('enable_seqscan')"))
        [[seqscan]] = cr.fetchall()
        cr.execute(SQL("SELECT set_config('enable_seqscan', 'off', true)"))
        try:
            rows = self._execute_hits(checksums, query, offset, limit)
        finally:
            cr.execute(SQL("SELECT set_config('enable_seqscan', %s, true)", seqscan))
        found = {}
        for checksum, page, total, content, headline in rows:
            text, spans = _excerpt(content, headline)
            entry = found.setdefault(checksum, {"hits": [], "total": total})
            entry["hits"].append(
                {"page": page, "parts": _snippet(text, spans), "terms": _terms(text, spans)}
            )
        return found

    @api.model
    def _execute_hits(self, checksums, query, offset, limit):
        """The rows of ``_content_hits``: ``(checksum, page, pages with a hit, text, headline)``."""
        return self.env.execute_query(
            SQL(
                """
                SELECT hit.checksum, hit.page, hit.total, page.content,
                       ts_headline('german', %(folded)s, %(query)s, %(options)s)
                  FROM (
                        SELECT page.id, text.checksum, page.page,
                               row_number() OVER (PARTITION BY text.checksum ORDER BY page.page) AS rank,
                               count(*) OVER (PARTITION BY text.checksum) AS total
                          FROM int_filemanager_text_page page
                          JOIN int_filemanager_text text ON text.id = page.text_id
                         WHERE text.checksum IN %(checksums)s
                           AND to_tsvector('german', %(folded)s) @@ %(query)s
                       ) hit
                  JOIN int_filemanager_text_page page ON page.id = hit.id
                 WHERE hit.rank > %(offset)s AND hit.rank <= %(until)s
                 ORDER BY hit.checksum, hit.page
                """,
                folded=SQL(folded("page.content")),
                query=query,
                options=f"HighlightAll=true, StartSel={MARK_START}, StopSel={MARK_END}",
                checksums=checksums,
                offset=offset,
                until=offset + limit,
            )
        )
