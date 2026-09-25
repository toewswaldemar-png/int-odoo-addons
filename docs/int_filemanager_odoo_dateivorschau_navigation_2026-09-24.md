# int_filemanager: Navigation innerhalb der Dateivorschau — Tiefenprüfung des nativen FileViewer + ein neuer, unbenutzter Baustein

Stand 2026-09-24. Zwölftes Dokument der Reihe, auf ausdrücklichen Wunsch besonders gründlich statt
in kleinen Schritten bearbeitet. Neue Dimension gegenüber den bisherigen elf Dokumenten: nicht
"wie navigiere ich zu einem Datensatz in einer Liste/einem Baum", sondern **wie navigiert man
innerhalb einer geöffneten Dateivorschau selbst** (nächste/vorherige Datei, Zoom, separates
Fenster) — ein bisher komplett unbetrachteter Navigationsraum. Ergebnis: eine vollständige,
positive Tiefenprüfung eines bereits vorbildlich genutzten Bausteins, und ein zweiter, echter,
bisher ungenutzter nativer Baustein. Reine Recherche, nichts umgesetzt.

---

## 1. Der native `FileViewer` (`@web/core/file_viewer`) — vollständig gelesen, vollständige Gegenprobe gegen `int_filemanager`s tatsächliche Nutzung

### 1.1 Was der Baustein selbst leistet

`addons/web/static/src/core/file_viewer/file_viewer.js` (261 Zeilen) +
`file_viewer_hook.js` (38 Zeilen), beide vollständig gelesen. Ein generischer, für jedes Modell
nutzbarer Lightbox-Betrachter, registriert über `useFileViewer().open(file, files)`:

- **`next()`/`previous()`** mit Rundlauf (letzte→erste Datei und umgekehrt), fest verdrahtet auf
  `ArrowRight`/`ArrowLeft` (`onKeydown`, Zeilen 103-117); `Escape`/`q` schließt.
- **Zoom** (`+`/`-`/`0`-Tasten UND Mausrad, `onWheelImage`), **Drehen** (`r`-Taste, `rotate()`,
  90°-Schritte, rein visueller `state.angle`), **Verschieben per Ziehen** im gezoomten Zustand
  (`onMousedownImage`/`onMousemoveView`/`onMouseupImage`).
- **Drucken** (`onClickPrint`, öffnet ein eigenes Druckfenster) und **Herunterladen**
  (`onClickDownload`).
- Formatbewusst über Props-Flags (`isImage`/`isPdf`/`isVideo`/`isText`/`isUrlYoutube`) — PDF wird
  als eingebettetes `<iframe>` mit `pdfjs`-Viewer gerendert, `hidePDFJSButtons()` blendet dessen
  eigene Download-Schaltfläche aus (Zeilen 62-71).

### 1.2 Abgleich mit `int_filemanager`s tatsächlicher Nutzung — vollständig positiv bestätigt

`filemanager_controller_mixin.js` (die relevanten Abschnitte vollständig gelesen, Zeilen 883-919):

```js
onPreview(record) {
    const files = this.model.root.records
        .filter((r) => !r.data.is_dir && isPreviewable(r.data.name))
        .map((r) => this.toViewerFile(r));
    const file = files.find((f) => f.path === record.data.path);
    this.fileViewer.open(file, files);
}
```

**`int_filemanager` nutzt den Baustein bereits exakt so, wie er gedacht ist:** `files` ist die
komplette, bereits geladene Liste aller vorschaubaren Dateien im **aktuell offenen Ordner**, nicht
nur die angeklickte Einzeldatei — Pfeiltasten-Navigation innerhalb der Vorschau blättert damit
korrekt durch den gesamten Ordnerinhalt, exakt wie ein Bildbetrachter unter Windows. `toViewerFile()`
(Zeilen 883-911) setzt zusätzlich eine verkleinerte Zwischengröße für die Vollbildvorschau
(`/int_filemanager/thumbnail?...&size=preview`, max. 1920px) statt des Originals, damit sich große
Handyfotos nicht sichtbar Stück für Stück aufbauen — eine sinnvolle, über den nativen Baustein
hinausgehende Ergänzung, keine Fehlnutzung.

**Dieselbe "alle Dateien dieses Typs im aktuellen Ordner"-Sammel-Logik wird bewusst konsistent
wiederverwendet:** `onPlayAudio()` (Zeilen 921-934, direkt im Anschluss an `onPreview()`) baut die
Wiedergabeliste für den eigenen Audio-Player nach demselben Muster — ein Konsistenzpunkt, der beim
Lesen auffällt, aber schon vorher richtig gemacht wurde.

**Bestätigt eine bereits in `project_int_filemanager_bild_ausbau.md` festgehaltene ältere
Beobachtung, jetzt mit der exakten Ursache:** "Rotation/Zoom in der Vorschau nicht persistiert" ist
kein übersehener Bug, sondern **strukturell unvermeidlich bei diesem Baustein** — `state.angle`/
`state.scale` in `file_viewer.js` sind reine, beim Schließen verworfene UI-Zustände, es gibt im
gesamten Baustein keinen Rückschreib-Pfad. Eine Persistenz wäre nur über den in
`int_filemanager_odoo_bildverarbeitung_vollstaendig_2026-09-24.md` beschriebenen Weg (eigener
Cropper.js-Aufruf + `modify_image`-Äquivalent) möglich, nicht über den `FileViewer` selbst.

**Ergebnis Abschnitt 1: kein offener Punkt.** Ein seltener Fall in dieser Reihe, in dem die
gründliche Prüfung zu "bereits vorbildlich gemacht" statt zu einem neuen Fund führt — selbst das
verdient Festhalten, damit später niemand denselben Baustein irrtümlich für ungenutzt hält.

---

## 2. Neuer Fund: `mail.popout`/Picture-in-Picture — ein echtes, ungenutztes zweites Navigationsmuster für die Vorschau

Ausgangspunkt: `mail`s eigener, **separater** Anhang-Betrachter für den Chatter
(`addons/mail/static/src/core/common/attachment_view.js`, 176 Zeilen, vollständig gelesen) —
bewusst nicht der `FileViewer`, sondern eine eigene, **inline in die Seite eingebettete** (nicht
modale) Ansicht mit eigener `onClickNext()`/`onClickPrevious()`-Logik über
`thread.attachmentsInWebClientView`.

**Der eigentlich wichtige Fund liegt in dessen `usePopoutAttachment()`-Hook** (Zeilen 82-158): er
nutzt einen **eigenständigen, generischen nativen Dienst** —
`addons/mail/static/src/core/common/mail_popout_service.js` (246 Zeilen, vollständig gelesen),
Service-Name `mail.popout`. Bisher in der gesamten Reihe nicht geprüft, weil er unter einem
Chat-spezifischen Namen registriert ist, aber **inhaltlich vollkommen generisch**:

- **`popout(component, props)`**: mountet eine **beliebige** OWL-Komponente in einem echten,
  separaten Browserfenster (`browser.open("about:blank", "_blank", "popup=yes")`) — kopiert dafür
  den kompletten `<head>` (CSS/Assets) der Hauptseite in das neue Fenster (`reset()`, Zeilen 32-51),
  damit die Komponente dort identisch aussieht.
- **`pip(component, props, {width, height, aspectRatio})`**: nutzt, falls vom Browser unterstützt,
  die **echte native Picture-in-Picture-API** (`window.documentPictureInPicture.requestWindow()`,
  Zeile 99-103) — ein immer-im-Vordergrund schwebendes Mini-Fenster, unabhängig vom
  Odoo-Browser-Tab; fällt bei fehlender Unterstützung auf ein normales Popup-Fenster zurück.
- **`createManager(id)`** (Zeilen 181-239): erlaubt **mehrere unabhängige Popout-Instanzen
  gleichzeitig**, über eine beliebige ID adressiert — nicht auf genau einen Chatter-Anhang
  beschränkt.
- Überwacht das externe Fenster per Polling (`pollClosedWindow()`, Zeilen 57-67) und ruft einen
  `afterPopoutClosed`-Hook auf, sobald der Nutzer es schließt — sauberes Aufräumen ohne eigenen
  Event-Verdrahtungsaufwand.

**Direkt nutzbar für `int_filemanager`, ohne neue Abhängigkeit:** `mail` ist bereits eingebunden
(Chatter-Nutzung, siehe `int_filemanager_odoo_navigation_weitere_bausteine_2026-09-24.md`). Ein
eigener Aufruf `useService("mail.popout").createManager("int_filemanager_preview").popout(FileViewer,
{files, startIndex, close})` (oder `.pip(...)` für ein schwebendes Mini-Fenster) würde es erlauben,
eine geöffnete Dateivorschau **in ein eigenes Fenster loszulösen** — z. B. ein PDF in einem zweiten
Fenster offen halten, während im Hauptfenster weiter durch andere Ordner navigiert wird. Bisher in
keinem Feature-Katalog dieser gesamten Session erwähnt, weder als Wunsch noch als geprüfte
Möglichkeit.

**Wichtige Einschränkung, ehrlich benannt:** `FileViewer` selbst hat kein `usePopoutAttachment()`-
Äquivalent und keine eingebaute "Popout"-Schaltfläche — die Verdrahtung (Popout-Button im
`FileViewer`-Template ergänzen, `mail.popout` von dort aus aufrufen) wäre eigene Integrationsarbeit,
kein Ein-Zeilen-Anschluss wie bei `useFileViewer()` selbst. Der Baustein (`mail.popout`) ist nativ
und fertig, die Verbindung zum `FileViewer` wäre neu zu bauen.

---

## 3. Einordnung

Ergänzt die Gesamtkarte um zwei Punkte: einen bestätigten, bereits korrekt genutzten Baustein
(`FileViewer`, mit jetzt vollständig verstandener Ursache für die alte
Rotation/Zoom-Persistenz-Lücke) und einen echten, bisher unbekannten, sofort verfügbaren aber noch
unverdrahteten Baustein (`mail.popout`/Picture-in-Picture) für eine bisher nirgends gewünschte,
aber plausible neue Fähigkeit: Dateivorschau in ein eigenes Fenster lösen.
