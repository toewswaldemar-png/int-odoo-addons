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
    const suffix = value < 1024 ? " " + _t("Bytes") : "b";
    return humanNumber(value, { decimals: 2 }) + suffix;
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
