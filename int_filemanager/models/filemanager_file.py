import fnmatch
import logging
import math
import os
import secrets
import shutil
import unicodedata
import uuid
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .. import authz
from ..fulltext import FulltextTooLarge, extract_fulltext, fulltext_type_of, pdf_word_index, suggest_from_text
from ..hash_utils import compute_stable_hash
from ..index_utils import TRASH_DIRNAME, rename_entry, trash_disk_path
from ..mediameta import MetaTooLarge, extract_metadata, media_type_of
from ..path_utils import get_root, resolve_path, to_relative

_logger = logging.getLogger(__name__)

# Default fuer int_filemanager.lock_file_patterns (res_config_settings.py), falls der
# Parameter noch nie gesetzt wurde - bewahrt das bisherige, hartkodierte "~$"-Verhalten
# unveraendert und ergaenzt die beiden vom Nutzer genannten Betriebssystem-/App-eigenen
# Sperr-/Metadatendateien als sinnvollen Startpunkt, nicht als abschliessende Liste.
DEFAULT_LOCK_FILE_PATTERNS = "~$*\nThumbs.db\ndesktop.ini"

# Gesamt-Hashbudget (Bytes) fuer das Ad-hoc-Hashen neu gefundener Kandidaten pro
# Scan-Lauf. "Nur wenige Kandidaten" ist keine garantierte Eigenschaft - ohne
# Budget koennte eine grosse neu aufgetauchte Datei den Scan lange blockieren.
# Kandidaten ueber dem Budget bleiben unangetastet (hash_state='pending') und
# werden konservativ NICHT in diesem Lauf gemergt, sondern beim naechsten
# Lauf bzw. vom asynchronen Hash-Cron erneut versucht.
SCAN_HASH_BUDGET_BYTES = 500 * 1024 * 1024

# Sicherheitsnetz gegen einen partiellen Voll-Wipe (live erlebt, 2026-09-17): ein
# einzelner Mount-Unterbaum (z.B. eine der drei CIFS-Freigaben) kann beim Scan-Start
# noch nicht wirklich eingehaengt sein, waehrend andere Teile des Baums (z.B. die
# lokale Array-Freigabe) normal vorhanden sind - der bisherige "total_walked == 0"-
# Schutz greift dann NICHT (die Gesamtzahl ist nicht null), wuerde aber trotzdem
# alle bestehenden Eintraege unter dem nicht erreichbaren Unterbaum als stale
# loeschen. Ein Wurzel-Unterordner mit mehr als dieser Zeilenzahl im Index gilt als
# "zu gross fuer eine plausible echte Loeschung in einem Lauf" - findet ein Scan
# darunter buchstaeblich 0 Eintraege, wird die Stale-Bereinigung fuer genau diesen
# Unterbaum uebersprungen (Rest des Baums laeuft normal weiter), statt den ganzen
# Lauf abzubrechen.
SCAN_STALE_TOPLEVEL_MIN_ROWS = 50

HASH_CRON_BATCH_SIZE = 200

MEDIA_META_CRON_BATCH_SIZE = 100

# Default-Groessenlimits je Medientyp fuer die Metadatenextraktion, ueberschreibbar
# per ir.config_parameter (int_filemanager.meta_max_bytes_<typ>) ohne Code-Aenderung.
DEFAULT_META_MAX_BYTES = {
    "image": 50 * 1024 * 1024,
    "pdf": 100 * 1024 * 1024,
    "audio": 100 * 1024 * 1024,
}

# Deutlich kleinere Batchgroesse als MEDIA_META_CRON_BATCH_SIZE: OCR eines mehrseitigen Scans kann
# real mehrere Sekunden bis niedrige zweistellige Sekunden dauern (Thumbnail/EXIF/Tags dagegen
# Millisekunden) - ein zu grosser Batch wuerde den Cron-Lauf unnoetig in die Laenge ziehen.
FULLTEXT_CRON_BATCH_SIZE = 20

DEFAULT_FULLTEXT_MAX_BYTES = {
    "plain": 5 * 1024 * 1024,
    "pdf": 50 * 1024 * 1024,
}

# Klartext-Vorschau im "Werte erkennen"-Dialog (Phase C, nur fuer Nicht-PDF-Dateien - PDFs
# bekommen stattdessen den gerenderten Highlight-Viewer) - reine UI-Bequemlichkeit, kein
# Sicherheitslimit wie DEFAULT_FULLTEXT_MAX_BYTES, daher grosszuegig bemessen statt konfigurierbar.
CONTENT_TEXT_PREVIEW_CHARS = 20000

# The only fields of this model a user may write through the ORM (``call_kw``, ``/json/2``).
# Every other field is index, state or content the server derives from the disk and acts
# on: a row pointed at any path would be deleted, published or read by the server. Users
# reach those through the routes and actions, which check the rights on the real path.
USER_WRITABLE_FIELDS = frozenset({"name", "tag_ids", "status_id", "partner_id", "shared_partner_ids"})

# What the review dialog may send as confirmed values.
MAX_EXTRACTED_VALUES = 200
MAX_EXTRACTED_VALUE_CHARS = 1000


class IntFilemanagerFile(models.Model):
    _name = "int_filemanager.file"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Filemanager-Datei"
    _order = "is_dir desc, name"

    name = fields.Char(index=True)
    path = fields.Char(
        required=True,
        index=True,
        help="Pfad relativ zum Filemanager-Stammverzeichnis.",
    )
    folder_path = fields.Char(index=True, help="Pfad des übergeordneten Ordners (leer = Wurzel).")
    # Relationale Repraesentation derselben Hierarchie wie folder_path (das bleibt der
    # literale Dateisystempfad fuer die Syscalls) - fuer den nativen SearchPanel-Ordnerbaum
    # (siehe docs/int_filemanager_native_ui.md). Selbstreferenzierend statt zweites
    # Kategorie-Modell, bewusste Entscheidung dort dokumentiert. ondelete=cascade heisst:
    # ir.attachment-Aufraeumung (thumbnail) fuer per DB-Kaskade mitgeloeschte Nachfahren
    # laeuft NICHT ueber Odoos unlink()-Hook - unkritisch hier, weil index_remove_tree
    # ohnehin den kompletten Teilbaum explizit per unlink() erfasst und die Kaskade damit
    # nie der einzige Loeschweg ist.
    parent_id = fields.Many2one(
        "int_filemanager.file", string="Übergeordneter Ordner", index=True, ondelete="cascade"
    )
    parent_path = fields.Char(index=True)
    _parent_name = "parent_id"
    _parent_store = True
    is_dir = fields.Boolean(string="Ist Ordner", index=True)
    # Nutzerwunsch 2026-09-14, erweitert 2026-09-23: Word/Excel/PowerPoint legen waehrend eine
    # Datei dort offen ist eine Sperrdatei "~$<name>" im selben Ordner an - urspruenglich hart
    # codiertes Praefix. Auf Nutzerwunsch (weitere Sperr-/Metadatendateitypen wie "Thumbs.db")
    # jetzt ueber int_filemanager.lock_file_patterns konfigurierbar (Muster per Zeile, per
    # fnmatch.fnmatch() abgeglichen - siehe DEFAULT_LOCK_FILE_PATTERNS oben, res_config_settings.py).
    # Stored Compute (nicht ueber eine reine Python-Property geloest), damit das Feld in der
    # Suchfilter-Domain unten verwendbar ist - ein Odoo-Domain-Ausdruck kann nur auf echte
    # Modellfelder zugreifen, nicht auf Methoden.
    is_lock_file = fields.Boolean(
        string="Sperrdatei",
        compute="_compute_is_lock_file",
        store=True,
        index=True,
        help="Temporäre Sperr-/Metadatendatei (Name passt auf eines der unter Einstellungen > "
        "Dateimanager konfigurierten Muster, standardmäßig u.a. Office-Sperrdateien \"~$*\" und "
        "\"Thumbs.db\"). Wird ganz normal mitindexiert, ist in der Listenansicht aber "
        "standardmäßig über den Suchfilter ausgeblendet.",
    )
    size = fields.Float(
        string="Größe (Bytes)", digits=(0, 0),
        help="Float statt Integer: Bytes sind zwar nie fraktional, aber int4 (Odoos Integer-Feld) "
        "kappt bei ~2,1 GB - reale Dateien hier werden bis 15 GB groß. digits=(0,0) unterdrückt "
        "trotzdem die Nachkommastellen in der Anzeige.",
    )
    mtime = fields.Datetime(string="Geändert")
    last_seen = fields.Datetime(
        help="Zeitpunkt des letzten Scans, bei dem dieser Eintrag noch auf der Platte existierte "
        "(informativ - für die Stale-Erkennung selbst wird scan_run_id verwendet, da Datetime-Felder "
        "nur sekundengenau verglichen werden und zwei Scans innerhalb derselben Sekunde sonst nichts "
        "als stale erkennen würden).",
    )
    scan_run_id = fields.Char(
        copy=False,
        help="Eindeutige ID des Scan-Laufs, der diesen Datensatz zuletzt auf der Platte bestätigt hat.",
    )
    tag_ids = fields.Many2many("int_filemanager.tag", string="Tags")
    # Baustein 4 (docs/int_filemanager_paperoffice_recherche.md): PaperOffice-Ampel-Freigabe.
    # Erst als state_selection-Selection-Feld umgesetzt (nur zwei Sonderfarben, rot/gruen,
    # hart im Odoo-Kern verdrahtet - siehe Punkt 24 in int_filemanager_native_ui.md), auf
    # Nutzerwunsch dann auf ein frei konfigurierbares Many2one umgestellt: Admins koennen
    # eigene Status-Werte samt Farbe unter "Dateimanager > Konfiguration > Status" anlegen,
    # ohne Code-/Modul-Aenderung. status_color ist ein reines Hilfsfeld fuers badge-Widget
    # (dessen color_field-Option ein Integer-Feld auf demselben Datensatz braucht, siehe
    # web/static/src/views/fields/badge/badge_field.js - kann nicht direkt ueber die
    # Many2one-Relation lesen). string bewusst allgemein "Status" statt "Freigabestatus"
    # (Nutzerwunsch 2026-09-06) - die Werte sind frei konfigurierbar, das Feld ist nicht
    # mehr zwingend an einen Freigabe-Workflow gebunden.
    # Bewusst OHNE default (Nutzerwunsch 2026-09-07) - neue Dateien/Ordner starten ohne
    # Status statt automatisch auf "Offen" (kein required=True, das Feld war schon vorher
    # ueber das Formular leerbar - jetzt ist "leer" auch der tatsaechliche Startzustand,
    # nicht nur ein erreichbarer Zwischenzustand).
    status_id = fields.Many2one(
        "int_filemanager.status",
        string="Status",
        tracking=True,
    )
    status_color = fields.Integer(related="status_id.color", string="Status-Farbe")
    # War zunaechst ein generisches Reference-Feld (beliebiges Odoo-Modell) - auf
    # Nutzerentscheidung 2026-09-07 ersetzt durch ein dediziertes Many2one auf res.partner.
    # Grund: Reference-Feldera rendern nativ eine zweistufige Modell-dann-Datensatz-Auswahl
    # (web/static/src/views/fields/reference/reference_field.xml: <select> ueber ALLE
    # installierten Modelle, erst danach die Many2one-Suche) - fuer den in der Praxis
    # einzigen tatsaechlichen Anwendungsfall (Kunde/Lieferant verknuepfen) unnoetig
    # umstaendlich. Die urspruenglich bewusste Generalitaet (Beispiel im alten Docstring:
    # "z.B. Reparaturauftrag") wird damit aufgegeben, war aber nie tatsaechlich genutzt.
    partner_id = fields.Many2one(
        "res.partner",
        string="Kontakt",
        help="Kunde/Lieferant/Kontakt, mit dem diese Datei/dieser Ordner inhaltlich "
        "verknüpft ist.",
    )

    @api.depends("name")
    def _compute_is_lock_file(self):
        # Parameter einmal pro Aufruf lesen, nicht pro Record - dieser Compute laeuft u.a. beim
        # Voll-Scan ueber potenziell zehntausende Dateien (siehe SCAN_HASH_BUDGET_BYTES-Kommentar
        # oben zur Groessenordnung), ein wiederholtes get_param() pro Record waere unnoetiger
        # Overhead fuer einen Wert, der sich waehrend eines einzelnen Compute-Laufs nie aendert.
        raw_patterns = self.env["ir.config_parameter"].sudo().get_param(
            "int_filemanager.lock_file_patterns", DEFAULT_LOCK_FILE_PATTERNS
        )
        patterns = [p.strip() for p in raw_patterns.splitlines() if p.strip()]
        # .lower() auf beiden Seiten statt fnmatch.fnmatch()s eigener, plattformabhaengiger
        # Gross-/Kleinschreibungsbehandlung (unter Linux standardmaessig case-sensitiv) - die
        # Dateien liegen auf SMB-Freigaben, die von Windows-Clients beschrieben werden
        # ("Thumbs.db" vs. "thumbs.db" soll unabhaengig von der genauen Schreibweise treffen).
        patterns_lower = [p.lower() for p in patterns]
        for record in self:
            name_lower = (record.name or "").lower()
            record.is_lock_file = bool(name_lower) and any(
                fnmatch.fnmatch(name_lower, pattern) for pattern in patterns_lower
            )

    def write(self, vals):
        """Direktes Bearbeiten von "name" im Formular (Nutzerwunsch 2026-09-06) - schreibt
        NICHT einfach die Spalte, sondern loest denselben echten Dateisystem-Rename aus wie
        der bestehende "Umbenennen"-Menuepunkt (rename_entry() in index_utils.py, dieselbe
        Funktion, dieselben Authz-Pruefungen - keine zweite Kopie). Ohne das wuerde der
        DB-Datensatz auf einen Pfad zeigen, der nicht mehr zur echten Datei passt.

        int_filemanager_syncing_index-Kontext-Guard: jede reine Index-Nachpflege, die "name"
        mitschreibt, ohne dass eine echte Rename-Absicht vorliegt, muss diesen Kontext setzen,
        sonst wuerde sie hier faelschlich als (unnoetiger oder mit falschem altem Pfad
        fehlschlagender) Rename-Auftrag verstanden. Betrifft: rename_entry() selbst
        (index_utils.py, schreibt "name" am Ende ueber index_move_tree() zurueck),
        index_upsert() (Watcher-CREATE/MODIFY auf unveraendertem Pfad) und die
        Scan-Reconciliation weiter unten (Vollscan-Refresh sowie Identitaetserkennung nach
        Umbenennen/Verschieben ausserhalb Odoos) - alle bereits entsprechend markiert.
        """
        if "name" in vals and not self.env.context.get("int_filemanager_syncing_index"):
            # A plain write would only change the label and leave the disk entry under its
            # old name, skipping the rights checks of the rename.
            if len(self) > 1:
                raise UserError(self.env._("Rename one entry at a time."))
            if self:
                rename_entry(self.env, self.path, vals.pop("name"))
                if not vals:
                    return True
        return super().write(vals)

    def _has_field_access(self, field, operation):
        if (
            operation == "write"
            and field._module == "int_filemanager"
            and field.name not in USER_WRITABLE_FIELDS
            and not self.env.su
        ):
            return False
        return super()._has_field_access(field, operation)

    content_sha256 = fields.Char(
        index=True,
        copy=False,
        help="SHA-256 des Dateiinhalts, laufend gepflegt (Watcher markiert pending, "
        "ein asynchroner Cron berechnet). Grundlage fuer die Identitaetserkennung "
        "bei einer Umbenennung/Verschiebung, die stattfand, waehrend Odoo nicht lief.",
    )
    hash_size = fields.Float(
        copy=False, digits=(0, 0),
        help="Groesse zum Zeitpunkt der Hash-Berechnung. Float statt Integer wie bei size: "
        "int4 kappt bei ~2,1 GB, reale Dateien werden bis 15 GB gross.",
    )
    hash_source_mtime_ns = fields.Char(
        copy=False, help="mtime_ns zum Zeitpunkt der Hash-Berechnung, verlustfrei als Text."
    )
    hash_state = fields.Selection(
        [
            ("pending", "Ausstehend"),
            ("running", "Läuft"),
            ("done", "Fertig"),
            ("error", "Fehler"),
        ],
        default="pending",
        index=True,
        copy=False,
    )

    # --- "Datenbank hat Vorrang": Veroeffentlichen auf den Share --------------------------------
    # docs/int_filemanager_konzept_db_vorrang_2026-09-24.md, Abschnitt 4.1. Bisher nur vom Upload-
    # Ueberschreiben genutzt (publish_service.py, Durchstich); die uebrigen Schreibwege folgen.
    # Der Request-Commit ist verbindlich: der neue Inhalt liegt dann als Blob im Filestore
    # (pending_content) und share_state='pending' - die Platte folgt per postcommit-Hook bzw. Cron
    # (_cron_publish_pending). "conflict" ist ein Hinweis-Zustand (der Ablauf kann nicht
    # weitermachen, z.B. Bestandsdatei nach dem Ablegen ueber die Versionsgroessengrenze
    # gewachsen), kein blockierender Sperrzustand.
    # OHNE Backfill der Bestandszeilen per ORM: die Spalten werden in
    # migrations/19.0.1.15.0/pre-migrate.py mit Metadaten-Default (PG >= 11, kein Tabellen-
    # Rewrite) angelegt - ein ORM-Backfill wuerde 1,39 Mio. breite Zeilen neu schreiben.
    share_state = fields.Selection(
        [("synced", "Auf Platte"), ("pending", "Wartet auf Veröffentlichung"), ("conflict", "Hinweis")],
        default="synced",
        copy=False,
        help="pending: der Inhalt ist in der Datenbank verbindlich, aber noch nicht auf dem Share "
        "veröffentlicht.",
    )
    revision = fields.Integer(default=0, copy=False, help="Zähler der über die App veröffentlichten Inhaltsstände.")
    pending_content = fields.Binary(
        attachment=True,
        copy=False,
        help="Noch nicht auf den Share veröffentlichter Inhalt (Filestore-Blob, nach dem Veröffentlichen geleert).",
    )
    pending_sha256 = fields.Char(copy=False)
    pending_version_id = fields.Many2one(
        "int_filemanager.version",
        copy=False,
        ondelete="set null",
        help="Bereits committete Sicherung des alten Plattenstands für den laufenden Veröffentlichungsvorgang "
        "(macht den Ablauf nach einem Abbruch wiederholbar, ohne Doppelversion).",
    )
    _share_state_open_idx = models.Index("(share_state) WHERE share_state <> 'synced'")

    # --- Phase 4: Vorschau & Metadaten -----------------------------------
    # meta_state bleibt False/leer fuer Ordner und fuer Dateitypen ohne
    # Extraktor (media_type_of() == None) - nur unterstuetzte Medientypen
    # durchlaufen ueberhaupt "pending", damit der Cron sie nicht faelschlich
    # als unbearbeitet betrachtet. Anders als hash_state also KEIN
    # Feld-Default, sondern explizit von Watcher/Scan gesetzt.
    meta_state = fields.Selection(
        [
            ("pending", "Ausstehend"),
            ("running", "Läuft"),
            ("done", "Fertig"),
            ("error", "Fehler"),
        ],
        index=True,
        copy=False,
    )
    meta_error = fields.Char(copy=False)
    meta_attempts = fields.Integer(copy=False, default=0)
    meta_source_size = fields.Integer(copy=False, help="Groesse zum Zeitpunkt der Extraktion.")
    meta_source_mtime_ns = fields.Char(
        copy=False, help="mtime_ns zum Zeitpunkt der Extraktion, verlustfrei als Text."
    )

    thumbnail = fields.Image(max_width=320, max_height=320, attachment=True, copy=False)
    # Vollbild-Vorschaugroesse (2026-09-20, Nutzerfeedback "Bild baut sich schrittweise auf" bei
    # mehrere-MB-Handyfotos ueber die externe Domain/mobil) - deutlich groesser als thumbnail,
    # aber weit unter der echten Kamera-Aufloesung. Ersetzt NICHT downloadUrl/das Original (siehe
    # controllers/main.py:download) - nur die Bildquelle der Vollbild-Vorschau im Kontroll-/
    # Datei-Viewer wechselt darauf (filemanager_controller_mixin.js:toViewerFile).
    preview = fields.Image(max_width=1920, max_height=1920, attachment=True, copy=False)
    media_width = fields.Integer(copy=False)
    media_height = fields.Integer(copy=False)
    taken_at = fields.Datetime(
        copy=False, help="Aufnahmezeitpunkt aus EXIF, naiv uebernommen (Kamera-Lokalzeit, keine Zeitzonenumrechnung)."
    )
    page_count = fields.Integer(copy=False, string="Seitenzahl")
    audio_duration = fields.Float(copy=False, string="Dauer (Sekunden)")
    audio_title = fields.Char(copy=False)
    audio_artist = fields.Char(copy=False)
    audio_album = fields.Char(copy=False)

    # --- Baustein 1: Volltextsuche/OCR (siehe docs/int_filemanager_paperoffice_recherche.md) ----
    # Eigener ocr_state statt meta_state wiederzuverwenden: OCR ist deutlich teurer als Thumbnail/
    # EXIF/Tags und hat einen anderen Anwendungsbereich (PDF/Text statt Bild/PDF/Audio) - ein
    # eigenes Budget/eigene Retry-Zaehlung vermeidet, dass beide Extraktionen sich gegenseitig
    # ausbremsen. Gleiche vier Zustaende, gleiche Semantik wie meta_state.
    ocr_state = fields.Selection(
        [
            ("pending", "Ausstehend"),
            ("running", "Läuft"),
            ("done", "Fertig"),
            ("error", "Fehler"),
        ],
        index=True,
        copy=False,
    )
    ocr_error = fields.Char(copy=False)
    ocr_attempts = fields.Integer(copy=False, default=0)
    ocr_source_size = fields.Integer(copy=False, help="Groesse zum Zeitpunkt der Extraktion.")
    ocr_source_mtime_ns = fields.Char(
        copy=False, help="mtime_ns zum Zeitpunkt der Extraktion, verlustfrei als Text."
    )
    content_text = fields.Text(
        copy=False, help="Volltext aus OCR/Textextraktion - fuer die Suche, nicht zur Anzeige gedacht."
    )

    # Erkannte Werte (2026-09-19, siehe docs/int_filemanager_ocr_selbstdefinierte_felder.md) -
    # echtes Datensatz-Modell statt eines JSON-Blobs (fields.Properties), ein Datensatz pro Muster
    # mit Treffer. Bis 2026-09-19 gab es zusaetzlich drei fest verdrahtete Char-Felder
    # (extracted_date/_invoice_number/_amount) fuer die drei mitgelieferten Muster - inzwischen
    # vereinheitlicht, jedes Muster (egal ob mitgeliefert oder selbstdefiniert) landet hier.
    # Bestandsdaten wurden per Migration uebernommen, siehe
    # migrations/19.0.1.11.0/post-migrate_legacy_fields_to_extracted_value.py.
    extracted_value_ids = fields.One2many("int_filemanager.extracted_value", "file_id", string="Erkannte Werte")

    # --- Phase 5: Freigaben (intern & extern) -----------------------------
    # "Intern": shared_partner_ids - persistente Freigabe an konkrete Portal-
    # Kontakte, durchgesetzt ueber den Portal-Zweig in acl_rules.py (siehe
    # dort). "Extern": share_token/share_expires_at - ein anonymer Link ohne
    # jedes Login, durchgesetzt ausschliesslich explizit im Controller (siehe
    # /int_filemanager/share/<token>), NICHT ueber ir.rule - beide
    # Mechanismen sind unabhaengig voneinander nutzbar.
    shared_partner_ids = fields.Many2many(
        "res.partner",
        "int_filemanager_shared_partner_rel",
        "file_id",
        "partner_id",
        string="Freigegeben für (Portal-Kontakte)",
        help="Portal-Kontakte mit persistentem Lesezugriff auf diese Datei, unabhängig von "
        "einem Freigabe-Link. Setzt einen Odoo-Portal-Zugang beim Kontakt voraus.",
    )
    share_token = fields.Char(
        copy=False,
        index=True,
        help="Zufälliges Token für den anonymen Freigabe-Link - nur gesetzt, solange die Freigabe "
        "aktiv ist (Widerrufen löscht es wieder).",
    )
    share_expires_at = fields.Datetime(
        copy=False,
        readonly=True,
        help="Wird ausschließlich von 'Link erzeugen' gesetzt (rotiert Token+Ablauf gemeinsam) - "
        "kein frei editierbares Feld, damit nie ein verlängerter Ablauf an einem alten Token hängt.",
    )
    share_url = fields.Char(compute="_compute_share_url", string="Freigabe-Link")

    @api.depends("share_token")
    def _compute_share_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        for rec in self:
            rec.share_url = "%s/int_filemanager/share/%s" % (base_url, rec.share_token) if rec.share_token else False

    # --- Papierkorb (docs/int_filemanager_papierkorb_konzept.md) -----------------------------
    # path/folder_path/parent_id zeigen bei trashed=True auf den tatsaechlichen Ort innerhalb
    # .trash/ (index_utils.trash_destination()/index_trash_tree()) - konsistent mit dem
    # Kernprinzip, dass path immer den echten Plattenort widerspiegelt, nicht auf eine separate
    # "logische" Position. original_path haelt den Pfad vor dem Loeschen fest, fuer Anzeige und
    # als Wiederherstellungsziel (index_restore_tree()).
    trashed = fields.Boolean(index=True, copy=False)
    trashed_at = fields.Datetime(copy=False)
    trashed_by = fields.Many2one("res.users", copy=False, help="Wer die Datei gelöscht hat - Grundlage für den Pro-Nutzer-Papierkorb (siehe rule_file_trash_visibility).")
    original_path = fields.Char(copy=False, help="Pfad vor dem Löschen, für Anzeige und Wiederherstellen.")

    def action_restore(self):
        """Move this trash entry back to the place it was deleted from."""
        self.ensure_one()
        # rule_file_trash_visibility lets a user write only to the own trash entries.
        self.check_access("write")
        if not self.trashed or self.folder_path != TRASH_DIRNAME:
            raise UserError(self.env._("Only entries in the trash can be restored."))
        # The original place may be protected differently now than when it was deleted.
        authz.require(self.env, os.path.dirname(self.original_path or ""), "write")
        from ..index_utils import index_restore_tree

        # sudo: the index fields are server-only, the rights are checked above.
        index_restore_tree(self.env, self.sudo())
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Wiederhergestellt"),
                "message": _("„%s“ wurde an den ursprünglichen Ort zurückverschoben.") % self.name,
                "type": "success",
            },
        }

    @api.ondelete(at_uninstall=False)
    def _unlink_except_live_entries(self):
        """Let users delete only entries of the trash; the live tree changes via the routes."""
        if self.env.su:
            return
        for rec in self:
            if not rec.trashed or trash_disk_path(self.env, rec.path) is None:
                raise AccessError(self.env._("Only entries in the trash can be deleted permanently."))

    def unlink(self):
        """Delete the rows and, for trashed entries, their bytes below .trash/."""
        # Resolved before the rows go; the bytes follow the rows so that a refused delete
        # leaves them alone.
        doomed = []
        for rec in self.filtered("trashed"):
            abs_path = trash_disk_path(self.env, rec.path)
            if abs_path is None:
                _logger.error(
                    "int_filemanager: trashed entry %s (%r) is not below %s, its bytes are left alone",
                    rec.id,
                    rec.path,
                    TRASH_DIRNAME,
                )
                continue
            doomed.append(abs_path)
        result = super().unlink()
        for abs_path in doomed:
            if os.path.isdir(abs_path):
                shutil.rmtree(abs_path)
            elif os.path.exists(abs_path):
                os.remove(abs_path)
        return result

    _path_uniq = models.Constraint("UNIQUE(path)", "Für diesen Pfad existiert bereits ein Metadaten-Eintrag.")
    _share_token_uniq = models.Constraint(
        "UNIQUE(share_token)", "Dieses Freigabe-Token ist bereits vergeben."
    )

    def action_generate_share_token(self):
        """Erzeugt (oder rotiert) den anonymen Freigabe-Link - Token und
        Ablauf werden immer gemeinsam neu gesetzt, nie das eine ohne das
        andere veraendert (siehe share_expires_at-Feldkommentar). Die
        Berechtigungspruefung (Schreibrecht samt Schutzordner-Regeln) steht
        ausdruecklich am Anfang: Token und Ablauf sind nur dem Server
        beschreibbar, geschrieben wird danach per sudo()."""
        self.ensure_one()
        self.check_access("write")
        if self.is_dir:
            raise UserError(_("Nur einzelne Dateien können freigegeben werden, keine Ordner."))
        days = int(self.env["ir.config_parameter"].sudo().get_param("int_filemanager.share_default_days", "30"))
        # sudo: the token fields are server-only; the write right is checked above.
        self.sudo().write(
            {
                "share_token": secrets.token_urlsafe(32),
                "share_expires_at": fields.Datetime.now() + timedelta(days=days),
            }
        )
        self.env["int_filemanager.share_log"].sudo().create(
            {"file_id": self.id, "path": self.path, "filename": self.name, "event_type": "created"}
        )

    def action_revoke_share_token(self):
        self.ensure_one()
        self.check_access("write")
        had_token = bool(self.share_token)
        # sudo: the token fields are server-only; the write right is checked above.
        self.sudo().write({"share_token": False, "share_expires_at": False})
        if had_token:
            self.env["int_filemanager.share_log"].sudo().create(
                {"file_id": self.id, "path": self.path, "filename": self.name, "event_type": "revoked"}
            )

    def _absolute_path(self):
        """Return the disk path of this entry; refuse one that leaves the root.

        ``path`` is index data, so every use of it on the disk goes through here.
        """
        self.ensure_one()
        return resolve_path(self.env, self.path)

    def _cron_scan_filemanager(self):
        self._scan_and_reconcile()

    def _cron_purge_trash(self):
        """Entfernt Papierkorb-Wurzel-Eintraege, die laenger als die konfigurierte Frist
        zurueckliegen - Nachfahren (falls Ordner) verschwinden automatisch mit (Kaskade ueber
        parent_id, ondelete="cascade"), nicht einzeln per unlink() angefasst.

        folder_path == TRASH_DIRNAME statt z.B. "kein trashed-Vorfahre": sowohl ein Wurzel-
        Eintrag als auch seine Nachfahren haben trashed=True UND einen trashed=True-Elternordner
        (der Nachfahre-Elternordner ist selbst Teil des verschobenen Teilbaums) - der einzige
        zuverlaessige Unterschied ist die flache Ablage direkt unter .trash/ (siehe
        index_utils.trash_destination(): Wurzel-Eintraege landen IMMER genau eine Ebene tief,
        nie gespiegelt am urspruenglichen Pfad).

        Frist als Settings-Feld (res_config_settings.py), Default 30 Tage wie bei den meisten
        Papierkorb-Referenzimplementierungen (siehe docs/int_filemanager_papierkorb_konzept.md)."""
        from ..index_utils import TRASH_DIRNAME

        days = int(self.env["ir.config_parameter"].sudo().get_param("int_filemanager.trash_retention_days", "30"))
        cutoff = fields.Datetime.now() - timedelta(days=days)
        Model = self.env["int_filemanager.file"].sudo()
        stale = Model.search([
            ("trashed", "=", True),
            ("trashed_at", "<", cutoff),
            ("folder_path", "=", TRASH_DIRNAME),
        ])
        stale.unlink()

    def _cron_publish_pending(self):
        """Recovery des Ablaufs "Datenbank hat Vorrang" (publish_service.py): holt Zeilen mit
        share_state='pending' nach, deren postcommit-Hook nicht (fertig) gelaufen ist (Prozess-
        abbruch, Fehler, gesperrte Zeile). Jeder Schritt ist wiederholbar."""
        from .. import publish_service

        publish_service.publish_all_pending(self.env)

    def _cron_compute_hashes(self):
        """Asynchroner Batch-Job: berechnet content_sha256 fuer alle Dateien mit
        hash_state='pending' (laufender Betrieb via Watcher UND Backfill fuer
        Bestandsdaten laufen ueber dieselbe Queue). Bewusst NICHT synchron im
        Watcher-Thread, damit eine grosse/kaputte Datei nicht die gesamte
        Inotify-Verarbeitung blockiert."""
        Model = self.env["int_filemanager.file"].sudo()
        records = Model.search(
            [("hash_state", "=", "pending"), ("is_dir", "=", False)],
            limit=HASH_CRON_BATCH_SIZE,
        )
        for rec in records:
            try:
                abs_path = rec._absolute_path()
            except ValidationError:
                _logger.error("int_filemanager: entry %s (%r) leaves the root, not hashed", rec.id, rec.path)
                rec.write({"hash_state": "error"})
                self.env["ir.cron"]._commit_progress(processed=1)
                continue
            result = compute_stable_hash(abs_path)
            if result is None:
                # Datei aendert sich gerade, ist unlesbar oder verschwunden -
                # bleibt pending, naechster Lauf versucht es erneut.
                pass
            else:
                sha256, size, mtime_ns = result
                rec.write(
                    {
                        "content_sha256": sha256,
                        "hash_size": size,
                        "hash_source_mtime_ns": mtime_ns,
                        "hash_state": "done",
                    }
                )
            self.env["ir.cron"]._commit_progress(processed=1)

    def _meta_max_bytes(self, media_type):
        ICP = self.env["ir.config_parameter"].sudo()
        param = ICP.get_param("int_filemanager.meta_max_bytes_%s" % media_type)
        if param:
            try:
                return int(param)
            except ValueError:
                pass
        return DEFAULT_META_MAX_BYTES[media_type]

    def _cron_extract_media_meta(self):
        """Asynchroner Batch-Job, analog zu _cron_compute_hashes: extrahiert
        Vorschau-/Metadaten (Bild-Thumbnail+EXIF, PDF-Seitenzahl, Audio-Tags)
        fuer alle Dateien mit meta_state='pending'. Bewusst NICHT synchron im
        Watcher-Thread - eine grosse/kaputte Mediendatei soll die inotify-
        Verarbeitung nicht blockieren."""
        Model = self.env["int_filemanager.file"].sudo()
        records = Model.search(
            [("meta_state", "=", "pending"), ("is_dir", "=", False)],
            limit=MEDIA_META_CRON_BATCH_SIZE,
        )
        for rec in records:
            media_type = media_type_of(rec.name)
            if media_type is None:
                # Kann durch eine Umbenennung auf eine nicht unterstuetzte
                # Endung entstehen (Watcher setzt pending vor der Pruefung
                # hier) - sicherer Endzustand statt eines Fehlers.
                rec.write({"meta_state": False})
                self.env["ir.cron"]._commit_progress(processed=1)
                continue

            try:
                abs_path = rec._absolute_path()
            except ValidationError:
                _logger.error("int_filemanager: entry %s (%r) leaves the root, no metadata read", rec.id, rec.path)
                rec.write(
                    {
                        "meta_state": "error",
                        "meta_error": "path outside the root",
                        "meta_attempts": rec.meta_attempts + 1,
                    }
                )
                self.env["ir.cron"]._commit_progress(processed=1)
                continue
            max_bytes = self._meta_max_bytes(media_type)
            try:
                result = extract_metadata(abs_path, media_type, max_bytes)
            except MetaTooLarge as exc:
                rec.write(
                    {"meta_state": "error", "meta_error": str(exc), "meta_attempts": rec.meta_attempts + 1}
                )
                self.env["ir.cron"]._commit_progress(processed=1)
                continue
            except Exception as exc:  # noqa: BLE001 - defekte/fremde Mediendatei darf den Batch nicht abbrechen
                _logger.warning("int_filemanager: Metadatenextraktion für %s fehlgeschlagen: %s", rec.path, exc)
                rec.write(
                    {"meta_state": "error", "meta_error": str(exc)[:500], "meta_attempts": rec.meta_attempts + 1}
                )
                self.env["ir.cron"]._commit_progress(processed=1)
                continue

            if result is None:
                # Datei aendert sich gerade oder ist kurz verschwunden -
                # bleibt pending, naechster Lauf versucht es erneut.
                pass
            else:
                result["meta_state"] = "done"
                result["meta_error"] = False
                rec.write(result)
            self.env["ir.cron"]._commit_progress(processed=1)

    def _fulltext_max_bytes(self, fulltext_type):
        ICP = self.env["ir.config_parameter"].sudo()
        param = ICP.get_param("int_filemanager.fulltext_max_bytes_%s" % fulltext_type)
        if param:
            try:
                return int(param)
            except ValueError:
                pass
        return DEFAULT_FULLTEXT_MAX_BYTES[fulltext_type]

    def _extract_fulltext_for_record(self):
        """Fuehrt die Volltextextraktion fuer genau einen Datensatz aus und schreibt das Ergebnis
        - gemeinsamer Kern fuer den Hintergrund-Cron (_cron_extract_fulltext, Pfad B: Scan-
        Eingangsordner, niemand da zum Bestaetigen) UND den interaktiven Analyse-Endpunkt
        (Pfad A: Drag&Drop direkt in die App, siehe controllers/main.py analyze_document) - beide
        wollen exakt dieselbe Extraktion, nur zu unterschiedlichen Zeitpunkten ausgeloest. Gibt
        content_text zurueck (leer, falls nichts extrahiert werden konnte) fuer den interaktiven
        Aufrufer, der direkt im Anschluss Vorschlaege daraus ableiten will. Gibt seit Phase B
        (siehe docs/int_filemanager_ocr_selbstdefinierte_felder.md) ein Tupel (text, word_index)
        zurueck statt nur text - word_index sind Wort-Boxen fuer das PDF-Highlighting (Phase C),
        None bei Klartextdateien oder wenn keine Positionen ermittelt werden konnten. Der
        Hintergrund-Cron unten ignoriert das zweite Element einfach."""
        self.ensure_one()
        fulltext_type = fulltext_type_of(self.name)
        if fulltext_type is None:
            self.write({"ocr_state": False})
            return "", None

        try:
            abs_path = self._absolute_path()
        except ValidationError:
            _logger.error("int_filemanager: entry %s (%r) leaves the root, no text read", self.id, self.path)
            self.write(
                {
                    "ocr_state": "error",
                    "ocr_error": "path outside the root",
                    "ocr_attempts": self.ocr_attempts + 1,
                }
            )
            return "", None

        # Schon fertig extrahiert und die Datei seitdem unveraendert (gleiche Groesse/mtime wie
        # beim letzten Lauf)? Dann reicht der gespeicherte content_text - keine erneute, bei
        # Scan-PDFs teure OCR-Extraktion. Nutzerfeedback 2026-09-07: der interaktive Analyse-
        # Endpunkt (Pfad A, via _analyze_document) rief bisher bei JEDEM "Werte
        # erkennen"-Klick unbedingt neu auf, auch wenn sich an der Datei seit der letzten (ggf.
        # vom Cron laengst erledigten) Extraktion nichts geaendert hatte - z.B. beim erneuten
        # Pruefen nach dem Anlegen eines neuen Erkennungsmusters, wo nur die bereits vorhandenen
        # content_text-Rohdaten neu ausgewertet werden muessen, nicht die Datei selbst. Der Cron
        # unten filtert ohnehin nur auf ocr_state="pending", dieser Kurzschluss greift also
        # ausschliesslich fuer den interaktiven Wiederholungsfall.
        if self.ocr_state == "done":
            try:
                current = os.stat(abs_path)
            except OSError:
                current = None
            if (
                current is not None
                and current.st_size == self.ocr_source_size
                and str(current.st_mtime_ns) == self.ocr_source_mtime_ns
            ):
                # Positionen trotzdem guenstig neu ermitteln (nur ein lesender pdfplumber-Pass,
                # NIE erneut OCRmyPDF - das waere fuer diesen reinen Wiederholungsfall zu teuer,
                # siehe pdf_word_index-Docstring). Liefert [] statt Boxen, wenn die Datei keinen
                # echten Textlayer (mehr) hat - z.B. ein Scan, dessen OCR-Textlayer beim letzten
                # Lauf nur in einer verworfenen Temp-Datei existierte. Die Werte selbst bleiben
                # in dem Fall trotzdem korrekt (aus dem gecachten content_text), nur ohne
                # Markierung im PDF.
                word_index = pdf_word_index(abs_path) if fulltext_type == "pdf" else None
                return self.content_text or "", word_index

        max_bytes = self._fulltext_max_bytes(fulltext_type)
        try:
            result = extract_fulltext(abs_path, fulltext_type, max_bytes)
        except FulltextTooLarge as exc:
            self.write({"ocr_state": "error", "ocr_error": str(exc), "ocr_attempts": self.ocr_attempts + 1})
            return "", None
        except Exception as exc:  # noqa: BLE001 - eine kaputte/fremde Datei darf den Aufrufer nicht abbrechen
            _logger.warning("int_filemanager: Volltextextraktion für %s fehlgeschlagen: %s", self.path, exc)
            self.write({"ocr_state": "error", "ocr_error": str(exc)[:500], "ocr_attempts": self.ocr_attempts + 1})
            return "", None

        if result is None:
            # Datei aendert sich gerade oder ist kurz verschwunden - bleibt pending.
            return "", None

        word_index = result.pop("_word_index", None)
        result["ocr_state"] = "done"
        result["ocr_error"] = False
        self.write(result)
        return result.get("content_text") or "", word_index

    def _cron_extract_fulltext(self):
        """Asynchroner Batch-Job, analog zu _cron_extract_media_meta: extrahiert Volltext (Text
        oder OCR) fuer alle Dateien mit ocr_state='pending'. Das ist Pfad B (siehe
        docs/int_filemanager_paperoffice_recherche.md, Baustein 0/1) - Dateien, die z.B. ueber
        einen beobachteten Scan-Eingangsordner ankommen, wo niemand einen Kontroll-Dialog
        bestaetigen kann. Dient gleichzeitig als Sicherheitsnetz fuer Pfad A (Drag&Drop in die
        App), falls der dortige interaktive Analyse-Aufruf uebersprungen oder abgebrochen wurde -
        ocr_state bleibt in dem Fall pending und wird hier nachgeholt."""
        Model = self.env["int_filemanager.file"].sudo()
        records = Model.search(
            [("ocr_state", "=", "pending"), ("is_dir", "=", False)],
            limit=FULLTEXT_CRON_BATCH_SIZE,
        )
        for rec in records:
            rec._extract_fulltext_for_record()
            self.env["ir.cron"]._commit_progress(processed=1)

    @api.model
    def _analyze_document(self, path):
        """Extract the text of one file and derive suggestions from it.

        Private: it works as superuser, so the caller has to check the write right on
        ``path`` first. ``res_id`` tells the dialog which record to write the tags to.
        """
        empty = {"res_id": False, "suggested_tags": [], "suggested_partner": False,
                 "matches": [], "content_text_preview": ""}
        rec = self.env["int_filemanager.file"].sudo().search([("path", "=", path)], limit=1)
        if not rec or rec.is_dir:
            return empty
        text, word_index = rec._extract_fulltext_for_record()
        if not text:
            return {**empty, "res_id": rec.id}
        result = suggest_from_text(self.env, text, word_index)
        result["content_text_preview"] = text[:CONTENT_TEXT_PREVIEW_CHARS]
        return {**result, "res_id": rec.id}

    @api.model
    def _clean_extracted_values(self, values):
        """Return the confirmed values as rows to create; raise UserError on bad input.

        The values come from the request body, so a wrong type must end as a message.
        """
        invalid = UserError(self.env._("The recognised values are not valid."))
        if not isinstance(values, list) or len(values) > MAX_EXTRACTED_VALUES:
            raise invalid

        def is_number(number):
            if isinstance(number, bool) or not isinstance(number, (int, float)):
                return False
            return math.isfinite(number)

        rows = []
        for item in values:
            if not isinstance(item, dict):
                raise invalid
            pattern_id = item.get("pattern_id")
            value = item.get("value")
            if not pattern_id or not value:
                continue
            if not is_number(pattern_id) or int(pattern_id) != pattern_id:
                raise invalid
            if not isinstance(value, str) or len(value) > MAX_EXTRACTED_VALUE_CHARS:
                raise invalid
            page = item.get("page") or 0
            if not is_number(page) or page < 0 or int(page) != page:
                raise invalid
            box = [item.get(key) or 0.0 for key in ("x0", "y0", "x1", "y1")]
            if not all(is_number(coordinate) for coordinate in box):
                raise invalid
            coordinates = [coordinate or False for coordinate in box]
            rows.append((int(pattern_id), value, int(page) or False, *coordinates))
        pattern_ids = {row[0] for row in rows}
        known = self.env["int_filemanager.extraction_pattern"].browse(pattern_ids).exists()
        if pattern_ids - set(known.ids):
            raise invalid
        return rows

    @api.model
    def _apply_extracted_values(self, path, values):
        """Replace the recognised values of the file at ``path`` by the confirmed ones.

        Private for the same reason as ``_analyze_document``. The old list is replaced
        as a whole, not merged; users have no write ACL on the values, hence ``sudo``.
        """
        rec = self.env["int_filemanager.file"].sudo().search([("path", "=", path)], limit=1)
        if not rec or rec.is_dir:
            return False
        rows = self._clean_extracted_values(values)
        rec.extracted_value_ids.unlink()
        Value = self.env["int_filemanager.extracted_value"].sudo()
        for pattern_id, value, page, x0, y0, x1, y1 in rows:
            Value.create({
                "file_id": rec.id,
                "pattern_id": pattern_id,
                "value": value,
                "page": page,
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
            })
        return True

    def _scan_and_reconcile(self, batch_size=2000):
        """Full filesystem scan, reconciling the search index with disk state.
        Runs in batches with periodic commits since the tree can hold hundreds
        of thousands of entries; safe to call repeatedly (upsert by path).

        Eine Umbenennung/Verschiebung, die passierte waehrend Odoo nicht lief
        (Watcher tot), wuerde ohne Weiteres als Loeschen+Neuanlegen erkannt -
        Tags/Versionen/Metadaten wuerden am neuen Datensatz verloren gehen.
        Deshalb werden neu gefundene Pfade ohne bestehenden Datensatz NICHT
        sofort angelegt, sondern zunaechst als Kandidaten gegen die am Ende
        dieses Laufs "stale" (nicht mehr gesehenen) Datensaetze abgeglichen -
        per Groesse als Vorfilter und SHA-256 als Bestaetigung. Nur bei
        eindeutigem Treffer wird der alte Datensatz auf den neuen Pfad
        umgeschrieben (ID bleibt erhalten); bei Mehrdeutigkeit oder fehlendem
        bestaetigten Hash bleibt es beim heutigen Verhalten (Loeschen+Neu),
        keine Verschlechterung.

        Bekannte, akzeptierte Grenze: ein Ordner ohne direkt eigene Dateien
        (nur verschachtelte Unterordner) hat kein direktes bestaetigtes Kind
        und wird deshalb nicht als Merge erkannt, auch wenn ein tieferer
        Unterordner es waere - sicherer False-Negative statt eines riskanten
        False-Positive.

        Fuer einen komplett leeren Ersteinlese-Scan (nichts vorher indexiert)
        haelt new_candidates den gesamten Baum im Speicher, bis die
        Reconciliation nach dem Walk laeuft - fuer den taeglichen
        Normalbetrieb (meiste Pfade bereits bekannt) bleibt new_candidates
        klein und das Batch-Commit-Verhalten der bestehenden Pfade
        unveraendert."""
        root = get_root(self.env)
        scan_started = fields.Datetime.now()
        # Eindeutige Lauf-ID statt Zeitstempelvergleich fuer die Stale-Erkennung -
        # last_seen (Datetime) ist nur sekundengenau vergleichbar, zwei Scans
        # innerhalb derselben Sekunde wuerden sonst gar nichts als stale
        # erkennen (empirisch im Test aufgefallen).
        scan_run_id = str(uuid.uuid4())
        Model = self.env["int_filemanager.file"].sudo()
        ScanLog = self.env["int_filemanager.scan_log"].sudo()
        batch = []
        total_walked = 0
        new_candidates = []

        # parent_id-Pflege (SearchPanel-Ordnerbaum, siehe docs/int_filemanager_native_ui.md):
        # ein Pfad -> ID-Cache, geteilt ueber den ganzen Scan-Lauf (spart wiederholte Lookups
        # fuer haeufig referenzierte Elternordner ueber Batches/Merges/Neuanlagen hinweg).
        # resolve_parent_id() faellt bei Cache-Miss auf eine einzelne Query zurueck - dank
        # desselben Cursors sieht sie auch bereits in diesem Lauf geschriebene (noch nicht
        # committete) Umbenennungen/Neuanlagen.
        path_to_id_cache = {}

        def resolve_parent_id(folder_path):
            if not folder_path:
                return False
            if folder_path not in path_to_id_cache:
                rec = Model.search([("path", "=", folder_path)], limit=1)
                path_to_id_cache[folder_path] = rec.id if rec else False
            return path_to_id_cache[folder_path]

        def flush():
            if not batch:
                return
            paths = [v["path"] for v in batch]
            existing_by_path = {r.path: r for r in Model.search([("path", "in", paths)])}
            # Batch-Resolve statt Query pro Datensatz: alle in diesem Batch noch nicht
            # gecachten Elternordner-Pfade in einer Abfrage nachladen.
            missing_parents = {
                v["folder_path"] for v in batch if v["folder_path"] and v["folder_path"] not in path_to_id_cache
            }
            if missing_parents:
                for r in Model.search([("path", "in", list(missing_parents))]):
                    path_to_id_cache[r.path] = r.id
                for p in missing_parents:
                    path_to_id_cache.setdefault(p, False)
            for vals in batch:
                rec = existing_by_path.get(vals["path"])
                parent_id = path_to_id_cache.get(vals["folder_path"], False) if vals["folder_path"] else False
                if rec:
                    write_vals = {k: v for k, v in vals.items() if k != "_abs_path"}
                    write_vals["parent_id"] = parent_id
                    if not vals["is_dir"] and (rec.size != vals["size"] or rec.mtime != vals["mtime"]):
                        # Inhalt hat sich seit dem letzten bekannten Stand
                        # geaendert (z.B. Aenderung waehrend der Watcher nicht
                        # lief) - Hash ist nicht mehr aktuell, neu berechnen.
                        write_vals["hash_state"] = "pending"
                        if media_type_of(vals["name"]):
                            write_vals["meta_state"] = "pending"
                    # int_filemanager_syncing_index: rec wurde ueber denselben Pfad gefunden
                    # (existing_by_path[vals["path"]]) - "name" hier ist immer schon der
                    # aktuelle Name, keine Rename-Absicht. Ohne den Guard wuerde jeder
                    # Scan-Lauf fuer JEDE unveraenderte Datei write() (siehe dort) und damit
                    # unnoetig rename_entry() samt Authz-Pruefungen ausloesen.
                    rec.with_context(int_filemanager_syncing_index=True).write(write_vals)
                    if vals["is_dir"]:
                        path_to_id_cache[vals["path"]] = rec.id
                else:
                    new_candidates.append(vals)
            batch.clear()
            self.env.cr.commit()

        # Fuer das per-Unterbaum-Sicherheitsnetz unten: welcher Wurzel-Unterordner
        # (erstes Pfadsegment) hatte in diesem Lauf ueberhaupt mindestens einen
        # tatsaechlich erreichten Eintrag - unabhaengig davon, ob batch_size-Fluesse
        # dazwischen liegen.
        walked_top_levels = set()

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            rel_dir = to_relative(self.env, dirpath)
            for raw_name in dirnames + [f for f in filenames if not f.startswith(".")]:
                # NFC-Normalisierung: Unicode-aequivalente, aber unterschiedlich
                # kodierte Namen (z.B. von macOS-SMB-Clients, NFD) sonst als
                # unterschiedliche Pfade behandelt - relevant fuer die
                # Schutzordner-Pfadpraefix-Erkennung.
                name = unicodedata.normalize("NFC", raw_name)
                abs_path = os.path.join(dirpath, raw_name)
                try:
                    st = os.stat(abs_path)
                    is_dir = os.path.isdir(abs_path)
                except OSError:
                    continue
                rel = f"{rel_dir}/{name}" if rel_dir else name
                total_walked += 1
                walked_top_levels.add(rel.split("/", 1)[0])
                batch.append(
                    {
                        "name": name,
                        "path": rel,
                        "folder_path": rel_dir or False,
                        "is_dir": is_dir,
                        "size": 0 if is_dir else st.st_size,
                        "mtime": datetime.fromtimestamp(st.st_mtime),
                        "last_seen": scan_started,
                        "scan_run_id": scan_run_id,
                        "_abs_path": abs_path,
                    }
                )
                if len(batch) >= batch_size:
                    flush()
        flush()

        # Sicherheitsnetz gegen einen Voll-Wipe des Index (live erlebt, 2026-09-11):
        # os.walk(root) fand bei diesem Lauf ueberhaupt nichts, obwohl der Index bereits
        # Eintraege hat - das ist auf dieser Instanz NIE ein legitimer Zustand (das
        # Stammverzeichnis kann ueber die UI nicht geloescht werden, siehe delete()-Route
        # in controllers/main.py), sondern praktisch immer ein voruebergehendes
        # Mount-/Zugriffsproblem (z.B. HM-Daten/fuse.shfs kurz nach einem Odoo-Neustart noch
        # nicht bereit). Ohne diese Bremse wuerde die Stale-Erkennung unten JEDEN
        # bestehenden Datensatz als verwaist behandeln und komplett loeschen - reale
        # Dateien blieben unangetastet, aber Tags/Status/Freigaben/Versionen/OCR-Text waeren
        # unwiederbringlich weg. Root-Ursache des beobachteten Vorfalls blieb ungeklaert
        # (kein Fehler im Log, os.walk lieferte einfach 0 Eintraege trotz vorhandener
        # Dateien) - dieser Guard verhindert den Schaden unabhaengig von der genauen Ursache.
        if total_walked == 0 and Model.search_count([]) > 0:
            _logger.error(
                "int_filemanager: scan fand 0 Eintraege unter %s, obwohl der Index nicht "
                "leer ist - ueberspringe die Stale-Bereinigung (vermutlich ein "
                "voruebergehendes Mount-/Zugriffsproblem, kein echter Voll-Wipe).",
                root,
            )
            return

        stale = Model.search([("scan_run_id", "!=", scan_run_id)])

        # Per-Unterbaum-Sicherheitsnetz (siehe SCAN_STALE_TOPLEVEL_MIN_ROWS oben, live als
        # Luecke gefunden 2026-09-17): ein Wurzel-Unterordner mit vielen bestehenden
        # Eintraegen, der in diesem Lauf aber buchstaeblich 0 Eintraege geliefert hat, gilt
        # als vermutlich nicht erreichbar (z.B. CIFS-Mount beim Scan-Start noch nicht bereit)
        # statt als echte Loeschung - seine Eintraege werden komplett aus der weiteren
        # Stale-Verarbeitung (Merge-Erkennung UND Loeschung) herausgenommen, der Rest des
        # Baums laeuft unveraendert weiter. Ergaenzt den bestehenden total_walked==0-Schutz
        # oben, der nur den Fall "der GESAMTE Baum liefert nichts" abdeckt.
        stale_top_level_counts = {}
        for rec in stale:
            top = rec.path.split("/", 1)[0]
            stale_top_level_counts[top] = stale_top_level_counts.get(top, 0) + 1
        suspicious_top_levels = {
            top
            for top, count in stale_top_level_counts.items()
            if top not in walked_top_levels and count >= SCAN_STALE_TOPLEVEL_MIN_ROWS
        }
        if suspicious_top_levels:
            _logger.error(
                "int_filemanager: Scan fand 0 Eintraege unter %s (bestehender Index-Bestand "
                "je Unterbaum: %s) - vermutlich ein nicht erreichbarer Mount, ueberspringe "
                "die Stale-Bereinigung fuer diese(n) Unterbaum/-baeume statt sie als "
                "geloescht zu behandeln.",
                ", ".join(sorted(suspicious_top_levels)),
                {top: stale_top_level_counts[top] for top in suspicious_top_levels},
            )
            stale = stale.filtered(lambda r: r.path.split("/", 1)[0] not in suspicious_top_levels)

        merged_stale_ids = set()
        merged_new_indices = set()
        # (old_folder_path, new_folder_path) je erfolgreich gemergter Datei -
        # Grundlage fuer die anschliessende Ordner-Identitaet.
        merge_folder_pairs = []
        hash_budget_remaining = SCAN_HASH_BUDGET_BYTES

        # --- Datei-Identitaet: Groesse als Vorfilter, SHA-256 als Bestaetigung ---
        # Gruppenbasiert statt "erster Treffer gewinnt": ein Merge passiert nur,
        # wenn fuer ein (size, sha256)-Schluesselpaar GENAU ein stale UND GENAU
        # ein neuer Kandidat existieren. Bei identischem Inhalt an mehreren neuen
        # Orten (mehrere neue Kandidaten, ein stale Datensatz) waere die Wahl
        # sonst von der - nicht garantierten - os.walk-Reihenfolge abhaengig;
        # das gilt als mehrdeutig, nicht als Treffer.
        stale_files_by_size = {}
        for rec in stale:
            if not rec.is_dir:
                stale_files_by_size.setdefault(rec.size, []).append(rec)

        new_by_key = {}
        for idx, vals in enumerate(new_candidates):
            if vals["is_dir"]:
                continue
            confirmed_stale = [r for r in stale_files_by_size.get(vals["size"], []) if r.hash_state == "done"]
            if not confirmed_stale:
                continue
            if hash_budget_remaining < vals["size"]:
                continue
            digest = compute_stable_hash(vals["_abs_path"])
            hash_budget_remaining -= vals["size"]
            if digest is None:
                continue
            sha256, confirmed_size, _mtime_ns = digest
            if confirmed_size != vals["size"]:
                continue
            new_by_key.setdefault((int(confirmed_size), sha256), []).append(idx)

        stale_by_key = {}
        for rec in stale:
            if not rec.is_dir and rec.hash_state == "done" and rec.content_sha256:
                stale_by_key.setdefault((int(rec.size), rec.content_sha256), []).append(rec)

        for key, new_idxs in new_by_key.items():
            stale_recs = stale_by_key.get(key, [])
            if not stale_recs:
                continue
            if len(new_idxs) == 1 and len(stale_recs) == 1:
                idx = new_idxs[0]
                vals = new_candidates[idx]
                old = stale_recs[0]
                old_path = old.path
                old_folder_path = old.folder_path or ""
                # int_filemanager_syncing_index: die Datei wurde ausserhalb Odoos
                # umbenannt/verschoben (sonst waere sie nicht "stale") - das hier ist reine
                # Index-Nachpflege auf den bereits existierenden neuen Pfad, kein Auftrag an
                # write() (siehe dort), noch einmal einen (nicht mehr existierenden) alten
                # Pfad umzubenennen.
                old.with_context(int_filemanager_syncing_index=True).write(
                    {
                        "name": vals["name"],
                        "path": vals["path"],
                        "folder_path": vals["folder_path"],
                        "parent_id": resolve_parent_id(vals["folder_path"] or False),
                        "mtime": vals["mtime"],
                        "last_seen": scan_started,
                        "scan_run_id": scan_run_id,
                        # content_sha256/hash_size/hash_state bleiben unveraendert -
                        # der Inhalt hat sich nicht geaendert, nur der Pfad.
                    }
                )
                merged_stale_ids.add(old.id)
                merged_new_indices.add(idx)
                merge_folder_pairs.append((old_folder_path, vals["folder_path"] or ""))
                ScanLog.create(
                    {
                        "scan_started": scan_started,
                        "event_type": "merged",
                        "old_path": old_path,
                        "new_path": vals["path"],
                    }
                )
            else:
                size_key, sha256_key = key
                ScanLog.create(
                    {
                        "scan_started": scan_started,
                        "event_type": "ambiguous",
                        "detail": "Hash %s (Größe %s): %d neue(r) Kandidat(en) gegen %d stale Datensatz/-sätze "
                        "- kein Merge." % (sha256_key, size_key, len(new_idxs), len(stale_recs)),
                    }
                )

        # --- Ordner-Identitaet: nur bei mindestens einem bestaetigten Kind ---
        old_to_new_folder = {}
        ambiguous_folder_sources = set()
        for old_fp, new_fp in merge_folder_pairs:
            if old_fp in old_to_new_folder and old_to_new_folder[old_fp] != new_fp:
                ambiguous_folder_sources.add(old_fp)
            else:
                old_to_new_folder[old_fp] = new_fp

        stale_dir_by_path = {r.path: r for r in stale if r.is_dir and r.id not in merged_stale_ids}
        new_dir_idx_by_path = {
            v["path"]: i for i, v in enumerate(new_candidates) if v["is_dir"] and i not in merged_new_indices
        }
        used_new_dir_indices = set()

        for old_fp, new_fp in old_to_new_folder.items():
            if old_fp in ambiguous_folder_sources or not old_fp:
                continue
            stale_dir = stale_dir_by_path.get(old_fp)
            new_idx = new_dir_idx_by_path.get(new_fp)
            if stale_dir is None or new_idx is None or new_idx in used_new_dir_indices:
                continue
            vals = new_candidates[new_idx]
            old_path = stale_dir.path
            # int_filemanager_syncing_index: siehe Kommentar bei der Datei-Reconciliation
            # oben - reine Index-Nachpflege, kein Rename-Auftrag an write().
            stale_dir.with_context(int_filemanager_syncing_index=True).write(
                {
                    "name": vals["name"],
                    "path": vals["path"],
                    "folder_path": vals["folder_path"],
                    "parent_id": resolve_parent_id(vals["folder_path"] or False),
                    "mtime": vals["mtime"],
                    "last_seen": scan_started,
                    "scan_run_id": scan_run_id,
                }
            )
            # Dieser Ordner behaelt seine ID (Merge, kein Neuanlegen) - Kinder,
            # die spaeter in diesem Lauf ueber ihn aufgeloest werden (auch als
            # Elternordner-Kandidat fuer noch zu erstellende Eintraege unten),
            # muessen ihn unter seinem NEUEN Pfad finden.
            path_to_id_cache[vals["path"]] = stale_dir.id
            merged_stale_ids.add(stale_dir.id)
            merged_new_indices.add(new_idx)
            used_new_dir_indices.add(new_idx)
            ScanLog.create(
                {
                    "scan_started": scan_started,
                    "event_type": "merged",
                    "old_path": old_path,
                    "new_path": vals["path"],
                    "detail": "Ordner-Merge über bestätigtes Kind abgeleitet.",
                }
            )

        remaining_stale = stale.filtered(lambda r: r.id not in merged_stale_ids)
        if remaining_stale:
            _logger.info("int_filemanager: removing %s stale index entries", len(remaining_stale))
            remaining_stale.unlink()

        to_create = []
        for i, vals in enumerate(new_candidates):
            if i in merged_new_indices:
                continue
            vals = {k: v for k, v in vals.items() if k != "_abs_path"}
            if not vals["is_dir"]:
                vals["hash_state"] = "pending"
                if media_type_of(vals["name"]):
                    vals["meta_state"] = "pending"
            to_create.append(vals)
        if to_create:
            # In Ebenen anlegen statt einer einzigen create()-Liste: ein Kind braucht die
            # bereits vergebene DB-ID seines Elternordners fuer parent_id, die bei einem
            # kompletten Ersteinlese-Scan (frisch entdeckter ganzer Teilbaum) noch nicht
            # existiert. os.walk liefert Eltern zwar bereits vor Kindern, aber batch_size-
            # Aufteilung/Merge-Reihenfolge garantieren das nicht zuverlaessig genug fuer
            # eine einzige Erstellung - daher explizit nach Pfadtiefe sortiert und pro
            # Ebene erstellt, mit path_to_id_cache als wachsendem Zwischenspeicher.
            by_depth = {}
            for vals in to_create:
                depth = vals["folder_path"].count("/") + 1 if vals["folder_path"] else 0
                by_depth.setdefault(depth, []).append(vals)
            # Zusaetzlich in batch_size-Haeppchen INNERHALB jeder Ebene - live als Bug
            # gefunden 2026-09-14 (MemoryError beim Erstimport einer 129GB-Netzwerkfreigabe):
            # ohne diese Aufteilung entsteht ein einziger unbegrenzt grosser create()-Aufruf,
            # sobald eine Ebene viele direkte Kinder hat (z.B. ein Ordner mit tausenden
            # Dateien). Sicher innerhalb einer Ebene, weil Geschwister nie voneinander
            # abhaengen - nur vom (bereits vollstaendig angelegten) Elternordner einer
            # flacheren Ebene. Commit pro Haeppchen macht Fortschritt ausserdem live in der
            # DB sichtbar und rettet bereits gescannte Haeppchen vor einem spaeteren Absturz.
            for depth in sorted(by_depth):
                level_vals = by_depth[depth]
                for vals in level_vals:
                    vals["parent_id"] = resolve_parent_id(vals["folder_path"] or False)
                for i in range(0, len(level_vals), batch_size):
                    chunk = level_vals[i : i + batch_size]
                    created = Model.create(chunk)
                    for rec, vals in zip(created, chunk):
                        if vals["is_dir"]:
                            path_to_id_cache[vals["path"]] = rec.id
                    self.env.cr.commit()

        self.env.cr.commit()

        self.env["ir.config_parameter"].sudo().set_param(
            "int_filemanager.last_scan_completed", fields.Datetime.to_string(fields.Datetime.now())
        )

        _logger.info("int_filemanager: scan finished, index reconciled with %s", root)
