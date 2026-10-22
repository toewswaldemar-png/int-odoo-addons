from odoo import api, fields, models


class IntKeepassEntry(models.Model):
    _name = "int.keepass.entry"
    _description = "KeePass Entry"
    _inherit = ["int.keepass.virtual"]
    _auto = False
    _table_query = "0"
    _order = "title, id"
    _rec_name = "title"
    _data_key = "entries"

    title = fields.Char(compute="_compute_values")
    username = fields.Char(compute="_compute_values")
    url = fields.Char(string="URL", compute="_compute_values")
    group_id = fields.Many2one("int.keepass.group", string="Group", compute="_compute_values")

    def _compute_values(self):
        for record in self:
            row = record._row()
            record.title = row.get("title", False)
            record.username = row.get("username", False)
            record.url = row.get("url", False)
            record.group_id = row.get("group_id", False)

    @api.model
    def get_source_info(self):
        """For the unlock screen, before there is a password: where the data comes from and which e-mail address to offer."""
        self.check_access("read")
        source = self.env["int.keepass.source"]
        return {"source": source._source(), "email": self.env.user.email or self.env.user.login}

    @api.model
    def action_unlock(self):
        """Called by the unlock screen: reads the source afresh with the login of the request, which fails if it is wrong."""
        self.check_access("read")
        source = self.env["int.keepass.source"]
        source._forget()
        source._data()
        return True

    @api.model
    def action_refresh(self):
        """Called by the refresh menu: this worker forgets what it holds for the login, the next read is afresh."""
        self.check_access("read")
        self.env["int.keepass.source"]._forget()
        return True

    @api.model
    def action_lock(self):
        """Called by the lock menu: the worker forgets what it holds; the browser forgets the password."""
        return self.action_refresh()
