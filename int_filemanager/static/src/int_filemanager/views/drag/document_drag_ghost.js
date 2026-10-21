import { _t } from "@web/core/l10n/translation";

/**
 * The picture of a drag, built like the box "N selected" of the core (`web.SelectionBox`): the icon
 * of the file and its name, or the number of the files when there are more than one. It follows
 * the pointer (`placeDragGhost`); the caller removes it at the end of the drag.
 * @param {Object[]} records the records that are dragged
 * @returns {HTMLElement}
 */
export function makeDragGhost(records) {
    const [first] = records;
    const ghost = document.createElement("div");
    ghost.className = "o_int_filemanager_drag_ghost list-group w-auto";
    const box = document.createElement("span");
    box.className = "list-group-item active d-flex align-items-center gap-2 rounded-1 shadow-sm";
    const icon = document.createElement("span");
    icon.className = "o_image";
    icon.dataset.mimetype = first.data.mimetype || "";
    box.append(icon);
    if (records.length > 1) {
        const count = document.createElement("b");
        count.textContent = records.length;
        box.append(count, " " + _t("documents"));
    } else {
        const name = document.createElement("b");
        name.className = "text-truncate";
        name.textContent = first.data.name;
        box.append(name);
    }
    ghost.append(box);
    document.body.append(ghost);
    return ghost;
}

/**
 * The upper left corner of the picture is at the pointer.
 * @param {HTMLElement} ghost
 * @param {{x: number, y: number}} pointer
 */
export function placeDragGhost(ghost, { x, y }) {
    ghost.style.transform = `translate(${x}px, ${y}px)`;
}
