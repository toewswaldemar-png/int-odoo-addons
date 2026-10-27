from odoo import Command, api, fields, models
from odoo.fields import Domain


class IntFilemanagerFavorite(models.AbstractModel):
    """What folders and documents have in common: a star that each user sets for themselves.

    The stars lie on the user (``_favorite_field``), so a star does not write the record: its
    ``write_date`` ("Modified") stays. Both sides of the relation are fields; a search by
    ``is_favorite`` is a search in the relation.
    """

    _name = "int.filemanager.favorite"
    _description = "Filemanager: a record that a user marks as favorite"

    # The field of ``res.users`` that holds the favorites of the model; each model names its own.
    _favorite_field = None

    favorite_user_ids = fields.Many2many("res.users", string="Favorite of", copy=False)
    is_favorite = fields.Boolean(
        string="Favorite",
        compute="_compute_is_favorite",
        readonly=False,
        search="_search_is_favorite",
        exportable=False,
    )

    @api.depends("favorite_user_ids")
    @api.depends_context("uid")
    def _compute_is_favorite(self):
        for record in self:
            record.is_favorite = self.env.user in record.favorite_user_ids

    @api.model
    def _search_is_favorite(self, operator, value):
        # A boolean is searched with ``in [True]`` or ``not in [True]``.
        if operator not in ("in", "not in"):
            return NotImplemented
        return Domain("favorite_user_ids", operator, [self.env.uid])

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [dict(vals) for vals in vals_list]
        for vals in vals_list:
            if vals.pop("is_favorite", False):
                vals["favorite_user_ids"] = [Command.link(self.env.uid)]
        return super().create(vals_list)

    def write(self, vals):
        """Set the star of the current user when ``is_favorite`` is written, and write the rest.

        The star is not a value of the record: a reader may set it, though readers may not write.
        The access right to write is therefore not asked for it, but the right to read is.
        """
        if "is_favorite" in vals:
            vals = dict(vals)
            self._set_favorite(vals.pop("is_favorite"))
            if not vals:
                return True
        return super().write(vals)

    def _set_favorite(self, is_favorite):
        # The method is reachable by RPC with any ids: the records are checked before anything is
        # written.
        self.check_access("read")
        command = Command.link if is_favorite else Command.unlink
        # sudo: res.users: a user may only change their own favorites, not their other fields; the
        # records were checked above
        # active_test: the field is read before it is written, and an archived record that is not
        # read cannot be unlinked
        user = self.env.user.sudo().with_context(active_test=False)
        user[self._favorite_field] = [command(record_id) for record_id in self.ids]
