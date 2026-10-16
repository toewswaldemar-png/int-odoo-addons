from collections import defaultdict

from odoo import fields, models
from odoo.fields import Domain

from .int_filemanager_link import FOLDER_ONLY_KEY


class IntFilemanagerDocument(models.Model):
    """The second way to see a document: through a record it is linked to.

    The folder rule stays as it is. A second rule of the group of all internal users says
    "``access_via_record``"; the rules of one group add up, so a document is seen when the
    folder shows it **or** a linked record may be read, and the rule for the companies still
    cuts both. The field exists for this rule only.
    """

    _inherit = "int.filemanager.document"

    link_ids = fields.One2many("int.filemanager.link", "document_id", string="Links")
    access_via_record = fields.Boolean(
        string="Seen through a linked record",
        compute="_compute_access_via_record",
        search="_search_access_via_record",
        exportable=False,
    )

    def _compute_access_via_record(self):
        """The Python side of the rule.

        ``_check_access`` evaluates the rules with ``filtered_domain`` on ``sudo()`` records, the
        search below builds the same as a query. The user is put back in both: the records of
        the other models must be those that the user reads, not all of them.
        """
        self.access_via_record = False
        if self.env.context.get(FOLDER_ONLY_KEY):
            return
        wanted = defaultdict(set)
        for link in self.link_ids:
            if link.res_model in self.env:
                wanted[link.res_model].add(link.res_id)
        readable = {}
        for res_model, res_ids in wanted.items():
            records = self.env[res_model].with_user(self.env.uid).with_context(active_test=False)
            readable[res_model] = set(records.browse(res_ids).exists()._filtered_access("read").ids)
        for document in self:
            document.access_via_record = any(
                link.res_id in readable.get(link.res_model, ()) for link in document.link_ids
            )

    def _search_access_via_record(self, operator, value):
        """Documents linked to a record that the user reads, as ``ir.attachment`` searches.

        Odoo optimizes the domain of a rule with ``self.sudo()`` (``_search`` in ``models.py``):
        the records of the other model are searched as the user again, or the records of other
        companies would be found. ``any!`` skips the rule of the link, which looks at the
        document and so at this rule.
        """
        if operator not in ("=", "!=") or not isinstance(value, bool):
            return NotImplemented
        parts = []
        if not self.env.context.get(FOLDER_ONLY_KEY):
            for res_model in self.env["int.filemanager.link"]._linkable_models():
                query = (
                    self.env[res_model]
                    .with_user(self.env.uid)
                    .with_context(active_test=False)
                    ._search([])
                )
                parts.append(
                    Domain(
                        "link_ids",
                        "any!",
                        [("res_model", "=", res_model), ("res_id", "in", query)],
                    )
                )
        domain = Domain.OR(parts)
        return domain if (operator == "=") == value else ~domain
