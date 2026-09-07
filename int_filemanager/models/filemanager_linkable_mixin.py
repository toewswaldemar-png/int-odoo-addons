from odoo import _, fields, models


class IntFilemanagerLinkableMixin(models.AbstractModel):
    """Inherit this on res.partner to get a 'Verknüpfte Dateien' smart button
    counting/opening the int_filemanager.file records whose partner_id points
    back at the record - the reverse direction of the per-file "Kontakt
    verknüpfen" action in the filemanager itself.

    Seit der Umstellung von res_reference (generisches Reference-Feld, beliebiges
    Modell) auf partner_id (Many2one fest auf res.partner, Nutzerentscheidung
    2026-09-07 - siehe filemanager_file.py) ist dieser Mixin faktisch auf res.partner
    zugeschnitten: die Domain unten setzt direkt partner_id = record.id voraus, das
    ergibt nur Sinn, wenn record selbst ein res.partner ist. Nicht mehr ohne Weiteres
    generisch auf ein anderes Modell uebertragbar wie zuvor.
    """

    _name = "int_filemanager.linkable.mixin"
    _description = "Filemanager: verknüpfbar mit Dateien/Ordnern"

    int_filemanager_count = fields.Integer(
        string="Verknüpfte Dateien", compute="_compute_int_filemanager_count"
    )

    def _compute_int_filemanager_count(self):
        for record in self:
            record.int_filemanager_count = self.env["int_filemanager.file"].search_count(
                [("partner_id", "=", record.id)]
            )

    def action_view_int_filemanager_files(self):
        self.ensure_one()
        # Oeffnet dieselbe native ListView/SearchPanel-Action wie das Hauptmenue
        # (action_filemanager_file_list_native), nur mit einer permanenten partner_id-Domain -
        # seit legacy_ui geloescht ist, gibt es keinen eigenen int_filemanager_browser-Client-
        # Action-Tag mehr, der einen Sondermodus dafuer haette anbieten koennen. context setzt
        # int_filemanager_recursive (siehe search_model_patch.js) - ohne das wuerde die Liste
        # beim Oeffnen nur Wurzel-Datensaetze zeigen (parent_id=False), was bei einer
        # domain-gefilterten Ansicht so gut wie immer leer waere, da verknuepfte Dateien so gut
        # wie nie im Wurzelverzeichnis liegen.
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "int_filemanager.action_filemanager_file_list_native"
        )
        action["name"] = _("Verknüpfte Dateien")
        action["domain"] = [["partner_id", "=", self.id]]
        action["context"] = {"int_filemanager_recursive": 1}
        return action
