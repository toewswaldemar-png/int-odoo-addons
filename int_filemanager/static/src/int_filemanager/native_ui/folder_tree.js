/** @odoo-module **/

// Eigene, wirklich lazy ladende Ordnerbaum-Komponente (2026-09-16) - ersetzt Odoos natives
// SearchPanel-Kategoriefeld (parent_id) als Navigationsquelle. Grund, live per EXPLAIN ANALYZE
// nachgewiesen (siehe project_int_filemanager_searchpanel_perf-Notiz): bei 69k Ordnern/1,38 Mio.
// Dateien war JEDER Odoo-Bordmittel-Pfad mehrere Sekunden teuer, egal ob expand="1" (laedt immer
// den GESAMTEN is_dir=True-Baum in einem search_read) oder ohne expand (faellt bei leerem
// Suchfilter auf ein GROUP BY parent_id UEBER DIE GESAMTE Tabelle zurueck, noch teurer) - beide
// Wege laden praktisch den kompletten Baum, weil Odoos hierarchize-Mechanik strukturell die volle
// Vorfahrenkette relativ zur AKTUELLEN GESAMT-Suchdomain aufloesen will, nicht nur die Kinder
// eines einzelnen angeklickten Knotens.
//
// Diese Komponente fragt stattdessen bei jedem Aufklappen genau EINE Ebene ueber die bereits
// bestehende /int_filemanager/tree-Route ab (controllers/main.py: tree_dir - eine einzelne, ueber
// folder_path indexierte Abfrage) - Kosten wachsen mit der Groesse der angeklickten Ebene, nicht
// mit der Gesamtzahl der Ordner im System. Navigation laeuft ueber literale Pfad-Strings statt
// SearchPanel-Kategoriewert-IDs (siehe native_search_model.js) - einfacher als Odoos eigene
// child_of/activeValueId-Buchhaltung, weil kein zweiter, von der Datei-Hierarchie unabhaengiger
// ID-Raum mehr im Spiel ist.
import { Component, onMounted, onWillUpdateProps, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

// Root-Knoten hat literal path==="" (Wurzel des Filemanager-Stammverzeichnisses) - als
// DOM-Attributwert dafuer bewusst NICHT die leere Zeichenkette direkt verwendet: t-att auf einem
// bereits live beobachteten, verwandten Fall (search_panel_patch.xml-Kommentar, jetzt entfernt)
// liess ein falsy Attribut (dort "false") komplett weg - kein Beleg, dass "" dasselbe Schicksal
// teilt, aber ein eigener, garantiert nie-falsy Sentinel kostet nichts und vermeidet das Risiko
// komplett.
export const ROOT_SENTINEL = "__root__";

export function domPathToPath(domPath) {
    return domPath === ROOT_SENTINEL ? "" : domPath;
}

function makeNode(path, name, hasChildren) {
    return { path, name, hasChildren, expanded: false, loaded: false, loading: false, children: [] };
}

export class FolderTree extends Component {
    static template = "int_filemanager.FolderTree";
    static props = {
        activePath: { type: String },
        onSelectFolder: { type: Function },
        registerApi: { type: Function, optional: true },
    };

    setup() {
        this.actionService = useService("action");
        this.nodes = useState({
            "": makeNode("", _t("Alle Ordner"), true),
        });
        onMounted(() => {
            this.props.registerApi?.({
                invalidate: (path) => this.invalidate(path),
                refresh: (path) => this.refresh(path),
            });
            this.ensureExpandedTo(this.props.activePath);
        });
        onWillUpdateProps((nextProps) => {
            if (nextProps.activePath !== this.props.activePath) {
                this.ensureExpandedTo(nextProps.activePath);
            }
        });
    }

    // Laedt genau EINE Ebene (die direkten Kinder von path) nach, falls noch nicht geschehen -
    // das ist die zentrale Kosten-Eigenschaft dieser Komponente (siehe Dateikommentar oben).
    async ensureLoaded(path) {
        const node = this.nodes[path];
        if (!node || node.loaded || node.loading) {
            return;
        }
        node.loading = true;
        try {
            const result = await rpc("/int_filemanager/tree", { path });
            for (const child of result.children) {
                const existing = this.nodes[child.path];
                if (existing) {
                    // Bereits von anderswo bekannt (z.B. erneutes Aufklappen nach invalidate()) -
                    // Blattdaten auffrischen, aber Expand-/Load-Zustand des Kindes selbst nicht
                    // zuruecksetzen, falls es seinerseits schon aufgeklappt war.
                    existing.name = child.name;
                    existing.hasChildren = child.has_children;
                } else {
                    this.nodes[child.path] = makeNode(child.path, child.name, child.has_children);
                }
            }
            node.children = result.children.map((c) => c.path);
            node.loaded = true;
        } finally {
            node.loading = false;
        }
    }

    // Klappt die komplette Vorfahrenkette von path auf und laedt dabei nur die Ebenen NEU, die
    // noch nicht bekannt sind - so bleibt z.B. ein Breadcrumb-Klick auf einen weiter oben
    // liegenden Ordner oder ein direkter Zeilen-Doppelklick tief im Baum genauso guenstig wie ein
    // Klick auf einen bereits sichtbaren Baumknoten selbst: Kosten pro noch unbekannter Ebene,
    // nie fuer den gesamten Baum.
    async ensureExpandedTo(path) {
        this.nodes[""].expanded = true;
        await this.ensureLoaded("");
        if (!path) {
            return;
        }
        // Ebene fuer Ebene absteigen, nie mehr als eine Ebene pro Schritt neu laden: jedes
        // ensureLoaded(parentPath) befuellt this.nodes fuer die naechste Ebene, BEVOR sie
        // gebraucht wird - Kosten skalieren mit der Tiefe von path, nicht mit der Groesse
        // des Gesamtbaums.
        const segments = path.split("/");
        let parentPath = "";
        for (const segment of segments) {
            const parent = this.nodes[parentPath];
            if (!parent) {
                return;
            }
            parent.expanded = true;
            await this.ensureLoaded(parentPath);
            parentPath = parentPath ? `${parentPath}/${segment}` : segment;
        }
        const node = this.nodes[path];
        if (node && node.hasChildren) {
            node.expanded = true;
            await this.ensureLoaded(path);
        }
    }

    // Verwirft den geladenen Stand eines Knotens (nach mkdir/rename/delete/move im Controller) -
    // beim naechsten Aufklappen wird die Ebene per ensureLoaded() neu vom Server geholt. Kein
    // sofortiges Nachladen hier, falls der Knoten gerade eingeklappt ist - erst wenn er wirklich
    // wieder gebraucht wird.
    invalidate(path) {
        const node = this.nodes[path];
        if (!node) {
            return;
        }
        node.loaded = false;
    }

    async refresh(path) {
        this.invalidate(path);
        const node = this.nodes[path];
        if (!node?.expanded) {
            return;
        }
        try {
            await this.ensureLoaded(path);
        } catch {
            // Bestenfalls-Aktualisierung, kein harter Fehler: reload() im Controller (siehe
            // filemanager_controller_mixin.js) ruft dies nach JEDER Mutation auf - ein hier
            // z.B. durch einen zwischenzeitlich geloeschten Pfad ausgeloester RPC-Fehler soll
            // nicht den umgebenden reload()-Aufruf (Listen-Refresh!) mitreissen. Der Baum bleibt
            // im schlimmsten Fall auf dem alten Stand, bis er naechstes Mal (z.B. Navigation
            // zurueck zur Wurzel und wieder herein) neu geladen wird.
        }
    }

    // Kombiniert Navigation + Auf-/Zuklappen in EINEM Klickziel - live gegen Odoos eigenen
    // Quellcode abgeglichen (Nutzerfrage 2026-09-16 "ist das odoo nativ?"): web/static/src/
    // search/search_panel/search_panel.js, toggleCategory() haengt am kompletten Zeilen-Header,
    // nicht am Chevron-Icon (das hat im nativen Template gar keinen eigenen Klick-Handler) - und
    // klappt nur dann ein, wenn der Knoten bereits AKTIV UND aufgeklappt ist, sonst klappt jeder
    // Klick auf - unabhaengig davon, ob er navigiert. 1:1 hier nachgebildet statt der eigenen
    // Erstfassung mit getrenntem Chevron-Klickziel.
    async onClickNode(node) {
        const wasActive = node.path === this.props.activePath;
        if (node.hasChildren) {
            if (node.expanded && wasActive) {
                node.expanded = false;
            } else {
                node.expanded = true;
                await this.ensureLoaded(node.path);
            }
        }
        if (!wasActive) {
            this.props.onSelectFolder(node.path, node.hasChildren);
        }
    }

    // Fester Eintrag unten im Baum (docs/int_filemanager_papierkorb_konzept.md, cloudreve-Vorbild) -
    // keine Ordner-Navigation, sondern ein eigenstaendiger Sprung in die separate Papierkorb-Liste
    // (filemanager_trash_views.xml). Gleicher this.actionService.doAction()-Mechanismus, den
    // filemanager_controller_mixin.js bereits fuer den Freigabe-Dialog nutzt - kein neuer
    // Navigationsweg.
    onClickTrash() {
        this.actionService.doAction("int_filemanager.action_filemanager_trash");
    }
}
