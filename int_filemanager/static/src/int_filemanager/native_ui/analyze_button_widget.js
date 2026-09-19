/** @odoo-module **/

// Direkter Icon-Button fuer "Werte erkennen" auf Zeile/Karte (2026-09-07, Nutzerfeedback
// "aktuell nicht sehr effizient") - bisher nur ueber das Aktionsmenue erreichbar (Auswahl +
// Dropdown + Klick). Kann NICHT ein simples <button type="object"> sein (Odoos eigener
// Mechanismus, der eine Server-Methode aufruft, die eine Odoo-Action zurueckgibt) -
// "Werte erkennen" ist ein rein clientseitiger Ablauf (RPC + Owl-Dialog),
// den es serverseitig gar nicht als Action gibt. Stattdessen ein natives <widget>
// (registry.category("view_widgets"), verifiziert am Odoo-19-Quellcode: web/static/src/
// views/widgets/widget.js) - bekommt ueber props.record vollen Zugriff auf den Datensatz und
// kann selbststaendig dialog/rpc nutzen, exakt dieselbe Logik wie
// filemanager_controller_mixin.js's onAnalyzeDocument(), hier nur direkt im Widget statt ueber
// den Controller-Umweg.
//
// Klick-Propagation muss hier SELBST gestoppt werden (ev.stopPropagation()) - anders als bei
// einem <button type="object"> bekommt ein <widget>-Knoten nicht automatisch die
// "oe_kanban_action"-Klasse, die Odoos Kanban-Compiler dort einsetzt, um den Klick von der
// Karten-Navigation auszunehmen (kanban_compiler.js, live am Quellcode verifiziert). Fuer die
// Liste ist das kein Problem: list_renderer.js prueft bei Klick ohnehin explizit
// ev.target.closest("button") und reicht nur bei Fehltreffer an die Zeilen-Navigation weiter -
// das native <button>-Element im Template hier reicht dort also allein schon aus.
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { IntDocumentReviewDialog } from "./document_review_dialog";
import { isFulltextSupported } from "./filemanager_controller_mixin";

export class IntFilemanagerAnalyzeButton extends Component {
    static template = "int_filemanager.AnalyzeButtonWidget";
    static props = { ...standardWidgetProps };

    setup() {
        this.dialog = useService("dialog");
        this.notification = useService("notification");
    }

    // Ordner und nicht unterstuetzte Dateitypen zeigen gar keinen Button - der Server bleibt
    // trotzdem die einzige Quelle der Wahrheit dafuer, was tatsaechlich unterstuetzt ist (siehe
    // isFulltextSupported-Kommentar in filemanager_controller_mixin.js), das hier ist nur die
    // UI-Verfuegbarkeit.
    get visible() {
        const data = this.props.record.data;
        return !data.is_dir && isFulltextSupported(data.name);
    }

    async onClick(ev) {
        ev.stopPropagation();
        const record = this.props.record;
        let result;
        try {
            result = await rpc("/int_filemanager/analyze_document", { path: record.data.path });
        } catch (e) {
            this.notification.add(e.data?.message || e.message, { type: "danger" });
            return;
        }
        if (!result.res_id) {
            this.notification.add(_t("Für diesen Dateityp ist keine Erkennung verfügbar."), { type: "warning" });
            return;
        }
        this.dialog.add(IntDocumentReviewDialog, {
            fileName: record.data.name,
            resId: result.res_id,
            suggestion: result,
            // record.model.load() statt this.reload() (das gibt es hier nicht, das Widget hat
            // keinen Controller) - dieselbe Methode, die reload() im Controller-Mixin selbst
            // aufruft (filemanager_controller_mixin.js).
            onSaved: () => record.model.load(),
        });
    }
}

export const intFilemanagerAnalyzeButton = {
    component: IntFilemanagerAnalyzeButton,
};

registry.category("view_widgets").add("int_filemanager_analyze_button", intFilemanagerAnalyzeButton);
