import functools
from collections import defaultdict

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError


class IntFilemanagerLink(models.Model):
    """A document tied to a record of another model (a contact, a repair order ...).

    Built like ``mail.activity`` and ``ir.attachment``: the name of the model and the id of the
    record, no foreign key. The database cannot cascade over it. ``int.filemanager.linkable``
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
        return [
            name
            for name in self.env.registry.descendants(["int.filemanager.linkable"], "_inherit")
            if not self.env[name]._abstract
        ]

    @api.depends("res_model", "res_id")
    def _compute_record_ref(self):
        linkable = self._linkable_models()
        for link in self:
            # only the models of the choice: a Reference field refuses any other
            if link.res_model in linkable and link.res_id:
                link.record_ref = f"{link.res_model},{link.res_id}"
            else:
                link.record_ref = False

    @api.model
    def _selection_record_ref(self):
        # sudo: ir.model: the choice of models does not depend on the rights on ir.model
        models = self.env["ir.model"].sudo().search([("model", "in", self._linkable_models())])
        return [(model.model, model.name) for model in models]

    @api.model
    def default_get(self, fields):
        """Drop the record from the context.

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
        """Return the (document id, model name, record id) triples that the user may tie or untie.

        Whoever sees a document only through a record must not pass it on to other records:
        the folder has to show it to the user. And the record has to be one the user may write.
        """
        documents = self.env["int.filemanager.document"].browse({triple[0] for triple in triples}).exists()
        by_folder = set(documents._filtered_folder_access("read").ids)
        ids_by_model = defaultdict(set)
        for __, res_model, res_id in triples:
            ids_by_model[res_model].add(res_id)
        writable = {
            res_model: set(self.env[res_model].browse(res_ids).exists()._filtered_access("write").ids)
            for res_model, res_ids in ids_by_model.items()
            if res_model in self.env  # a model that is not installed (any more): nobody may write it
        }
        return {
            triple
            for triple in triples
            if triple[0] in by_folder and triple[2] in writable.get(triple[1], ())
        }

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._prepare_vals(vals) for vals in vals_list]
        # sudo: ir.model: only the name of the model is read
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
        vals = self._record_values(vals)
        if not vals.get("res_model_id") or not vals.get("res_id"):
            raise UserError(self.env._("Choose the record that the document is linked to."))
        return vals

    def _record_values(self, vals):
        vals = dict(vals)
        record_ref = vals.pop("record_ref", False)
        if isinstance(record_ref, models.BaseModel):  # from Python (Form); the browser sends text
            record_ref = f"{record_ref._name},{record_ref.id}"
        if record_ref:
            res_model, __, res_id = record_ref.partition(",")
            vals["res_model_id"] = self.env["ir.model"]._get_id(res_model)
            vals["res_id"] = int(res_id)
        if vals.get("res_model_id"):
            # sudo: ir.model: only the name of the model is read
            res_model = self.env["ir.model"].sudo().browse(vals["res_model_id"]).model
            if res_model not in self._linkable_models():
                raise UserError(self.env._("Documents cannot be linked to this kind of record."))
        return vals

    def write(self, vals):
        """Change the record of a link, which is all that can be changed, as whoever may untie and tie again.

        The record is the one thing a user may want to correct in the list; the document stays.
        The rights are those of a new link, on the old record and on the new one.
        """
        vals = self._record_values(vals)
        if set(vals) - {"res_model_id", "res_id"}:
            raise UserError(self.env._("Only the record of a link can be changed."))
        if not vals:
            return True
        if len(vals) != 2 or not vals["res_model_id"] or not vals["res_id"]:
            raise UserError(self.env._("Choose the record that the document is linked to."))
        # sudo: ir.model, int.filemanager.link: only names and ids are read; the rights are
        # checked by ``_manageable``
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
        """Require for untying and changing what tying requires.

        The folder shows the document and the record is writable (the old one for a change;
        ``write`` looks at the new one). ``ir.attachment`` likewise asks for write access on the
        record to create or delete an attachment.
        """
        result = super()._check_access(operation)
        if operation not in ("unlink", "write") or not self or self.env.su:
            return result
        # sudo: only ids and names are read; the rights are checked by ``_manageable``
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
        # sudo: the notes are posted also on a record or document that the user cannot read
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
        self.ensure_one()
        if self.res_model not in self.env:
            return False
        # sudo: the note is posted on the record also if the user cannot read it
        return self.env[self.res_model].sudo().with_context(active_test=False).browse(self.res_id).exists()

    @api.autovacuum
    def _gc_orphan_links(self):
        """Remove the links of records that were deleted without ``unlink`` (SQL, cascade)."""
        for res_model, res_ids in self._read_group([], ["res_model"], ["res_id:array_agg"]):
            if res_model not in self.env:
                continue
            # sudo: the vacuum looks at the records of all companies, archived ones too
            existing = self.env[res_model].sudo().with_context(active_test=False)
            missing = set(res_ids) - set(existing.browse(res_ids).exists().ids)
            if missing:
                self.sudo().search(
                    [("res_model", "=", res_model), ("res_id", "in", list(missing))]
                ).unlink()

    @api.model
    def _toggle_access_via_record(self, active):
        """Switch the access over the linked records on or off (the setting).

        Four records belong together: the rules that show a document and its links through a
        record, and the right of the internal users to read documents and links. A right without
        the rules would show every document to every internal user.

        :param active: True to switch on, False to switch off
        """
        # sudo: ir.rule, ir.model.access: the setting switches them, whoever changes the setting
        rules = (
            self.env.ref("int_filemanager_record.int_filemanager_document_rule_record")
            + self.env.ref("int_filemanager_record.int_filemanager_link_rule_record")
        ).sudo()
        accesses = (
            self.env.ref("int_filemanager_record.access_int_filemanager_document_internal")
            + self.env.ref("int_filemanager_record.access_int_filemanager_link_internal")
        ).sudo()
        rules.filtered(lambda rule: rule.active != active).write({"active": active})
        accesses.filtered(lambda access: access.active != active).write({"active": active})
