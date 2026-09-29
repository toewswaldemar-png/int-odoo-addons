# int_filemanager: TXT/andere Textformate mit Odoos Rich-Text-Editor bearbeiten — Untersuchung

Stand 2026-09-21. Reine Analyse auf ausdrücklichen Wunsch, nichts umgesetzt. Fragestellung:
sollen `txt` und die übrigen heute im nativen `CodeEditor`-Dialog bearbeitbaren Textformate
(`csv`/`log`/`md`/`json`, siehe `TEXT_EDIT_EXTENSIONS` in `filemanager_controller_mixin.js`)
stattdessen — oder zusätzlich — mit Odoos **Rich-Text-Editor** (dem WYSIWYG-Editor, den Odoo für
Formatiertext/E-Mail-Vorlagen/Website-Inhalte nutzt) bearbeitbar gemacht werden.

**Ergebnis vorweg, danach im Detail begründet:** für `txt`/`csv`/`log`/`json` ist das die falsche
Idee (technische Gründe unten, nicht nur Geschmackssache) — für `md` grundsätzlich denkbar, aber
mit echten, hier konkret benannten Kosten, weil Odoo **kein natives Markdown-Format** kennt. Der
eigentlich günstigste Weg zu "Rich-Text am Datei-Datensatz" existiert bereits, ganz ohne die
Text-Dateien selbst anzufassen (Abschnitt 5).

**Methodik:** Web-Recherche zu Odoo 19s Editor-Architektur (Quellen je Abschnitt) plus Abgleich
mit dem bestehenden Code dieses Moduls (`text_editor_dialog.js`, `filemanager_controller_mixin.js`).
Keine Live-Instanz-Verifikation in dieser Session.

---

## 1. Was Odoos Rich-Text-Editor technisch ist

Odoos WYSIWYG-Editor besteht aus zwei Schichten: einer `Wysiwyg`-Komponente, die intern eine
`OdooEditor`-Instanz hält (`this.odooEditor`), plus einer "Powerbox" für Slash-artige
Befehle/Formatierungen. Er ist der Standard-Widget für **`fields.Html`** — ein Feldtyp, der in
PostgreSQL als `TEXT`-Spalte liegt, deren Inhalt aber **ein HTML-String** ist, kein Klartext. Beim
Speichern läuft standardmäßig `html_sanitize()` (Python, `odoo.tools`) darüber, um gefährliches
HTML/Script-Inhalte herauszufiltern — Sicherheitsmechanismus, aber auch ein Hinweis darauf, dass
der Editor grundsätzlich **HTML produziert und konsumiert**, nichts anderes.

Bild-Einbettung läuft über `ir.attachment` plus die Routen `/web/image/...`/`/web/content/...` —
ein eingefügtes Bild wird als eigener `ir.attachment`-Datensatz abgelegt, der HTML-Inhalt trägt
danach einen `<img src="/web/image/<attachment_id>">`-Verweis. Das ist für Odoos eigene
Datensätze (Produktbeschreibung, E-Mail-Vorlage) genau richtig — die Referenz bleibt innerhalb
derselben Datenbank gültig.

**Quellen:** [Odoo Editor — Odoo 19.0 documentation](https://www.odoo.com/documentation/19.0/developer/reference/frontend/odoo_editor.html), [HTML Field in Odoo: Complete Developer and Business Guide](https://www.dasolo.ai/blog/odoo-data-api-5/odoo-html-field-guide-112), [Media — Odoo 19.0 documentation](https://www.odoo.com/documentation/19.0/developer/howtos/website_themes/media.html)

---

## 2. Der Kernkonflikt: der Editor ist HTML-zentriert, die betroffenen Dateien sind es nicht

`int_filemanager` behandelt die Platte als Wahrheit — eine `.txt`-Datei ist danach exakt die
Bytes, die auf der Platte liegen, nichts sonst. Odoos Rich-Text-Editor kennt aber nur **ein**
Ausgabeformat: HTML. Jede Nutzung für ein Nicht-HTML-Format braucht also zwingend eine
Konvertierung in beide Richtungen (Laden: Dateiformat → HTML für den Editor; Speichern: HTML →
zurück ins Dateiformat) — das ist kein Implementierungsdetail, sondern der entscheidende
Unterschied zum heutigen `CodeEditor`-Ansatz, der Dateiinhalt 1:1 als Text lädt/speichert, ganz
ohne Übersetzungsschritt.

### Format für Format bewertet

**`txt` (explizit in der Fragestellung genannt) — klar ungeeignet.** Klartext kennt per Definition
keine Formatierung. Ein Rich-Text-Editor bietet Fett/Kursiv/Überschriften/Listen an — jede dieser
Formatierungen hätte beim Zurückschreiben in `.txt` **kein Ziel** (müsste beim Speichern wieder
auf reinen Text reduziert werden, d.h. die im Editor gesetzte Formatierung ginge beim Speichern
kommentarlos verloren). Ergebnis: ein Editor, der optisch Formatierung anbietet, die nie ankommt —
verwirrender, nicht besser als der heutige `CodeEditor`.

**`csv` — noch klarer ungeeignet.** CSV ist tabellarische, maschinenlesbare Struktur (Trennzeichen,
Zeilen=Datensätze). Ein Fließtext-Editor mit Formatierungsoptionen ist konzeptionell das falsche
Werkzeug — CSV bräuchte, wenn überhaupt, einen Grid-/Tabellen-Editor, keinen WYSIWYG-Text-Editor.

**`log` — wie `txt`.** Diagnosetext, in der Praxis eher gelesen als redigiert; dieselbe
Formatierungs-geht-verloren-Problematik wie bei `txt`, zusätzlich meist sehr lang (Performance des
Rich-Text-Editors bei vielen tausend Zeilen unklar/ungeprüft, der `CodeEditor` ist dafür gebaut).

**`json` — ungeeignet, mit einem konkreten Korruptionsrisiko zusätzlich zur reinen
Eignungsfrage.** JSON ist strikt syntaktisch (Anführungszeichen, Kommas, Klammern müssen exakt
stimmen). Rich-Text-Editoren führen typischerweise automatische Zeichenersetzung durch
("intelligente Anführungszeichen" `"` → `„`/`"`, Gedankenstrich-Ersetzung u.ä.) — würde ein
Editor das auf JSON-Inhalt anwenden, entstünde ungültiges JSON, ohne dass es beim Tippen auffällt.
Selbst wenn eine reine HTML↔JSON-Rückkonvertierung fehlerfrei bliebe, ist das Grundrisiko real und
in keiner Weise ein Vorteil gegenüber dem syntax-bewussten `CodeEditor` (der JSON zudem mit
Syntax-Highlighting darstellt, was der Rich-Text-Editor nicht leistet).

**`md` (Markdown) — der einzige plausible Kandidat, aber mit echten Kosten.** Markdown ist
inhaltlich näher an "Rich Text" (Überschriften, Fett/Kursiv, Listen, Links) als die anderen vier
Formate — die intuitive Erwartung "Markdown ↔ Rich Text sollte doch fast dasselbe sein" ist
nachvollziehbar. **Aber laut Recherche unterstützt Odoos eigener Editor — selbst die
Enterprise-Knowledge-App, deren ganzer Zweck redigierbare Artikel sind — kein natives
Markdown-Import/-Export.** Mehrere Community-Zusatzmodule (`web_widget_markdown`, `oe_markdown`,
`praetorx_markdown`) existieren genau deshalb, um diese Lücke zu schließen — das ist also ein
bekanntes, wiederkehrendes Problem im Odoo-Ökosystem, keine Eigenheit dieses Projekts. Eine
Umsetzung bräuchte:
- eine JS-Konvertierungsbibliothek in beide Richtungen (z.B. `marked`/`markdown-it` für
  Markdown→HTML beim Öffnen, `turndown` für HTML→Markdown beim Speichern) — zusätzliche
  Abhängigkeit, nicht Teil des heutigen Stacks.
- **Rundreise-Drift als strukturelles Risiko, nicht nur Kantenfall:** Markdown hat mehrere
  gültige Schreibweisen für dieselbe Formatierung (`*Text*` vs. `_Text_` für Kursiv, `-`/`*`/`+`
  als Listenzeichen). Eine Markdown→HTML→Markdown-Rückkonvertierung normalisiert typischerweise
  auf eine feste Schreibweise — jede Datei, die im neuen Editor geöffnet und gespeichert wird,
  würde sich in ihrer Zeichenebene ändern, auch wenn optisch nichts verändert wurde. Bei Dateien,
  die z.B. per Git versioniert werden oder deren exakte Schreibweise anderswo erwartet wird
  (Konfigurationsdateien im Markdown-Format, wie sie z.B. **in diesem Repo selbst** als
  `docs/*.md` massenhaft vorliegen), wäre das ein unerwünschter Nebeneffekt.
- **Dasselbe Bild-Einbettungsproblem wie bei HTML (Abschnitt 1), hier verschärft:** fügt ein
  Nutzer im Rich-Text-Editor ein Bild in eine Markdown-Datei ein, müsste dieses Bild entweder (a)
  als `ir.attachment` in der Odoo-Datenbank landen und die Markdown-Datei bekäme einen
  `/web/image/...`-Verweis — dann ist die `.md`-Datei nicht mehr portabel, ihr Bild existiert nur
  noch innerhalb dieser einen Odoo-Instanz, ein struktureller Bruch mit dem Grundprinzip "Platte
  ist die Wahrheit" — oder (b) müsste eine eigens gebaute Brücke das Bild stattdessen als Datei
  neben die `.md`-Datei auf die Platte schreiben und einen relativen Pfad einsetzen — technisch
  machbar, aber ein komplett neuer, nicht von Odoo mitgelieferter Mechanismus.

**Zwischenfazit:** von den fünf heute unterstützten Formaten profitiert **keines** risikofrei von
einem Wechsel/einer Ergänzung um den Rich-Text-Editor. `md` wäre der einzig ernsthaft diskutable
Kandidat, aber nur mit selbst gebauter Konvertierung und den oben benannten strukturellen
Kompromissen — kein "kleiner Umbau".

---

## 3. Der eigentlich passende, bisher nicht genannte Kandidat: `.html`

Nicht Teil der heutigen `TEXT_EDIT_EXTENSIONS`, aber der einzige Dateityp, bei dem **kein**
Konvertierungsschritt nötig wäre: eine `.html`-Datei ist bereits genau das Format, das der Editor
nativ produziert/konsumiert. Trotzdem zwei reale Einschränkungen, die vor einer Umsetzung zu
klären wären: (1) Odoos Editor ist für **Fragment**-Bearbeitung gebaut (der Inhalt eines
`fields.Html`-Felds, kein eigenständiges Dokument) — eine vollständige `.html`-Datei mit
`<html>`/`<head>`/eingebundenen `<style>`/`<script>`-Blöcken würde beim Laden vermutlich auf den
Body-Inhalt reduziert und externe Kopfzeilen-Bestandteile beim Speichern verlieren, nicht
1:1-roundtrip-fähig. (2) `html_sanitize()` würde standardmäßig aktive Inhalte
(`<script>`) entfernen — für "echte" HTML-Dateien mit eigenem JavaScript ungeeignet, nur für
reine Formatierungs-HTML brauchbar. Realistischer Anwendungsfall wäre also eher "eine einfache
formatierte Notiz als `.html` ablegen", nicht "beliebige HTML-Dateien editieren".

---

## 4. Vergleich zum Status quo: warum `CodeEditor` für alle fünf heutigen Formate die richtige Wahl bleibt

Der aktuelle Ansatz (`CodeEditor`, Odoos ACE-basierter Editor, derselbe, den Odoo für
View-XML-Bearbeitung im Entwicklermodus nutzt, siehe `../int_filemanager_native_ui.md`, Punkt 9) hat
gegenüber dem Rich-Text-Editor für **genau diese** Formate strukturelle Vorteile, die kein
Implementierungsdetail sind: kein Konvertierungsschritt (Inhalt = Inhalt, keine
Formatverlust-Gefahr), Syntax-Highlighting passend zum jeweiligen Format (u.a. für `json`
relevant), keine automatische Zeichenersetzung, die Klartext/Daten korrumpieren könnte, und
Zeilennummern, die bei Log-/Konfigurationsdateien tatsächlich gebraucht werden. Der Rich-Text-
Editor wäre hier ein Rückschritt, kein Upgrade — unabhängig vom Implementierungsaufwand.

---

## 5. Der eigentlich schon vorhandene, kostenlose Weg zu Rich-Text an einer Datei

Falls der eigentliche Bedarf hinter der Fragestellung "ich möchte formatierten Text zu/an einer
Datei erfassen können" ist (nicht zwingend "die Datei selbst soll HTML enthalten"): **das gibt es
bereits, ganz ohne die Text-Dateien anzufassen.** `int_filemanager.file` erbt seit Baustein 2
(`../../int_filemanager_paperoffice_recherche.md`) von `mail.thread` — der Chatter jeder Datei hat
damit bereits eine "Notiz protokollieren"-Funktion, die **intern exakt denselben Rich-Text-Editor
nutzt** (Odoos Mail-Message-Composer ist ebenfalls ein `fields.Html`-Feld mit Wysiwyg-Widget).
Ein Nutzer kann heute schon zu jeder Datei eine formatierte Notiz (fett, Listen, Links) im Chatter
hinterlassen — journalisiert, mit Zeitstempel/Autor, durchsuchbar über die normale
Chatter-Historie. Das deckt vermutlich den eigentlichen Wunsch ("Rich-Text am Datei-Datensatz")
vollständig ab, ohne eines der oben beschriebenen Format-/Portabilitätsprobleme — kein neuer Code
nötig, nur Sichtbarkeit/Bewusstsein für eine bereits vorhandene Fähigkeit.

---

## 6. Nachtrag: wie Cloudreve und OpenCloud dasselbe Problem lösen, plus MDXEditor-Alternativen

Direkt am Code des zweiten Nutzer-Projekts geprüft (`cloudreve/assets/src/component/Viewers/MarkdownEditor/`,
siehe auch `../../erp-odoo-vs-cloudreve-vergleich-2026-09-21.md`). **Wichtige Klarstellung zuerst:**
Cloudreve nutzt für `.md`-Dateien **nicht** einen generischen HTML-Rich-Text-Editor (wie Odoos
OdooEditor), sondern eine dedizierte, **Markdown-native** Komponente
(`@mdxeditor/editor`/`MDXEditor`) — deren internes Datenmodell ist Markdown selbst (AST), nicht
HTML. Das bestätigt genau die in Abschnitt 2 gezogene Schlussfolgerung: der richtige Rich-Editor
für Markdown ist ein Markdown-spezifisches Werkzeug, kein zweckentfremdeter HTML-Editor — Cloudreve
löst das Problem nicht, indem es die HTML-Hürde überwindet, sondern indem es sie gar nicht erst
aufbaut.

**Wie die drei in Abschnitt 2 offen gelassenen Probleme dort konkret gelöst sind:**

- **Rundreise-Drift:** über einen `diffSourcePlugin` mit umschaltbarer "Quelltext"-Ansicht
  (`DiffSourceToggleWrapper`) kann jederzeit zwischen WYSIWYG- und rohem Markdown-Text gewechselt
  werden — das Risiko wird nicht technisch eliminiert (MDXEditor normalisiert beim Parsen/Rendern
  ebenfalls), aber durch Transparenz entschärft: der Nutzer sieht/kontrolliert die tatsächliche
  Zeichenebene, statt ihr blind zu vertrauen.
- **Bild-Portabilität (das in Abschnitt 2 als "ungelöst, bräuchte eigene Brücke" benannte
  Problem) — genau diese Brücke existiert bei Cloudreve bereits, code-bestätigt:**
  `markdownImagePreviewHandler()` (`redux/thunks/viewer.ts`) löst ein Bild im Markdown-Text als
  **relativen Pfad zum Ordner der `.md`-Datei selbst** auf (`new CrUri(mdFileUri).parent().join_raw(imageSource)`),
  sucht die Zieldatei ganz normal im Dateibaum und holt sich nur zur Anzeige eine temporäre
  signierte URL — der gespeicherte Markdown-Text selbst enthält weiterhin einen simplen relativen
  Pfad (`![](bild.png)`), keine Cloudreve-interne ID. `uploadMarkdownImage()` lädt ein neu
  eingefügtes Bild ganz regulär in den Dateibaum hoch (`uploadRawFile()`) und schreibt nur den
  **Dateinamen** als Referenz in den Markdown-Text zurück. Ergebnis: eine mit Cloudreve bearbeitete
  `.md`-Datei bleibt vollständig portabel — exakt Standard-Markdown mit Standard-Bildpfaden, lesbar
  und weiterverwendbar auch komplett außerhalb von Cloudreve. `saveMarkdown()` selbst schreibt
  reinen Text zurück, keine HTML-Zwischenform.
- **Formatierungsumfang über reines CommonMark hinaus:** Tabellen, Frontmatter (YAML-Kopfblock),
  Admonition-Callouts (Hinweis-/Warnkästen im GitHub-Docs-Stil), Codeblöcke mit
  sprachspezifischem Syntax-Highlighting (eigenes CodeMirror-Plugin, ca. 20 Sprachen) — deutlich
  über das hinaus, was eine einfache HTML-Rückkonvertierung bieten würde.

### 6a. Zweiter unabhängiger Beleg: OpenCloud (github.com/opencloud-eu) — dieselbe Linie, andere Bibliothek

Direkt am Quellcode geprüft (`opencloud-eu/web`, `packages/web-app-text-editor/src/`, GitHub-Browser
dieser Session, nicht nur Marketing-Text). **Wichtiger Fund vorweg:** OpenClouds eigenes
Marketing-README nennt "Markdown Editor (ToastUI)" — der tatsächliche, aktuelle Code nutzt aber
**TipTap** (`@opencloud-eu/web-pkg/editor`, ProseMirror-basiert) **plus Yjs** für echte
Echtzeit-Zusammenarbeit (`ydoc`/`awareness`, dasselbe CRDT-Prinzip, das auch Odoos eigene
Enterprise-Knowledge-App für kollaborative Artikel nutzt, siehe
`int_filemanager_odoo_native_integration_2026-09-21.md`, Punkt 4) — ein Beleg dafür, dass man bei
diesem Thema grundsätzlich dem Code, nicht der Beschreibung glauben sollte, genau die in diesem
Repo durchgehend gepflegte Sorgfalt.

**`detectContentType()` (`yjs.ts`) zieht exakt dieselbe Grenze, die auch dieses Dokument zieht —
unabhängig ermittelt, drittes konvergierendes Ergebnis:**

```ts
if (extension === 'ocnote') return 'tiptap-json'
if (extension === 'md' || extension === 'markdown' || mimeType === 'text/markdown') return 'markdown'
return 'plain-text'
```

Nur `.md`/`.markdown` bekommt die Rich-Text-Behandlung. Alles andere (auch dort implizit
`txt`/`csv`/`json`/`log`) bleibt bewusst `plain-text`. **Bemerkenswert zusätzlich:** OpenCloud
führt für "echte", kollaborative Notizen ein **eigenes, proprietäres Format** ein (`.ocnote`,
TipTaps natives JSON-Dokumentmodell) — getrennt von `.md`. Das bestätigt eine Unterscheidung, die
auch für `int_filemanager` relevant wäre: "eine bestehende portable `.md`-Datei komfortabler
bearbeiten" und "ein neues, editor-natives Rich-Notiz-Format einführen" sind zwei verschiedene
Anwendungsfälle mit unterschiedlichen Kompromissen (Portabilität vs. Funktionsumfang/
Kollaboration) — OpenCloud baut bewusst beides statt eines Kompromisses.

### 6b. MDXEditor-Alternativen im Überblick, mit Blick auf Eignung für Odoos OWL-Frontend

Alle unten genannten Bibliotheken sind laut Recherche **MIT-lizenziert** — Lizenz ist bei keiner
davon ein Unterscheidungskriterium, wohl aber die **Framework-Kopplung**, was für eine mögliche
`int_filemanager`-Umsetzung (OWL, nicht React/Vue) der praktisch entscheidende Punkt ist, den die
ursprüngliche Einschätzung in Abschnitt 6 ("framework-unabhängig genug für OWL") zu MDXEditor so
**nicht korrekt wiedergegeben hatte** — Korrektur hiermit:

| Bibliothek | Architektur | Framework-Kopplung | Genutzt von | Eignung für OWL |
|---|---|---|---|---|
| **MDXEditor** (`@mdxeditor/editor`) | eigener Markdown-AST-Editor | **fest an React gekoppelt** (React-Komponente, kein headless Core) | Cloudreve | schlecht — React müsste als komplette Zusatz-Laufzeit neben OWL eingebettet werden (manuelles React-Mounting in einen OWL-Container, kein sauberer Weg) |
| **TipTap** (`@tiptap/core` + `@tiptap/markdown`) | ProseMirror-Wrapper, **Framework-agnostischer Core**, dünne View-Bindings für React/Vue/Svelte | Core selbst framework-frei, OpenCloud nutzt nur die Vue-Bindung | OpenCloud (dort mit eigener Vue-Bindung) | **am ehesten geeignet** — der Core ließe sich mit einer eigenen, dünnen OWL-Bindung ansteuern, genau wie OpenCloud es für Vue getan hat, kein fremdes UI-Framework nötig |
| **Milkdown** | ProseMirror + `remark` (derselbe Markdown-Parser wie viele Static-Site-Generatoren), Plugin-System, von Typora inspiriert | Core ebenfalls framework-agnostisch, offizielle Bindings unter anderem für Vue/React | — | ähnlich geeignet wie TipTap, weniger verbreitet/erprobt als TipTap in diesem Vergleich |
| **Toast UI Editor** (`@toast-ui/editor`, `nhn/tui.editor`) | eigener Markdown-Editor mit Split-/WYSIWYG-Modus | **vanilla-JS-Core**, Vue/React nur als optionale dünne Wrapper obendrauf | (im OpenCloud-Marketing genannt, im tatsächlichen Code nicht mehr verwendet, siehe oben) | technisch ebenfalls geeignet (kein Framework-Zwang), aber laut Recherche das mit Abstand größte Bundle (~450 KB) |
| **@uiw/react-md-editor** | einfacher Split-Pane-Editor mit Live-Vorschau, kein echtes WYSIWYG | **React-spezifisch** | — | ungeeignet für OWL, zudem kein echtes Inline-WYSIWYG (eher CodeMirror+Vorschau nebeneinander — inhaltlich näher am heutigen `CodeEditor`-Ansatz als an "Rich Text") |

**Korrigierte Einordnung für `int_filemanager`:** dieser Befund ändert die Grundempfehlung aus
Abschnitt 2/7 nicht (Odoos **eigener** OdooEditor bleibt die falsche Wahl für `.md`), präzisiert
aber den Bauplan aus der ursprünglichen Fassung dieses Abschnitts: **nicht** MDXEditor (React-
Bindung, schlechte Passform zu OWL), sondern **TipTap** (framework-agnostischer Core, freie
`@tiptap/markdown`-Erweiterung, genau die Bibliothek, die OpenCloud bereits produktiv für exakt
denselben Anwendungsfall einsetzt) wäre der naheliegendere Ausgangspunkt — mit einer eigenen,
schlanken OWL-Anbindung anstelle der Vue-Anbindung, die OpenCloud gebaut hat. Die
Bild-Portabilitätslösung bliebe unverändert am Cloudreve-Vorbild orientiert (Abschnitt 6, relativer
Pfad zum Ordner der Markdown-Datei, Sibling-Datei-Upload statt `ir.attachment`) — das ist
Bibliothek-unabhängig und gilt für TipTap genauso wie für MDXEditor. **Echtzeit-Kollaboration
(Yjs, wie bei OpenCloud) wäre ein deutlich größerer Zusatzschritt** und für den heutigen
`int_filemanager`-Anwendungsfall (ein Firmenverzeichnis, keine ausdrücklich für Live-Co-Editing
vorgesehene Nutzung) nicht ohne Weiteres als notwendig anzunehmen — separat zu bewerten, falls der
Bedarf je entsteht.

**Bliebe unverändert ein eigenständiges Umsetzungsprojekt** (neue Frontend-Abhängigkeit, eigene
Route für den Bild-Upload-Handler, eigene OWL-Anbindung für TipTap) — aber mit einem konkreten,
inzwischen von zwei unabhängigen Systemen bewährten Bauplan statt einer offenen Frage.

**Quellen:** [github.com/opencloud-eu/opencloud](https://github.com/opencloud-eu/opencloud), [github.com/opencloud-eu/web](https://github.com/opencloud-eu/web), [Tiptap – Open Source Text Editor Framework](https://tiptap.dev/open-source-to-platform), [aguingand/tiptap-markdown](https://github.com/aguingand/tiptap-markdown), [5 React Markdown Editors Compared: Size & Maintenance](https://strapi.io/blog/top-5-markdown-editors-for-react), [Best React Markdown Editor 2026 (Eddyter)](https://eddyter.com/blogs/best-markdown-editor-components-react-2026)

## 7. Empfehlung

**Nicht umsetzen:** Rich-Text-Editor für `txt`/`csv`/`log`/`json` — technisch die falsche Wahl,
nicht nur unüblich (Abschnitt 2).

**Nur mit explizitem Zusatzaufwand und akzeptierten Kompromissen umsetzbar:** `md` — bräuchte
eine eigene Markdown↔HTML-Konvertierungsbibliothek (kein Odoo-Bordmittel), hat ein
strukturelles Rundreise-Drift-Risiko und ein ungelöstes Bild-Portabilitätsproblem. Nur sinnvoll,
falls der Bedarf tatsächlich "WYSIWYG-Markdown-Bearbeitung" ist und die Nebenwirkungen (Datei
ändert sich beim bloßen Öffnen+Speichern in der Zeichenebene) akzeptiert werden.

**Ohne jeden Zusatzaufwand bereits verfügbar:** die Chatter-Notiz-Funktion (Abschnitt 5) — falls
das den eigentlichen Bedarf deckt, ist das die mit Abstand günstigste Option.

**Falls tatsächlich HTML-Dateien ein Anwendungsfall werden:** `.html` zur unterstützten Liste
hinzuzufügen wäre der einzige technisch saubere Rich-Text-Kandidat unter den Dateiformaten selbst
— aber ein neuer, bisher nicht vorhandener Anwendungsfall, keine Verbesserung eines bestehenden.
