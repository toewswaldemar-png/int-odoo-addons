import { registry } from "@web/core/registry";
import { selectionField } from "@web/views/fields/selection/selection_field";

/**
 * Odoo's selection field (a menu of the choices, also for a many2one, with its domain), which saves the row at once when a choice is made.
 * Odoo does that only in kanban; in a list the row is saved when it is left, and a clamp that is chosen in a cell must not wait for that
 * (the switch, boolean_toggle, saves at once in a list as well). Nothing else is changed.
 */
export const autosaveSelectionField = {
    ...selectionField,
    extractProps(params, dynamicInfo) {
        return { ...selectionField.extractProps(params, dynamicInfo), autosave: true };
    },
};

registry.category("fields").add("int_workbench.autosave_selection", autosaveSelectionField);
