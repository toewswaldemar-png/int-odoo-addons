from odoo import api, fields, models
from odoo.fields import Domain
from odoo.tools import SQL

from .int_filemanager_text import TEXT_CRON_XMLID
from .int_filemanager_text_page import folded

# The context key with the words of the full text search (see ``content_hits``), the most words
# and the longest word that are used.
CONTENT_WORDS_KEY = "int_filemanager_words"
CONTENT_WORDS_MAX = 10
CONTENT_WORD_LENGTH = 200
# The hits that the list loads at a time for one file (``get_content_hits``), and the most that
# one call may ask for.
CONTENT_BLOCK = 20
CONTENT_BLOCK_MAX = 50


class IntFilemanagerDocument(models.Model):
    _inherit = "int.filemanager.document"

    # The text inside the file, for the search only (the pages are in ``int.filemanager.text``).
    # Not "Content": that is the label of the binary field above, Odoo warns of two alike.
    content_search = fields.Char(
        string="Full text",
        compute="_compute_content_search",
        search="_search_content_search",
        exportable=False,
    )
    # Where the words of the full text search are, for the column of the list: set only while
    # the list is searched by them (the search puts them in the context, see the search view).
    content_hits = fields.Json(
        string="Found in the text",
        compute="_compute_content_hits",
        exportable=False,
    )
    # How many pages of the file have the words (the badge of the list).
    content_hit_count = fields.Integer(
        string="Hits",
        compute="_compute_content_hits",
        exportable=False,
    )

    @api.depends("checksum", "preview_checksum")
    def _compute_viewer_pdf_checksum(self):
        # An office file has the preview instead.
        super()._compute_viewer_pdf_checksum()
        # sudo: int.filemanager.text: users cannot read the text rows; the checksum of the PDF is no
        # secret to whoever may read the document it belongs to
        Text = self.env["int.filemanager.text"].sudo()
        found = {
            row.checksum: row.ocr_checksum
            for row in Text.search_fetch(
                [("checksum", "in", self.mapped("checksum")), ("ocr_checksum", "!=", False)],
                ["checksum", "ocr_checksum"],
            )
        }
        for document in self:
            document.viewer_pdf_checksum = found.get(document.checksum) or document.viewer_pdf_checksum

    def _compute_content_search(self):
        self.content_search = False

    @api.model
    def _content_words(self, words):
        if isinstance(words, str):
            words = [words]
        elif not isinstance(words, (list, tuple)):
            words = []
        words = [word[:CONTENT_WORD_LENGTH] for word in words if isinstance(word, str) and word.strip()]
        return words[:CONTENT_WORDS_MAX]

    @api.depends_context(CONTENT_WORDS_KEY)
    def _compute_content_hits(self):
        """Compute the first page with a hit of each file, with an excerpt, and the number of hits.

        The words come from the context: the search view sets them from what was typed in the
        field "Full text". Whoever sets them by hand only gets excerpts of files they can read
        anyway (the field is read for readable documents), and no more than they could search.
        The words go with the hits: the list asks for the other hits with them.
        """
        words = self._content_words(self.env.context.get(CONTENT_WORDS_KEY) or [])
        found = self.env["int.filemanager.text.page"]._content_hits(self.mapped("checksum"), words)
        for document in self:
            entry = found.get(document.checksum)
            document.content_hits = {**entry, "words": words} if entry else False
            document.content_hit_count = entry["total"] if entry else 0

    def get_content_hits(self, words, offset=0, limit=CONTENT_BLOCK):
        """Return a block of the pages of this file that have the words, for the list that shows all of them.

        Public (the list calls it), so it checks the right itself: only a file that the user may
        read gives hits, and no more than the search would find.

        :param words: the words of the search (see ``_content_words``)
        :param offset: how many of the pages with a hit (by page number) are skipped
        :param limit: how many are given, at most ``CONTENT_BLOCK_MAX``
        :return: ``{"hits": [{"page", "parts", "terms"}], "total": n}``
        """
        self.ensure_one()
        self.check_access("read")
        offset = offset if isinstance(offset, int) and offset > 0 else 0
        limit = min(limit, CONTENT_BLOCK_MAX) if isinstance(limit, int) and limit > 0 else CONTENT_BLOCK
        found = self.env["int.filemanager.text.page"]._content_hits(
            [self.checksum], self._content_words(words), offset, limit
        )
        return found.get(self.checksum, {"hits": [], "total": 0})

    def _search_content_search(self, operator, value):
        """Search the documents whose file has these words in it.

        The syntax is ``websearch`` (quotes, ``-``, ``or``). It matches words, not letters:
        ``Mueller`` finds ``Müller`` and the other way round, ``Rechnung`` finds ``Rechnungen``,
        ``Rechn`` finds nothing. A plural with an umlaut is another word: ``Haus`` does not find
        ``Häuser`` (the folding makes ``haeuser``, the stemmer cuts ``haeus``). A text belongs to a
        blob, so every document with the checksum is found; the rules of the folders still decide
        which of them the user sees, as the search runs over the documents. Equal checksum means
        equal content, so a hit in a folder the user cannot see gives nothing away.
        """
        if operator == "ilike" and isinstance(value, str):
            values = [value]
        elif operator == "in" and value and all(isinstance(item, str) for item in value):
            values = list(value)  # the ORM turns ``=`` into ``in``
        else:
            return NotImplemented
        domains = [Domain.custom(to_sql=self._content_sql(item)) for item in values if item.strip()]
        return Domain.OR(domains) if domains else Domain.TRUE

    @api.model
    def _content_sql(self, words):
        def to_sql(model, alias, query):
            model.env["int.filemanager.text"]._use_search_memory()
            return SQL(
                """
                %(checksum)s IN (
                    SELECT text.checksum
                      FROM int_filemanager_text_page page
                      JOIN int_filemanager_text text ON text.id = page.text_id
                     WHERE to_tsvector('german', %(content)s)
                           @@ websearch_to_tsquery('german', %(words)s))
                """,
                checksum=model._field_to_sql(alias, "checksum", query),
                content=SQL(folded("page.content")),
                words=SQL(folded("%s::text"), words),
            )

        return to_sql

    @api.model
    def _crons_after_preview(self):
        # The text of the old formats is read from the preview.
        return [*super()._crons_after_preview(), TEXT_CRON_XMLID]

    @api.model
    def _gc_lock_tables(self):
        # The recognized PDFs are blobs of the storage too: the garbage collector locks their table as well.
        return [*super()._gc_lock_tables(), self.env["int.filemanager.text"]._table]

    @api.model
    def _blobs_in_use(self, names):
        return super()._blobs_in_use(names) | self.env["int.filemanager.text"]._used_ocr_checksums(names)
