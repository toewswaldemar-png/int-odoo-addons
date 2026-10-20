import functools
from collections import defaultdict

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

# The rule that lets a user see a document through a record says False when this is set: the
# check "may this user pass the document on" wants to know about the folder only.
FOLDER_ONLY_KEY = "int_filemanager_folder_only"


class IntFilemanagerLink(models.Model):
    """A document tied to a record of another model (a contact, a repair order ...).

    Built like ``mail.activity`` and ``ir.attachment``: the name of the model and the id of the
    record, no foreign key. The database cannot cascade over it; ``int.filemanager.linkable``
    removes the links of a deleted record, and an autovacuum those that were left over.
    """

    _name = "int.filemanager.link"
    _description = "Filemanager link"
    _order = "id desc"

    document_id = fields.Many2one(
        "int.filemanager.document", required=True, index=True, ondelete="cascade"
    )
    res_model_id = fields.Many2one(
        "ir.model", string="Model", required=True, index=True, ondelete="cascade"
    )
    res_model = fields.Char(
        string="Model name",
        index=True,
        related="res_model_id.model",
        precompute=True,
        store=True,
        readonly=True,
    )
    res_id = fields.Many2oneReference(
        string="Record ID", model_field="res_model", required=True, index=True
    )
    # The same, as one field for the list of a document: the model and the record are chosen
    # together. Only for ``create``; a link is removed and made again, never changed.
    record_ref = fields.Reference(
        selection="_selection_record_ref",
        string="Record",
        compute="_compute_record_ref",
        readonly=False,
    )

    _record_index = models.Index("(res_model, res_id)")
    _document_record_uniq = models.Constraint(
        "UNIQUE(document_id, res_model_id, res_id)",
        "This document is already linked to this record.",
    )

    @api.model
    def _linkable_models(self):
        """The names of the models whose records can have documents."""
        return [
            name
            for name in self.env.registry.descendants(["int.filemanager.linkable"], "_inherit")
            if not self.env[name]._abstract
        ]

    @api.depends("res_model", "res_id")
    def _compute_record_ref(self):
        linkable = self._linkable_models()
        for link in self:
            # only what the list offers: a Reference field refuses any other model
            if link.res_model in linkable and link.res_id:
                link.record_ref = f"{link.res_model},{link.res_id}"
            else:
                link.record_ref = False

    @api.model
    def _selection_record_ref(self):
        models = self.env["ir.model"].sudo().search([("model", "in", self._linkable_models())])
        return [(model.model, model.name) for model in models]

    @api.model
    def default_get(self, fields):
        """No record from the context.

        The keys ``default_res_model`` and ``default_res_id`` are those of the attachments: a
        screen that is open for another record may carry them into the new line of a list. A
        link takes its record from the choice in the list only.
        """
        values = super().default_get(fields)
        for name in ("res_model", "res_model_id", "res_id", "record_ref"):
            values.pop(name, None)
        return values

    @api.model
    def _manageable(self, triples):
        """The (document id, model name, record id) the user may tie or untie.

        Whoever sees a document only through a record must not pass it on to other records:
        the folder has to show it to the user. And the record has to be one the user writes.
        """
        folder_only = self.env["int.filemanager.document"].with_context(**{FOLDER_ONLY_KEY: True})
        documents = folder_only.browse({triple[0] for triple in triples}).exists()
        by_folder = set(documents._filtered_access("read").ids)
        ids_by_model = defaultdict(set)
        for __, res_model, res_id in triples:
            ids_by_model[res_model].add(res_id)
        writable = {
            res_model: set(self.env[res_model].browse(res_ids).exists()._filtered_access("write").ids)
            for res_model, res_ids in ids_by_model.items()
            if res_model in self.env  # a model that is not installed (any more): nobody may
        }
        return {
            triple
            for triple in triples
            if triple[0] in by_folder and triple[2] in writable.get(triple[1], ())
        }

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._prepare_vals(vals) for vals in vals_list]
        triples = {
            (vals["document_id"], self.env["ir.model"].sudo().browse(vals["res_model_id"]).model, vals["res_id"])
            for vals in vals_list
        }
        if not self.env.su and not triples <= self._manageable(triples):
            raise AccessError(
                self.env._(
                    "You may only link a document that its folder shows to you, to a record "
                    "that you may change."
                )
            )
        links = super().create(vals_list)
        links._post_notes(linked=True)
        return links

    def _prepare_vals(self, vals):
        """Turn the choice of the list (``record_ref``) into the model and the id."""
        vals = self._record_values(vals)
        if not vals.get("res_model_id") or not vals.get("res_id"):
            raise UserError(self.env._("Choose the record that the document is linked to."))
        return vals

    def _record_values(self, vals):
        """``record_ref`` as the model and the id; the model must be one that can be linked."""
        vals = dict(vals)
        record_ref = vals.pop("record_ref", False)
        if isinstance(record_ref, models.BaseModel):  # from Python (Form), the browser sends text
            record_ref = f"{record_ref._name},{record_ref.id}"
        if record_ref:
            res_model, __, res_id = record_ref.partition(",")
            vals["res_model_id"] = self.env["ir.model"]._get_id(res_model)
            vals["res_id"] = int(res_id)
        if vals.get("res_model_id"):
            res_model = self.env["ir.model"].sudo().browse(vals["res_model_id"]).model
            if res_model not in self._linkable_models():
                raise UserError(self.env._("Documents cannot be linked to this kind of record."))
        return vals

    def write(self, vals):
        """Only the record of a link can be changed, by whoever may untie and tie again.

        The record is the one thing a user may want to correct in the list; the document stays.
        The same rights as for a new link, on the old record and on the new one.
        """
        vals = self._record_values(vals)
        if set(vals) - {"res_model_id", "res_id"}:
            raise UserError(self.env._("Only the record of a link can be changed."))
        if not vals:
            return True
        if len(vals) != 2 or not vals["res_model_id"] or not vals["res_id"]:
            raise UserError(self.env._("Choose the record that the document is linked to."))
        res_model = self.env["ir.model"].sudo().browse(vals["res_model_id"]).model
        triples = {(link.document_id.id, res_model, vals["res_id"]) for link in self.sudo()}
        if not self.env.su and not triples <= self._manageable(triples):
            raise AccessError(
                self.env._(
                    "You may only link a document that its folder shows to you, to a record "
                    "that you may change."
                )
            )
        self._post_notes(linked=False)
        result = super().write(vals)
        self._post_notes(linked=True)
        return result

    def _check_access(self, operation):
        """Untying and changing need the same as tying: the folder shows the document, the record
        is writable (the old one, for a change; ``write`` looks at the new one).

        As ``ir.attachment`` asks for write access on the record to create or delete one.
        """
        result = super()._check_access(operation)
        if operation not in ("unlink", "write") or not self or self.env.su:
            return result
        triples = {link.id: (link.document_id.id, link.res_model, link.res_id) for link in self.sudo()}
        manageable = self._manageable(set(triples.values()))
        forbidden = self.browse(id_ for id_, triple in triples.items() if triple not in manageable)
        if forbidden:
            if result:
                forbidden |= result[0]
            rule = self.env["ir.rule"]
            return forbidden, functools.partial(rule._make_access_error, operation, forbidden)
        return result

    def unlink(self):
        self._post_notes(linked=False)
        return super().unlink()

    def _post_notes(self, linked):
        """Say in the chatter of the record and of the document that they were (un)tied."""
        for link in self.sudo():
            document, record = link.document_id, link._record()
            if not record:
                continue
            record_link = Markup(
                '<a href="#" data-oe-model="%s" data-oe-id="%s">%s</a>'
            ) % (record._name, record.id, record.display_name)
            author = self.env.user.partner_id.id
            if hasattr(record, "message_post"):
                record.message_post(
                    body=(
                        self.env._("A document was linked.")
                        if linked
                        else self.env._("A document was unlinked.")
                    ),
                    author_id=author,
                    subtype_xmlid="mail.mt_note",
                )
            document.message_post(
                body=(
                    self.env._("Linked to %(record)s.", record=record_link)
                    if linked
                    else self.env._("Unlinked from %(record)s.", record=record_link)
                ),
                author_id=author,
                subtype_xmlid="mail.mt_note",
            )

    def _record(self):
        """The record of the other model, empty if it is gone or its model is not installed."""
        self.ensure_one()
        if self.res_model not in self.env:
            return False
        return self.env[self.res_model].sudo().with_context(active_test=False).browse(self.res_id).exists()

    @api.autovacuum
    def _gc_orphan_links(self):
        """Remove the links of records that were deleted without ``unlink`` (SQL, cascade)."""
        for res_model, res_ids in self._read_group([], ["res_model"], ["res_id:array_agg"]):
            if res_model not in self.env:
                continue
            existing = self.env[res_model].sudo().with_context(active_test=False)
            missing = set(res_ids) - set(existing.browse(res_ids).exists().ids)
            if missing:
                self.sudo().search(
                    [("res_model", "=", res_model), ("res_id", "in", list(missing))]
                ).unlink()

    @api.model
    def _toggle_access_via_record(self, active):
        """Switch the way over the linked records on or off (the setting).

        Four records belong together: the rules that show a document and its links through a
        record, and the right of the internal users to read documents and links. A right without
        the rules would show every document to every internal user.

        :param active: True to switch on, False to switch off
        """
        rules = (
            self.env.ref("int_filemanager.int_filemanager_document_rule_record")
            + self.env.ref("int_filemanager.int_filemanager_link_rule_record")
        ).sudo()
        accesses = (
            self.env.ref("int_filemanager.access_int_filemanager_document_internal")
            + self.env.ref("int_filemanager.access_int_filemanager_link_internal")
        ).sudo()
        rules.filtered(lambda rule: rule.active != active).write({"active": active})
        accesses.filtered(lambda access: access.active != active).write({"active": active})
