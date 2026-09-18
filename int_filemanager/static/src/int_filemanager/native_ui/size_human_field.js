/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { humanNumber } from "@web/core/utils/numbers";
import { _t } from "@web/core/l10n/translation";

// Odoo formatiert jede Binary-Feld-Groesse (z.B. Anhaenge) intern exakt so
// (web/static/src/views/fields/formatters.js, humanSize()) - dort aber nur ueber
// formatBinary() erreichbar, das Base64-Daten oder Odoos eigenen "bin_size"-Platzhalter-
// String erwartet, keine rohe Zahl. Unser size ist bewusst ein fields.Float (int4-2GB-Limit,
// siehe Kommentar in filemanager_file.py), keine Binary-Spalte - deshalb hier dieselbe
// kleine, sonst nicht exportierte Logik 1:1 nachgebaut statt eines nicht moeglichen Imports.
// humanNumber() selbst ist ein oeffentlicher Core-Baustein (web/core/utils/numbers.js).
export function humanFileSize(value) {
    if (!value) {
        return "";
    }
    // decimals: 0 statt Odoos eigenem 2 (Nutzerwunsch 2026-09-18, nur Ganzzahlen in der
    // Spalte) - abweichend vom Original-humanSize() in formatters.js, bewusste Entscheidung,
    // kein Versehen. humanNumber() selbst rundet dabei ganz normal (Math.round, numbers.js),
    // keine eigene Rundungslogik noetig.
    if (value < 1024) {
        return humanNumber(value, { decimals: 0 }) + " " + _t("Bytes");
    }
    // Grossbuchstabe "B" statt Odoos eigenem klein geschriebenem "b" (siehe formatters.js:
    // humanSize(), dort identisch klein) - Nutzerreport 2026-09-18: humanNumber()s eigene
    // SI-Symbole ("kMGTPE", k klein/M-P gross, numbers.js) kombiniert mit einem klein
    // geschriebenen "b" ergab uneinheitlich wirkende "kb"/"Mb". "B" macht daraus die normale
    // SI-Schreibweise (kleines k nur bei Kilo, B immer gross) - "kB"/"MB"/"GB", deckungsgleich
    // mit Odoos eigenem "Bytes" (ebenfalls grosses B) oben.
    //
    // Leerzeichen zwischen Zahl und Einheit (Nutzerwunsch 2026-09-18), aber NICHT mitten im
    // Einheitensymbol selbst ("kB"/"MB" bleiben ein Wort): humanNumber() klebt Zahl und
    // SI-Praefix ohne Leerzeichen zusammen ("2M", numbers.js: "return int + symbol"). Ein
    // simples "+ ' B'" danach haette das Leerzeichen deshalb FALSCH zwischen Praefix und B
    // gesetzt ("2M B", live so gesehen und vom Nutzer korrigiert) statt zwischen Zahl und
    // Einheit ("2 MB"). Deshalb das Leerzeichen gezielt VOR den letzten Buchstaben (den
    // SI-Praefix aus humanNumber()s eigener Symbolliste "kMGTPE") einfuegen, "B" bleibt direkt
    // am Praefix haengen.
    const formatted = humanNumber(value, { decimals: 0 });
    return formatted.replace(/([kMGTPE])$/, " $1") + "B";
}

export class IntFilemanagerSizeField extends Component {
    static template = "int_filemanager.SizeField";
    static props = { ...standardFieldProps };

    get formattedValue() {
        return humanFileSize(this.props.record.data[this.props.name]);
    }
}

export const intFilemanagerSizeField = {
    component: IntFilemanagerSizeField,
    supportedTypes: ["float", "integer"],
};

registry.category("fields").add("int_filemanager_size", intFilemanagerSizeField);
