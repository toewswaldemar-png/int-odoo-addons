/** @odoo-module **/

// Pure helpers of the value review: where a found value lies on its page, as shares of
// the page so that the box follows every zoom of the viewer. No DOM, no Odoo imports.

// A page the server sent no size for is taken as A4 (the unit of the word positions is
// PDF points).
export const DEFAULT_PAGE_SIZE = [595, 842];

/**
 * Width and height of a page in the unit of the boxes.
 * @param {Object} pageSizes {"1": [width, height]} as sent by suggest_field_values
 * @param {Number} page
 * @returns {Number[]}
 */
export function pageSize(pageSizes, page) {
  const size = pageSizes && pageSizes[String(page)];
  if (Array.isArray(size) && size[0] > 0 && size[1] > 0) {
    return size;
  }
  return DEFAULT_PAGE_SIZE;
}

function clamp(share) {
  return Math.min(Math.max(share, 0), 1);
}

/**
 * The box of a suggestion as shares (0 to 1) of its page, or null when the value has no
 * place (text files) or an empty one.
 * @param {Object} suggestion one entry of a field's ``suggestions``
 * @param {Object} pageSizes
 * @returns {{page: Number, left: Number, top: Number, width: Number, height: Number}|null}
 */
export function relativeBox(suggestion, pageSizes) {
  if (!suggestion || !(suggestion.page > 0)) {
    return null;
  }
  const [width, height] = pageSize(pageSizes, suggestion.page);
  const left = clamp(suggestion.x0 / width);
  const top = clamp(suggestion.top / height);
  const right = clamp(suggestion.x1 / width);
  const bottom = clamp(suggestion.bottom / height);
  if (right <= left || bottom <= top) {
    return null;
  }
  return {page: suggestion.page, left, top, width: right - left, height: bottom - top};
}

/**
 * The outlines to draw: the best suggestion of every field that has a place.
 * @param {Object[]} fields the ``fields`` of suggest_field_values
 * @param {Object} pageSizes
 * @returns {{fieldId: Number, name: String, box: Object}[]}
 */
export function markers(fields, pageSizes) {
  const result = [];
  for (const field of fields || []) {
    const box = relativeBox((field.suggestions || [])[0], pageSizes);
    if (box) {
      result.push({fieldId: field.field_id, name: field.name, box});
    }
  }
  return result;
}

/**
 * The fields worth showing without being asked: those with a suggestion or a confirmed
 * value. The other ones of the catalogue are added by the user.
 * @param {Object[]} fields
 * @returns {Object[]}
 */
export function shownFields(fields) {
  return (fields || []).filter(
    (field) => (field.suggestions && field.suggestions.length) || field.confirmed
  );
}

/**
 * Index of the file to show next in a list of node ids, wrapping around like Odoo's pager.
 * @param {Number} index
 * @param {Number} count
 * @returns {Number}
 */
export function wrapIndex(index, count) {
  if (!count) {
    return 0;
  }
  return ((index % count) + count) % count;
}
