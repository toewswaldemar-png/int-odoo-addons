from odoo import fields, models


class IntUiShowcaseWizard(models.TransientModel):
    _name = "int.ui.showcase.wizard"
    _description = "UI Showcase Dialog"

    showcase_id = fields.Many2one(
        "int.ui.showcase",
        required=True,
        default=lambda self: self.env.context.get("active_id"),
    )
    message = fields.Text(required=True)

    def action_confirm(self):
        """Post the message to the chatter of the record."""
        for wizard in self:
            wizard.showcase_id.message_post(body=wizard.message)
        return {"type": "ir.actions.act_window_close"}
