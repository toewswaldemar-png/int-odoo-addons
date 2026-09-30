# Prüf-Fenster der Werterkennung: Abgleich mit Optik und Bedienmustern von Odoo 19

Stand 2026-09-30. Reine Lese-Prüfung, nichts geändert. Auftrag des Nutzers: „Prüfe gründlich, dass die Optik nicht selbst
erfunden ist, sondern 1:1 Odoo folgt.“

Geprüft wurde das Konzept `docs/int_filemanager_v2_werterkennung_oberflaeche_konzept_2026-09-29.md` (ganz gelesen) gegen den
lokalen Odoo-19-Quellcode (`C:\Users\Admin\Documents\GitHub\odoo`, Branch `19.0`, letzter Commit `2e2acfd6` vom
2026-09-24; Odoo Enterprise ist dort **nicht** enthalten) und gegen die vorhandene v2-Oberfläche des Moduls
(`int_filemanager/static/src/int_filemanager/v2/` und `native_ui/`).

Kleine Begriffserklärungen vorweg:

- **Client-Aktion:** eine ganze Odoo-Seite, die von eigenem Code gezeichnet wird (Beispiel in Odoo: der Import-Assistent).
- **Formularansicht:** Odoos Standard-Bearbeitungsseite eines Datensatzes (Rechnung, Kontakt …).
- **Hotkey / Alt-Taste:** Odoos Tastenkürzel. Wer die Alt-Taste drückt, sieht kleine Buchstaben an den Knöpfen.
- **Popover:** kleines Fensterchen, das an einem Knopf hängt (kein Vollbild-Dialog).
- **Component / Hook:** fertige Odoo-Bausteine im Programmcode.
- **SCSS-Variable / Bootstrap-Variable:** benannte Farb- und Abstandswerte, damit nichts „von Hand“ eingefärbt wird.

## 1. Ergebnis in Kürze

1. **Der Grundaufbau ist Odoo-konform, aber anders als im Konzept beschrieben.** Odoo hat für „Dokument neben den Feldern“
   genau ein Muster: die Formularansicht mit Vorschau links (`o_attachment_preview`, bei Eingangsrechnungen, Spesen,
   Urlaub, Bewerbungen). Es funktioniert nur für Odoos Anhänge und zeigt die Vorschau **nur ab 1400 Pixel Breite**. Für
   unser Prüf-Fenster ist es deshalb **nicht nutzbar**, aber die **Optik** (Vorschau links, Formular rechts, Symbol
   „eigenes Fenster“, Kopfzeile) soll nachgebaut werden. Die Client-Aktion mit Kopfleiste, Knöpfen und Seitenbereich
   hat in Odoo selbst Vorbilder (Import-Assistent, Berichtsansicht): **eine Client-Aktion ist Odoo-üblich.**
2. **Vier Stellen im Konzept widersprechen dem, was Odoo tatsächlich tut, und sollten korrigiert werden:**
   (a) die **Brotkrumen** („Dateien / Rechnungen 2025 / Jahresbescheid…“): in Odoo sind Brotkrumen die Liste der
   geöffneten Seiten, nicht ein Ordnerpfad; (b) **„Speichern und weiter“ als eigener Knopf mit Strg+Enter**: Odoo speichert
   beim Weiterblättern selbst und belegt Alt+N für „weiter“; (c) **Reiter „Dokument/Werte“ mit dem Odoo-Notebook**: das
   Notebook lädt immer nur den aktiven Reiter, das Dokument würde bei jedem Wechsel neu geladen; (d) **Knöpfe rechts
   oben**: Odoo setzt Aktionsknöpfe links neben die Brotkrumen und das Blättern rechts.
3. **Für fast jedes „Eigenbau“-Element hat Odoo ein Vorbild, dessen Aussehen kopiert werden soll:** Werkzeugumschalter wie
   der Ansichtsumschalter, Kästen-Griffe wie im Website-Builder, „→ Feld…“ wie im Import-Assistenten
   (Auswahlmenü mit Suche), „Neues Feld“-Fenster wie „Eigenschaft hinzufügen“, Warnhinweise wie das
   „Dublette?“-Band an Odoo-Rechnungen, Namensmarken wie Odoo-Tags, Schalter wie Odoos `form-switch`.
4. **Wirklich ohne Odoo-Gegenstück (Eigenbau begründet):** Wortflächen über der PDF-Seite, Kasten aufziehen/verschieben/
   skalieren auf einer PDF-Seite, Verbindung Hover Dokument ↔ Feldzeile, Textebene über pdf.js. Odoo nutzt pdf.js im Kern
   nur für Vorschaubilder und im fertigen Viewer (Rahmen), nie mit eigener Überlagerung.
5. **Farben und Markierung:** das Konzept legt keine Farbwerte fest (gut). Der vorhandene v1-Viewer (`IntPdfHighlightViewer`)
   nutzt aber feste Farben (Gelb, Rot, Grau `#525659`) und Mausrad-Zoom, das den Seitenscroll sperrt. Beides weicht von
   Odoo ab und darf nicht in v2 übernommen werden. Dazu kommt: mehrere im vorhandenen Modul benutzte CSS-Variablen
   (`--o-view-background-color`, `--body-bg-secondary`, `--o-webclient-hover-bg`) **gibt es im Odoo-Community-Quellcode
   nicht**; sie fallen immer auf ihren festen Ersatzwert zurück.
6. **Dunkelmodus:** in Odoo 19 Community ist er nicht vorhanden (die Funktion `color_scheme()` liefert immer „light“; der
   Dunkel-Bereich wird nur von Enterprise umgeschaltet). Er lässt sich hier also **nicht prüfen**; wer nur Odoos
   Variablen benutzt, ist für Enterprise vorbereitet.

## 2. Prüfung je Element

Legende Urteil: **1:1** = Odoo-nativ übernehmbar 1:1; **Anp.** = Odoo-nativ mit Anpassung; **Eigenbau** = kein
Odoo-Gegenstück, Eigenbau begründet; **Widerspruch** = Konzept widerspricht Odoo; **n. p.** = nicht prüfbar.
Alle Dateipfade beziehen sich auf `odoo/addons/`. Alle genannten Dateien wurden geöffnet und gelesen (Umfang siehe
Abschnitt 6).

### (a) Gesamtaufbau: Client-Aktion oder Formular mit Vorschau

| Punkt | Odoo-Baustein (Beleg) | Urteil | Was zu tun ist |
|---|---|---|---|
| Ganzseitige Client-Aktion mit Kopfleiste | `web/static/src/search/layout.js` (`Layout`), `control_panel/control_panel.xml`; Vorbilder **im Kern**: `base_import/static/src/import_action/import_action.xml` (Client-Aktion mit Knöpfen im `control-panel-create-button`-Platz, Seitenleiste, „Cancel“) und `web/static/src/webclient/actions/reports/report_action.xml` | **1:1** | Kein Widerspruch zu Odoo: das Konzept darf sich auf diese beiden Vorbilder berufen. |
| Formularansicht + Vorschau links | `mail/static/src/chatter/web/form_compiler.js` (`compileAttachmentPreview`), `form_renderer.js` (`mailLayout`), `mail/static/src/core/common/attachment_view.js/.xml/.scss`; genutzt in `account/views/account_move_views.xml`, `account_payment_view.xml`, `hr_expense`, `hr_holidays`, `hr_recruitment` | **Widerspruch in der Reichweite, Vorbild für die Optik** | Der Baustein greift nur auf `ir.attachment` am Datensatz zu (`thread.attachmentsInWebClientView`, nur PDF/Bild), zeigt bis 1399 px **keine** Vorschau (nur bei `SIZES.XXL`, sonst `BOTTOM_CHATTER`) und ist ein Rahmen (`<iframe>` mit pdf.js-Viewer) ohne Überlagerung. **Konzept-Aussage in Abschnitt 3 stimmt.** Abweichung begründet: bei uns ist das Dokument die Hauptsache, nicht Beiwerk ab 1400 px. |
| Optik der Vorschau | `attachment_view.scss` (`.o_attachment_preview`, `.o_attachment_control.popout`: Rundknopf mit `fa fa-window-restore` am rechten Rand, `data-tooltip="Open preview in a separate window."`) | **Eigenbau nach Vorbild** | Symbol und Sprechblase für „eigenes Fenster“ genau so übernehmen (Symbol `fa-window-restore`, Sprechblase, Lage am Dokumentrand); Konzept schreibt nur „⧉“. |
| Formular rechts | `web/static/src/views/form/form_compiler.js` (Klassen `o_form_sheet_bg`, `o_form_sheet`), `form_controller.scss` (`.o_xxl_form_view`: Vorschau und Blatt als zwei Spalten) | **Anp.** | Rechte Spalte als „Formularblatt“ (`o_form_view` > `o_form_sheet_bg` > `o_form_sheet`) bauen, damit weißes Blatt, Abstände und Beschriftungsspalte wie im übrigen Odoo aussehen. |
| Alternative: echtes Formular an `int_filemanager.node` | `web/static/src/views/form/form_controller.js` (`usePager`, `onPagerUpdate`, Autospeichern), `model/relational_model/record.js` (`hooks.onWillSaveRecord`, `onRecordSaved`), `mail`-Chatter (Knoten erbt `mail.thread`) | **n. p., als Option prüfen** | Pager, Alt+N/P, Alt+S/J, Chatter, Handy-Anpassung kämen geschenkt. Nachteil: unsere Werte werden über `apply_field_values` gespeichert (Lernen, Fassungsprüfung), das im Formular an Odoos Speichern gehängt werden müsste. Nicht erprobt; **nur als Alternative im Konzept nennen**, damit die Entscheidung bewusst fällt. |

### (b) Geteilte Ansicht, Reiter „Dokument / Werte“ auf schmalen Bildschirmen

| Punkt | Odoo-Baustein | Urteil | Hinweis |
|---|---|---|---|
| Trennlinie ziehbar | `web/static/src/core/resizable_panel/resizable_panel.js/.xml/.scss` (`ResizablePanel`, Griff `o_resizable_panel_handle`, 5 px breit, `cursor: col-resize`; Breite in Pixel, `minWidth` Standard 400); genutzt in `mail/.../discuss_sidebar.xml`, `discuss/core/common/action_panel`, `website/.../website_builder_action.xml`; **auch schon im v2-Explorer** (`v2/shared.xml`, `list_view.js`) | **1:1** | Der Griff reagiert nur auf **Maus** (`mousedown`/`mousemove`), nicht auf Finger und nicht auf Tastatur; für Tablets (768–1399 px) ungelöst. Mindestbreite 400 px auf beiden Seiten ist bei 768 px eng. |
| Vorschau in Odoo selbst nicht ziehbar | `attachment_view.scss` (feste Breite `$o-mail-Chatter-minWidth`, `flex: auto`) | Hinweis | Das Ziehen ist eine Verbesserung gegenüber dem Odoo-Muster; wegen des v2-Explorers (dort schon so) vertraut. |
| Reiter „Dokument / Werte“ | `web/static/src/core/notebook/notebook.js/.xml` (`Notebook`, Klassen `o_notebook`, `nav nav-tabs`); Kern-Handyschwelle `env.isSmall` (Breite bis 767 px, `core/ui/ui_service.js`) | **Anp.** | **Der Notebook-Baustein rendert immer nur die aktive Seite** (`t-slot` der aktiven Seite): beim Wechsel wird das Dokument neu aufgebaut, Zoom und Kästen gehen verloren. Lösung: gleiche Optik (`nav nav-tabs`), aber beide Bereiche eingehängt lassen und mit `d-none` umschalten. |
| „Form-Statusbar“ als Umschalter | `o_form_statusbar` / Statusbar-Feld | **kein Gegenstück** | Die Statusleiste ist nur die Zustandskette im Kopf (Entwurf → Gebucht …), kein Reiter. |
| Odoos eigenes Handyverhalten der Vorschau | `form_renderer.js` (`mailLayout`) | Hinweis | Odoo blendet die Vorschau unter 1400 px einfach aus. Deshalb gibt es dort keine Handy-Vorlage zum Kopieren außer dem Notebook-Aussehen. |

### (c) Kopfzeile: Brotkrumen, Pager, Knöpfe

| Punkt | Odoo-Baustein | Urteil | Hinweis |
|---|---|---|---|
| Brotkrumen mit Ordnerpfad | `web/static/src/search/breadcrumbs/breadcrumbs.xml`; `web/static/src/webclient/actions/action_service.js` (`_getBreadcrumbs`: **eine Brotkrume je geöffneter Seite**, Name = `controller.displayName`) | **Widerspruch** | Im Konzept (4.1, Skizze 4.2) steht „Dateien / Rechnungen 2025 / Jahresbescheid Wasser.pdf“. Der v2-Explorer setzt seine Ordner-Krumen nur in das eigene Feld `env.config.breadcrumbs` seines Listen-Controllers (`v2/controller_navigation.js`, `updateBreadcrumbs`). Beim Öffnen einer neuen Aktion baut Odoo die Kette aus den Seiten neu; die Ordnerkrumen erscheinen dort **nicht**. Erwartbares Bild: „Dateien / Jahresbescheid Wasser.pdf“ (ungeprüft im Browser, aus dem Code abgeleitet). Zurück-Knopf (Alt+B, `data-hotkey="b"`) führt zur Liste. Empfehlung: Konzept auf dieses Bild anpassen; der Ordner steht dann im Namen der Seite oder als kleine Unterzeile. |
| Pager „3 / 17“ | `web/static/src/core/pager/pager.js/.xml` (`Pager`; Knöpfe `btn btn-secondary o_pager_previous/next` mit `oi-chevron-left/right`, `data-hotkey="p"`/`"n"`, Zahl klickbar zum Eintippen), `search/pager_hook.js` (`usePager`), Anzeige im ControlPanel (`o_cp_pager`) | **1:1** | `usePager` setzt `env.config.pagerProps`, das ControlPanel liest es. Im Kern nutzen es nur Formular-, Listen-, Kanban- und Aktivitäts-Controller; **eine Client-Aktion mit `usePager` gibt es im Kern nicht**, der Mechanismus ist aber allgemein (ControlPanel liest nur `env.config.pagerProps`). Technisch plausibel, im Browser noch nicht erprobt. Auf dem Handy zeigt Odoo die Zahl nur kurz als Einblendung (`PagerIndicator`). |
| Speichern / Verwerfen | `web/static/src/views/form/form_status_indicator/form_status_indicator.xml` (Wolken-Symbol `fa-cloud-upload`, Kreuz `fa-times`, Klassen `o_form_button_save/cancel btn btn-light`, `data-hotkey="s"`/`"j"`, erscheinen nur bei Änderung); Dialog-/Import-Fassung: `web.FormView.Buttons` (`btn btn-primary o_form_button_save` „Save“, `btn btn-secondary o_form_button_cancel` „Discard“) | **Anp.** | Text-Knöpfe „Speichern“/„Verwerfen“ sind in Odoo bei Client-Aktionen und Dialogen üblich (Import-Assistent). Im Formular bleibt nur das Wolken-Symbol, weil Odoo dort **selbst speichert**. |
| „Speichern und weiter“ als eigener Knopf | Formular: `form_controller.js` (`onPagerUpdate` speichert bei Änderung und lädt den nächsten Datensatz); Dialoge: `Save & New` (`data-hotkey="n"`, `web/static/src/views/view_dialogs/form_view_dialog.xml`) | **Widerspruch** | Es gibt in Odoo keinen „Speichern und weiter“-Knopf im Vollbild, weil das Blättern (Pager) selbst speichert. Alt+N ist der Pager-Kürzel „weiter“. Empfehlung: **Weiter-Knopf des Pagers = Speichern und weiter** (bei Änderung erst speichern), zusätzlich „Speichern“ (Alt+S) und „Verwerfen“ (Alt+J). Sichtbar bleiben darf ein Hauptknopf im Stil des Import-Assistenten. |
| Lage der Knöpfe | `control_panel.xml`: links `o_control_panel_breadcrumbs` (**erst die Aktionsknöpfe, dann die Brotkrumen**, Slot `control-panel-create-button`), rechts `o_control_panel_navigation` (Pager, Umschalter) | **Widerspruch zur Skizze** | In der Skizze steht „Speichern und weiter“ rechts außen nach dem Pager. In Odoo steht der Hauptknopf links vor den Brotkrumen. Auf dem Handy (`env.isSmall`) schiebt das ControlPanel die Knöpfe automatisch in ein „⋮“-Menü (`o-control-panel-adaptive-dropdown`). |
| Ungespeichert-Hinweis | `settings_form_view.xml` (`o_dirty_warning`, Text „Unsaved changes“ im Slot `control-panel-status-indicator`), `settings_confirmation_dialog.js` (`SettingsConfirmationDialog`, „Stay here“), `form_error_dialog.xml` („Stay here“ / „Discard changes“) | **1:1** | Passt auf 10.4/11 („Warnung bei ungespeicherten Änderungen“). Vorbild für unser explizites Speichern ist die **Einstellungsseite**, nicht das selbstspeichernde Formular. |
| Statusanzeige Prüfstatus | Badge-Widget (v2-Liste nutzt es schon: `widget="badge"`, `color_field`) | **1:1** | Prüfstatus (ungeprüft/geprüft/automatisch) als Badge; **nicht** als `statusbar` (Zustandskette). |

### (d) Werkzeugleiste: Zeiger / Kasten / Nachlesen, Zoom, Schalter „Feldnamen“

| Punkt | Odoo-Baustein | Urteil | Hinweis |
|---|---|---|---|
| Werkzeug-Umschalter | `control_panel.xml`, Ansichtsumschalter: `nav.btn-group.o_cp_switch_buttons` mit `btn btn-secondary o_switch_view` (+ `active`), Symbol `oi-fw`/`fa`, `data-tooltip`, `aria-label`; verfügbare Symbole in `web/static/src/libs/fontawesome` (FontAwesome 4.7): `fa-mouse-pointer`, `fa-crop`, `fa-object-group`, `fa-search-plus/-minus`, `fa-window-restore`, `fa-i-cursor` | **Anp.** (Eigenbau nach Vorbild) | Zeiger / Kasten / Nachlesen als `btn-group` mit reinen Symbolknöpfen und Sprechblase, aktiver Knopf `active`. Gegenstück für die **Funktion** gibt es nicht. |
| Zoom | `core/file_viewer/file_viewer.xml`: Bild-Werkzeugleiste unten mit `+` (`fa-plus`), Lupe (`fa-search`, „Zoom zurücksetzen“), `−` (`fa-minus`), Drehen, Drucken, Download, Klasse `o-FileViewer-toolbarButton`; **nur für Bilder**, PDFs laufen im pdf.js-Rahmen mit dessen eigener Leiste (`fileViewer` hat keine PDF-Zoomleiste) | **Anp.** | Wenn wir eine eigene Leiste bauen, soll sie Symbole und Sprechblasen von `FileViewer` übernehmen (`fa-plus`/`fa-minus`, Tastenkürzel + / − / 0 wie dort). **Prozentanzeige „100 %“ hat Odoo im FileViewer nicht** (im pdf.js-Viewer schon, als Auswahlliste `scaleSelect`). |
| Zoomen mit dem Mausrad | v1: `native_ui/pdf_highlight_viewer.js` sperrt Seitenscroll (`ev.preventDefault()`); Odoo-Bildviewer: `onWheelImage` zoomt ebenfalls, pdf.js-Viewer: Strg+Rad | **Widerspruch (v1)** | In v2 Mausrad = Scrollen, Strg+Mausrad = Zoomen (wie pdf.js und Browser). |
| Schalter „Feldnamen einblenden“ | `core/checkbox/checkbox.xml` (`CheckBox`) mit `className="'form-switch'"` (so in `core/domain_selector/domain_selector.xml`, `views/fields/boolean_toggle`) | **1:1** | `CheckBox` mit `form-switch` benutzen; nicht einen eigenen Schieber bauen. |
| Alternative: fertiger pdf.js-Viewer | `web/static/lib/pdfjs/web/viewer.html` (zeigt genau die Leiste, die der Nutzer von Vorschau/Anhang kennt; **der v2-Explorer nutzt ihn schon** für seine Vorschau: `v2/controller_mutations.js`, `toViewerFile`); Odoo greift selbst in den Rahmen (`core/utils/pdfjs.js`, `hidePDFJSButtons`); im gebündelten `viewer.js` ist `window.PDFViewerApplication` erreichbar, Ereignisse `pagerendered`, `textlayerrendered`; Farbschema über Cookie `color_scheme=dark` | **n. p., aber Option** | Vorteil: Zoom, Seitenleiste, Suche, Farben exakt wie überall in Odoo; Nachteil: Kästen/Wortflächen müssen in den Rahmen hineingezeichnet werden. **Nicht erprobt.** Im Konzept als bewusste Entscheidung „eigene Leinwand oder Odoos Viewer mit Überlagerung“ festhalten. |

### (e) Feldliste rechts

| Punkt | Odoo-Baustein | Urteil | Hinweis |
|---|---|---|---|
| Eingabefelder mit Odoo-Widgets ohne echtes Modell | `web/static/src/model/record.js` (`Record`, `_Record`, `StandaloneRelationalModel`); genutzt in `analytic/static/src/components/analytic_distribution/analytic_distribution.js` (`recordProps`: Felder + Werte ohne `resModel`) und `web/static/src/views/view_components/multi_create_popover.xml` | **1:1** | **Konzept-Aussage in Abschnitt 3 stimmt.** Beim Kontakt-Feld (many2one) muss `relation` angegeben werden (`analytic_distribution` macht das). |
| Beschriftungen und Reihenfolge wie im Formular | `views/form/form_group/form_group.xml` (`o_group`, `o_inner_group grid`, `o_wrap_label`, `o_wrap_input`), `views/form/form_label.xml` (`label.o_form_label` mit Hilfe-Fragezeichen `sup ?` aus `help`), `form_controller.scss` (`.o_xxs_form_view`: Beschriftung über dem Feld auf dem Handy) | **Anp.** | Feldzeilen in dieselben Klassen setzen (Beschriftung links, Feld rechts), oder mit `FormRenderer` und einer zur Laufzeit erzeugten Formular-Beschreibung arbeiten (so macht es `multi_create_popover`: `FormArchParser` + `FormRenderer` + `Record`). Der **„Hilfetext“ aus Konzept 10.6 ist exakt Odoos Feldhilfe** (`help`, sichtbar als `?`). |
| Ungültiger Wert | `o_field_invalid` (rote Umrandung, `FormLabel.className`) | **1:1** | Für „IBAN-Prüfziffer falsch“ usw. |
| Hinweisbänder (abweichende IBAN, Dublette, Summen) | `account/views/account_move_views.xml`: `alert alert-warning` mit Text „This document might be a duplicate of…“ und Knopf `btn btn-link text-danger`; `alert alert-info` | **1:1** | Genau das Muster für „Dublette?“ und „abweichende IBAN“ (`role="alert"`). |
| „+ Feld“-Menü mit Suche | `core/select_menu/select_menu.js/.xml` (`SelectMenu`: Suchfeld, `groups`, „No results“; auf dem Handy als Bottom-Sheet); Vorbild **im Kern**: Import-Assistent (`base_import/.../import_data_content.xml`, „Search a field…“) | **1:1** | `SelectMenu` statt eigenem Menü. Paperless-Vorbild bleibt Inspiration, Odoo-Optik gewinnt. |
| „→ Feld …“ bei „Weitere Werte in Kästen“ | Import-Assistent: Tabelle „Dateispalte → Odoo-Feld“, je Zeile `SelectMenu` mit Typ-Symbol, „Comments“-Spalte mit `alert`-Kästchen | **Anp.** | Das ist das nächste Odoo-Vorbild für „Wert → Feld zuordnen“. Layout, Suchfeld und Typ-Symbole kopieren. |
| Alternativen-Aufklappliste „▾ (2)“ | `core/dropdown/dropdown.js` (`Dropdown`, `DropdownItem`; `bottomSheet` auf dem Handy) | **1:1** | Auswahlkandidaten als `DropdownItem`-Liste. Odoo hat keine fertige „Kandidat“-Anzeige; Aussehen wie Many2one-Vorschlagsliste. |
| Bestätigen / Entfernen | Symbole: `fa-check` (`text-success`, in `many2many_binary_field.xml`), `fa-times`/`oi-close` (Tags: `web.TagsList` `a.o_delete`), Papierkorb `fa-trash-o` (`analytic_distribution.xml`); Formular-Statusanzeige (`btn btn-light border-0 px-1 py-0`) | **1:1** | Symbolknöpfe mit `aria-label` und `data-tooltip` (das v1-Dialogsymbol `fa-times role="button"` hat beides nicht). |
| „Herkunft“, „gedruckter Wert darunter“ | – | **Eigenbau** | Kleiner Text: `small text-muted` unter dem Feld; kein Odoo-Widget. |

### (f) Markierungen im Dokument: Umrandung, Namensmarke, Hover, aktive Stelle

| Punkt | Odoo-Baustein | Urteil | Hinweis |
|---|---|---|---|
| Farben und Umrandungen | Farbvariablen `$o-action` (=Primärfarbe), `$o-component-active-bg/-border` (`web/static/src/scss/primary_variables.scss`), Hilfsklassen `bg-action`, `text-bg-action`, `text-action` (`$o-bg-colors-custom` / `$o-text-colors-custom`, Verwendung `search_bar.xml`). Vorbilder für „Hervorhebung“: `webclient/settings_form_view/settings/searchable_setting.scss` (`tint-color($o-action, 90%)` Fläche + `$o-action` Rand), `views/kanban/kanban_record.scss` (`KanbanColumn__highlight-selected*`) | **Anp.** | Ruhig: 1 px Rand in gedämpfter Bootstrap-Farbe (z. B. `var(--bs-border-color)` bzw. `$o-gray-…`); aktiv: `tint-color($o-action, 90%)` Fläche plus `$o-action`-Rand. **Keine eigenen Farbwerte.** Das entspricht auch der Entscheidung N6 im Konzept. |
| Namensmarken | `core/tags_list/tags_list.xml/.scss` (`TagsList`; Klassen `o_tag o_badge badge rounded-pill o_tag_color_N`, Abmessung `$font-size-sm`); Farben `o_tag_color_0…11` aus `$o-colors` | **1:1** | Namensmarke als Badge/`TagsList`-Stil: gleiche Pillenform, kleine Schrift, Farbklasse `o_tag_color_0` (neutral). |
| Farbliste je Feld | `core/colorlist/colorlist.js` (`ColorList`, 12 Farben) | **1:1, nicht nutzen** | Konzept N6 („keine Farbe je Feld“) ist damit vereinbar; falls doch, `ColorList` und `o_tag_color_N` verwenden statt eigener Palette. |
| Hover verbindet Zeile und Fläche | – | **Eigenbau** | Kein Odoo-Gegenstück. Aussehen: Odoos Zeilen-Hover (`--table-hover-bg`) verwenden. |
| Wortflächen (Klick auf Wort) | Odoo nutzt pdf.js nur in `mail/static/src/utils/common/pdf_thumbnail.js` (Vorschaubild), `web/static/src/core/utils/pdfjs.js` (`loadPDFJSAssets`), `website_slides` (Vorschaubild) und im Rahmen-Viewer; **kein Kern-Modul benutzt `TextLayer`** (nur die pdf.js-Bibliothek selbst) | **Eigenbau begründet** | Konzept-Aussage in Abschnitt 3 stimmt (pdf.js 4.8.69: `apiVersion`/`version` = `4.8.69`, Klasse `TextLayer` vorhanden). |

### (g) Kasten aufziehen, verschieben, Größe ändern

| Punkt | Odoo-Baustein | Urteil | Hinweis |
|---|---|---|---|
| Aufziehen | `core/barcode/crop_overlay.js` (`CropOverlay`): nur Kamera-Scanner, symmetrisch zur Mitte, speichert in `localStorage` | **Eigenbau begründet** | **Konzept-Aussage in Abschnitt 3 stimmt.** Zusätzlich gibt es `html_editor/.../media/image_crop.js` mit Bibliothek **cropperjs** (`html_editor/static/lib/cropperjs`): Ausschnitt mit 8 Griffen auf einem Bild (`<img>`), Seitenverhältnisse, Zurücksetzen, „Apply“/„Discard“. Nicht für eine PDF-Seite nutzbar, aber das Aussehen ist das Vorbild für Kastengriffe. |
| Größe ändern (Griffe) | `html_builder/static/src/core/builder_overlay/builder_overlay.xml/.scss` (`o_handle`, `o_handle_indicator`: 8 runde Griffe an Ecken und Seiten, Farbe `$o-we-handles-accent-color`, RTL-Cursor, `body.o_rtl`), `html_editor/.../image_transformation.xml/.scss` (`transfo-scaler`, 8 Quadrat-Griffe) | **Eigenbau nach Vorbild** | Aussehen der Griffe und der Cursor (`nwse-resize`, `ew-resize` …) genau nach `builder_overlay.scss` übernehmen (inklusive `o_rtl`-Umkehr). Der Code ist an den Website-Builder gebunden und **nicht wiederverwendbar**. |
| Verschieben | `core/utils/draggable.js` (`useDraggable`, Zeiger- und Touch-Ereignisse in `draggable_hook_builder.js`; im Kern für Dialogverschieben und Sortieren) | **Anp.** | Für Verschieben grundsätzlich brauchbar, für „Größe ändern“ nicht. Der `ResizablePanel` exportiert seinen `useResizable`-Baustein **nicht**. |
| Ziehen im zweiten Fenster | `mail/static/src/core/common/mail_popout_service.js` | **Hinweis** | Im zweiten Fenster hängen `useExternalListener(document, …)`/`window`-Beobachter am **Hauptfenster**. Zieh-Code deshalb mit Zeiger-Erfassung am Element (`setPointerCapture`) bauen, nicht mit globalen Beobachtern. (Das ist eine Folgerung aus dem Code, nicht getestet.) |
| Handy | `hasTouch()` (`start.js` setzt Klasse `o_touch_device`) | **Hinweis** | Kasten-Ziehen mit dem Finger konkurriert mit Scrollen: Werkzeugmodus (Zeiger/Kasten) ist dafür der richtige Weg; auf der Überlagerung `touch-action: none` (eigene Folgerung, nicht getestet). |

### (h) „Als neues Feld anlegen“-Popover

| Punkt | Odoo-Baustein | Urteil | Hinweis |
|---|---|---|---|
| Popover | `core/popover/popover_hook.js` (`usePopover`); `views/fields/properties/properties_field.js` (`onPropertyCreate`, `usePopover(PropertyDefinition, { position: "right", popoverClass: "o_property_field_popover", … })`), `property_definition.xml` (Zeilen: Label, „Field Type“-Auswahl mit Typ-Bildern aus `icons/`, je nach Typ Werte/Modell; „Delete“; auf dem Handy Zurückpfeil `oi-arrow-left`) | **Anp.** | **Konzept-Aussage in Abschnitt 3 stimmt im Kern**, aber Feinheit: Odoos Knopf **„Add Property“** (`btn btn-light text-muted` mit `fa-plus`, nur ab `sm`) legt zuerst einen Platzhalter „Property N“ an und öffnet dann das Popover. Es gibt kein „Formular mit OK“. Für unser Popover: gleiche Zeilenanordnung und Typ-Auswahl mit Bildchen, Knöpfe **„Add“ (btn-primary btn-sm) / „Discard“ (btn-secondary btn-sm)** wie im `multi_create_popover.xml`. |
| Verwaltungsrecht | `properties_field.js` (`checkDefinitionWriteAccess` mit Hinweis `notification` bei fehlendem Recht) | **1:1** | Vorbild für „nur Verwalter“ (U2): ohne Recht kommt eine Warnmeldung statt eines unsichtbaren Knopfs. |

### (i) Kontakt aus Dokument

| Punkt | Odoo-Baustein | Urteil | Hinweis |
|---|---|---|---|
| Formular im Dialog, vorbelegt | `views/view_dialogs/form_view_dialog.js/.xml` (`FormViewDialog`), `views/fields/relational_utils.js` (`Many2XAutocomplete.slowCreate`, `getCreationContext`: setzt `default_<Feld>` = getippter Name plus `props.context`) | **1:1** | Das Absender-Feld (many2one) bietet „Create and edit…“ schon von selbst; ein Feld-`context` mit `default_*`-Werten (Name, `vat`, E-Mail …) reicht. **Nur „Kontakte: Anlegen“ zeigt den Eintrag** (Odoo prüft das Recht selbst). Kein eigener Knopf nötig; höchstens ein zusätzlicher Menüpunkt. |
| Tastenkürzel im Dialog | `core/dialog/dialog.js`: `Strg+Enter` = erster sichtbarer Fußknopf, `Esc` schließt; Dialogknöpfe `data-hotkey="c"` (Save), `"n"` (Save & New), `"j"` (Discard) | **1:1** | Gilt automatisch, solange der Dialog aktiv ist. |

### (j) Leer-, Lade-, Fehlerzustände

| Zustand | Odoo-Baustein | Urteil | Hinweis |
|---|---|---|---|
| Leer („keine Wortliste“, „Bild ohne Text“) | `web/static/src/views/no_content_helpers.xml` (`web.NoContentHelper`: `o_view_nocontent`, `o_nocontent_help`, `o_view_nocontent_smiling_face/neutral_face/empty_folder`), `views/action_helper.xml`; Client-Aktion-Beispiel: `base_import` („Drop or upload a file to import“) | **1:1** | Texte im selben Stil („Titel + eine Zeile“). |
| Laden | `fa fa-circle-o-notch fa-spin` (`core/autocomplete`, `command_palette`, `file_viewer.xml` mit `fa-3x … text-white`), globale Ladeanzeige `webclient/loading_indicator` | **1:1** | Ladeanzeige am Kasten: dasselbe Symbol. |
| Meldungen | `core/notifications/notification.xml` (`o_notification`, `bg-{type}`, `role="alert"`, optionale Textknöpfe `btn btn-link`), Fehlerdialoge `core/errors/error_dialogs.js` (`WarningDialog`, `ErrorDialog`, `RPCErrorDialog`) | **1:1** | „Umwandler nicht erreichbar“ = `warning`-Meldung; „Abbrechen/Rückgängig“ als Meldungsknopf. |
| Bestätigung | `core/confirmation_dialog` (`data-hotkey="q"` bestätigen, `"x"` abbrechen) | **1:1** | Für „Gemerkte Kästen verwerfen“. |

### (k) Tastaturkürzel

Belegt in `web/static/src/core/hotkeys/hotkey_service.js` (Datei ganz gelesen) und `hotkey_hook.js`:

- Erlaubte Tasten: `a–z`, `0–9`, Pfeile, Bild, Pos1/Ende, Rücktaste, Enter, Tab, Entf, Leertaste, `Esc`, `<`, `>`;
  **F-Tasten sind nicht erlaubt.** Modifikatoren sind Alt, Strg, Umschalt (auf dem Mac Strg statt Alt, Cmd statt Strg).
- `data-hotkey="x"` an einem Knopf = **Alt+X**; Alt-Taste allein blendet Buchstaben an den Knöpfen ein (kostenlose Anzeige).
- Kürzel, die per Hook oder Service registriert werden (`useHotkey("control+enter", …)`), gelten mit **beliebigen**
  Modifikatoren, werden aber in Eingabefeldern **blockiert**, außer bei `bypassEditableProtection: true`; `Esc` ist in
  Eingabefeldern immer erlaubt.

| Kürzel im Konzept | Beleg im Odoo-Code | Urteil |
|---|---|---|
| Alt+N / Alt+P (nächstes/voriges Dokument) | `core/pager/pager.xml`: `data-hotkey="p"` / `"n"` an den Pager-Knöpfen | **1:1**, funktioniert von selbst, wenn der Pager benutzt wird |
| Strg+Enter = „Speichern und weiter“ | `core/dialog/dialog.js` und `webclient/switch_company_menu`: Strg+Enter bestätigt nur **in Dialogen** den ersten Fußknopf; in Formularen und Client-Aktionen ist es frei. In einem Eingabefeld nur mit `bypassEditableProtection` | **Anp. / Widerspruch zum Odoo-Muster** | Frei nutzbar, aber ungewöhnlich; Odoo-konform ist Alt+N (wie Pager) und Alt+S (Speichern). Wenn Strg+Enter bleibt, dann mit `bypassEditableProtection: true`. Im aufgesetzten Kontakt-Dialog bleibt Strg+Enter beim Dialog. |
| „K“ = Kasten, „Esc“ = Zeiger | Kein Kern-Kürzel ohne Modifikator außer `Esc`, `Enter`, Pfeile, Leertaste und `Umschalt+M/D`; einzelne Buchstaben nur als Alt+Buchstabe (`data-hotkey`) | **Anp.** | Ein nackter Buchstabe „K“ ist zulässig, wirkt aber nur außerhalb von Eingabefeldern. Odoo-üblicher: `data-hotkey="k"` am Kasten-Knopf (**Alt+K**; `k` ist in anderen Odoo-Masken für „Print/Remove“ belegt, aber jeweils nur dort aktiv). `Esc` mit offenem Popover/Dropdown gehört zuerst dem Popover; ein eigenes `Esc` = Zeiger ist nur sinnvoll, wenn nichts offen ist. |
| Tab / Umschalt+Tab, Enter | Standardverhalten der Odoo-Felder | **1:1** | „Enter bestätigt den Vorschlag“ ist in Odoo-Feldern nicht belegt (nur in Datumsauswahl und Schnellanlage). |
| Bereits belegte Alt-Buchstaben in Odoo | im Kern: `s` Speichern, `j` Verwerfen, `c` Neu/Speichern, `n`/`p` Pager, `b` Zurück, `u` Aktionen, `x` Entfernen, `q` Bestätigen, `z`/`v` Schließen/Ansicht, `h` Startmenü | Hinweis | Für neue Knöpfe nicht doppelt belegen. |
| Strg+K | `core/commands/command_service.js`: öffnet die Befehlspalette | Hinweis | Nicht überschreiben. |

### (l) Farben, Abstände, Schrift, Icons

| Punkt | Befund | Urteil |
|---|---|---|
| Vorgabe des Konzepts | Nennt keine Farbwerte; „Odoo-eigene Mechanismen“ (K5) | **1:1** in der Absicht, aber **keine verbindliche Regel** im Text. Empfehlung: Regel aufnehmen (siehe Abschnitt 5, Nr. 5). |
| Vorhandener v1-Viewer | `native_ui/pdf_highlight_viewer.scss`: `rgba(255,193,7,…)`, `rgba(220,53,69,…)`, `#525659` | **Widerspruch** (nicht für v2 übernehmen) |
| Vorhandene Ersatzwerte im Modul | `native_ui/*.scss`, `document_review_dialog.scss`: `var(--o-view-background-color, #fff)`, `var(--body-bg-secondary, #f8f9fa)`, `var(--border-color, #dee2e6)`, `var(--o-webclient-hover-bg, …)`, `var(--o-view-background-color-alt, …)`. Im Odoo-Community-Quellcode **nicht als CSS-Variable definiert** (Suche in `addons` und `odoo` nach `.scss`/`.css`: keine Treffer; `--border-color` nur lokal in `delivery` und `html_builder`); Odoo selbst nutzt `$o-view-background-color` als **SCSS-Variable** (`core/notebook/notebook.scss`) und Bootstrap-Variablen wie `--bs-primary-rgb` | **Hinweis / Fehlerquelle** | Es greift immer der feste Ersatzwert. Ob Enterprise diese Variablen definiert, ist nicht prüfbar. Für neue Dateien besser SCSS-Variablen (`$o-view-background-color`, `$o-gray-…`, `$o-action`) oder Bootstrap-Variablen (`--bs-border-color`, `--bs-primary-rgb`). |
| Icons | FontAwesome 4.7 (`web/static/src/libs/fontawesome`) und `oi-…` (`odoo_ui_icons`); im Konzept genannt: „fa-Icons“ | **1:1** |
| Schrift/Abstände | Bootstrap-Größen (`small`, `text-muted`, `gap-*`, `p-*`) sind im Kern durchgängig | **1:1** |

### (m) Dunkelmodus, Rechts-nach-Links, Barrierefreiheit

| Punkt | Beleg | Urteil |
|---|---|---|
| Dunkelmodus | `web/models/ir_http.py`: `color_scheme()` gibt `"light"` zurück (Enterprise überschreibt); Dunkel-Bereich `web.assets_web_dark` mit `*.dark.scss` in `web/__manifest__.py`; nur wenige Kern-Komponenten haben eine Dunkelvariante (`file_viewer.dark.scss`, `emoji_picker.dark.scss`, `calendar_renderer.dark.scss`); der pdf.js-Viewer folgt dem Cookie `color_scheme=dark` | **n. p. in Community**. Nur Odoo-Variablen verwenden; PDF-Seiten bleiben weiß (das ist auch in Odoo so). |
| Rechts-nach-Links | Odoo lässt Stylesheets automatisch spiegeln (`odoo/addons/base/models/assetsbundle.py`, `run_rtlcss`), Klasse `body.o_rtl` (`start.js`), Ausnahmen mit `/*rtl:ignore*/`; `ResizablePanel` und `builder_overlay.scss` behandeln RTL ausdrücklich | **Anp.** Die Kästen im Dokument dürfen nicht gespiegelt werden. Positionen per Inline-Stil (`left/top`) sind davon unberührt (eigene Folgerung: der v1-Viewer macht es so), Regeln in SCSS mit `/*rtl:ignore*/` schützen; Seitenbereich auf `direction: ltr` festhalten. Nur die Bedienleisten sollen spiegeln. |
| Barrierefreiheit | Odoo-Bausteine setzen `aria-label`, `data-tooltip` und `role="alert"` an Pager, Statusanzeige, Meldungen, Schließen-Knöpfen (`pager.xml`, `form_status_indicator.xml`, `notification.xml`); `ResizablePanel`-Griff hat weder Tastatur noch Beschriftung | **Anp.** Symbolknöpfe immer mit `aria-label`; Kästen brauchen eine Tastaturbedienung (Pfeile verschieben, Entf löschen) als zusätzliche Leistung über Odoos Niveau hinaus; Meldungen mit `notification` (lesen Bildschirmleser vor). |

### (n) Handy

| Punkt | Beleg | Urteil |
|---|---|---|
| Erkennung | `env.isSmall` = Breite ≤ 767 px (`core/ui/ui_service.js`, `SIZES.SM`), `hasTouch()` → Klasse `o_touch_device` (`start.js`) | **1:1** Schwelle „schmal“ = `env.isSmall`. Zwischen 768 und 1399 px ist die Teilung mit 400 px Mindestbreite knapp; die Grenze des Umschaltens zu Reitern sollte am echten Gerät entschieden werden (Vorschlag: eher `LG`, 992 px). |
| ControlPanel am Handy | `control_panel.xml`: Brotkrumen → Zurückpfeil (`o_back_button`), Knöpfe → „⋮“-Menü, Pager-Zahl aus, `PagerIndicator` | **1:1**, kostenlos bei Verwendung von `Layout` |
| Formular am Handy | `form_controller.js` (`className`: `o_xxs_form_view`, `o_field_highlight`), `form_controller.scss` (Beschriftung über dem Feld) | **1:1**, wenn die Feldliste die Formularklassen benutzt |
| Popover am Handy | `properties/property_definition.xml` (Zurückpfeil), `core/dropdown/dropdown.js` (`bottomSheet` auf Touch + schmal), `select_menu.js` | **1:1**, für „+ Feld“ und Alternativen |

## 3. Stimmen die Aussagen in Konzept-Abschnitt 3 (Odoo-Bausteine)?

| Konzept-Aussage | Am Code | Urteil |
|---|---|---|
| `ir.actions.client` + `Layout`/ControlPanel, `usePager` (`web/static/src/search/pager_hook.js`) | Pfade und Namen stimmen. Einschränkung: kein Kern-Client-Aktions-Beispiel mit `usePager` | stimmt, Einschränkung ergänzen |
| Blättern wie Datensatz-Pager (Alt+N/P) | `pager.xml`: `data-hotkey` `n`/`p` | stimmt |
| `ResizablePanel`, „u. a. in Discuss und Website-Builder“ | `discuss_sidebar.xml`, `action_panel`, `website_builder_action.xml` | stimmt; Ergänzung: nur Maus, Breite in Pixel; Template intern `web_studio.ResizablePanel` benannt (harmlos) |
| `mail` `AttachmentView` + `o_attachment_preview` nur für `ir.attachment`, fertiger iframe-Viewer ohne Überlagerung → nur Vorbild | `attachment_view.xml` (`iframe`, `img`), `thread_model.js` (`attachmentsInWebClientView`) | stimmt; **Ergänzung nötig:** Vorschau nur ab 1400 px, `o_attachment_control` (Popout-Symbol) als Optikvorlage |
| pdf.js 4.8.69 (`web/static/lib/pdfjs/build/pdf.js`, inkl. `TextLayer`) | `apiVersion`/`version` = `4.8.69`, Klasse `TextLayer` vorhanden | stimmt |
| `Record` mit `fields`-Definition ohne echtes Modell (`analytic_distribution`, `multi_create_popover`) | beide Dateien gelesen; `multi_create_popover` lädt seine Felder allerdings aus einer echten Formularansicht (`multi_selection_buttons.js`, `loadMultiCreateView`), nur `analytic_distribution` baut Felder von Hand | stimmt, präzisieren |
| Popover-Muster der Properties (`usePopover`, `property_definition`) | siehe (h) | stimmt |
| `mail_popout_service.js` (`documentPictureInPicture` bzw. `window.open`) | `popout()` (vom AttachmentView benutzt) öffnet **nur** ein `window.open`-Popup; `pip()` nutzt `documentPictureInPicture` mit `window.open` als Ersatz und startet mit **kleiner Standardhöhe** (`Math.min(240, …)`) | teilweise: Wortlaut präzisieren, Größe muss angegeben werden |
| `zxing-library` liest Canvas | (nicht Oberfläche; nicht geprüft) | nicht geprüft |
| `CropOverlay` nur für den Kamera-Scanner, nicht wiederverwendbar | `crop_overlay.js` gelesen (symmetrisch, `localStorage`-Ablage, `--o-crop-x`) | stimmt; Ergänzung: `image_crop.js`/cropperjs und `builder_overlay` als Optik-Vorbilder |
| 10.6 Typen der Eigenschaften (`ALLOWED_TYPES`) | `odoo/orm/fields_properties.py` stimmt wörtlich | stimmt |
| 10.7 `properties.base.definition.mixin` für `res.partner` und `mailing.contact` | `base/models/res_partner.py`, `mass_mailing/models/mailing_contact.py` | stimmt |
| Abschnitt 2, „Odoo selbst“: Extract-Werte, `coords`, Vorschau-Hervorhebung, Einstellung automatisch/auf Knopfdruck/aus | Enterprise, nicht im Quellcode | **nicht prüfbar** (Dokumentationsangabe, im Konzept richtig als Enterprise markiert) |
| „AI-Felder … lizenzpflichtig“ | Im Community-Quellcode gibt es kein KI-Modul; Lizenz nicht am Code prüfbar | nicht prüfbar |
| Abschnitt 3 nennt Images `odoo:19.0-hm-test` (692 Module) | Der lokale Klon hat 638 Modul-Ordner | Hinweis: Prüfbasis weicht leicht vom Image ab; alle geprüften Dateien existieren im Klon |

## 4. Weitere Befunde

1. **Vorhandene Vorschau im v2-Explorer nutzt Odoos pdf.js-Rahmen** (`v2/controller_mutations.js`, `toViewerFile`, `#pagemode=none`). Ein
   Prüf-Fenster mit eigener Leinwand sähe daneben **anders** aus (Leiste, Zoom, Seitenleiste). Entweder Odoos Viewer mit
   Überlagerung (siehe (d)) oder eine bewusst kopierte Leiste.
2. **Odoo-Formular = Autospeichern, Einstellungsseite = explizites Speichern.** Unser explizites „Speichern“ passt zur
   Einstellungsseite (Hinweis „Unsaved changes“, Dialog „Stay here“); das sollte im Konzept so benannt werden, damit
   das Verhalten erwartbar ist.
3. **Der Pager schaltet in Odoo zyklisch** (letzter → erster; `Pager.navigate`); bei „Speichern und weiter“ am letzten
   Dokument sollte dasselbe geschehen.
4. **Pager, Breadcrumb und Zurück (Alt+B)** liefern ohne eigenen Code die Hotkeys; das v2-Konzept sollte diese Kürzel
   nicht neu definieren.
5. **Odoos Abschnitt „Import-Assistent“ ist der nächste Verwandte** unserer Oberfläche (Datei links, Zuordnung „Spalte
   → Feld“ rechts, Warnungen als `alert`, Knöpfe im Kopf). Ein Gespräch mit dem Nutzer darüber, „so ähnlich wie der
   Import“, ist eine verständliche Erklärung.
6. **Nicht gefunden (Odoo-Community):** ein Baustein für „Kasten auf PDF ziehen“, „Wort in PDF anklicken“, „Kreuz-Hover
   zwischen Liste und Dokument“, „Zoom mit Prozent im Viewer außer pdf.js“. Das ist der begründete Eigenbau.

## 5. Empfehlungen: Änderungen am Konzept (nach Wichtigkeit)

**Hoch (Widerspruch zu Odoo oder verwirrend):**

1. **4.1/4.2, Brotkrumen:** ersetzen durch: „Kopfzeile wie Odoo: links die Knöpfe, daneben die Brotkrumen (`Dateien` › Name der
   Datei; Zurück mit Alt+B), rechts der Pager ‚3 / 17‘. Der Ordnerpfad erscheint nicht als Brotkrume (Odoo bildet dort nur
   geöffnete Seiten ab), sondern als kleine Zeile unter dem Dateinamen.“ Skizze anpassen.
2. **4.1, Knöpfe:** „**Speichern und weiter**, Speichern, Verwerfen“ ändern in: „Der ‚Weiter‘-Knopf des Pagers speichert bei
   Änderungen zuerst (wie beim Odoo-Formular; Alt+N). Zusätzlich Text-Knöpfe **Speichern** (Alt+S) und **Verwerfen** (Alt+J)
   links neben den Brotkrumen, wie im Import-Assistenten. Ungespeicherte Änderungen zeigt der Hinweis ‚Ungespeicherte
   Änderungen‘ im Statusplatz der Kopfzeile; beim Verlassen fragt der Odoo-Dialog ‚Hier bleiben / Verwerfen‘.“
3. **4.5 Tastatur:** „Strg+Enter“ streichen oder als Zusatz führen; Hauptkürzel = Alt+N/P/S/J (`data-hotkey`, damit die
   Alt-Anzeige stimmt). „K“ und „Esc“ ersetzen durch „Alt+K = Kasten, Alt+Z = Zeiger (oder Esc, wenn nichts offen ist)“ **oder**
   bewusst als Ausnahme markieren („nackte Buchstaben arbeiten nur außerhalb von Eingabefeldern“).
4. **4.2/(b), Reiter am Handy:** „Odoos `Notebook` lädt nur den aktiven Reiter; deshalb Reiter im selben Aussehen (`nav nav-tabs`),
   beide Bereiche bleiben geladen, umgeschaltet wird sichtbar/unsichtbar.“ Handy-Schwelle: `env.isSmall`; Tablets
   getrennt festlegen.
5. **Neue Regel (Abschnitt 4 oder eigener Abschnitt „Optik-Regeln“):** „Keine eigenen Farbwerte, keine eigenen Schriftgrößen. Nur
   Odoo/Bootstrap-Variablen (`$o-action`, `tint-color($o-action, 90%)`, `$o-gray-*`, `--bs-*`), Odoo-Klassen (`btn`,
   `btn-group`, `badge`, `alert`, `form-switch`, `o_tag`) und FontAwesome-/`oi`-Symbole. Feste Farben des v1-Viewers
   (`pdf_highlight_viewer.scss`) und die im Community-Code nicht definierten Variablen (`--o-view-background-color`,
   `--body-bg-secondary`, `--o-webclient-hover-bg`) werden nicht übernommen. Mausrad scrollt, Strg+Mausrad zoomt.“

**Mittel (Odoo-Vorbild soll zum Aussehen genutzt werden):**

6. **Abschnitt 3, Zeile „Vorbild Layout“:** ergänzen: „Vorschau nur ab 1400 px (Odoo blendet darunter aus); bei uns immer sichtbar,
   Grund: Dokument ist Hauptsache. Aussehen von `o_attachment_control` (Symbol `fa-window-restore`, Sprechblase ‚Open preview in
   a separate window.‘) und `o_form_sheet_bg` übernehmen.“ Zusätzlich die **Option „echtes Formular an `int_filemanager.node` mit
   eigenem Vorschau-Baustein und `apply_field_values` an `onWillSaveRecord`/`onRecordSaved`“** als bewusst abgelehnte oder offene
   Alternative eintragen.
7. **4.3, Werkzeugleiste:** „Zeiger / Kasten / Nachlesen als `btn-group` mit Symbolknöpfen wie Odoos Ansichtsumschalter
   (`fa-mouse-pointer`, `fa-crop`, `fa-refresh` o. ä.), Zoom-Symbole und Sprechblasen wie `FileViewer` (`fa-plus`/`fa-minus`);
   Schalter ‚Feldnamen einblenden‘ als `CheckBox` mit `form-switch`.“
8. **4.4, Feldliste:** „Zeilen im Formularaufbau (`o_group`/`o_inner_group`, Beschriftung links, Hilfetext als Odoo-`?`), ‚+ Feld‘ als
   `SelectMenu` mit Suche, ‚→ Feld …‘ wie die Spaltenzuordnung im Import-Assistenten, Hinweise (abweichende IBAN, Dublette)
   als `alert alert-warning`, ungültige Werte mit `o_field_invalid`.“
9. **4.3/(g), Kästen:** „Aussehen der Griffe wie `builder_overlay.scss`/`o_handle` (8 Griffe, Cursor je Griff, RTL-Umkehr). Zieh-Code eigen
   (Zeigerereignisse mit Zeigererfassung am Element, damit es auch im zweiten Fenster arbeitet); `useDraggable` nur für Verschieben
   prüfen.“
10. **Abschnitt 2 „Odoo selbst“ / 3, Popover:** Formulierung „Eigenschaft hinzufügen direkt im Formular über ein Popover“ präzisieren:
    „Der Knopf ‚Add Property‘ legt einen Platzhalter an und öffnet das Definitions-Popover (Beschriftung, Feldtyp mit Bildchen);
    unser Popover übernimmt Anordnung und ‚Add/Discard‘ aus `multi_create_popover`.“
11. **11.4 (Oberfläche im Detail), Zustände:** „Leer: `NoContentHelper` (`o_view_nocontent`); Laden: `fa-circle-o-notch fa-spin`;
    Fehler und Umwandler nicht erreichbar: Odoo-Meldung `warning`/`danger` mit optionalem Textknopf; Rückfrage: `ConfirmationDialog`.“

**Niedrig (Genauigkeit der Aussagen):**

12. Abschnitt 3, Zeile „Dokument in zweitem Fenster“: „`popout()` öffnet ein Popup (`window.open`), `pip()` nutzt
    `documentPictureInPicture` mit Ersatz `window.open` und beginnt mit kleiner Höhe; Größe angeben. Beobachter im zweiten Fenster
    hängen am Hauptfenster.“
13. Abschnitt 3, Zeile „Pager“: „Im Kern nutzen ihn nur Formular/Liste/Kanban/Aktivität; Nutzung in einer Client-Aktion ist
    neu und wird in U-3 zuerst im Browser bestätigt.“
14. **11 (Barrierefreiheit):** „Odoo-Niveau: `aria-label`/`data-tooltip` an Symbolknöpfen, `role="alert"` an Meldungen. Darüber hinaus
    Tastaturbedienung der Kästen (Pfeile, Entf).“
15. **(m) Dunkelmodus:** im Konzept vermerken „in Community nicht prüfbar, nur Odoo-Variablen verwenden“.

## 6. Abdeckung

**Vollständig gelesen:**
- Das Konzept (alle 533 Zeilen, inklusive der geforderten Abschnitte 3, 4, 5, 6, 8, 10.6, 10.7, 11).
- Odoo: `mail/.../attachment_view.js/.xml/.scss`, `mail/.../chatter/web/form_compiler.js` und `form_renderer.js`,
  `mail_popout_service.js`, `web/.../resizable_panel` (alle drei Dateien), `core/pager/pager.js/.xml`, `search/pager_hook.js`,
  `search/layout.js/.xml`, `search/control_panel/control_panel.xml`, `search/breadcrumbs/breadcrumbs.xml`, `form_status_indicator`
  (`.js`/`.xml`), `form_controller.xml`, `core/hotkeys/hotkey_service.js` (bis zur Registrierung) und `hotkey_hook.js`,
  `core/utils/pdfjs.js`, `model/record.js`, `web/.../multi_create_popover.js/.xml`, `select_menu.xml`, `notebook.xml`,
  `tags_list.xml/.scss`, `checkbox.xml`, `notification.xml`, `no_content_helpers.xml`, `action_helper.xml`,
  `core/file_viewer/file_viewer.xml/.js/.scss/.dark.scss`, `pdf_viewer_field.js/.xml`, `crop_overlay.js` (Beginn bis zum Zeigerteil),
  `image_crop.xml`, `image_transformation.xml`, `builder_overlay.xml`, `base_import/.../import_action.xml`,
  `import_data_content.xml` (Kernteil), `report_action.xml`, `form_group.xml`, `form_label.js/.xml`, `settings_confirmation_dialog.js`,
  `form_error_dialog.xml`.
- v2/native_ui des Moduls: `pdf_highlight_viewer.js/.scss/.xml`, `document_review_dialog.xml/.scss`, `previews.scss`, `upload_panel.scss`,
  `versions_dialog.xml`, `text_input_dialog.xml`, `text_editor_dialog.xml`, `controller_navigation.js` (Breadcrumbs-Teil),
  `controller_previews.js`, `search_model.js`, `views/int_filemanager_node_views.xml` (Details-Formular).

**Teilweise gelesen (Ausschnitte, Rest überflogen):** `form_controller.js` (Pager, Speichern, `beforeLeave`, `discard`, `className`),
`properties_field.js`/`.xml` und `property_definition.xml/.js` (Erstellen, Popover, Kopf), `select_menu.js` (Kopf), `notebook.js`
(Kopf und Doku), `ui_service.js` (Schwellen), `dropdown.js` (`isBottomSheet`), `draggable_hook_builder.js` (Zeiger/Touch-Stellen
per Suche), `builder_overlay.scss` (Griffe), `primary_variables.scss` (Farben), `relational_utils.js` (Anlegen), `action_service.js`
(`_getBreadcrumbs`), `start.js` (Klassen), `assetsbundle.py` (RTL-Zeilen), `controller_mutations.js` (Vorschau-URL),
`filemanager_controller_mixin.js` (nur Fundstellen).

**Nur per Suche bestätigt:** `web/static/lib/pdfjs/web/viewer.js` (Vorhandensein von `window.PDFViewerApplication`, Ereignisnamen,
Cookie `color_scheme`), `web/models/ir_http.py` (`color_scheme`), Suche nach CSS-Variablen im gesamten Quellcode,
Vorkommen von `usePager`, `TextLayer`, `ResizablePanel`, `o_attachment_preview`, `data-hotkey`, `form-switch`, `useHotkey`.

**Nicht geprüft:**
- Odoo Enterprise (Rechnungs-Digitalisierung, Extract, Studio, Dunkelmodus, Enterprise-CSS): nicht im Klon.
- **Verhalten im Browser:** ob `usePager` in einer Client-Aktion sichtbar arbeitet, wie die Brotkrumen wirklich aussehen, ob
  Ziehen/Kästen im zweiten Fenster funktionieren, Zoom im pdf.js-Rahmen mit Überlagerung, Tablet-Breiten, echtes Handy.
- Barrierefreiheit im Sinne von Bildschirmleser-Tests; nur Attribute im Code gesehen.
- Übersetzungen (`i18n`), Rechte-/Servermodelle, Konzeptteile 2, 7, 9 und 10.1–10.5 (inhaltlich, nicht Oberfläche).
- Der Odoo-Klon ist der Stand 2026-09-24, nicht das Docker-Image `odoo:19.0-hm-test`; Abweichungen zwischen beiden
  sind nicht ausgeschlossen (Modulzahl 638 gegenüber 692 im Konzept).
