/** @odoo-module **/

// Baustein 1 (docs/int_filemanager_paperoffice_recherche.md): Kontroll-Dialog fuer die per
// einfacher Regex vorgeschlagenen Tags/Werte (fulltext.suggest_from_text) - zeigt nur an, was
// schon im System existiert bzw. im Text gefunden wurde, schreibt aber NICHTS automatisch. Erst
// "Übernehmen" schreibt via normalem this.orm.write() - bewusst kein sudo()/kein Custom-Endpoint
// dafuer, das sind reine Feldaenderungen (tag_ids/partner_id/extracted_*), keine
// Dateisystem-Operation, laufen also korrekt ueber dieselben ir.rule-Regeln wie jede andere
// Bearbeitung am Datensatz (siehe filemanager_file.py, action_analyze_document-Docstring).
import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

export class IntDocumentReviewDialog extends Component {
    static template = "int_filemanager.DocumentReviewDialog";
    static components = { Dialog };
    static props = {
        fileName: String,
        resId: Number,
        suggestion: Object,
        close: Function,
        onSaved: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        const s = this.props.suggestion;
        this.state = useState({
            tags: [...s.suggested_tags],
            partner: s.suggested_partner,
            date: s.suggested_date || "",
            invoiceNumber: s.suggested_invoice_number || "",
            amount: s.suggested_amount || "",
        });
    }

    get hasSuggestions() {
        const s = this.state;
        return Boolean(s.tags.length || s.partner || s.date || s.invoiceNumber || s.amount);
    }

    removeTag(index) {
        this.state.tags.splice(index, 1);
    }

    clearPartner() {
        this.state.partner = false;
    }

    async onConfirm() {
        const vals = {
            tag_ids: [[6, 0, this.state.tags.map((t) => t.id)]],
            extracted_date: this.state.date || false,
            extracted_invoice_number: this.state.invoiceNumber || false,
            extracted_amount: this.state.amount || false,
            partner_id: this.state.partner ? this.state.partner.id : false,
        };
        await this.orm.write("int_filemanager.file", [this.props.resId], vals);
        this.props.onSaved?.();
        this.props.close();
    }

    onSkip() {
        // content_text/ocr_state wurden bereits beim Analyse-Aufruf gespeichert (siehe
        // action_analyze_document) - "Verwerfen" laesst nur die Tag-/Wert-Vorschlaege ungenutzt,
        // der Volltext bleibt durchsuchbar.
        this.props.close();
    }
}
