import logging
import os
import secrets
import unicodedata
import uuid
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..hash_utils import compute_stable_hash
from ..mediameta import MetaTooLarge, extract_metadata, media_type_of
from ..path_utils import get_root, to_relative

_logger = logging.getLogger(__name__)

# Gesamt-Hashbudget (Bytes) fuer das Ad-hoc-Hashen neu gefundener Kandidaten pro
# Scan-Lauf. "Nur wenige Kandidaten" ist keine garantierte Eigenschaft - ohne
# Budget koennte eine grosse neu aufgetauchte Datei den Scan lange blockieren.
# Kandidaten ueber dem Budget bleiben unangetastet (hash_state='pending') und
# werden konservativ NICHT in diesem Lauf gemergt, sondern beim naechsten
# Lauf bzw. vom asynchronen Hash-Cron erneut versucht.
SCAN_HASH_BUDGET_BYTES = 500 * 1024 * 1024

HASH_CRON_BATCH_SIZE = 200

MEDIA_META_CRON_BATCH_SIZE = 100

# Default-Groessenlimits je Medientyp fuer die Metadatenextraktion, ueberschreibbar
# per ir.config_parameter (int_filemanager.meta_max_bytes_<typ>) ohne Code-Aenderung.
DEFAULT_META_MAX_BYTES = {
    "image": 50 * 1024 * 1024,
    "pdf": 100 * 1024 * 1024,
    "audio": 100 * 1024 * 1024,
}


class IntFilemanagerFile(models.Model):
    _name = "int_filemanager.file"
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
    size = fields.Float(string="Größe (Bytes)")
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
    res_reference = fields.Reference(
        string="Verknüpfter Datensatz",
        selection="_selection_target_model",
        help="Beliebiger Odoo-Datensatz (z.B. Reparaturauftrag, Kontakt), mit dem diese "
        "Datei/dieser Ordner inhaltlich verknüpft ist.",
    )

    def _selection_target_model(self):
        return [(model.model, model.name) for model in self.env["ir.model"].sudo().search([])]

    @api.model
    def search_panel_select_range(self, field_name, **kwargs):
        """Erzwingt is_dir=True fuer den parent_id-Ordnerbaum server-seitig. Noetig, weil das
        native SearchPanel fuer ein Category-Feld (kein select="multi") das eigene domain-
        Attribut der Arch clientseitig gar nicht erst an comodel_domain weiterreicht -
        live verifiziert, siehe docs/int_filemanager_native_ui.md, Smoke-Test-Abschnitt."""
        if field_name == "parent_id":
            kwargs["comodel_domain"] = (kwargs.get("comodel_domain") or []) + [("is_dir", "=", True)]
        return super().search_panel_select_range(field_name, **kwargs)

    content_sha256 = fields.Char(
        index=True,
        copy=False,
        help="SHA-256 des Dateiinhalts, laufend gepflegt (Watcher markiert pending, "
        "ein asynchroner Cron berechnet). Grundlage fuer die Identitaetserkennung "
        "bei einer Umbenennung/Verschiebung, die stattfand, waehrend Odoo nicht lief.",
    )
    hash_size = fields.Integer(copy=False, help="Groesse zum Zeitpunkt der Hash-Berechnung.")
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

    _path_uniq = models.Constraint("UNIQUE(path)", "Für diesen Pfad existiert bereits ein Metadaten-Eintrag.")
    _share_token_uniq = models.Constraint(
        "UNIQUE(share_token)", "Dieses Freigabe-Token ist bereits vergeben."
    )

    def action_generate_share_token(self):
        """Erzeugt (oder rotiert) den anonymen Freigabe-Link - Token und
        Ablauf werden immer gemeinsam neu gesetzt, nie das eine ohne das
        andere veraendert (siehe share_expires_at-Feldkommentar). Die
        eigentliche Berechtigungspruefung uebernimmt der normale write()-Weg
        (ORM -> ir.rule-Schreibregel), kein zusaetzlicher Check hier noetig -
        wer diese Methode ueber die Formularansicht erreichen kann, hat
        bereits Schreibrecht auf den Datensatz."""
        self.ensure_one()
        if self.is_dir:
            raise UserError(_("Nur einzelne Dateien können freigegeben werden, keine Ordner."))
        days = int(self.env["ir.config_parameter"].sudo().get_param("int_filemanager.share_default_days", "30"))
        self.write(
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
        had_token = bool(self.share_token)
        self.write({"share_token": False, "share_expires_at": False})
        if had_token:
            self.env["int_filemanager.share_log"].sudo().create(
                {"file_id": self.id, "path": self.path, "filename": self.name, "event_type": "revoked"}
            )

    def action_open_form(self):
        """Oeffnet das Formular als Dialog - Zielknopf fuer den Pfeil-Button in der nativen
        Listenansicht (native_list_view.js), bewusst getrennt vom Namens-Klick dort (Navigation/
        Vorschau/Download). Ein <button type="object"> in einer Listenzeile loest nie
        openRecord()/den Zeilenklick aus (list_renderer.js: onButtonCellClicked prueft
        ev.target.closest("button") und reicht nur bei Fehltreffer an onCellClicked weiter) -
        deshalb reicht die reine Arch-Deklaration, kein JS-Klick-Abfang noetig."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.display_name,
            "res_model": "int_filemanager.file",
            "res_id": self.id,
            "views": [(False, "form")],
            "target": "new",
        }

    def _cron_scan_filemanager(self):
        self._scan_and_reconcile()

    def _cron_compute_hashes(self):
        """Asynchroner Batch-Job: berechnet content_sha256 fuer alle Dateien mit
        hash_state='pending' (laufender Betrieb via Watcher UND Backfill fuer
        Bestandsdaten laufen ueber dieselbe Queue). Bewusst NICHT synchron im
        Watcher-Thread, damit eine grosse/kaputte Datei nicht die gesamte
        Inotify-Verarbeitung blockiert."""
        root = get_root(self.env)
        Model = self.env["int_filemanager.file"].sudo()
        records = Model.search(
            [("hash_state", "=", "pending"), ("is_dir", "=", False)],
            limit=HASH_CRON_BATCH_SIZE,
        )
        for rec in records:
            abs_path = os.path.join(root, rec.path)
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
        root = get_root(self.env)
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

            abs_path = os.path.join(root, rec.path)
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
                    rec.write(write_vals)
                    if vals["is_dir"]:
                        path_to_id_cache[vals["path"]] = rec.id
                else:
                    new_candidates.append(vals)
            batch.clear()
            self.env.cr.commit()

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

        stale = Model.search([("scan_run_id", "!=", scan_run_id)])
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
                old.write(
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
            stale_dir.write(
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
            for depth in sorted(by_depth):
                level_vals = by_depth[depth]
                for vals in level_vals:
                    vals["parent_id"] = resolve_parent_id(vals["folder_path"] or False)
                created = Model.create(level_vals)
                for rec, vals in zip(created, level_vals):
                    if vals["is_dir"]:
                        path_to_id_cache[vals["path"]] = rec.id

        self.env.cr.commit()

        self.env["ir.config_parameter"].sudo().set_param(
            "int_filemanager.last_scan_completed", fields.Datetime.to_string(fields.Datetime.now())
        )

        _logger.info("int_filemanager: scan finished, index reconciled with %s", root)
