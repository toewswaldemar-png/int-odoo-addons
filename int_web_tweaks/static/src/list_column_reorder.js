/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { patch } from "@web/core/utils/patch";
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

    onColumnDragStart(ev, column) {
        if (!column.name || column.type !== "field") {
            return;
        }
        this._draggedColumnName = column.name;
        ev.dataTransfer.effectAllowed = "move";
        ev.dataTransfer.setData("text/plain", column.name);
        ev.currentTarget.classList.add("o_column_dragging");
    },

    onColumnDragEnd(ev) {
        ev.currentTarget.classList.remove("o_column_dragging");
        this._draggedColumnName = null;
    },

    onColumnDrop(ev, column) {
        ev.currentTarget.classList.remove("o_column_dragging");
        const draggedName = this._draggedColumnName;
        this._draggedColumnName = null;
        if (!draggedName || column.type !== "field" || draggedName === column.name) {
            return;
        }
        const names = this.columns.filter((c) => c.type === "field").map((c) => c.name);
        const fromIndex = names.indexOf(draggedName);
        const toIndex = names.indexOf(column.name);
        if (fromIndex === -1 || toIndex === -1) {
            return;
        }
        names.splice(fromIndex, 1);
        names.splice(toIndex, 0, draggedName);
        saveOrder(this.props.list.resModel, names);
        this.render();
    },
});
