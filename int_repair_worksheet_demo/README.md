# BE01412 QWeb-Layouttest für Odoo 19 Community

Installierbares Testmodul. Der Assistent erfasst Daten in normalen Odoo-Formularen und druckt sie mit QWeb im nachgebauten BE01412-Arbeitsblatt. Keine Enterprise-Abhängigkeit.

## Installation und Test

1. Den Ordner int_repair_worksheet_demo in einen konfigurierten Addons-Pfad kopieren.
2. Odoo neu starten, Apps-Liste aktualisieren und „BE01412 QWeb-Arbeitsblatt (Layouttest)“ installieren. Apps-Filter ggf. entfernen.
3. Reparaturen → BE01412 Layouttest öffnen. Alternativ am Reparaturauftrag im Menü Aktionen → BE01412 Arbeitsblatt testen.
4. Gerätetyp, Seriennummer, RB, Prüfer und Datum eingeben. Prüfwerte und Maßnahmen setzen, Materialzeilen ergänzen.
5. „HTML-Vorschau“ oder „Arbeitsblatt als PDF“ drücken. PDF benötigt das für Odoo konfigurierte wkhtmltopdf.

Der gewählte Reparaturauftrag liefert Seriennummer und Referenz. Der Gerätetyp wird bewusst ausgewählt. Leer gelassene Prüfergebnisse bleiben unmarkiert. Bei ATC ist der Vereisungsschalter für BR185.2 nicht anwendbar. Bei einer Maßnahme bedeutet das Häkchen je nach Originalzeile: erneuert, gereinigt, gebohrt oder auf Stand gebracht. OK und Maßnahme sind unabhängig.

## Umfang

- A4-Hochformat; Originaltabellen, Dokumentkopf, 27 Prüfpunkte, Logo aus der XLS-Datei.
- Seite 1: Geräteidentifikation, Eingangsprüfung und Reparaturcheckliste.
- Seite 2: Material Alt/Neu und Bemerkungen; weitere Materialblätter ab 15 Positionen.
- Status „LAYOUTTEST“ anstelle einer vorgetäuschten Freigabe.
- Quellvorlage: BE01412 Arbeitsschritte Reparatur 185.2 ATC.xls, Blatt Protokoll. Historische Texte und Kopfadresse sind für den Vergleich erhalten. Das separate Deckblatt ist nicht Teil dieses Arbeitsblatt-Tests.

## Technische Grenzen

Der Assistent verwendet TransientModel. Daten werden von Odoo automatisch bereinigt und sind kein dauerhaftes Reparaturprotokoll. Es gibt keine Freigabeprüfung, keine automatischen Materialbuchungen, keine Messwertbewertung und keine elektronische Signatur. Für produktiven Betrieb sind dauerhafte Ergebnisdatensätze, freigegebene Prüfplanversionen und Berechtigungs-/Freigaberegeln zu ergänzen.

Die historischen Angaben nennen z. B. Stromwerte ohne Toleranzen und Drehmomentprüfungen ohne Sollwerte. Diese Inhalte wurden nicht technisch freigegeben.

Die mitgelieferte lokale HTML-/PDF-Vorschau verwendet dasselbe QWeb-Dokumenttemplate mit einem kleinen Offline-Renderer und fiktiven Daten. Sie ist keine Ausgabe aus einer laufenden Odoo-Instanz. Der Browser-PDF-Umbruch ist zusätzlich mit Odoos wkhtmltopdf zu prüfen. Lange Materialtexte/Bemerkungen können zusätzliche physische Seiten erzeugen; die Blattzählung im Kopf zählt die vorgesehenen logischen Blätter. Für Serienbetrieb ist die Überlaufbehandlung anzupassen.

## Validierung

Python-Syntax, XML und lokale Templateauswertung werden offline geprüft. Odoo-Integrationstests liegen in tests/test_worksheet.py und müssen gegen eine Testdatenbank laufen:

    odoo-bin -d TEST_DB -i int_repair_worksheet_demo --test-enable --test-tags /int_repair_worksheet_demo --stop-after-init

Die Integrationstests prüfen leere Ergebnisse, ATC-Abgrenzung, Materialfolgeblätter und echtes QWeb-HTML-Rendering. Eine Odoo-Testdatenbank steht in dieser Umgebung nicht zur Verfügung.
