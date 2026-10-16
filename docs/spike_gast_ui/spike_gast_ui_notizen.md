# Spike Gast-UI (Stufe 3) – Notizen der Spike-Sitzung

Branch `spike/gast-ui` (Repo int-odoo-addons), Commits be68cae und 2fc23e5, nicht gepusht. Wegwerf-Instanz auf HM-SRV ist entfernt.

Dateien im Branch (alles Wegwerfcode):
- `int_filemanager/controllers/spike.py` – Seite `/int_filemanager/spike/<token>`, Gateway `/int_filemanager/spike/rpc`, Hilfsfunktion fuer die Binaerrouten
- `int_filemanager/models/ir_binary.py` – `_find_record` liest das Cookie `fm_spike_token`
- `int_filemanager/static/src/guest/` – boot.js, guest_app.js/.xml, guest_orm.js, guest_action_service.js, guest_user_patch.js, guest_views.js
- `int_filemanager/views/int_filemanager_spike_views.xml` – Gast-Views (list, kanban, search) und Seiten-Template
- `int_filemanager/__manifest__.py` – Bundle `int_filemanager.assets_guest`
- `int_filemanager/tools/spike_gateway_attacks.py` – Angriffsskript (129 Zeilen Ausgabe), Lauf: `spike_attacks_final.txt` in diesem Ordner

Aufbau der Testinstanz (zum Wiederholen): Postgres 17 mit tmpfs, Image `int-filemanager-odoo:19.0-ocr` mit `--entrypoint /entrypoint.sh`,
Konfig mit `addons_path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons`, `odoo -i int_filemanager --stop-after-init`, dann Seed per `odoo shell`
(Seed: Benutzer `fmspike_creator` nur in Gruppe Filemanager-Benutzer, Ordner Gastbereich/Vertraege/Bilder/2025, ein fuer den Ersteller unsichtbarer Ordner
innerhalb des Bereichs, ein Ordner ausserhalb, je ein Dokument mit Tag "Geheim-Tag" in beiden; PDFs, PNGs, Text).

Hinweis zum Core-Stand: das Image hat Odoo 19.0-20260908, die lokale Kopie unter GitHub\odoo ist vom 2026-09-24; Zeilennummern koennen leicht abweichen.
