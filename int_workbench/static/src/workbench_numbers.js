import { formatFloat } from "@web/views/fields/formatters";
import { parseFloat as parseLocaleFloat } from "@web/views/fields/parsers";

/** The digits of the numbers of a row (the fields "value" and "clamp_value" of int.workbench.parameter have three). */
const DIGITS = [16, 3];

/** A number as the user writes it (the decimal point of the language, no thousands separator, no trailing zeros). */
export function formatNumber(value) {
    return formatFloat(Number(value) || 0, { digits: DIGITS, trailingZeros: false, thousandsSep: "" });
}

/** A number as the user typed it, in the number format of the user (as every float field of Odoo reads it); NaN if it is none. */
export function parseNumber(text) {
    const raw = String(text ?? "").trim();
    if (raw === "") {
        return NaN;
    }
    try {
        return parseLocaleFloat(raw);
    } catch {
        return NaN;
    }
}
