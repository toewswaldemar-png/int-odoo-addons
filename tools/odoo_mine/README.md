# odoo_mine: Konventionen aus dem Odoo-Quelltext messen

Liest nur. Misst im Odoo-19-Core (Community-Module im Image `odoo:19.0-hm`) und in `int_filemanager`, wie oft Odoo selbst welches Muster benutzt.

```bash
# im Image des Odoo-Servers, Quelltext liegt unter /usr/lib/python3/dist-packages/odoo/addons
docker run --rm --user root --entrypoint python3 -v $PWD/tools/odoo_mine:/m:ro odoo:19.0-hm /m/mine.py core \
  /usr/lib/python3/dist-packages/odoo/addons '^(l10n_|test_|hw_|.*_demo$|pos_|website_|spreadsheet_dashboard_)' > result_core.json
docker run --rm --user root --entrypoint python3 -v $PWD/tools/odoo_mine:/m:ro -v <Ordner mit int_filemanager>:/src:ro odoo:19.0-hm /m/mine.py ours_all /src > result_ours_all.json
python report_python.py <Ordner mit result_*.json>      # Python-Muster
python report_other.py <Ordner mit result_*.json>       # Manifest, XML, Rechte, JS, SCSS, Tests
```

`mine_views_lines.py` zählt zusätzlich Zeilenlängen, View-, Menü- und Gruppen-IDs. Die Python-Zählung benutzt den AST; XML, JS und SCSS sind Textmuster (Näherung).
