/** @odoo-module **/

// Datei-Explorer-Klickverhalten (Einzelklick = nur auswaehlen, Doppelklick = oeffnen/
// navigieren) statt Odoos Standard (Einzelklick oeffnet immer, ausser eine Checkbox ist
// bereits aktiv - siehe onCellClicked in web/static/src/views/list/list_renderer.js).
// Nutzerwunsch 2026-09-11, bewusste Abweichung vom Odoo-Standard (der Rest von Odoo bleibt
// unveraendert, siehe resModel-Scope unten).
//
// MouseEvent.detail (1 = Einzelklick, 2 = Doppelklick, 0 = programmatisch/Tastatur ausgeloest
// z.B. per Enter) unterscheidet beides ueber denselben t-on-click-Handler, den Odoo bereits
// auf der Datenzelle verdrahtet hat - keine eigene dblclick-Verdrahtung, kein XML-Template-
// Erben noetig. detail===0 faellt bewusst auf das Original-Verhalten (oeffnen) zurueck, sonst
// waere die Liste per Tastatur/Screenreader nicht mehr bedienbar (dort gibt es kein
// Doppelklick-Konzept).
//
// Scoped auf this.props.list.resModel, exakt dasselbe Muster wie search_model_patch.js fuer
// SearchModel.prototype._getCategoryDomain - jede andere Odoo-Liste im System (Kanban-Klicks
// sind ohnehin ein anderer Code-Pfad) bleibt unangetastet.
import { onMounted, onWillUnmount } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        if (this.props.list.resModel !== "int_filemanager.file") {
            return;
        }
        // Klick ausserhalb der Liste (leerer Platz unterhalb der Zeilen, Seitenleiste, Navbar
        // oben, aber auch Suchleiste/Pager/"Neu"-Button im Control-Panel) deselektiert alles -
        // Nutzerwunsch, Datei-Explorer-Semantik. Bewusst NICHT deselektiert: Klicks auf eine
        // Datenzeile selbst (eigene Logik in onCellClicked unten), auf die "N ausgewaehlt"/
        // Aktionen-Box selbst (sonst waere die Aktionen-Schaltflaeche der Auswahl nie klickbar,
        // da der Klick darauf schon deselektieren wuerde, bevor die Aktion greift) und auf
        // offene Dropdowns/Dialoge (Aktionen-Menuepunkte werden teils ausserhalb des
        // Control-Panels in den body portiert). Bewusst NUR .o_selection_box ausgenommen, nicht
        // das gesamte .o_control_panel - Suchleiste/Pager/View-Umschalter sollen deselektieren.
        const onDocumentClick = (ev) => {
            if (!this.props.list.selection.length) {
                return;
            }
            if (
                ev.target.closest("tr.o_data_row") ||
                ev.target.closest(".o_selection_box") ||
                ev.target.closest(".dropdown-menu, .o-dropdown--menu") ||
                ev.target.closest(".modal, .o_dialog")
            ) {
                return;
            }
            for (const record of this.props.list.records) {
                if (record.selected) {
                    record.toggleSelection(false);
                }
            }
        };
        onMounted(() => document.addEventListener("click", onDocumentClick, true));
        onWillUnmount(() => document.removeEventListener("click", onDocumentClick, true));
    },
    async onCellClicked(record, column, ev, newWindow) {
        if (this.props.list.resModel !== "int_filemanager.file" || ev.detail === 0) {
            return super.onCellClicked(record, column, ev, newWindow);
        }
        if (ev.detail >= 2) {
            // NICHT super.onCellClicked() aufrufen: das Original prueft selbst wieder
            // hasSelection (durch den Einzelklick-Handler unten kurz zuvor haeufig bereits
            // aktiv) und wuerde dann erneut nur toggleRecordSelection() ausloesen statt zu
            // oeffnen - live so beobachtet (Doppelklick schaltete die Auswahl zweimal um,
            // navigierte nie). Direkt openRecord() aufrufen umgeht diesen Konflikt, exakt der
            // Original-Zweig aus list_renderer.js's eigenem onCellClicked.
            if (!this.props.archInfo.noOpen) {
                this.props.openRecord(record, { newWindow });
            }
            return;
        }
        if (!this.canSelectRecord) {
            return;
        }
        // Datei-Explorer-Semantik: einfacher Klick (ohne Modifier) ersetzt die Auswahl durch
        // genau diese eine Zeile, statt additiv umzuschalten - live so gemeldet (mehrere Klicks
        // nacheinander sammelten Zeilen an, statt immer nur eine auszuwaehlen). Ctrl/Cmd- bzw.
        // Shift-Klick bleiben additiv/Bereichsauswahl (this.shiftKeyMode wird von der Basisklasse
        // bereits per keydown/keyup gepflegt, siehe list_renderer.js) - toggleRecordSelection()
        // deckt beide Faelle unveraendert ab, nur der Plain-Click-Fall ist hier neu.
        if (ev.ctrlKey || ev.metaKey || this.shiftKeyMode) {
            this.toggleRecordSelection(record);
            return;
        }
        for (const other of this.props.list.records) {
            if (other !== record && other.selected) {
                other.toggleSelection(false);
            }
        }
        record.toggleSelection(true);
        this.lastCheckedRecord = record;
    },
});
