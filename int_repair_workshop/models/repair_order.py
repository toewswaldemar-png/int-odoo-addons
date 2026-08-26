from odoo import api, fields, models


class RepairOrder(models.Model):
    _inherit = "repair.order"

    x_auftragsart = fields.Selection(
        [("reparatur", "Reparatur"), ("revision", "Revision")],
        string="Auftragsart",
        help="Bestimmt, welche der beiden sich gegenseitig ausschließenden Werkstattstufen "
        "(Reparatur nach Befund / Revision nach Anweisung) für diesen Auftrag gilt.",
    )
    x_eingangsdatum = fields.Date(string="Eingangsdatum")
    x_verfuegbare_arbeitstage = fields.Integer(
        string="Verfügbare Arbeitstage",
        compute="_compute_x_verfuegbare_arbeitstage",
        help="Geplantes Datum minus heute, in Kalendertagen. Negativ = Termin überschritten.",
    )

    x_stage_reinigung_aussen = fields.Many2one("hr.employee", string="Reinigung Außen")
    x_stage_eingangspruefung = fields.Many2one("hr.employee", string="Eingangsprüfung")
    x_stage_reinigung_gesamt = fields.Many2one("hr.employee", string="Reinigung Gesamt")
    x_stage_reparatur_befund = fields.Many2one("hr.employee", string="Reparatur nach Befund")
    x_stage_revision_anweisung = fields.Many2one("hr.employee", string="Revision nach Anweisung")
    x_stage_endpruefung = fields.Many2one("hr.employee", string="Endprüfung")
    x_stage_reinigen_verpacken = fields.Many2one("hr.employee", string="Reinigen Verpacken")

    @api.depends("schedule_date")
    def _compute_x_verfuegbare_arbeitstage(self):
        today = fields.Date.context_today(self)
        for order in self:
            if order.schedule_date:
                order.x_verfuegbare_arbeitstage = (order.schedule_date.date() - today).days
            else:
                order.x_verfuegbare_arbeitstage = 0
