import os
import secrets
import shutil
import unicodedata
from datetime import datetime

from odoo import _, fields
from odoo.exceptions import UserError
from odoo.tools.sql import escape_psql

from . import authz
from .fulltext import fulltext_type_of
from .mediameta import media_type_of
from .path_utils import get_root, resolve_path, safe_name, suppress_watcher, to_relative

BUS_CHANNEL = "int_filemanager"
BUS_NOTIFICATION_TYPE = "int_filemanager.change"

# Punkt-Praefix: sowohl der Watcher (watcher.py:_is_hidden()) als auch der Vollscan
# (models/filemanager_file.py) schliessen punktpraefixierte Namen bereits aus - der Papierkorb
# nutzt genau diese bestehende Konvention, statt eine eigene Ausschlussregel zu brauchen (siehe
# docs/int_filemanager_papierkorb_konzept.md).
TRASH_DIRNAME = ".trash"


def _notify_change(env):
    """Tell any open Filemanager view to refresh - queued for delivery on
    commit (bus.bus._sendone writes via env.cr.precommit), so it only
    actually reaches clients once the caller's transaction lands."""
    env["bus.bus"]._sendone(BUS_CHANNEL, BUS_NOTIFICATION_TYPE, {})


def _entry_vals(env, abs_path):
    st = os.stat(abs_path)
    # NFC-Normalisierung: Unicode-aequivalente, aber unterschiedlich kodierte
    # Pfade (z.B. von macOS-SMB-Clients, NFD) sonst als unterschiedliche Pfade
    # behandelt - relevant fuer die Schutzordner-Pfadpraefix-Erkennung.
    rel = unicodedata.normalize("NFC", to_relative(env, abs_path))
    parent_rel = os.path.dirname(rel) if rel else ""
    is_dir = os.path.isdir(abs_path)
    vals = {
        "name": unicodedata.normalize("NFC", os.path.basename(abs_path)),
        "path": rel,
        "folder_path": parent_rel or False,
        "is_dir": is_dir,
        "size": 0 if is_dir else st.st_size,
        "mtime": datetime.fromtimestamp(st.st_mtime),
        "last_seen": fields.Datetime.now(),
    }
    if not is_dir:
        # Watcher-getriebenes CREATE/MODIFY markiert den Inhalt immer als neu
        # zu hashen - der asynchrone Hash-Cron berechnet content_sha256 danach.
        vals["hash_state"] = "pending"
        if media_type_of(vals["name"]):
            # Dasselbe unbedingt-pending-Verhalten fuer unterstuetzte
            # Medientypen - der Metadaten-Cron extrahiert danach neu. Alte
            # Werte (Thumbnail etc.) bleiben bis dahin unveraendert stehen,
            # write() unten aendert nur die hier gesetzten Felder.
            vals["meta_state"] = "pending"
        if fulltext_type_of(vals["name"]):
            # Gleiches Prinzip fuer den Volltext (Baustein 1) - eigener Zustand (ocr_state), siehe
            # filemanager_file.py fuer die Begruendung der Trennung von meta_state. Bewusst KEIN
            # Backfill fuer bereits vor dieser Aenderung indexierte Bestandsdateien (Entscheidung
            # 2026-09-05) - nur neu ankommende/geaenderte Dateien ab jetzt.
            vals["ocr_state"] = "pending"
    return vals


def index_upsert(env, abs_path):
    """Create or refresh the index record for a single filesystem path.

    Race-Absicherung (docs/int_filemanager_papierkorb_konzept.md, live 2026-09-21
    ueberarbeitet): der VORHERIGE Ansatz - ein pg_advisory_xact_lock VOR der Suche - konnte das
    Watcher-vs-App-Rennen strukturell nicht loesen. Odoo setzt seine Cursor auf REPEATABLE READ
    (sql_db.py) - eine Transaktion, die auf einen Lock gewartet hat, sieht bei ihrer
    anschliessenden Suche trotzdem nur ihren eingefrorenen Schnappschuss, nie den inzwischen
    committeten Gewinner. Die eigentliche, an der Wurzel ansetzende Loesung: der Watcher
    unterdrueckt sich fuer App-eigene Pfade jetzt selbst (path_utils.suppress_watcher(), von
    allen App-Aufrufern - Upload/mkdir/Papierkorb/Wiederherstellen/Umbenennen/Verschieben - um
    die jeweilige physische Operation gelegt) - der Watcher versucht fuer diese Pfade also gar
    nicht erst, parallel denselben Datensatz zu pflegen. Fuer den seltenen Rest (zwei
    GLEICHZEITIGE App-Anfragen, oder falls die Unterdrueckung doch einmal nicht greift) reicht
    kein reines ORM: Odoo wiederholt einen UniqueViolation NICHT automatisch (nur
    SerializationFailure/DeadlockDetected, service/model.py:retrying(), live am Odoo-19-
    Quellcode verifiziert), siehe _upsert_by_path() fuer die atomare Alternative.
    """
    Model = env["int_filemanager.file"].sudo()
    vals = _entry_vals(env, abs_path)
    parent_rel = vals["folder_path"]
    # Unmittelbarer Elternordner ist bei Watcher-/Mkdir-getriebenen Einzelaenderungen immer
    # schon selbst indexiert (er muss existieren, damit dieser Pfad ueberhaupt entstehen
    # konnte) - anders als beim BFS-Ersteinlese-Scan reicht hier eine einzelne Query.
    vals["parent_id"] = Model.search([("path", "=", parent_rel)], limit=1).id if parent_rel else False

    rec = Model.search([("path", "=", vals["path"])], limit=1)
    if rec:
        # int_filemanager_syncing_index: Watcher-getriebenes CREATE/MODIFY auf einem
        # unveraenderten Pfad (nur Inhalt/Metadaten aktualisiert) - vals enthaelt "name"
        # immer (aus _entry_vals), aber das ist keine Rename-Absicht. Ohne den Guard wuerde
        # int_filemanager.file.write() (siehe dort) hier bei JEDER Inhaltsaenderung
        # faelschlich rename_entry() ausloesen, inkl. dessen Authz-Pruefungen - die dieser
        # sudo()-Aufruf hier bewusst NICHT durchlaufen soll (Watcher-Indexierung muss immer
        # durchlaufen, unabhaengig von Schutzordner-Rechten).
        rec.with_context(int_filemanager_syncing_index=True).write(vals)
    else:
        rec = _upsert_by_path(env, vals)
    _notify_change(env)
    return rec


def _upsert_by_path(env, vals):
    """Atomarer Ersatz fuer Model.create() im "existiert noch nicht"-Zweig von index_upsert()
    (und den Selbstheilungs-Stellen in diesem Modul) - ein einzelnes
    INSERT ... ON CONFLICT (path) DO UPDATE, das (anders als eine SELECT-dann-INSERT-Folge
    unter REPEATABLE READ) immer den tatsaechlichen aktuellen Stand prueft, nicht Odoos
    eingefrorenen Transaktions-Schnappschuss - siehe index_upsert()-Docstring fuer die
    Begruendung, warum das hier nicht durch reines ORM ersetzbar ist. Offizielle Postgres-
    Empfehlung fuer genau dieses Muster (postgresql.org/docs/current/transaction-iso.html).

    Bypasst Model.create()/write(), muss also die Handvoll Felder nachbilden, die Model.create()
    sonst automatisch ueber ihren Python-Default fuellt: hash_state="pending" und
    meta_attempts/ocr_attempts=0 sind die einzigen Felder auf diesem Modell mit einem
    (grep -n "default=" auf filemanager_file.py) - alles andere, was hier fehlt, wird NULL/
    False, genau wie bei einem echten create().

    invalidate_model(): rohes SQL ist fuer Odoos ORM-Cache unsichtbar - ohne das wuerde ein
    bereits VOR diesem Aufruf im selben Environment gecachter Datensatz fuer dieselbe id weiter
    seine alten Feldwerte zeigen, obwohl die DB-Zeile gerade per ON CONFLICT aktualisiert wurde
    (live als Test-Fehlschlag gefunden, 2026-09-21)."""
    cols = dict(vals)
    cols.setdefault("hash_state", "pending")
    cols["meta_attempts"] = 0
    cols["ocr_attempts"] = 0
    now = fields.Datetime.now()
    cols["create_date"] = now
    cols["create_uid"] = env.uid
    cols["write_date"] = now
    cols["write_uid"] = env.uid

    # Bei einem Konflikt nur echte vals-Felder aktualisieren - dieselbe Menge, die auch
    # rec.write(vals) an anderer Stelle in diesem Modul anfassen wuerde. meta_attempts/
    # ocr_attempts (Retry-Zaehler) und create_date/create_uid eines bereits existierenden
    # Datensatzes bleiben unangetastet, write_date/write_uid werden wie bei jedem echten
    # ORM write() nachgezogen.
    update_cols = [c for c in vals if c != "path"] + ["write_date", "write_uid"]

    columns = list(cols.keys())
    query = 'INSERT INTO int_filemanager_file ({}) VALUES ({}) ON CONFLICT (path) DO UPDATE SET {} RETURNING id'.format(
        ", ".join('"%s"' % c for c in columns),
        ", ".join(["%s"] * len(columns)),
        ", ".join('"%s" = EXCLUDED."%s"' % (c, c) for c in update_cols),
    )
    # False ist Odoos eigene "leer"-Konvention fuer Char/Many2one (folder_path/parent_id an der
    # Wurzel) - psycopg2 braucht dafuer echtes None/NULL, sonst laeuft z.B. parent_id=False als
    # Integer 0 statt NULL in die Spalte. is_dir ist das einzige echte Boolean-Feld hier, wo
    # False ein gueltiger Wert bleibt statt "leer" zu bedeuten.
    params = tuple(cols[c] if c == "is_dir" or cols[c] is not False else None for c in columns)
    env.cr.execute(query, params)
    (row_id,) = env.cr.fetchone()
    env["int_filemanager.file"].invalidate_model(columns)
    return env["int_filemanager.file"].sudo().browse(row_id)


def index_remove_tree(env, rel_path):
    """Remove the index record for rel_path and, if it was a folder, all descendants."""
    Model = env["int_filemanager.file"].sudo()
    # escape_psql(): rel_path kommt aus einem echten Datei-/Ordnernamen, der "%"/"_" enthalten
    # kann - beides SQL-LIKE-Wildcards. Ungeschaetzt wuerde z.B. "Plan_2026" auch Zeilen eines
    # unbeteiligten Nachbarn wie "PlanX2026" treffen ("_" matcht ein beliebiges Zeichen). Gleiche
    # Absicherung wie bereits in acl_rules.py/authz.py fuer denselben "=like"-Praefix-Aufbau.
    Model.search(["|", ("path", "=", rel_path), ("path", "=like", escape_psql(rel_path) + "/%")]).unlink()
    _notify_change(env)


def index_move_tree(env, old_rel, new_rel):
    """Rewrite path/folder_path for a renamed or moved file/folder and all its descendants."""
    Model = env["int_filemanager.file"].sudo()
    new_parent = os.path.dirname(new_rel) if new_rel else ""

    root = Model.search([("path", "=", old_rel)], limit=1)
    if root:
        # Nur die verschobene Wurzel braucht ein neues parent_id - Nachfahren behalten
        # denselben unmittelbaren Elternordner (dieselbe ID) innerhalb des mitverschobenen
        # Teilbaums, _parent_store kaskadiert deren parent_path automatisch mit.
        new_parent_rec = Model.search([("path", "=", new_parent)], limit=1) if new_parent else Model.browse()
        # int_filemanager_syncing_index: reine Index-Nachpflege, kein neuer Rename-Wunsch -
        # ohne den Kontext wuerde int_filemanager.file.write() (siehe dort) "name" hier als
        # Auftrag missverstehen, die (bereits umbenannte!) Datei ein zweites Mal
        # umzubenennen, mit dem inzwischen falschen alten Pfad.
        root.with_context(int_filemanager_syncing_index=True).write({
            "path": new_rel,
            "name": os.path.basename(new_rel),
            "folder_path": new_parent or False,
            "parent_id": new_parent_rec.id,
        })

    prefix = old_rel + "/"
    # escape_psql(): dieselbe Wildcard-Absicherung wie in index_remove_tree() oben.
    for rec in Model.search([("path", "=like", escape_psql(prefix) + "%")]):
        suffix = rec.path[len(old_rel):]
        new_child_path = new_rel + suffix
        new_child_parent = os.path.dirname(new_child_path)
        rec.write({"path": new_child_path, "folder_path": new_child_parent or False})
    _notify_change(env)


def _trash_name(original_name):
    """Kollisionsarmer Papierkorb-Dateiname - bewusst UNABHAENGIG von jeder DB-ID (waere bei
    einem verlorenen Watcher-Rennen, siehe index_trash_tree(), nicht zuverlaessig verfuegbar,
    schon BEVOR wir wissen, ob wir den Selbstheilungspfad brauchen). Gleiches Schema wie
    friendly_fallback_name() in path_utils.py."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(2)
    return "%s_%s__%s" % (stamp, suffix, original_name)


def trash_destination(env, rel):
    """Berechnet den Papierkorb-Zielpfad fuer den (noch existierenden) Pfad rel - reiner
    Namensentscheid ohne DB-Zugriff, siehe _trash_name(). Ruft _ensure_trash_folder() auf, damit
    der physische .trash-Ordner vor dem eigentlichen shutil.move() des Aufrufers garantiert
    existiert."""
    _ensure_trash_folder(env)
    name = os.path.basename(rel)
    return "%s/%s" % (TRASH_DIRNAME, _trash_name(name))


def _ensure_trash_folder(env):
    """Stellt sicher, dass .trash als eigener, aber unsichtbarer (trashed=True) Ordner-Datensatz
    existiert. Scan/Watcher legen ihn NIE an (dot-Praefix-Ausschluss, siehe TRASH_DIRNAME oben) -
    der Papierkorb-Code muss also selbst dafuer sorgen, sonst waere parent_id fuer den ersten
    Papierkorb-Eintrag nicht aufloesbar. _upsert_by_path() statt Model.create() fuer den seltenen
    Fall zweier gleichzeitiger ERSTER Papierkorb-Operationen (kein Watcher-Rennen hier moeglich -
    der Watcher sieht .trash nie -, aber zwei App-Anfragen koennten sich theoretisch
    ueberholen)."""
    Model = env["int_filemanager.file"].sudo()
    os.makedirs(os.path.join(get_root(env), TRASH_DIRNAME), exist_ok=True)
    rec = Model.search([("path", "=", TRASH_DIRNAME)], limit=1)
    if rec:
        return rec
    return _upsert_by_path(env, {
        "name": TRASH_DIRNAME,
        "path": TRASH_DIRNAME,
        "folder_path": False,
        "is_dir": True,
        "size": 0,
        "trashed": True,
        "trashed_at": fields.Datetime.now(),
        "trashed_by": env.uid,
    })


def _insert_trashed_from_disk(env, trash_rel, parent_id, original_path):
    """Selbstheilungspfad fuer index_trash_tree(): baut einen frischen, sofort als trashed
    markierten Datensatz aus der Datei/dem Ordner, die JETZT bereits auf trash_rel liegt - fuer
    den (dank path_utils.suppress_watcher() seltenen) Fall, dass der urspruengliche Datensatz
    schon verschwunden war. Wiederverwendet _entry_vals() ganz normal (liest den tatsaechlichen,
    jetzt korrekten Plattenzustand)."""
    abs_path = resolve_path(env, trash_rel)
    vals = _entry_vals(env, abs_path)
    vals["parent_id"] = parent_id
    vals["trashed"] = True
    vals["trashed_at"] = fields.Datetime.now()
    vals["trashed_by"] = env.uid
    vals["original_path"] = original_path
    return _upsert_by_path(env, vals)


def index_trash_tree(env, old_rel, trash_rel):
    """Nachpflege im Index, NACHDEM die aufrufende Route Datei/Ordner physisch bereits nach
    trash_rel verschoben hat (shutil.move) - setzt trashed/trashed_at/trashed_by/original_path
    und schreibt path/folder_path/parent_id auf den neuen Ort um, fuer den verschobenen Eintrag
    selbst UND alle Nachfahren (falls Ordner).

    Race-Absicherung liegt jetzt beim Aufrufer (controllers/main.py:delete() legt alles ab
    dem shutil.move() in path_utils.suppress_watcher(alter_pfad)) - der Watcher versucht fuer
    diesen Pfad also gar nicht erst parallel index_remove_tree() aufzurufen. Der Selbstheilungs-
    Zweig unten (root nicht gefunden -> neu anlegen) bleibt als Sicherheitsnetz fuer den
    seltenen Rest (siehe index_upsert()-Docstring fuer die ausfuehrliche Begruendung)."""
    Model = env["int_filemanager.file"].sudo()
    trash_parent_rec = _ensure_trash_folder(env)

    root = Model.search([("path", "=", old_rel)], limit=1)
    now = fields.Datetime.now()
    if root:
        root.with_context(int_filemanager_syncing_index=True).write({
            "path": trash_rel,
            "name": os.path.basename(trash_rel),
            "folder_path": TRASH_DIRNAME,
            "parent_id": trash_parent_rec.id,
            "trashed": True,
            "trashed_at": now,
            "trashed_by": env.uid,
            "original_path": old_rel,
        })
    else:
        # Selbstheilung - siehe Docstring oben.
        root = _insert_trashed_from_disk(env, trash_rel, trash_parent_rec.id, old_rel)

    prefix = old_rel + "/"
    for rec in Model.search([("path", "=like", escape_psql(prefix) + "%")]):
        suffix = rec.path[len(old_rel):]
        new_child_path = trash_rel + suffix
        rec.write({
            "path": new_child_path,
            "folder_path": os.path.dirname(new_child_path) or False,
            "trashed": True,
            "trashed_at": now,
            "trashed_by": env.uid,
            "original_path": old_rel + suffix,
        })
    _notify_change(env)
    return root


def index_restore_tree(env, rec):
    """Verschiebt einen einzelnen, bereits als trashed markierten Datensatz (und seinen
    physischen Unterbaum, falls Ordner) zurueck an original_path - fuehrt dabei selbst den
    physischen shutil.move() aus (anders als index_trash_tree(), das vom Aufrufer schon
    verschoben erwartet - hier gibt es keinen Aufrufer, der das vorab sinnvoll tun koennte, weil
    erst hier der Kollisionscheck gegen den Zielort passiert). Kollision wird hart blockiert,
    kein stilles Ausweichen (siehe docs/int_filemanager_papierkorb_konzept.md, Punkt 3) - exakt
    dieselbe Linie wie der bestehende move()-Controller.

    Nur fuer Wurzel-Eintraege gedacht (der Aufrufer - action_restore() auf dem Modell - wird nur
    auf einem trashed-Wurzel-Datensatz angeboten); Nachfahren werden hier mit demselben
    Nachfahren-Umschreibe-Muster wie index_trash_tree()/index_move_tree() mitgezogen.

    suppress_watcher(abs_new) statt Lock: beim Wiederherstellen quert der Uebertritt in den
    beobachteten Baum am NEUEN Ort (new_rel/abs_new), wo der Watcher sonst per CREATE/MOVED_TO
    parallel sein eigenes index_upsert() versuchen wuerde - siehe index_upsert()-Docstring fuer
    die Begruendung, warum ein DB-Lock das nicht loesen konnte. Innerhalb .trash/ selbst
    (old_rel) gibt es kein Watcher-Rennen, weil der Ordner bewusst unbeobachtet ist - nur der
    NEUE Ort muss unterdrueckt werden."""
    Model = env["int_filemanager.file"].sudo()
    old_rel = rec.path
    new_rel = rec.original_path
    if not new_rel:
        raise UserError(_("Kein ursprünglicher Pfad bekannt."))
    new_parent = os.path.dirname(new_rel) if new_rel else ""

    abs_new = resolve_path(env, new_rel)
    if os.path.exists(abs_new):
        raise UserError(_("Am ursprünglichen Ort existiert bereits ein Eintrag mit diesem Namen."))
    abs_new_parent = resolve_path(env, new_parent) if new_parent else get_root(env)
    if not os.path.isdir(abs_new_parent):
        raise UserError(_("Der ursprüngliche Ordner existiert nicht mehr."))

    abs_old = resolve_path(env, old_rel)
    with suppress_watcher(abs_new):
        shutil.move(abs_old, abs_new)

        new_parent_rec = Model.search([("path", "=", new_parent)], limit=1) if new_parent else Model.browse()
        rec.with_context(int_filemanager_syncing_index=True).write({
            "path": new_rel,
            "name": os.path.basename(new_rel),
            "folder_path": new_parent or False,
            "parent_id": new_parent_rec.id,
            "trashed": False,
            "trashed_at": False,
            "trashed_by": False,
            "original_path": False,
        })

        prefix = old_rel + "/"
        for child in Model.search([("path", "=like", escape_psql(prefix) + "%")]):
            suffix = child.path[len(old_rel):]
            new_child_path = new_rel + suffix
            child.write({
                "path": new_child_path,
                "folder_path": os.path.dirname(new_child_path) or False,
                "trashed": False,
                "trashed_at": False,
                "trashed_by": False,
                "original_path": False,
            })
    _notify_change(env)
    return rec


def rename_entry(env, old_rel, new_name):
    """Bennent eine Datei/einen Ordner tatsaechlich auf der Platte um (nicht nur den
    DB-Spiegel) und pflegt danach den Index nach (index_move_tree).

    Einzige Stelle mit den sicherheitsrelevanten Authz-Pruefungen fuers Umbenennen -
    sowohl die /int_filemanager/rename-Route (controllers/main.py, "Umbenennen" in der
    Toolbar) als auch int_filemanager.file.write() (models/filemanager_file.py, direktes
    Bearbeiten des Namensfelds im Formular) rufen ausschliesslich diese Funktion auf,
    damit es nur eine Kopie dieser Pruefungen gibt statt einer driftgefaehrdeten zweiten.

    Gibt den neuen relativen Pfad zurueck.
    """
    new_name = safe_name(new_name)
    abs_path = resolve_path(env, old_rel)
    authz.require(env, old_rel, "write")
    authz.require_rename_or_move_allowed(env, old_rel, os.path.dirname(old_rel))
    if not os.path.exists(abs_path):
        raise UserError(_("Eintrag nicht gefunden."))
    new_abs = os.path.join(os.path.dirname(abs_path), new_name)
    new_rel = to_relative(env, new_abs)
    with suppress_watcher(abs_path, new_abs):
        if new_abs != abs_path:
            if os.path.exists(new_abs):
                raise UserError(_("Es existiert bereits ein Eintrag mit diesem Namen."))
            os.rename(abs_path, new_abs)
        index_move_tree(env, old_rel, new_rel)
    return new_rel
