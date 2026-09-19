/** @odoo-module **/

// Baustein 1 (docs/int_filemanager_paperoffice_recherche.md): Kontroll-Dialog fuer die per
// einfacher Regex vorgeschlagenen Tags/Werte (fulltext.suggest_from_text) - zeigt nur an, was
// schon im System existiert bzw. im Text gefunden wurde, schreibt aber NICHTS automatisch. Erst
// "Übernehmen" schreibt via normalem this.orm.write() - bewusst kein sudo()/kein Custom-Endpoint
// dafuer, das sind reine Feldaenderungen (tag_ids/partner_id/extracted_*), keine
// Dateisystem-Operation, laufen also korrekt ueber dieselben ir.rule-Regeln wie jede andere
// Bearbeitung am Datensatz (siehe filemanager_file.py, action_analyze_document-Docstring).
//
// Seit 2026-09-19 (docs/int_filemanager_ocr_selbstdefinierte_felder.md) zusaetzlich: eine
// dynamische Liste der selbstdefinierten Felder (custom_matches, ein Eintrag pro aktivem
// Erkennungsmuster ausserhalb der drei festen Legacy-Felder) sowie, fuer PDFs, ein eigener
// Highlight-Viewer links (Phase C) statt eines fixen 3-Spalten-Layouts - die dynamische Liste
// bekommt KEIN separates Uebernehmen, sie schreibt beim selben Klick auf "Übernehmen" ueber einen
// eigenen Endpunkt (/int_filemanager/apply_extracted_values), da int_filemanager.extracted_value
// bewusst keine direkte Nutzer-ACL hat (siehe ir.model.access.csv).
import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { IntPdfHighlightViewer } from "./pdf_highlight_viewer";

function extOf(name) {
    const i = name.lastIndexOf(".");
    return i === -1 ? "" : name.slice(i + 1).toLowerCase();
}

export class IntDocumentReviewDialog extends Component {
    static template = "int_filemanager.DocumentReviewDialog";
    static components = { Dialog, IntPdfHighlightViewer };
    static props = {
        fileName: String,
        path: String,
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
            // pattern_id ist innerhalb einer Analyse eindeutig (ein Muster liefert hoechstens
            // einen Treffer, siehe fulltext._match_custom_patterns) - dient hier zugleich als
            // React-artiger t-key UND als "welche Zeile ist aktiv"-Schluessel fuer den
            // Highlight-Viewer.
            customFields: s.custom_matches.map((m) => ({ ...m })),
            activeKey: false,
            pageNum: s.custom_matches.find((m) => m.page)?.page || 1,
            pageCount: 0,
        });
        this.isPdf = extOf(this.props.fileName) === "pdf";
        this.downloadUrl = `/int_filemanager/download?path=${encodeURIComponent(this.props.path)}&disposition=inline`;
        this.contentTextPreview = s.content_text_preview || "";
    }

    get hasSuggestions() {
        const s = this.state;
        return Boolean(
            s.tags.length || s.partner || s.date || s.invoiceNumber || s.amount || s.customFields.length
        );
    }

    get pdfBoxes() {
        // Nur Felder mit tatsaechlich ermittelter Position (page ist truthy) koennen ueberhaupt
        // eine Box zeichnen - siehe fulltext._match_custom_patterns fuer die Faelle ohne Position
        // (z.B. Scan-Wiederholungsklick ohne erneutes OCR).
        return this.state.customFields
            .filter((f) => f.page)
            .map((f) => ({ key: f.pattern_id, page: f.page, x0: f.x0, y0: f.y0, x1: f.x1, y1: f.y1 }));
    }

    removeTag(index) {
        this.state.tags.splice(index, 1);
    }

    clearPartner() {
        this.state.partner = false;
    }

    removeCustomField(index) {
        this.state.customFields.splice(index, 1);
    }

    onFocusCustomField(field) {
        this.state.activeKey = field.pattern_id;
        if (field.page) {
            this.state.pageNum = field.page;
        }
    }

    onBlurCustomField() {
        this.state.activeKey = false;
    }

    onBoxClick(box) {
        this.state.activeKey = box.key;
    }

    onPageCountKnown(count) {
        this.state.pageCount = count;
    }

    prevPage() {
        this.state.pageNum = Math.max(1, this.state.pageNum - 1);
    }

    nextPage() {
        this.state.pageNum = Math.min(this.state.pageCount || this.state.pageNum, this.state.pageNum + 1);
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
        await rpc("/int_filemanager/apply_extracted_values", {
            path: this.props.path,
            values: this.state.customFields.map((f) => ({
                pattern_id: f.pattern_id,
                value: f.value,
                page: f.page,
                x0: f.x0,
                y0: f.y0,
                x1: f.x1,
                y1: f.y1,
            })),
        });
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
