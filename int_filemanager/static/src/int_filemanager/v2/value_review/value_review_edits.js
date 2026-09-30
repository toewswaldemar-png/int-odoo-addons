/** @odoo-module **/

// The rows of the value review as plain data, and how they turn into what the server
// stores. No DOM, no Odoo imports. The server reads every text again with the type of the
// field (apply_field_values), so the client only says what was printed or typed.

import {relativeBox, shownFields} from "./value_review_geometry.js";

/**
 * One row per field worth showing, filled with its best suggestion or its stored value.
 * @param {Object[]} fields the ``fields`` of suggest_field_values
 * @returns {Object[]}
 */
export function initialRows(fields) {
  return shownFields(fields).map((field) => {
    const best = (field.suggestions || [])[0];
    return {
      fieldId: field.field_id,
      name: field.name,
      valueType: field.value_type,
      confirmed: field.confirmed || false,
      suggestions: field.suggestions || [],
      text: field.confirmed || (best ? best.source_text : ""),
      // "rule" = a suggestion accepted as printed, "manual" = typed.
      source: field.confirmed || !best ? "manual" : "rule",
      ruleId: field.confirmed || !best ? false : best.rule_id || false,
      start: field.confirmed || !best ? false : best.start,
      touched: false,
      removed: false,
    };
  });
}

/** The user typed into the row. */
export function typeText(row, text) {
  Object.assign(row, {
    text,
    source: "manual",
    ruleId: false,
    start: false,
    touched: true,
    removed: false,
  });
}

/** The user chose one of the other suggestions of the row. */
export function chooseSuggestion(row, suggestion) {
  Object.assign(row, {
    text: suggestion.source_text,
    source: "rule",
    ruleId: suggestion.rule_id || false,
    start: suggestion.start,
    touched: true,
    removed: false,
  });
}

/** The user took the row away: a stored value is removed on saving, a suggestion dropped. */
export function removeRow(row) {
  Object.assign(row, {removed: true, touched: true});
}

/**
 * Whether anything was changed since the rows were made.
 * @param {Object[]} rows
 * @param {{changedSender?: boolean, changedTags?: boolean}} [others]
 * @returns {Boolean}
 */
export function isDirty(rows, {changedSender = false, changedTags = false} = {}) {
  return changedSender || changedTags || rows.some((row) => row.touched);
}

/**
 * The outlines to draw: the chosen suggestion of every row that still stands on a place
 * of the document. A typed or removed row has none.
 * @param {Object[]} rows
 * @param {Object} pageSizes
 * @returns {{fieldId: Number, name: String, box: Object}[]}
 */
export function rowMarkers(rows, pageSizes) {
  const result = [];
  for (const row of rows) {
    if (row.removed || row.source !== "rule") {
      continue;
    }
    const chosen = row.suggestions.find((s) => s.start === row.start);
    const box = relativeBox(chosen, pageSizes);
    if (box) {
      result.push({fieldId: row.fieldId, name: row.name, box});
    }
  }
  return result;
}

/**
 * The ``values`` argument of apply_field_values. Suggestions the user left alone are
 * confirmed by saving; a stored value the user left alone is not sent again.
 * @param {Object[]} rows
 * @returns {Object[]}
 */
export function valuesToSave(rows) {
  const values = [];
  for (const row of rows) {
    if (row.removed) {
      if (row.confirmed) {
        values.push({field_id: row.fieldId, text: ""});
      }
    } else if (row.touched || !row.confirmed) {
      const text = row.text.trim();
      if (text || row.confirmed) {
        values.push({
          field_id: row.fieldId,
          text,
          source: row.source,
          rule_id: row.ruleId,
          start: row.start,
        });
      }
    }
  }
  return values;
}
