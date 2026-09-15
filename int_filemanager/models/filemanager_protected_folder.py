from odoo import api, fields, models
from odoo.exceptions import ValidationError


class IntFilemanagerProtectedFolder(models.Model):
    _name = "int_filemanager.protected_folder"
    _description = "Filemanager geschützter Ordner"
    _order = "path"

    path = fields.Char(
        required=True,
        index=True,
        help="Pfad relativ zum Filemanager-Stammverzeichnis (z.B. 'Buchhaltung' oder "
        "'Buchhaltung/Gehaltsdaten'). Die Wurzel selbst kann nicht geschützt werden.",
    )
    read_group_ids = fields.Many2many(
        "res.groups",
        "int_filemanager_pf_read_rel",
        "folder_id",
        "group_id",
        string="Lesen erlaubt für",
    )
    write_group_ids = fields.Many2many(
        "res.groups",
        "int_filemanager_pf_write_rel",
        "folder_id",
        "group_id",
        string="Schreiben erlaubt für",
    )
    unlink_group_ids = fields.Many2many(
        "res.groups",
        "int_filemanager_pf_unlink_rel",
        "folder_id",
        "group_id",
        string="Löschen erlaubt für",
    )

    _path_uniq = models.Constraint("UNIQUE(path)", "Für diesen Pfad existiert bereits ein Schutz-Eintrag.")

    @api.constrains("path")
    def _check_path(self):
        for rec in self:
            path = (rec.path or "").strip()
            if not path:
                raise ValidationError("Die Wurzel kann nicht als geschützter Ordner registriert werden.")
            if path.startswith("/") or path.endswith("/"):
                raise ValidationError("Der Pfad darf nicht mit '/' beginnen oder enden.")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._rebuild_acl_rules()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._rebuild_acl_rules()
        return res

    def unlink(self):
        res = super().unlink()
        self.env["int_filemanager.protected_folder"]._rebuild_acl_rules()
        return res

    def _rebuild_acl_rules(self):
        from ..acl_rules import rebuild_rules

        rebuild_rules(self.env)

    def _register_hook(self):
        # Selbstheilung, live noetig geworden (2026-09-15): die sechs ir.rule-Datensaetze in
        # security/security.xml haben ohne noupdate="1" bei jedem Modul-Upgrade ihren
        # domain_force auf den dortigen "alles offen"-Platzhalter zurueckgesetzt und damit
        # jeden ueber die UI gesetzten Schutzordner-Eintrag stillschweigend wieder aufgehoben
        # (live an ir_rule.domain_force nachgewiesen: stand nach mehreren "-u
        # int_filemanager"-Upgrades wieder auf "[(1,'=',1)]", obwohl "Kunden und Angebote" als
        # Schutzordner konfiguriert war). noupdate="1" ist jetzt gesetzt und behebt die
        # Upgrade-Ursache direkt - dieser Hook ist die zusaetzliche Absicherung: _register_hook()
        # laeuft bei JEDEM Registry-Aufbau (Odoo ruft es nach dem Laden aller Modul-Daten fuer
        # jedes Modell auf - auch bei einem reinen Server-Neustart ohne Upgrade, live an Odoos
        # eigenem loading.py verifiziert), nicht nur bei "-u". Baut die Regeln unabhaengig vom
        # noupdate-Zustand immer aus dem aktuellen Schutzordner-Stand neu auf - ohne
        # Schutzordner-Eintraege ist das Ergebnis identisch zum Platzhalter, kein Verhaltens-
        # unterschied fuer Installationen ohne konfigurierte Schutzordner.
        super()._register_hook()
        self._rebuild_acl_rules()
