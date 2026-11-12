# BE01412 – interaktives QWeb-Arbeitsblatt für Odoo 19 CE

Die Vorlage wird als echte QWeb-Seite mit HTML-Eingabefeldern ausgefüllt. Speichern erfolgt serverseitig in Odoo, der PDF-Bericht greift auf denselben gespeicherten Datensatz zu. Kein Enterprise, kein Studio und kein Website-Modul erforderlich.

## Benutzung in Odoo

1. Modulordner int_repair_worksheet in den Addons-Pfad legen, Odoo neu starten, Apps aktualisieren und „BE01412 Interaktives QWeb-Arbeitsblatt“ installieren. Apps-Filter ggf. entfernen.
2. Reparaturen → Auftrag öffnen → **Arbeitsblatt ausfüllen**. Dabei entsteht ein dauerhaftes Arbeitsblatt pro Reparaturauftrag. Ein vorhandenes Blatt wird erneut geöffnet.
3. Im Arbeitsblatt ATC/BR185.2, Seriennummer, RB, Prüfdatum, Prüfer, Ergebnisse, Maßnahmen und Material eintragen.
4. **Speichern** übernimmt alle Werte. **Speichern & PDF** speichert zuerst und öffnet anschließend den QWeb-Bericht. Für den PDF-Bericht benötigt der Odoo-Server wkhtmltopdf.
5. Bereits erfasste Blätter sind auch unter Reparaturen → Arbeitsblätter BE01412 erreichbar.

Die Änderung an Seriennummer oder RB im Blatt ändert keine Gerätestammdaten und keine Auftragsnummer im Reparaturauftrag. Die Werte sind Angaben des jeweiligen Protokolls. Die Initialwerte kommen aus dem zugeordneten Auftrag.

## Bedienung

- Eingangsprüfung: OK oder nicht OK auswählen; ↺ setzt ein Ergebnis wieder auf offen.
- Reparatur: Ergebnis und durchgeführte Maßnahme separat erfassen. Eine erneuerte Komponente kann anschließend OK sein.
- ATC: der ausschließlich für BR185.2 geltende Vereisungsschalter wird nicht anwendbar; eine zuvor gesetzte Maßnahme wird entfernt. Beim Zurückwechseln auf BR185.2 wird die Prüfung wieder offen.
- Material: Zeilen hinzufügen oder mit × leeren. Erst Speichern übernimmt die Änderung. Alt/Neu bleiben Dokumentationsfelder; Standard-Lagerbuchungen erfolgen im Reparaturauftrag.
- Ungespeicherte Änderungen sind sichtbar. Beim Verlassen wird gewarnt.
- Ein veralteter Browserstand wird serverseitig zurückgewiesen. Die Eingaben bleiben für den Abgleich sichtbar; „Neuen Stand laden“ verwirft sie bewusst.

## Speicherung und Zugriff

Persistentes Modell repair.worksheet, fest mit einem Reparaturauftrag verbunden. Eine Momentaufnahme der 27 Prüfplanzeilen wird bei der Anlage gespeichert. Änderungen am späteren PLAN ändern bestehende Blätter nicht. Dies ist noch kein Prüfplan-Freigabe-/Versionsverwaltungssystem.

Die QWeb-Seite verlangt eine Odoo-Anmeldung. Speichern ist ausschließlich als CSRF-geschützter POST möglich, mit normalen ORM-Berechtigungen und ohne sudo. Lagerbenutzer dürfen erstellen/lesen/bearbeiten, Lagermanager zusätzlich löschen. Eine globale Unternehmensregel beschränkt Datensätze auf die erlaubten Unternehmen. Die Controller prüfen zusätzlich den Lesezugriff auf den Reparaturauftrag. Formulardaten werden über eine feste Feldliste eingelesen, nicht als beliebige ORM-Werte übernommen.

Es gibt keine automatische Reparaturfreigabe oder Lagerbuchung und keine elektronische Signatur. Das Blatt ist als Entwurf gekennzeichnet. Die historischen technischen Texte sind für den Vorlagentest erhalten und noch fachlich freizugeben. Gedruckte Blattnummern zählen die vorgesehenen Blätter; sehr lange Texte können physische Zusatzseiten verursachen.

## Lokale Vorschau

Die Datei BE01412-Interaktiv.html wird aus demselben QWeb-Eingabetemplate erzeugt. Sie lässt sich ohne Odoo im Browser ausfüllen. **Speichern** verwendet dort ausschließlich localStorage dieses Browsers, **Speichern & Drucken** den Browserdruck. Die Vorschau enthält keinen Odoo-Zugang und überträgt keine Daten an einen Odoo-Server. Browserdaten löschen oder ein anderer Browser/Computer stehen nicht für eine dauerhafte Archivierung. Im installierten Modul erfolgt die dauerhafte Speicherung in der Odoo-Datenbank.

## Prüfung

Offline ausgeführt: Python-Syntax, XML, Formularparser (leere Werte, Abwählen, ATC, ungültige Daten, Feldbegrenzung und Feldliste), Auswertung des verwendeten QWeb-Teilumfangs und HTML-Escaping. Browser geprüft: Eingabe, Speichern/Neuladen, zurückgenommene Häkchen, Variantenwechsel, neue Materialzeilen, mobile Darstellung und JavaScript-Fehler.

Es steht hier keine lauffähige Odoo-Testdatenbank zur Verfügung. Die Vorschau ist daher kein Nachweis eines vollständigen Odoo-Laufzeittests. Integrationstests sind enthalten:

    odoo-bin -d TEST_DB -i int_repair_worksheet --test-enable --test-tags /int_repair_worksheet --stop-after-init

Vor Nutzung im Betrieb Installation, Berechtigungen, Controller/CSRF, gleichzeitige Bearbeitung und PDF-Ausgabe in einer Odoo-19-CE-Testdatenbank prüfen. Das neue Modul ist eigenständig; int_repair_worksheet_demo muss dafür nicht installiert werden. Der frühere Transient-Assistent wird nicht verändert und nicht migriert.
