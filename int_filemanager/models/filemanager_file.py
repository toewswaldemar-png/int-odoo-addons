import logging
import os
import unicodedata
import uuid
from datetime import datetime

from odoo import fields, models

from ..hash_utils import compute_stable_hash
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

    _path_uniq = models.Constraint("UNIQUE(path)", "Für diesen Pfad existiert bereits ein Metadaten-Eintrag.")

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

        def flush():
            if not batch:
                return
            paths = [v["path"] for v in batch]
            existing_by_path = {r.path: r for r in Model.search([("path", "in", paths)])}
            for vals in batch:
                rec = existing_by_path.get(vals["path"])
                if rec:
                    write_vals = {k: v for k, v in vals.items() if k != "_abs_path"}
                    if not vals["is_dir"] and (rec.size != vals["size"] or rec.mtime != vals["mtime"]):
                        # Inhalt hat sich seit dem letzten bekannten Stand
                        # geaendert (z.B. Aenderung waehrend der Watcher nicht
                        # lief) - Hash ist nicht mehr aktuell, neu berechnen.
                        write_vals["hash_state"] = "pending"
                    rec.write(write_vals)
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
                    "mtime": vals["mtime"],
                    "last_seen": scan_started,
                    "scan_run_id": scan_run_id,
                }
            )
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
            to_create.append(vals)
        if to_create:
            Model.create(to_create)

        self.env.cr.commit()

        self.env["ir.config_parameter"].sudo().set_param(
            "int_filemanager.last_scan_completed", fields.Datetime.to_string(fields.Datetime.now())
        )

        _logger.info("int_filemanager: scan finished, index reconciled with %s", root)
