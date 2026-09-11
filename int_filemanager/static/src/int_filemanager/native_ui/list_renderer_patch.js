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
import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

patch(ListRenderer.prototype, {
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
        if (this.canSelectRecord) {
            this.toggleRecordSelection(record);
        }
    },
});
