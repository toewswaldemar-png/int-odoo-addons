"""Generiert den domain_force-Text der drei globalen Read/Write/Unlink-Regeln
auf int_filemanager.file aus den admin-gepflegten int_filemanager.protected_folder-
Einträgen.

Warum generierter Text statt eines gespeicherten Many2many-Felds auf
int_filemanager.file: ein Bulk-UPDATE auf ein Many2many-Feld funktioniert nicht
(liegt in einer separaten Relationstabelle), und "nächstgelegener Pfadpräfix
aus einem anderen Modell" ist keine natürliche @api.depends-Abhängigkeit. Odoos
eigenes Record-Rule-System (ir.rule) übernimmt stattdessen die eigentliche
Durchsetzung - hier wird nur der domain_force-TEXT der drei strukturellen,
per XML angelegten Regeln bei jeder Änderung an protected_folder neu erzeugt.

Warum domain_force als Text zusammengesetzt statt vollständig über
odoo.fields.Domain: domain_force wird über safe_eval() ausgewertet, dessen
Kontext nur `user`/`company_ids`/`company_id` und eine feste Builtins-Liste
enthält - odoo.fields.Domain selbst steht dort nicht zur Verfügung, ein fertig
evaluierter Domain-Ausdruck kann also nicht direkt referenziert werden. Der
STATISCHE Teil (Pfad-Präfix-Struktur, Override-Ausschlüsse tieferer
Schutzordner) wird trotzdem über Domain-Objekte zusammengesetzt (&, |, ~) -
das übernimmt die polnische-Notation-Verflachung korrekt und sicher escaped
Pfad-Literale automatisch über repr(). Nur die pro Anfrage dynamische
Gruppenprüfung (referenziert user.all_group_ids zur Laufzeit) bleibt als
Platzhalter-Leaf, der am Ende textuell durch den echten Python-Ausdruck
ersetzt wird.
"""

import logging

from odoo.exceptions import ValidationError
from odoo.orm.domains import Domain
from odoo.tools.safe_eval import safe_eval
from odoo.tools.sql import escape_psql

_logger = logging.getLogger(__name__)

ADMIN_GROUP_XML_ID = "int_filemanager.group_filemanager_admin"

# int_filemanager.version hat keinen eigenen Pfad, sondern haengt am
# geschuetzten file_id - dieselbe Generator-Logik wird einfach mit
# path_field="file_id.path" (Odoo-Domains unterstuetzen Punktnotation durch
# Many2one-Relationen) statt "path" wiederverwendet, kein separates
# gespeichertes Feld auf int_filemanager.version noetig.
MODELS = {
    "int_filemanager.file": {
        "path_field": "path",
        "rule_xml_ids": {
            "read": "int_filemanager.rule_file_protected_read",
            "write": "int_filemanager.rule_file_protected_write",
            "unlink": "int_filemanager.rule_file_protected_unlink",
        },
        # Phase 5, nur beim "read"-Zweig verwendet: Portal-Nutzer sehen NICHT
        # den internen (schutzordner-basierten) Zweig, sondern ausschliesslich
        # Datensaetze, in denen sie in diesem Many2many stehen. Bewusst nicht
        # auf int_filemanager.version uebertragen - Portal-Kontakte bekommen
        # den aktuellen Dateiinhalt, keine Versionshistorie.
        "portal_share_field": "shared_partner_ids",
    },
    "int_filemanager.version": {
        "path_field": "file_id.path",
        "rule_xml_ids": {
            "read": "int_filemanager.rule_version_protected_read",
            "write": "int_filemanager.rule_version_protected_write",
            "unlink": "int_filemanager.rule_version_protected_unlink",
        },
        "portal_share_field": None,
    },
}

PORTAL_GROUP_XML_ID = "base.group_portal"

_GROUP_FIELD_BY_PERM = {
    "read": "read_group_ids",
    "write": "write_group_ids",
    "unlink": "unlink_group_ids",
}

_PLACEHOLDER_FIELD = "__acl_group_check__"


class _FakeGroups:
    """Duck-typing fuer user.all_group_ids in Selbsttest-Kontexten - nur .ids
    wird von der generierten Domain ueberhaupt gelesen."""

    def __init__(self, ids):
        self.ids = list(ids)


class _FakePartner:
    def __init__(self, id_):
        self.id = id_


class _FakeUser:
    """Minimaler Ersatz fuer res.users im Selbsttest: deckt genau die
    Aufrufe ab, die die generierte Domain zur Laufzeit tatsaechlich macht
    (has_group, all_group_ids.ids, seit Phase 5 auch partner_id.id) - keine
    echten res.users-Datensaetze noetig, um die STRUKTUR jeder
    Ternary-Verzweigung zu pruefen."""

    def __init__(self, admin=False, group_ids=(), portal=False, partner_id=0):
        self._admin = admin
        self._portal = portal
        self.all_group_ids = _FakeGroups(group_ids)
        self.partner_id = _FakePartner(partner_id)

    def has_group(self, xml_id):
        if xml_id == ADMIN_GROUP_XML_ID:
            return self._admin
        if xml_id == PORTAL_GROUP_XML_ID:
            return self._portal
        return False


def _folder_scope_domain(path_field, path):
    """under_path: Ordner selbst ODER darunter."""
    return Domain(path_field, "=", path) | Domain(path_field, "=like", escape_psql(path) + "/%")


def _internal_branch_text(folders, perm, path_field):
    """Baut den domain_force-Text fuer den internen (Nicht-Admin-)Zweig einer
    Operation. Override-Semantik: fuer jeden Schutzordner wird der Bereich
    aller tieferen Schutzordner explizit aus der eigenen Klausel
    ausgeschlossen - der spezifischste (tiefste) Eintrag gewinnt vollstaendig,
    keine Kumulation mehrerer Vorfahren-Gruppen."""
    field_name = _GROUP_FIELD_BY_PERM[perm]
    all_paths = [f.path for f in folders]

    combined = Domain.TRUE
    placeholders = {}
    for i, folder in enumerate(folders):
        deeper_paths = [p for p in all_paths if p != folder.path and p.startswith(folder.path + "/")]
        scope = _folder_scope_domain(path_field, folder.path)
        for dp in deeper_paths:
            scope = scope & ~_folder_scope_domain(path_field, dp)

        placeholder_value = -(i + 1)
        placeholder_leaf = Domain(_PLACEHOLDER_FIELD, "=", placeholder_value)
        combined = combined & (~scope | placeholder_leaf)

        gids = sorted(folder[field_name].ids)
        placeholder_text = repr((_PLACEHOLDER_FIELD, "=", placeholder_value))
        real_text = "((1,'=',1) if bool(set(%r) & set(user.all_group_ids.ids)) else (0,'=',1))" % (gids,)
        placeholders[placeholder_text] = real_text

    text = repr(combined)
    for placeholder_text, real_text in placeholders.items():
        text = text.replace(placeholder_text, real_text)
    return text


def _domain_force_text(folders, perm, path_field, portal_share_field):
    internal = _internal_branch_text(folders, perm, path_field)
    non_admin = internal
    if perm == "read" and portal_share_field:
        # Eigener, vollstaendig getrennter Zweig statt einer Ergaenzung des
        # internen Zweigs: ein Portal-Nutzer soll AUSSCHLIESSLICH ueber
        # shared_partner_ids sehen, nie zusaetzlich ueber Schutzordner-Gruppen
        # (die fuer Portal-Kontakte gar nicht vergeben werden).
        portal_branch = "[('%s','in',[user.partner_id.id])]" % portal_share_field
        non_admin = "(%s if user.has_group(%r) else %s)" % (portal_branch, PORTAL_GROUP_XML_ID, internal)
    return "[(1,'=',1)] if user.has_group(%r) else %s" % (ADMIN_GROUP_XML_ID, non_admin)


def _self_test_contexts(folders, perm, portal_share_field):
    """Repraesentative Nutzerkontexte fuer den Struktur-Selbsttest: Admin,
    interner Nutzer ohne jede Schutzgruppe, je Schutzordner ein Nutzer mit
    genau dessen fuer diese Operation hinterlegter Gruppe, und (seit Phase 5,
    nur beim read-Zweig mit Portal-Feld) ein Portal-Nutzer - der in Phase 2
    mangels shared_partner_ids-Feld noch nicht sinnvoll testbar war."""
    field_name = _GROUP_FIELD_BY_PERM[perm]
    contexts = [
        ("admin", _FakeUser(admin=True)),
        ("interner_nutzer_ohne_gruppe", _FakeUser()),
    ]
    for folder in folders:
        gids = folder[field_name].ids
        if gids:
            contexts.append(("schutzordner_%s_%s" % (folder.path, perm), _FakeUser(group_ids=gids)))
    if perm == "read" and portal_share_field:
        contexts.append(("portal_nutzer", _FakeUser(portal=True, partner_id=999999)))
    return contexts


def _validate_domain_text(env, model, domain_text, contexts):
    for label, fake_user in contexts:
        eval_context = {"user": fake_user}
        try:
            result = safe_eval(domain_text, eval_context)
            Domain(result).validate(model)
        except Exception as exc:
            raise ValidationError(
                "ACL-Regelgenerierung fehlgeschlagen für Kontext '%s': %s\n\nDomain:\n%s"
                % (label, exc, domain_text)
            ) from exc


def rebuild_rules(env):
    """Regeneriert domain_force der sechs globalen Read/Write/Unlink-Regeln
    (je drei auf int_filemanager.file und int_filemanager.version) aus dem
    aktuellen Stand von int_filemanager.protected_folder. Wird bei jeder
    Änderung (create/write/unlink) an protected_folder aufgerufen. Validiert
    jede neue Domain vor dem Schreiben gegen mehrere Nutzerkontexte (Odoos
    eigener domain_force-Constraint prüft nur den gerade aktiven
    Installations-/Bearbeiter-Nutzer und würde einen kaputten Zweig, den
    dieser Nutzer gar nicht durchläuft, nicht bemerken) - bei einem
    fehlgeschlagenen Selbsttest bleibt die bisherige domain_force unverändert
    scharf, die Regenerierung wird für alle sechs Regeln abgebrochen und
    geloggt (lieber die ganze Änderung an protected_folder ablehnen als
    veraltete/inkonsistente Regeln stehen zu lassen)."""
    folders = env["int_filemanager.protected_folder"].sudo().search([])

    pending_writes = []
    for model_name, config in MODELS.items():
        Model = env[model_name].sudo()
        path_field = config["path_field"]
        portal_share_field = config.get("portal_share_field")
        for perm, xml_id in config["rule_xml_ids"].items():
            text = _domain_force_text(folders, perm, path_field, portal_share_field)
            contexts = _self_test_contexts(folders, perm, portal_share_field)
            try:
                _validate_domain_text(env, Model, text, contexts)
            except ValidationError:
                _logger.exception(
                    "int_filemanager: ACL-Regelgenerierung für %s/%s fehlgeschlagen, "
                    "domain_force bleibt für alle Regeln unverändert.",
                    model_name,
                    perm,
                )
                raise
            rule = env.ref(xml_id, raise_if_not_found=False)
            if rule is None:
                _logger.error(
                    "int_filemanager: Record Rule %s nicht gefunden, kann nicht aktualisiert werden.", xml_id
                )
                continue
            pending_writes.append((rule, text))

    for rule, text in pending_writes:
        rule.sudo().write({"domain_force": text})
