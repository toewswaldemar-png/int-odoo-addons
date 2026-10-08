# Odoo 19 Regeln: Mixins und nützliche Klassen (Destillat)

Quellen (nur diese): Odoo-19-Core (Branch 19.0, `addons/mail`, `addons/website`, `addons/utm`, `addons/rating`) und die
offizielle Entwicklerdokumentation `developer/reference/backend/mixins`
(<https://www.odoo.com/documentation/19.0/developer/reference/backend/mixins.html>).
**Rangfolge: Core-Code vor Dokumentation.** Die Doku ist an mehreren Stellen veraltet; hier steht der Core-Stand.
Geprüft: 2026-10-02, Korrekturen gegen den Core: 2026-10-08.

Vorbilder der Doku: `crm.lead`, `sale.order`, `project.task`.

## 1. Messaging (`mail.thread`)

- **Einbinden:** `_inherit = ['mail.thread']` und `<chatter/>` im Formular-`arch`.
  Optionen am Element: `open_attachments`, `reload_on_attachment`, `reload_on_follower`, `reload_on_post`.
- Nachrichten gehen an Follower; interne Notizen an Mitarbeiter (`base.group_user`).
- **Senden:** `message_post(*, body, subject, message_type, email_from, author_id, parent_id, subtype_xmlid, subtype_id,
  partner_ids, attachments, attachment_ids, body_is_html, …)` – **nur Keyword-Argumente**, einen Parameter `subtype` gibt es
  nicht (Core: `mail.thread`); `body` wird als `str` **escaped**, HTML nur als **`Markup`** (Sicherheits-Destillat). Anhänge als
  `(name, content)` mit **nicht** base64-kodiertem Inhalt. Weitere: `message_post_with_source(source_ref, …)` (Quelle: `mail.template`, `ir.ui.view` oder deren XML-ID).
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
  (Core 19.0) `active`, `has_button_access`, `button_access` (`url`, `title`), `notification_group_name`; Follow-/Unfollow-Knöpfe und
  `actions` gibt es nicht mehr (`actions` löst eine Warnung aus). Links: `_notify_get_action_link(link_type, **kwargs)` kennt nur
  `view`, `unfollow` und `controller` (andere Typen: `NotImplementedError`). **Portalnutzern keine Aktionsknöpfe anzeigen**
  (Standard `has_button_access=False` für `portal`, `follower`, `customer`).
- **Defaults beeinflussen:** Attribut `_mail_post_access` (Recht zum Posten; Standard `write`, auch `read`); Kontext
  `mail_create_nosubscribe`, `mail_create_nolog`, `mail_notrack`, `tracking_disable` (kein MailThread-Feature),
  `mail_notify_force_send` (Standard True; direkter Versand, wenn weniger Mails als der Systemparameter
  `mail.mail.force.send.limit` (Standard 100) anstehen, sonst Queue). `mail_auto_delete` ist in 19.0 ein Keyword-Argument
  (z. B. von `_notify_thread_by_email`), kein Kontextschlüssel; `mail_notify_user_signature` gibt es im Core nicht mehr.

## 2. Mail-Alias (`mail.alias.mixin`)

- Konfigurierbare Mailadresse an einem Datensatz, die per Mail neue Datensätze erzeugt. Braucht ein korrekt
  konfiguriertes Mail-Gateway mit **einer** Catchall-Domain; Routing passiert in Odoo (leichter als eigene Gateways,
  kein System-Recht nötig).
- Das **erzeugte Modell MUSS `mail.thread` erben**.
- Das Mixin legt den Alias beim Anlegen des Datensatzes an; Werte dafür liefert `_alias_get_creation_values()` (überschreiben, `super()` aufrufen;
  `alias_defaults` setzt Standardwerte, z. B. `{'trip_id': self.id}`). `mail.alias.mixin.optional` ist die Variante, bei der der Alias fehlen darf.
- Alias-Felder: `alias_name`, `alias_domain_id`, `alias_defaults` (Python-Dict als Text), `alias_force_thread_id` (alle Mails an einen Thread,
  keine Neuanlage), `alias_contact` (`everyone`/`partners`/`followers`, Standard `everyone`).
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
- **`website.published.mixin`:** `website_published` (related auf `is_published`), `website_url` (Core-Standard `'#'`;
  **`_compute_website_url` überschreiben**); `website_publish_button` schaltet in 19.0 `website_published` direkt um
  (die Weiterleitung ins Frontend aus der Doku gibt es im Core nicht); Frontend-Knöpfe nur für
  `base.group_website_publisher` (oder eine andere passende Gruppe); Template `website.publish_management` braucht
  Variable `object`.
- **`website.seo.metadata`:** `website_meta_title`, `website_meta_description`, `website_meta_keywords`.

## 5. Rating (`rating.mixin`)

- `_inherit = ['rating.mixin']` (erbt `mail.thread`); liefert die Statistikfelder `rating_last_value`, `rating_last_feedback`, `rating_last_text`,
  `rating_count`, `rating_avg`, `rating_avg_text`, `rating_percentage_satisfaction` sowie `rating_get_grades(domain)` und
  `rating_get_stats(domain)`. Überschreibbar: `_rating_get_parent_field_name()`, `_rating_domain()`.
- Bewertungen sind Datensätze von `rating.rating`; Bewertungslinks haben die Form `/rate/<access_token>/<wert>`; Aktion über
  `rating.rating` mit Domain `consumed = True`, Stat-Button (`rating_count`, Widget `statinfo`).
