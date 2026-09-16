/** @odoo-module **/

// Ersetzt seit 2026-09-16 Odoos natives SearchPanel-Kategoriefeld als Quelle der aktuellen
// Ordner-Navigation (siehe folder_tree.js fuer die Begruendung: bei 69k Ordnern war JEDER
// SearchPanel-Bordmittel-Pfad live mehrere Sekunden teuer, unabhaengig von expand/hierarchize).
// Der eigene Ordnerbaum navigiert ueber literale Pfad-Strings statt Kategoriewert-IDs - dieser
// Override haengt genau EINE zusaetzliche Domain-Klausel an, die aus dem aktuell aktiven Pfad
// (this.intFilemanagerFolderPath, siehe setIntFilemanagerFolderPath()) berechnet wird, statt sie
// wie zuvor aus this.categories/section.activeValueId zu lesen.
//
// _getDomain() statt des vormaligen _getCategoryDomain()-Overrides: ohne ein <searchpanel
// type="category">-Arch-Element bleibt this.categories/this.sections leer, Odoos eigener
// display.searchPanel-Flag (_getDisplay(), gespeist aus this.sections.size) wird dadurch false,
// und _getSearchPanelDomain() (der bisherige Aufrufer von _getCategoryDomain) wird gar nicht mehr
// aufgerufen - der alte Erweiterungspunkt existiert bei dieser Konfiguration also nicht mehr.
// _getDomain() selbst ist dagegen unabhaengig davon immer der zentrale Punkt, an dem SearchModel
// alle Domain-Quellen zusammenfuehrt (Filter/Facetten/globalDomain/searchPanel) - ein zusaetzlicher
// AND hier trifft ausnahmslos jede Ansicht, die dieses SearchModel nutzt (List UND Kanban, siehe
// native_list_view.js/native_kanban_view.js), unabhaengig vom searchPanel-Zustand.
//
// Rekursion (Unterordner einbeziehen, siehe filemanager_file_search.xml: filter_search_recursive)
// unveraendert uebernommen: "=like path/%" statt des vormaligen child_of-Operators auf parent_id -
// beide Varianten haben denselben Kostenkarakter (Praefixsuche ueber eine Textspalte, kein
// Regressions- ODER Verbesserungsanspruch hier), aber "=like" auf dem literalen Pfad braucht keine
// Datensatz-ID mehr, konsistent mit der restlichen pfadbasierten Navigation dieser Datei. Der
// vormalige Sonderfall "child_of ist selbstinklusiv, eigene ID explizit ausschliessen" entfaellt
// dadurch ersatzlos: ein Praefix "path/%" kann den Ordner selbst (Pfad ohne "/%"-Suffix) per
// Konstruktion nie mit einschliessen.
import { Domain } from "@web/core/domain";
import { SearchModel } from "@web/search/search_model";

// Name-Attribut des Marker-Filters aus filemanager_file_search.xml (<filter
// name="filter_search_recursive">, ohne eigene domain) - node.name kommt 1:1 aus dem XML-
// Attribut durch (search_arch_parser.js: preSearchItem.name = node.getAttribute("name"), am
// Odoo-Quellcode verifiziert), das reicht als eindeutiger Erkennungsschluessel.
const RECURSIVE_FILTER_NAME = "filter_search_recursive";

export class IntFilemanagerSearchModel extends SearchModel {
    setup(services) {
        super.setup(services);
        this.intFilemanagerFolderPath = "";
    }

    // Von folder_tree.js (Klick auf einen Knoten) und filemanager_controller_mixin.js
    // (Breadcrumb-/Zeilen-Navigation, "Alle Ordner") aufgerufen - genau ein Schreiber fuer diesen
    // Teil der Domain, analog zum vormaligen toggleCategoryValue().
    setIntFilemanagerFolderPath(path) {
        this.intFilemanagerFolderPath = path || "";
        this._notify();
    }

    _isIntFilemanagerRecursive() {
        const recursiveFilterActive = this.query.some(
            (queryElem) => this.searchItems[queryElem.searchItemId]?.name === RECURSIVE_FILTER_NAME
        );
        return recursiveFilterActive || Boolean(this.globalContext.int_filemanager_recursive);
    }

    _getIntFilemanagerFolderDomain() {
        const path = this.intFilemanagerFolderPath;
        const recursive = this._isIntFilemanagerRecursive();
        if (recursive) {
            // Kein Pfad aktiv (Wurzel) UND rekursiv: kompletter Baum, keine Einschraenkung - deckt
            // auch den "Verknuepfte Dateien"-Smart-Button ab (filemanager_linkable_mixin.py, siehe
            // int_filemanager_recursive-Kontext-Flag), der diese Ansicht domain-restringiert
            // auf partner_id oeffnet, ohne dass je eine Ordner-Navigation stattgefunden hat.
            return path ? new Domain([["path", "=like", `${path}/%`]]) : new Domain([]);
        }
        return new Domain([["folder_path", "=", path || false]]);
    }

    _getDomain(params = {}) {
        const folderDomain = this._getIntFilemanagerFolderDomain();
        if (params.raw) {
            return Domain.and([super._getDomain(params), folderDomain]);
        }
        return Domain.and([new Domain(super._getDomain(params)), folderDomain]).toList(this.domainEvalContext);
    }
}
