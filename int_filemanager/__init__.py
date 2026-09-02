from . import controllers
from . import models
from . import watcher


def post_load():
    watcher.start_watcher()


def post_init_hook(env):
    """Regeneriert die domain_force der sechs ACL-Regeln direkt bei der
    Erstinstallation, statt bis zur ersten Aenderung an protected_folder auf
    dem in security.xml hinterlegten statischen Platzhalter ([(1,'=',1)],
    "alles offen") stehen zu bleiben (rebuild_rules() liefe sonst erst
    reaktiv beim ersten protected_folder-Write). Seit Phase 5 sicherheits-
    relevant: ohne diesen Lauf wuerde ein Portal-Nutzer dank des neuen
    ir.model.access-Leserechts UND des noch nicht regenerierten, weiterhin
    "immer wahr" lautenden Platzhalters saemtliche Dateien sehen statt nur
    die ueber shared_partner_ids freigegebenen.

    Deckt nur den Install-Pfad ab - Odoo ruft post_init_hook laut eigenem
    Quellcode (odoo/modules/loading.py) ausschliesslich bei
    update_operation == 'install', nicht bei 'upgrade'. Ein Upgrade einer
    bereits laufenden Installation braucht denselben Lauf einmalig manuell
    (z.B. per Odoo-Shell: env["int_filemanager.protected_folder"].
    _rebuild_acl_rules()) - siehe docs/int_filemanager_ausbau.md,
    Rollout-Abschnitt."""
    from .acl_rules import rebuild_rules

    rebuild_rules(env)
