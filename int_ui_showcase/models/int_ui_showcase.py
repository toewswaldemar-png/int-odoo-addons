import datetime
import json

import pytz

from odoo import api, fields, models
from odoo.addons.base.models.res_partner import _tzs


def _default_json(_model):
    return {"key": "value", "number": 42, "list": [1, 2, 3], "nested": {"flag": True}}


def _default_checkboxes(_model):
    return {
        "first": {"checked": True, "label": "First", "question_circle": "Help text"},
        "second": {"checked": False, "label": "Second"},
        "locked": {"checked": True, "label": "Read-only", "readonly": True},
    }


def _default_statistics(_model):
    return [
        {"label": "Orders", "value": 12, "iconClass": "fa-shopping-cart"},
        {"label": "Invoices", "value": 4, "iconClass": "fa-file-text-o", "tagClass": "o_tag_color_10"},
        {"label": "Tickets", "value": 1, "iconClass": "fa-life-ring", "tagClass": "o_tag_color_1"},
    ]


def _default_line_graph(_model):
    points = [("Mon", 3), ("Tue", 7), ("Wed", 4), ("Thu", 9), ("Fri", 6), ("Sat", 2), ("Sun", 5)]
    return json.dumps(
        [
            {
                "values": [{"x": x, "y": y, "name": x} for x, y in points],
                "title": "",
                "key": "Line",
                "area": True,
                "color": "#875A7B",
                "is_sample_data": False,
            }
        ]
    )


def _default_bar_graph(_model):
    points = [("Jan", 3, "past"), ("Feb", 7, "past"), ("Mar", 4, "past"), ("Apr", 9, "future")]
    return json.dumps(
        [
            {
                "values": [{"value": v, "label": label, "type": kind} for label, v, kind in points],
                "title": "",
                "key": "Bar",
                "is_sample_data": False,
            }
        ]
    )


class IntUiShowcase(models.Model):
    """One record that carries a field for every kind of field widget."""

    _name = "int.ui.showcase"
    _description = "UI Showcase"
    _inherit = [
        "mail.tracking.duration.mixin",
        "mail.activity.mixin",
        "image.mixin",
    ]
    _order = "priority desc, sequence, id desc"
    _track_duration_field = "stage_id"

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        return stages.search([])

    def _default_stage_id(self):
        return self.env["int.ui.showcase.stage"].search([], limit=1)

    # === TEXT === #
    name = fields.Char(required=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    email = fields.Char()
    phone = fields.Char()
    url = fields.Char("Website")
    secret = fields.Char()
    hex_color = fields.Char("Hex Color", default="#714b67")
    copy_char = fields.Char("Reference Code", default="SHOW-0001")
    copy_button = fields.Char("Share Link", default="https://www.odoo.com")
    emoji_char = fields.Char("Char with Emojis", default="Hello")
    emoji_text = fields.Text("Text with Emojis")
    note = fields.Text()
    description = fields.Html()
    iframe_html = fields.Html(
        "HTML in an Iframe",
        sanitize=False,
        default="<h2>Iframe</h2><p>This HTML is rendered in an <b>iframe</b>.</p>",
    )
    code = fields.Text("Code Snippet", default="def hello():\n    return 'world'\n")
    image_url = fields.Char("Image URL", default="/web/static/img/odoo-icon-192x192.png")
    slide_url = fields.Char(
        "Google Slides",
        default="https://docs.google.com/presentation/d/1BnUdSC1Wyl0XGs2Tcd1LBMEDEqhVL6jrmQ8wZTZaHCk/edit",
    )

    # === NUMBERS === #
    integer_value = fields.Integer()
    float_value = fields.Float(digits=(16, 3))
    float_time = fields.Float("Duration")
    float_factor_value = fields.Float("Minutes (stored as hours)", default=1.5)
    float_toggle_value = fields.Float("Toggle", default=0.5)
    percentage = fields.Float(default=0.25)
    progress = fields.Integer(default=40)
    satisfaction = fields.Float(default=65.0)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )
    amount = fields.Monetary()

    # === DATES === #
    date = fields.Date(default=fields.Date.context_today)
    deadline = fields.Date()
    date_start = fields.Datetime(default=fields.Datetime.now)
    date_end = fields.Datetime()
    scheduled_date = fields.Datetime()
    mon = fields.Boolean(default=True)
    tue = fields.Boolean(default=True)
    wed = fields.Boolean(default=True)
    thu = fields.Boolean(default=True)
    fri = fields.Boolean(default=True)
    sat = fields.Boolean()
    sun = fields.Boolean()
    tz = fields.Selection(_tzs, "Timezone", default=lambda self: self.env.context.get("tz"))
    tz_offset = fields.Char("Timezone offset", compute="_compute_tz_offset")

    # === SELECTIONS === #
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        copy=False,
    )
    kanban_state = fields.Selection(
        [("normal", "In Progress"), ("done", "Ready"), ("blocked", "Blocked")],
        default="normal",
        required=True,
    )
    priority = fields.Selection(
        [("0", "Normal"), ("1", "Low"), ("2", "High"), ("3", "Urgent")], default="0"
    )
    kind = fields.Selection(
        [("a", "Alpha"), ("b", "Beta"), ("c", "Gamma"), ("d", "Delta")], default="a"
    )
    # Codes of the kinds that selection widgets with a filter offer.
    allowed_kinds = fields.Char(default="abc")
    color = fields.Integer()
    is_favorite = fields.Boolean()
    is_pinned = fields.Boolean()
    flag = fields.Boolean()

    # === RELATIONS === #
    stage_id = fields.Many2one(
        "int.ui.showcase.stage",
        tracking=True,
        copy=False,
        index=True,
        default=_default_stage_id,
        group_expand="_read_group_stage_ids",
    )
    date_last_stage_update = fields.Datetime(
        compute="_compute_date_last_stage_update", store=True, readonly=True
    )
    category_id = fields.Many2one("int.ui.showcase.category")
    partner_id = fields.Many2one("res.partner")
    partner_ids = fields.Many2many("res.partner", "int_ui_showcase_partner_rel", "showcase_id", "partner_id")
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user, tracking=True)
    user_ids = fields.Many2many(
        "res.users", "int_ui_showcase_user_rel", "showcase_id", "user_id", string="Team"
    )
    tag_ids = fields.Many2many("int.ui.showcase.tag")
    reference = fields.Reference([("res.partner", "Contact"), ("res.users", "User")])
    res_model = fields.Char("Related Model", default="res.partner")
    res_id = fields.Many2oneReference("Related Record", model_field="res_model")
    parent_id = fields.Many2one("int.ui.showcase", index=True, ondelete="set null")
    child_ids = fields.One2many("int.ui.showcase", "parent_id")
    line_ids = fields.One2many("int.ui.showcase.line", "showcase_id", copy=True)
    properties = fields.Properties(
        "Properties", definition="category_id.showcase_properties_definition"
    )

    # === FILES === #
    attachment = fields.Binary("File", attachment=True)
    attachment_name = fields.Char()
    attachment_ids = fields.Many2many("ir.attachment", "int_ui_showcase_attachment_rel")
    image_attachment_id = fields.Many2one("ir.attachment", "Cover Image")
    pdf_file = fields.Binary("PDF", attachment=True)
    pdf_name = fields.Char()
    signature = fields.Binary(attachment=True)

    # === STRUCTURED DATA === #
    json_data = fields.Json("JSON", default=_default_json)
    checkbox_data = fields.Json("JSON Checkboxes", default=_default_checkboxes)
    statistics_data = fields.Json("Statistics", default=_default_statistics)
    graph_line_data = fields.Text("Line Graph Data", default=_default_line_graph)
    graph_bar_data = fields.Text("Bar Graph Data", default=_default_bar_graph)
    domain_model = fields.Char("Domain Model", default="res.partner")
    domain = fields.Char(default="[('name', 'ilike', 'a')]")
    field_path = fields.Char("Field Path", default="name")

    # === COMPUTED === #
    line_count = fields.Integer(compute="_compute_line_count")
    amount_total = fields.Monetary(compute="_compute_amount_total", store=True)

    @api.depends("tz")
    def _compute_tz_offset(self):
        for record in self:
            record.tz_offset = datetime.datetime.now(pytz.timezone(record.tz or "GMT")).strftime("%z")

    @api.depends("stage_id")
    def _compute_date_last_stage_update(self):
        for record in self:
            record.date_last_stage_update = self.env.cr.now()

    @api.depends("line_ids")
    def _compute_line_count(self):
        for record in self:
            record.line_count = len(record.line_ids)

    @api.depends("line_ids.subtotal")
    def _compute_amount_total(self):
        for record in self:
            record.amount_total = sum(record.line_ids.mapped("subtotal"))

    # === BUTTONS === #
    def action_draft(self):
        self.state = "draft"

    def action_confirm(self):
        self.state = "confirmed"

    def action_done(self):
        self.state = "done"

    def action_cancel(self):
        self.state = "cancel"

    def action_open_lines(self):
        """Return the lines of the record in a list (target of the stat button)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Lines"),
            "res_model": "int.ui.showcase.line",
            "view_mode": "list,form",
            "domain": [("showcase_id", "=", self.id)],
            "context": {"default_showcase_id": self.id},
        }

    def action_notify(self):
        """Show a notification and reload the view."""
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Notification"),
                "message": self.env._("%s was notified.", self.name),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }

    def action_rainbow(self):
        """Show the rainbow man effect."""
        return {
            "effect": {
                "fadeout": "slow",
                "message": self.env._("Well done!"),
                "type": "rainbow_man",
            },
        }

    def action_attach_document(self, attachment_ids=None):
        """Link the uploaded files (attach_document widget calls this after the upload)."""
        self.ensure_one()
        self.attachment_ids = [(4, attachment_id) for attachment_id in attachment_ids or []]
