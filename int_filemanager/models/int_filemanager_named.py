import unicodedata

from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..tools.clash import NAME_TRIES, clash_summary, clashing_names

# The longest name of a folder or a document (Windows allows 255 characters per name).
NAME_MAX_LENGTH = 255
# The names that ``_create_numbered_name`` asks the database about in one go.
NUMBERED_LOOKUP = 100


class IntFilemanagerNamed(models.AbstractModel):
    """What folders and documents have in common: a name that is unique where the record lies.

    Two active records of one place cannot share a name (case aside; the unique index of the model
    says so). The mixin keeps the name fit for it, whatever way it comes in (upload, form,
    RPC), numbers a new record whose name is taken, and names the clashes of a move.
    """

    _name = "int.filemanager.named"
    _description = "Filemanager: a record with a name that is unique where it lies"

    name = fields.Char(required=True)

    @api.model
    def _normalize_name(self, name):
        """The name composed (NFC: an "ä" typed as one character and as "a" plus a mark are one
        name), without control characters and without space around it."""
        name = unicodedata.normalize("NFC", name)
        return "".join(char for char in name if unicodedata.category(char) != "Cc").strip()

    def _with_clean_name(self, vals):
        if isinstance(vals.get("name"), str):
            return {**vals, "name": self._normalize_name(vals["name"])}
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._with_clean_name(vals) for vals in vals_list])

    def write(self, vals):
        return super().write(self._with_clean_name(vals))

    @api.constrains("name")
    def _check_name(self):
        """A name is something, not ``.`` or ``..``, and not longer than a file system allows.

        A slash may be in it ("Invoices 2025/26"): the ZIP of a download makes the name of the
        entry (``export_name``), and an upload cuts the path off its file name (``_clean_name``).
        """
        for record in self:
            name = record.name or ""
            if not name or name in (".", ".."):
                raise ValidationError(self.env._("A name is not empty, and not . or ..: %(name)s", name=name))
            if len(name) > NAME_MAX_LENGTH:
                raise ValidationError(
                    self.env._("A name has %(limit)s characters at most.", limit=NAME_MAX_LENGTH)
                )

    @api.model
    def _numbered_name(self, name, number):
        """``name`` with the number of the try (``a (2)``); a model with endings keeps them."""
        return f"{name} ({number})"

    @api.model
    def _create_numbered_name(self, name, domain, constraint, create):
        """Make a record under ``name`` or under the first free ``name (2)``.

        The names of the place (``domain``) that are taken are looked up in one go; one that slips
        through (another case, a parallel request) is caught by the unique index ``constraint``
        of the database. Odoo does not retry on that error.

        :param create: called with the name to try; makes the record
        """

        def numbered(number):
            return name if number == 1 else self._numbered_name(name, number)

        taken = {
            record.name.lower()
            for record in self.search_fetch(
                [*domain, ("name", "in", [numbered(number) for number in range(1, NUMBERED_LOOKUP + 1)])],
                ["name"],
            )
        }
        constraint = constraint.full_name(self)
        for number in range(1, NAME_TRIES + 1):
            candidate = numbered(number)
            if candidate.lower() in taken:
                continue
            try:
                with self.env.cr.savepoint():
                    return create(candidate)
            except IntegrityError as error:
                if error.diag.constraint_name != constraint:
                    raise
                taken.add(candidate.lower())
        raise UserError(self.env._("No free name for %(name)s in this folder.", name=name))

    def _names_taken(self, column, target):
        """The names, as text for a message, that these records cannot take into ``target``.

        ``target`` is a folder, or none for the top. The records that are moving leave their place,
        so their old names do not count; two of them with one name clash, since they all come to
        the same place. Empty if nothing clashes.

        :param column: the field of the model that holds the place (``parent_id``, ``folder_id``)
        """
        active = self.filtered("active")
        clash = clashing_names(self.env, self._table, column, target.id, active.mapped("name"), active.ids)
        return clash_summary(clash) if clash else ""
