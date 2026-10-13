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
 * @returns {String}
 */
export function humanFileSize(value) {
    if (!value) {
        return "";
    }
    if (value < 1024) {
        return `${humanNumber(value, { decimals: 0 })} ${_t("Bytes")}`;
    }
    return `${humanNumber(value, { decimals: 0 }).replace(/([kMGTPE])$/, " $1")}B`;
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
