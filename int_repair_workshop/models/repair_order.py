from datetime import datetime, time

from odoo import api, fields, models

BUS_CHANNEL = "int_repair_workshop"
BUS_NOTIFICATION_TYPE = "int_repair_workshop.change"


class RepairOrder(models.Model):
    _inherit = "repair.order"

    x_auftragsart = fields.Selection(
        [("reparatur", "Reparatur"), ("revision", "Revision")],
        string="Auftragsart",
        help="Bestimmt, welche der beiden sich gegenseitig ausschließenden Werkstattstufen "
        "(Reparatur nach Befund / Revision nach Anweisung) für diesen Auftrag gilt.",
    )
    x_eingangsdatum = fields.Date(string="Eingangsdatum")
    x_lieferdatum = fields.Date(
        string="Lieferdatum",
        compute="_compute_x_lieferdatum",
        inverse="_inverse_x_lieferdatum",
        store=True,
        help="Reines Datum, gespiegelt aus dem geplanten Datum (schedule_date). Die Uhrzeit "
        "von schedule_date bleibt beim Ändern hier unangetastet - andere Odoo-Teile (Lager-"
        "Dispo) verlassen sich auf sie.",
    )
    x_verfuegbare_arbeitstage = fields.Integer(
        string="Arbeitstage",
        compute="_compute_x_verfuegbare_arbeitstage",
        help="Geplantes Datum minus heute, in Kalendertagen. Negativ = Termin überschritten.",
    )

    x_werkstattstufe = fields.Selection(
        [
            ("reinigung_aussen", "Außenreinigung"),
            ("eingangspruefung", "Eingangsprüfung"),
            ("reinigung_gesamt", "Gesamtreinigung"),
            ("in_bearbeitung", "In Bearbeitung"),
            ("endpruefung", "Endprüfung"),
            ("reinigen_verpacken", "Verpacken"),
        ],
        string="Status",
        default="reinigung_aussen",
    )
    x_stufe_mitarbeiter = fields.Many2one(
        "hr.employee",
        string="Ausgeführt von",
        help="Nachträglicher Vermerk, wer die aktuelle Werkstattstufe gemacht hat.",
    )
    x_geraete_snr = fields.Char(string="Geräte-SNr.")

    @api.depends("schedule_date")
    def _compute_x_lieferdatum(self):
        for order in self:
            order.x_lieferdatum = order.schedule_date.date() if order.schedule_date else False

    def _inverse_x_lieferdatum(self):
        for order in self:
            if not order.x_lieferdatum:
                continue
            existing_time = order.schedule_date.time() if order.schedule_date else time(0, 0)
            order.schedule_date = datetime.combine(order.x_lieferdatum, existing_time)

    @api.depends("schedule_date")
    def _compute_x_verfuegbare_arbeitstage(self):
        today = fields.Date.context_today(self)
        for order in self:
            if order.schedule_date:
                order.x_verfuegbare_arbeitstage = (order.schedule_date.date() - today).days
            else:
                order.x_verfuegbare_arbeitstage = 0

    def action_open_form(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def _notify_workshop_change(self):
        """Tell any open Werkstatt list to refresh - queued for delivery on
        commit, so it only reaches clients once the caller's transaction lands."""
        self.env["bus.bus"]._sendone(BUS_CHANNEL, BUS_NOTIFICATION_TYPE, {})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._notify_workshop_change()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._notify_workshop_change()
        return res

    def unlink(self):
        res = super().unlink()
        self.env["bus.bus"]._sendone(BUS_CHANNEL, BUS_NOTIFICATION_TYPE, {})
        return res
