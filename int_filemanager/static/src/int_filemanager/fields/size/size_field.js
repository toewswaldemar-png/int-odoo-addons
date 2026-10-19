import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { humanNumber } from "@web/core/utils/numbers";
import { _t } from "@web/core/l10n/translation";

/**
 * "512 Bytes", "2 kB", "14 MB": the core does this only for binary fields, and `size` is a Float
 * (it exceeds int4 above 2 GiB). `humanNumber` yields "2M": the space goes before the prefix.
 * @param {Number} value
 * @param {Object} [options]
 * @param {Number} [options.decimals=0]
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

/** The size as the pivot and graph views show it: one decimal, "0 Bytes" for none. */
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
// The pivot and graph views take the `widget` of a measure from the formatters.
registry.category("formatters").add("int_filemanager_size", formatFileSize);
