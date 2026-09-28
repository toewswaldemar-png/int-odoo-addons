import secrets
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

DEFAULT_SHARE_DAYS = 30
MAX_SHARE_DAYS = 365
SHARE_DAYS_PARAM = "int_filemanager.share_default_days"


class IntFilemanagerShare(models.Model):
    """An anonymous download link for ONE file (Kern 4 "Teilen"): a random token, an
    expiry, and a log of what happened. Links are created and revoked only through
    the methods below - users can read the rows their scope lets them write to, but
    never write them, so nobody can plant a token of their own choosing or stretch
    an expiry."""

    _name = "int_filemanager.share"
    _description = "Filemanager v2 share link"
    _order = "id desc"

    node_id = fields.Many2one(
        "int_filemanager.node", required=True, index=True, ondelete="cascade"
    )
    token = fields.Char(required=True, copy=False, index=True)
    expires_at = fields.Datetime(required=True, copy=False)
    revoked_at = fields.Datetime(copy=False)
    download_count = fields.Integer(default=0, copy=False)
    url = fields.Char(compute="_compute_url")

    _token_uniq = models.Constraint("UNIQUE(token)", "This share token already exists.")

    @api.depends("token")
    def _compute_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        for share in self:
            share.url = f"{base_url}/int_filemanager/v2/share/{share.token}"

    def _is_active(self):
        self.ensure_one()
        return not self.revoked_at and self.expires_at > fields.Datetime.now()

    def _log(self, event_type, partner=None):
        self.ensure_one()
        node = self.node_id.sudo()
        self.env["int_filemanager.share_log"].sudo().create(
            {
                "node_id": node.id,
                "path": node._display_path(),
                "filename": node.name,
                "event_type": event_type,
                "partner_id": partner.id if partner else False,
            }
        )

    @api.model
    def create_link(self, node_id, days=None):
        """A new link for a file the caller may write to (the same right that lets them
        change who else may read it). Several links per file are fine; each has its own
        expiry and can be revoked on its own."""
        node = self.env["int_filemanager.node"].browse(node_id)
        node.check_access("write")
        if node.is_dir or not node.current_revision_id:
            raise UserError(
                self.env._("Only single files with content can be shared by link.")
            )
        if not days:
            days = int(
                self.env["ir.config_parameter"]
                .sudo()
                .get_param(SHARE_DAYS_PARAM, DEFAULT_SHARE_DAYS)
            )
        days = max(1, min(int(days), MAX_SHARE_DAYS))
        # sudo() keeps the caller as create_uid; the right was checked just above.
        share = self.sudo().create(
            {
                "node_id": node.id,
                "token": secrets.token_urlsafe(32),
                "expires_at": fields.Datetime.now() + timedelta(days=days),
            }
        )
        share._log("created")
        return {
            "share_id": share.id,
            "url": share.url,
            "expires_at": fields.Datetime.to_string(share.expires_at),
        }

    @api.model
    def revoke_link(self, share_id):
        share = self.browse(share_id).exists()
        if not share:
            raise UserError(self.env._("This link does not exist any more."))
        share.node_id.check_access("write")
        if not share.revoked_at:
            share.sudo().write({"revoked_at": fields.Datetime.now()})
            share._log("revoked")
        return True

    @api.model
    def _find_active(self, token):
        """For the anonymous download route: the active share of a token, or nothing.
        Unknown, expired, revoked and trashed are deliberately indistinguishable - a
        difference would tell a guesser whether a token ever existed."""
        if not token:
            return self.browse()
        share = self.sudo().search([("token", "=", token)], limit=1)
        if not share or not share._is_active():
            return self.browse()
        node = share.node_id
        if not node.active or node.is_dir or not node.current_revision_id:
            return self.browse()
        return share
