"""Zentraler Authorization-Service für die rohen Dateisystem-Routen in
controllers/main.py - ersetzt sieben leicht unterschiedliche
Controller-Prüfungen durch einen einzigen, testbaren Weg.

int_filemanager.file ist über die drei generierten globalen Record Rules aus
acl_rules.py geschützt, aber die Routen in controllers/main.py führen die
eigentlichen Dateisystem-Operationen direkt über os/shutil aus, nicht über die
ORM - ir.rule würde diese rohen Zugriffe also NICHT automatisch absichern,
nur was bei einer nicht-sudo ORM-Suche sichtbar ist. require() macht diese
ORM-Suche deshalb explizit, bevor die rohe Dateioperation ausgeführt wird."""

from odoo.exceptions import AccessError
from odoo.tools.sql import escape_psql

ADMIN_GROUP_XML_ID = "int_filemanager.group_filemanager_admin"


def require(env, rel_path, perm):
    """perm in ('read', 'write', 'unlink'). Für die Wurzel (rel_path == "")
    gibt es keinen eigenen Indexeintrag - dort bleibt die Mitgliedschaft in
    group_filemanager_user (Odoos normale ir.model.access-Prüfung) die
    einzige Schranke, wie vor Phase 2.

    Wirft AccessError explizit, wenn der Datensatz laut sudo-Suche existiert,
    aber über die nicht-sudo-Suche unsichtbar ist (durch eine Regel
    verweigert) - ein leeres Recordset darf nie stillschweigend wie
    "existiert nicht" behandelt werden. Existiert der Pfad wirklich nicht
    (auch nicht sudo), wirft require() nichts - der Aufrufer entscheidet
    selbst, wie ein "nicht gefunden" zu behandeln ist."""
    if not rel_path:
        return
    Model = env["int_filemanager.file"]
    rec = Model.search([("path", "=", rel_path)], limit=1)
    if rec:
        rec.check_access(perm)
        return
    exists = Model.sudo().search_count([("path", "=", rel_path)]) > 0
    if exists:
        raise AccessError("Kein Zugriff auf '%s'." % rel_path)


def require_subtree_deletable(env, rel_path):
    """Zusätzlicher Vollständigkeitscheck für delete: verweigert, wenn
    irgendein Nachfahre stärker geschützt ist als der Aufrufer erlaubt - ein
    Löschen des Elternordners darf einen enger geschützten Unterordner nicht
    stillschweigend mitreißen. Vergleicht die Anzahl sichtbarer gegen
    tatsächliche (sudo) Nachfahren; bei Abweichung wird die gesamte Löschung
    verweigert, nicht nur der unsichtbare Teil übersprungen."""
    Model = env["int_filemanager.file"]
    prefix_domain = [("path", "=like", escape_psql(rel_path) + "/%")]
    visible_count = Model.search_count(prefix_domain)
    total_count = Model.sudo().search_count(prefix_domain)
    if visible_count != total_count:
        raise AccessError(
            "Der Ordner '%s' enthält Inhalte, für die keine Löschberechtigung vorliegt." % rel_path
        )


def _protection_signature(env, rel_path):
    """Ermittelt den anwendbaren (nächstgelegenen) Schutzordner-Eintrag für
    rel_path, oder None wenn ungeschützt - nur für den Boundary-Check bei
    rename/move, NICHT für die eigentliche Zugriffskontrolle (die läuft über
    die generierten ir.rule-Regeln)."""
    folders = env["int_filemanager.protected_folder"].sudo().search([], order="path desc")
    for folder in folders:
        if rel_path == folder.path or rel_path.startswith(folder.path + "/"):
            return folder
    return None


def require_rename_or_move_allowed(env, src_rel, dest_folder_rel):
    """Rename/Move über eine Schutzgrenze hinweg verlangt zusätzlich die
    Admin-Gruppe, weil eine Dateisystemoperation sonst stillschweigend die
    Sicherheitsklassifikation ändern könnte (protected_folder.path hängt an
    einem statischen Pfad).

    Ist die Quelle selbst als Schutzordner registriert, wird das Umbenennen/
    Verschieben in Phase 2 komplett verweigert (auch für Admins) statt nur
    admin-gated: protected_folder.path müsste dabei atomar mitgeführt werden,
    das ist bewusst erst Teil des Journal-Mechanismus in Phase 3. Bis dahin:
    zuerst den Schutzordner-Eintrag in den Einstellungen anpassen/entfernen,
    dann umbenennen/verschieben."""
    is_protected_root = (
        env["int_filemanager.protected_folder"].sudo().search_count([("path", "=", src_rel)]) > 0
    )
    if is_protected_root:
        raise AccessError(
            "'%s' ist als Schutzordner registriert und kann derzeit nicht umbenannt/verschoben werden - "
            "das würde den Schutz vom tatsächlichen Ordner lösen. Zuerst den Schutzordner-Eintrag in den "
            "Einstellungen anpassen." % src_rel
        )
    src_folder = _protection_signature(env, src_rel)
    dest_folder = _protection_signature(env, dest_folder_rel)
    src_id = src_folder.id if src_folder else None
    dest_id = dest_folder.id if dest_folder else None
    if src_id != dest_id and not env.user.has_group(ADMIN_GROUP_XML_ID):
        raise AccessError("Verschieben/Umbenennen über eine Schutzgrenze hinweg erfordert Admin-Rechte.")
