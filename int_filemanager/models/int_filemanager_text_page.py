from odoo import fields, models


def folded(expression):
    """SQL text that makes ``expression`` ready for the full text search: umlauts folded.

    ``Müller`` and ``Mueller`` become one word (the ``german`` configuration alone makes
    ``mull`` and ``muell``). The one place of the folding: the index and the search use it, so
    they cannot drift apart (the index would not be found). It must not depend on the locale of
    the database: ``lower`` follows ``LC_CTYPE`` and leaves ``Ü`` as it is in a database with
    ``LC_CTYPE C``, so the capitals are named. Only ``replace`` and ``lower`` (immutable).
    """
    capitals = f"replace(replace(replace({expression}, 'Ä', 'Ae'), 'Ö', 'Oe'), 'Ü', 'Ue')"
    return (
        f"replace(replace(replace(replace(lower({capitals}), 'ä', 'ae'), 'ö', 'oe'), 'ü', 'ue'),"
        " 'ß', 'ss')"
    )


class IntFilemanagerTextPage(models.Model):
    """The text of one page of a file (a block of at most some KB for files without pages).

    Read by the search and by the administrator only: the users have no access right, the
    documents that point to the text by checksum carry the rules of their folders.
    """

    _name = "int.filemanager.text.page"
    _description = "Filemanager text of a page"
    _order = "text_id, page"
    # Millions of rows; nobody asks who made or changed a page.
    _log_access = False

    text_id = fields.Many2one("int.filemanager.text", required=True, ondelete="cascade")
    page = fields.Integer(required=True)
    # Not read along with the other fields: it is large.
    content = fields.Text(prefetch=False)

    # Also the index of ``text_id`` (its first column) for the cascade and the lookups.
    _page_per_text = models.UniqueIndex(
        "(text_id, page)", "A text has one entry per page."
    )
    _content_index = models.Index(f"USING gin (to_tsvector('german', {folded('content')}))")
