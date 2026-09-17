/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { patch } from "@web/core/utils/patch";
import { useSortable } from "@web/core/utils/sortable_owl";
import { ListRenderer } from "@web/views/list/list_renderer";

function storageKey(resModel) {
    return `int_web_tweaks.column_order:${resModel}`;
}

function loadOrder(resModel) {
    try {
        const raw = browser.localStorage.getItem(storageKey(resModel));
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null;
    }
}

function saveOrder(resModel, names) {
    try {
        browser.localStorage.setItem(storageKey(resModel), JSON.stringify(names));
    } catch {
        // Private browsing / storage disabled - reordering just won't persist.
    }
}

patch(ListRenderer.prototype, {
    getActiveColumns() {
        const columns = super.getActiveColumns();
        const resModel = this.props.list.resModel;
        const saved = loadOrder(resModel);
        if (!saved || !saved.length) {
            return columns;
        }
        // Only field columns are reorderable - buttons, handles and other
        // structural columns always stay pinned at their view-defined slot,
        // so a saved order captured before one existed can never bump it
        // out of place.
        const fieldColumns = columns.filter((c) => c.type === "field");
        const remaining = new Map(fieldColumns.map((c) => [c.name, c]));
        const ordered = [];
        for (const name of saved) {
            const col = remaining.get(name);
            if (col) {
                ordered.push(col);
                remaining.delete(name);
            }
        }
        // Columns not in the saved order (new field, newly-enabled optional
        // field, different view) keep their original relative order,
        // appended after the remembered ones - never dropped, never crashes
        // on a column set that no longer matches exactly.
        for (const col of fieldColumns) {
            if (remaining.has(col.name)) {
                ordered.push(col);
            }
        }
        let i = 0;
        return columns.map((c) => (c.type === "field" ? ordered[i++] : c));
    },

    setup() {
        super.setup();
        // Odoo's own generic drag system (useSortable, built on pointer events - see
        // list_renderer.js's own useSortable() call for row resequencing right above this
        // one in its setup()) instead of raw HTML5 draggable/dragstart. Two independent
        // benefits over the previous native-drag version: no default browser drag-ghost
        // screenshot (there's no native drag operation at all, pointer events just move the
        // real element - Nutzerreport 2026-09-17, Screenshot zeigte den haesslichen
        // Standard-Browser-Ghost), and it reuses Odoo's own .o_dragged base styling
        // (draggable_hook_builder.scss) instead of a hand-rolled visual. th[data-name] is
        // already set natively by list_renderer.xml itself (t-att-data-name="column.name"),
        // no own attribute needed - only the scoping class below to select field-column
        // headers specifically (buttons/handle columns have no data-name and are excluded by
        // the selector automatically).
        useSortable({
            ref: this.rootRef,
            elements: ".o_int_web_tweaks_column_draggable",
            cursor: "grabbing",
            // Placeholder must be a real <th> clone (not useSortable's default plain <div>) -
            // a <div> as a direct child of <tr> would be invalid table markup and break the
            // header row's column layout while dragging.
            clone: true,
            followingElementClasses: ["o_column_dragging"],
            onDrop: ({ element, previous, next }) => {
                const draggedName = element.dataset.name;
                if (!draggedName) {
                    return;
                }
                const names = this.columns.filter((c) => c.type === "field").map((c) => c.name);
                const fromIndex = names.indexOf(draggedName);
                if (fromIndex === -1) {
                    return;
                }
                names.splice(fromIndex, 1);
                // previous/next are the dragged element's new DOM neighbours at drop time
                // (useSortable never touches the DOM itself here - applyChangeOnDrop is left
                // at its default false, our own order lives in localStorage + render() below,
                // not in DOM position). Falls back to index 0 when dropped before every column
                // (no previous) and to the end when dropped after the last one (neither has a
                // data-name, e.g. dropped past the last header cell).
                let toIndex = previous?.dataset.name
                    ? names.indexOf(previous.dataset.name) + 1
                    : next?.dataset.name
                    ? names.indexOf(next.dataset.name)
                    : 0;
                if (toIndex === -1) {
                    toIndex = names.length;
                }
                names.splice(toIndex, 0, draggedName);
                saveOrder(this.props.list.resModel, names);
                this.render();
            },
        });
    },
});
