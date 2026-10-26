from collections import defaultdict
from collections.abc import Collection

from odoo import api, fields, models
from odoo.fields import Domain


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
    # The links to contacts as one field, as ``message_partner_ids`` shows the followers.
    partner_ids = fields.Many2many(
        "res.partner",
        string="Contacts",
        compute="_compute_partner_ids",
        inverse="_inverse_partner_ids",
        search="_search_partner_ids",
    )

    @api.depends("link_ids.res_model", "link_ids.res_id")
    @api.depends_context("uid")
    def _compute_access_via_record(self):
        """The Python side of the rule.

        ``_check_access`` evaluates the rules with ``filtered_domain`` on ``sudo()`` records, the
        search below builds the same as a query. The user is put back in both: the records of
        the other models must be those that the user reads, not all of them.
        """
        self.access_via_record = False
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
        for res_model in self.env["int.filemanager.link"]._linkable_models():
            query = (
                self.env[res_model].with_user(self.env.uid).with_context(active_test=False)._search([])
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

    @api.depends("link_ids.res_model", "link_ids.res_id")
    @api.depends_context("uid", "allowed_company_ids")
    def _compute_partner_ids(self):
        linked = self._linked_partners()
        for document in self:
            document.partner_ids = linked[document.id]

    def _inverse_partner_ids(self):
        """Tie the documents to the contacts that were added, untie those that were taken away.

        The links do the rest: the rights, the notes. Links to other models stay as they are.
        Archived contacts are compared like the field reads them (the core hides them in every
        many2many), so that the links to those the user does not see stay.
        """
        linked = self._linked_partners()
        active_test = self.env.context.get("active_test", True)
        to_create, to_unlink = [], self.env["int.filemanager.link"]
        for document in self:
            previous = linked[document.id]
            if active_test:
                previous = previous.filtered("active")
            to_create += [
                {"document_id": document.id, "record_ref": f"res.partner,{partner.id}"}
                for partner in document.partner_ids - previous
            ]
            removed = (previous - document.partner_ids).ids
            to_unlink += document.link_ids.filtered(
                lambda link: link.res_model == "res.partner" and link.res_id in removed
            )
        to_unlink.unlink()
        self.env["int.filemanager.link"].create(to_create)

    def _search_partner_ids(self, operator, value):
        """The documents linked to a contact, or to none (``False`` among the ids).

        The ORM turns a typed name into ``any`` and ``= False`` into ``in {False}`` before it gets
        here, and answers the negative operators from these. As in the core, ``False`` among
        other ids means "one of them, or no contact at all".
        """
        if operator in Domain.NEGATIVE_OPERATORS:
            return NotImplemented
        without = operator == "in" and isinstance(value, Collection) and False in value
        if without:
            value = [res_id for res_id in value if res_id]
        domain = Domain.FALSE
        if value:
            partners = self.env["res.partner"].with_context(active_test=False)
            found = partners._search(value if operator == "any" else Domain("id", operator, value))
            domain = Domain(
                "link_ids", "any", [("res_model", "=", "res.partner"), ("res_id", "in", found)]
            )
        if without:
            domain |= Domain("link_ids", "not any", [("res_model", "=", "res.partner")])
        return domain

    def _linked_partners(self):
        """The contacts that the user reads and the document is linked to.

        :return: the contacts by id of the document
        :rtype: dict
        """
        res_ids = {
            document.id: [link.res_id for link in document.link_ids if link.res_model == "res.partner"]
            for document in self
        }
        Partner = self.env["res.partner"]
        readable = Partner.browse({res_id for ids in res_ids.values() for res_id in ids}).exists()
        readable = readable._filtered_access("read")
        return {document_id: Partner.browse(ids) & readable for document_id, ids in res_ids.items()}

    def _documents_referenced(self):
        """The documents that are linked to a record, besides what the core names."""
        linked = self.env["int.filemanager.link"].sudo().search([("document_id", "in", self.ids)])
        return super()._documents_referenced() | self.browse(linked.document_id.ids)
