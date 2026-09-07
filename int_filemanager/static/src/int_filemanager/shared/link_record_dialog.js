/** @odoo-module **/

import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { Record } from "@web/model/record";
import { Field } from "@web/views/fields/field";

// War urspruenglich fuer ein generisches Reference-Feld gebaut (beliebiges Odoo-Modell,
// daher der eigene ir.model-Abruf fuer den Modell-Picker) - auf Nutzerentscheidung
// 2026-09-07 vereinfacht auf ein festes Many2one auf res.partner (siehe
// filemanager_file.py, partner_id), weil das Reference-Feld fuer den einzigen
// tatsaechlichen Anwendungsfall (Kunde/Lieferant verknuepfen) eine unnoetig umstaendliche
// zweistufige Modell-dann-Datensatz-Auswahl erzwang. Kein eigener ir.model-Abruf mehr
// noetig, dadurch deutlich einfacher als vorher.
export class IntLinkRecordDialog extends Component {
    static template = "int_filemanager.LinkRecordDialog";
    static components = { Dialog, Record, Field };
    static props = {
        path: String,
        metaId: { type: [Number, Boolean], optional: true },
        close: Function,
        onSaved: Function,
    };

    get fields() {
        return {
            path: { type: "char", string: "Path" },
            partner_id: {
                type: "many2one",
                string: "Kontakt",
                relation: "res.partner",
            },
        };
    }

    get activeFields() {
        return {
            path: {},
            partner_id: {},
        };
    }

    get initialValues() {
        return this.props.metaId ? undefined : { path: this.props.path, partner_id: false };
    }

    async onSave(record) {
        await record.save({ reload: false });
        this.props.onSaved(record.resId);
        this.props.close();
    }

    async onClear(record) {
        record.update({ partner_id: false });
        await record.save({ reload: false });
        this.props.onSaved(record.resId);
        this.props.close();
    }
}
