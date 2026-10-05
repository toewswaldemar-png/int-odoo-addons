# Odoo 19 Regeln: Mixins und nützliche Klassen (Destillat)

Quelle: `odoo/documentation`, Branch 19.0, Commit `eee2e56` (2026-10-02),
`content/developer/reference/backend/mixins.rst`
(Web: <https://www.odoo.com/documentation/19.0/developer/reference/backend/mixins.html>).
Geprüft: 2026-10-02. Index: `docs/odoo_regeln/odoo_regeln_index_2026-10-02.md`.

Signaturen vor Gebrauch im Core prüfen (Suchraster `CLAUDE.md`); Vorbilder sind `crm.lead`, `sale.order`, `project.task`.

Für dieses Repo relevant: Mail/Chatter (`int_repair_workshop`, `int_filemanager` falls Verlauf/Aktivitäten) –
Website-Mixins (`utm`, `website.published`, `website.seo.metadata`) und Rating nur bei Bedarf.

## 1. Messaging (`mail.thread`)

- **Einbinden:** `_inherit = ['mail.thread']` und `<chatter/>` im Formular-`arch`.
  Optionen am Element: `open_attachments`, `reload_on_attachment`, `reload_on_follower`, `reload_on_post`.
- Nachrichten gehen an Follower; interne Notizen an Mitarbeiter (`base.group_user`).
- **Senden:** `message_post(body, subject, message_type, subtype, parent_id, attachments, …)`;
  `body` wird als `str` **escaped**, HTML nur als **`Markup`** (Sicherheits-Destillat). Anhänge als `(name,
  content)` mit **nicht** base64-kodiertem Inhalt. Weitere: `message_post_with_source(source_ref, …)` (Quelle: `mail.template`, `ir.ui.view` oder deren XML-ID).
- **Empfangen:** `message_new(msg_dict, custom_values)` (neuer Thread; `custom_values` können Werte aus der Mail
  überschreiben – Vorsicht), `message_update(msg_dict, update_vals)` (bestehender Thread). Überschreiben, um Werte aus
  der Mail zu setzen.
- **Follower:** `message_subscribe(partner_ids, subtype_ids)`, `message_unsubscribe(partner_ids)`.
- **Änderungsverfolgung:** `tracking=True` am Feld; protokolliert Änderungen im Chatter (der Name wird zur
  Orientierung immer mit angezeigt). `_track_subtype(initial_values)` wählt den Subtyp je Änderung
  (`initial_values` = alte Werte der geänderten Felder; neue Werte stehen schon im Cache; `self.ensure_one()`;
  `super()` aufrufen; Rückgabe: Subtyp oder `False`).
- **Subtypen** (`mail.message.subtype`) als Daten: `name` (Pflicht), `description`, `internal` (nur Mitarbeiter),
  `parent_id`/`relation_field` (automatische Abonnierung, z. B. Projekt→Aufgabe), `res_model` (leer = alle),
  `default`, `sequence`, `hidden`.
- **Benachrichtigungen anpassen:** `_notify_get_recipients_groups(message, model_description, msg_vals=False)` – Gruppen `(name, func, data)`;
  Standard `user`, `portal`, `follower`, `customer`; erste passende Gruppe gewinnt, Reihenfolge der Liste zählt; `data`-Schlüssel
  `has_button_access|follow|unfollow`, `button_*`, `actions`. Links: `_notify_get_action_link(link_type, **kwargs)`
  mit `view`, `assign`, `follow`, `unfollow`, `method`, `new`. **Portalnutzern keine Aktionsknöpfe anzeigen** (Standard
  `False` für `portal`/`customer`).
- **Defaults beeinflussen:** Attribut `_mail_post_access` (Recht zum Posten; Standard `write`, auch `read`); Kontext
  `mail_create_nosubscribe`, `mail_create_nolog`, `mail_notrack`, `tracking_disable` (kein MailThread-Feature),
  `mail_auto_delete` (Standard True), `mail_notify_force_send` (Standard True, < 50 Mails direkt), 
  `mail_notify_user_signature` (Standard True). Vorbild für **eigene Kontextschlüssel** mit Modulpräfix (Coding Guidelines 3).

## 2. Mail-Alias (`mail.alias.mixin`)

- Konfigurierbare Mailadresse an einem Datensatz, die per Mail neue Datensätze erzeugt. Braucht ein korrekt
  konfiguriertes Mail-Gateway mit **einer** Catchall-Domain; Routing passiert in Odoo (leichter als eigene Gateways,
  kein System-Recht nötig).
- Das **erzeugte Modell MUSS `mail.thread` erben**.
- Das Mixin legt den Alias beim Anlegen des Datensatzes an; Werte dafür liefert `_alias_get_creation_values()` (überschreiben, `super()` aufrufen;
  `alias_defaults` setzt Standardwerte, z. B. `{'trip_id': self.id}`). `mail.alias.mixin.optional` ist die Variante, bei der der Alias fehlen darf.
- Alias-Felder: `alias_name`, `alias_domain_id`, `alias_defaults` (Python-Dict als Text), `alias_force_thread_id` (alle Mails an einen Thread,
  keine Neuanlage), `alias_contact` (`everyone`/`partners`/`followers`, Standard `everyone` – **restriktiv wählen**).
- Alias nutzt **Delegations-Vererbung** (`_inherits`), Felder sind direkt am Elterndatensatz sichtbar.
  `alias_id` Many2one mit `ondelete="restrict"`, `required=True`.

## 3. Aktivitäten (`mail.activity.mixin`)

- Nicht Teil von `mail.thread`: `_inherit = ['mail.thread', 'mail.activity.mixin']`, `<chatter/>` zeigt die
  offenen Aktivitäten; Kanban nutzt Widget `kanban_activity` auf `activity_ids`. Vorbilder: `crm.lead`,
  `sale.order`, `project.task`.

## 4. Website-Mixins (nur bei Website-Bezug)

- **`utm.mixin`:** `campaign_id`, `source_id`, `medium_id`; Werte kommen aus Cookies (URL-Parameter) bei
  `create()` aus Website-Formularen. Erweiterung: `tracking_fields()` mit `(URL-Parameter, Feldname, Cookie-Name)`;
  das Zielmodell muss Quick-Create (`create({'name': …})`) können.
- **`website.published.mixin`:** `website_published`, `website_url` (**Compute-Methode `_compute_website_url`
  selbst implementieren**); Button `website_publish_button` (mit `website_url` → Weiterleitung ins Frontend, damit
  nichts versehentlich online geht); Frontend-Knöpfe nur für `base.group_website_publisher`; Template
  `website.publish_management` braucht Variable `object`.
- **`website.seo.metadata`:** `website_meta_title`, `website_meta_description`, `website_meta_keywords`.

## 5. Rating (`rating.mixin`)

- `_inherit = ['rating.mixin']` (erbt `mail.thread`); liefert die Statistikfelder `rating_last_value`, `rating_last_feedback`, `rating_last_text`,
  `rating_count`, `rating_avg`, `rating_avg_text`, `rating_percentage_satisfaction` sowie `rating_get_grades(domain)` und
  `rating_get_stats(domain)`. Überschreibbar: `_rating_get_parent_field_name()`, `_rating_domain()`.
- Bewertungen sind Datensätze von `rating.rating`; Bewertungslinks haben die Form `/rate/<access_token>/<wert>`; Aktion über
  `rating.rating` mit Domain `consumed = True`, Stat-Button (`rating_count`, Widget `statinfo`).
