/** @odoo-module **/

// What the values and the preview of the properties form tell each other. Both are fields of
// the same form record, so they meet on the bus of its model, the way Odoo's own fields do
// (FIELD_IS_DIRTY, NEED_LOCAL_CHANGES).
export const EVENTS = {
  // Values -> preview: a field waits for a value from the document {fieldId, name}
  PICK: "INT_FILEMANAGER_PICK",
  // Preview -> values: words were chosen {fieldId, suggestion}
  PICKED: "INT_FILEMANAGER_PICKED",
  // Either -> both: the choosing ends without a value
  PICK_CANCEL: "INT_FILEMANAGER_PICK_CANCEL",
  // Values -> preview: the outlines of the values in use {markers}
  MARKERS: "INT_FILEMANAGER_MARKERS",
  // Values -> preview: the field the user works in {fieldId}
  ACTIVE: "INT_FILEMANAGER_ACTIVE",
  // Preview -> values: the viewer is up, send the outlines
  PREVIEW_READY: "INT_FILEMANAGER_PREVIEW_READY",
};
