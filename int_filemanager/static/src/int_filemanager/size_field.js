import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { humanNumber } from "@web/core/utils/numbers";
import { _t } from "@web/core/l10n/translation";

/**
 * "512 Bytes", "2 kB", "14 MB": whole numbers only, a space between number and unit but
 * not inside it. Odoo formats attachment sizes like this internally but only for binary
 * fields; size here is a Float (it exceeds int4 above 2 GiB), hence the small copy.
 * humanNumber glues number and SI prefix together ("2M"), so the space goes before the
 * prefix letter and the "B" stays attached to it.
 * @param {Number} value
 * @param {Object} [options]
 * @param {Number} [options.decimals=0] decimals of the number before the unit
 * @returns {String}
 */
export function humanFileSize(value, { decimals = 0 } = {}) {
    if (!value) {
        return "";
    }
    if (value < 1024) {
        return `${humanNumber(value, { decimals: 0 })} ${_t("Bytes")}`;
    }
    return `${humanNumber(value, { decimals }).replace(/([kMGTPE])$/, " $1")}B`;
}

/**
 * The size as the pivot and graph views show it: the sum of many files, so one decimal
 * ("1.6 GB", not "2 GB"), and "0 Bytes" for none (the list shows nothing for an empty file).
 * @param {Number} value
 * @returns {String}
 */
export function formatFileSize(value) {
    return humanFileSize(value, { decimals: 1 }) || `0 ${_t("Bytes")}`;
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
// The pivot and graph views take the `widget` of a measure from the formatters, not from the
// fields (like the core's `float_time`, which is in both).
registry.category("formatters").add("int_filemanager_size", formatFileSize);
