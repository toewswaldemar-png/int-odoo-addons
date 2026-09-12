/** @odoo-module **/

// Zeigt das Inhaltsverzeichnis einer ZIP-Datei (Nutzerwunsch 2026-09-12) - flache Liste mit Pfad
// als Namenspraefix statt echter Ordner-Navigation im Dialog (bewusste Vereinfachung fuer v1),
// pro Eintrag nur Einzeldatei-Download statt echtem Entpacken aufs Dateisystem (kein Zip-Slip-
// Risiko, keine authz "write" noetig - siehe zip_utils.py). Laedt die Liste synchron beim
// Oeffnen ueber /int_filemanager/zip_list, kein Pending-State/Cron wie bei OCR/Thumbnails, da ein
// ZIP-Inhaltsverzeichnis lesen kein Dekomprimieren braucht.
import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { rpc } from "@web/core/network/rpc";
import { humanFileSize } from "./size_human_field";

export class IntZipContentsDialog extends Component {
    static template = "int_filemanager.ZipContentsDialog";
    static components = { Dialog };
    static props = {
        fileName: String,
        path: String,
        close: Function,
    };

    setup() {
        this.state = useState({ entries: null, error: null });
        onWillStart(async () => {
            try {
                const res = await rpc("/int_filemanager/zip_list", { path: this.props.path });
                this.state.entries = res.entries;
            } catch (e) {
                this.state.error = e.data?.message || e.message;
            }
        });
    }

    humanSize(value) {
        return humanFileSize(value);
    }

    downloadEntry(entry) {
        const url =
            `/int_filemanager/zip_extract_entry?path=${encodeURIComponent(this.props.path)}` +
            `&entry=${encodeURIComponent(entry)}`;
        window.open(url, "_blank");
    }
}
