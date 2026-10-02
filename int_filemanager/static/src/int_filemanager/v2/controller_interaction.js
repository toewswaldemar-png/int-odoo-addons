/** @odoo-module **/

// Explorer interaction of the controller: keyboard (F2 rename, Escape deselects), the
// right-click menu, moving items by dragging them onto a folder (row or tree), and keeping
// the selection when the controller is re-created (back from another action).
import {onMounted, onPatched, useExternalListener} from "@odoo/owl";
import {usePopover} from "@web/core/popover/popover_hook";
import {useChildRef} from "@web/core/utils/hooks";
import {useNavigation} from "@web/core/navigation/navigation";
import {useSetupAction} from "@web/search/action_hook";
import {IntFilemanagerV2ContextMenu} from "./context_menu.js";
import {isTypingContext} from "./utils.js";

const MOVE_DRAG_TYPE = "application/x-int-filemanager-move";

export const interactionMixin = (Base) =>
    class extends Base {
        setup() {
            super.setup();
            this._setupSelectionPersistence();
            this._setupKeyboard();
            this._setupContextMenu();
            this._setupMoveDrag();
        }

        // ------------------------------------------------------- selection persistence

        // Coming back to this view through a breadcrumb (e.g. from an editor) creates a whole
        // new controller and model, so the selection is carried in the action's local state
        // (Odoo hands it back as props.state) and re-applied after the first load. Within one
        // controller, reload() does the same for reloads.
        _setupSelectionPersistence() {
            const originalLoad = this.model.load.bind(this.model);
            this.model.load = async (...args) => {
                // Model.root does not exist yet during the very first load.
                const selectedIds = new Set(
                    (this.model.root?.selection || []).map((r) => r.resId)
                );
                const result = await originalLoad(...args);
                // The saved state only matters for the first load of a fresh instance; an
                // in-memory selection wins, otherwise nothing could be deselected later.
                const toReselect = selectedIds.size
                    ? selectedIds
                    : new Set(this.props.state?.int_filemanager_selectedResIds || []);
                if (toReselect.size) {
                    for (const record of this.model.root.records) {
                        if (toReselect.has(record.resId)) {
                            record.toggleSelection(true);
                        }
                    }
                }
                return result;
            };
            useSetupAction({
                getLocalState: () => ({
                    int_filemanager_selectedResIds:
                        this.model.root?.selection.map((r) => r.resId) || [],
                }),
            });
        }

        // ------------------------------------------------------------------ keyboard

        _setupKeyboard() {
            // Not useHotkey: Odoo's hotkey service refuses F-keys outright, and Escape is
            // authorised but gets consumed by Odoo's own list handling before a bubbling
            // listener sees it - hence a capture-phase window listener for both.
            useExternalListener(
                window,
                "keydown",
                (ev) => {
                    if (ev.key === "F2") {
                        // PreventDefault first: otherwise a second F2 (focus already in the rename
                        // input) reaches the browser, which opens its own command list.
                        ev.preventDefault();
                        if (!isTypingContext(document.activeElement)) {
                            this.onF2Rename();
                        }
                    } else if (ev.key === "Escape") {
                        const blocked =
                            isTypingContext(document.activeElement) ||
                            document.querySelector(
                                ".modal.show, .o_dialog, .o-FileViewer"
                            );
                        if (blocked) {
                            return;
                        }
                        for (const record of this.model.root.selection) {
                            record.toggleSelection(false);
                        }
                        // Checkbox selection and Odoo's focused-cell frame are two things: without
                        // this the frame stays and it looks as if Escape did nothing.
                        document.activeElement?.blur();
                    }
                },
                {capture: true}
            );
        }

        // ---------------------------------------------------------------- context menu

        _setupContextMenu() {
            // The same items as the "Actions" dropdown (getStaticActionMenuItems), opened at the
            // cursor. Configured like Odoo's own Dropdown: useNavigation gives the hover /
            // arrow-key highlight (Odoo's dropdown CSS switches :hover off on purpose and
            // relies on the ".focus" class this hook maintains), usePopover the same options.
            this.contextMenuRef = useChildRef();
            this.contextMenuNavigation = useNavigation(this.contextMenuRef, {
                shouldRegisterHotkeys: false,
                isNavigationAvailable: () => this.contextMenuPopover.isOpen,
                getItems: () =>
                    this.contextMenuPopover.isOpen && this.contextMenuRef.el
                        ? this.contextMenuRef.el.querySelectorAll(":scope .o-navigable")
                        : [],
            });
            this.contextMenuPopover = usePopover(IntFilemanagerV2ContextMenu, {
                animation: false,
                arrow: false,
                closeOnEscape: false,
                popoverClass: "o-dropdown--menu dropdown-menu mx-0",
                position: "bottom-start",
                ref: this.contextMenuRef,
                role: "menu",
                setActiveElement: false,
                onClose: () => {
                    this._contextMenuAnchorEl?.remove();
                    this._contextMenuAnchorEl = null;
                },
            });
            useExternalListener(window, "contextmenu", (ev) => this._onContextMenu(ev));
        }

        _recordForLocalId(id) {
            return this.model.root.records.find((r) => r.id === id);
        }

        _rowRecordFromEvent(ev) {
            // Ev.target can be a bare text node (no closest()), e.g. during a native text drag.
            const targetEl =
                ev.target.nodeType === Node.ELEMENT_NODE
                    ? ev.target
                    : ev.target.parentElement;
            const rowEl = targetEl?.closest("[data-id]");
            return {rowEl, record: rowEl && this._recordForLocalId(rowEl.dataset.id)};
        }

        // Only on a real row or card: everywhere else the browser's own menu stays.
        async _onContextMenu(ev) {
            if (!this.rootRef.el?.contains(ev.target)) {
                return;
            }
            const {record} = this._rowRecordFromEvent(ev);
            if (!record) {
                return;
            }
            ev.preventDefault();
            // Explorer convention: right-clicking inside a multi-selection keeps it (the menu
            // then acts on all); right-clicking outside it selects just that row.
            if (!record.selected) {
                for (const other of this.model.root.records) {
                    if (other !== record && other.selected) {
                        other.toggleSelection(false);
                    }
                }
                await record.toggleSelection(true);
            }
            const items = Object.values(this.getStaticActionMenuItems())
                .filter((item) => item.isAvailable())
                .sort((a, b) => a.sequence - b.sequence);
            if (!items.length) {
                return;
            }
            // The popover service needs a real element to position against: a 0x0 anchor at
            // the click, removed when the menu closes.
            const anchor = document.createElement("div");
            anchor.style.position = "fixed";
            anchor.style.left = `${ev.clientX}px`;
            anchor.style.top = `${ev.clientY}px`;
            document.body.appendChild(anchor);
            this._contextMenuAnchorEl = anchor;
            this.contextMenuPopover.open(anchor, {
                items,
                close: () => this.contextMenuPopover.close(),
                navigator: this.contextMenuNavigation,
            });
        }

        // ------------------------------------------------------------- move by dragging

        _setupMoveDrag() {
            // Rows and cards are rendered by Odoo, their root elements are not ours to
            // attribute: draggable is set after each render, and the drag events are handled by
            // delegation on window (every row carries a native data-id).
            onMounted(() => this._makeRecordsDraggable());
            onPatched(() => this._makeRecordsDraggable());
            useExternalListener(window, "dragstart", (ev) =>
                this._onDragStartRecord(ev)
            );
            useExternalListener(window, "dragover", (ev) => this._onDragOverRecord(ev));
            useExternalListener(window, "drop", (ev) => this._onDropRecord(ev));
            useExternalListener(window, "dragend", () => this._clearDragState());
        }

        // A list row is NOT draggable as a whole, only its icon and name label: that is what
        // one grabs in an explorer, and the free part of the row must stay available for the
        // rubber band (a whole-row drag target made almost every drag start a move). Cards
        // are draggable entirely.
        _makeRecordsDraggable() {
            const els = this.rootRef.el?.querySelectorAll("[data-id]") || [];
            for (const el of els) {
                if (el.tagName !== "TR") {
                    el.draggable = true;
                    continue;
                }
                el.draggable = false;
                const handles = el.querySelectorAll(
                    ".o_int_filemanager_name_icon, .o_int_filemanager_name_label"
                );
                for (const handle of handles) {
                    handle.draggable = true;
                }
            }
        }

        // Grabbing an item that is part of the selection moves the whole selection.
        _recordsForDrag(startRecord) {
            const selection = this.model.root.selection;
            return selection.includes(startRecord) ? selection : [startRecord];
        }

        // Target = a folder row/card of this view or a node of the tree. Must not be a dragged
        // item or below one; below is only known when its ancestor chain was seen before,
        // otherwise the server refuses (it checks anyway).
        _isValidDropTarget(records, target) {
            if (!target.isDir || !target.folderId) {
                return false;
            }
            const chain = this._crumbChains.get(target.folderId);
            return records.every((record) => {
                if (record.resId === target.folderId) {
                    return false;
                }
                return !(
                    record.data.is_dir &&
                    chain &&
                    chain.some((crumb) => crumb.id === record.resId)
                );
            });
        }

        _dropTargetFromEvent(ev) {
            const rowEl = ev.target.closest("[data-id]");
            if (rowEl) {
                const record = this._recordForLocalId(rowEl.dataset.id);
                if (record) {
                    return {
                        el: rowEl,
                        folderId: record.resId,
                        isDir: record.data.is_dir,
                    };
                }
            }
            const treeEl = ev.target.closest("[data-int-filemanager-tree-id]");
            if (treeEl) {
                return {
                    el: treeEl,
                    folderId: Number(treeEl.dataset.intFilemanagerTreeId),
                    isDir: true,
                };
            }
            return null;
        }

        _onDragStartRecord(ev) {
            if (!this.rootRef.el?.contains(ev.target)) {
                return;
            }
            const {rowEl, record} = this._rowRecordFromEvent(ev);
            if (!record) {
                return;
            }
            this._draggedRecords = this._recordsForDrag(record);
            ev.dataTransfer.effectAllowed = "move";
            // Only a marker to tell this drag from a file drag out of the OS (which carries
            // "Files"); the real state is this._draggedRecords.
            ev.dataTransfer.setData(MOVE_DRAG_TYPE, "1");
            this._setDragImage(ev, rowEl);
        }

        // One drag image whether the icon or the label was grabbed, with a "+N" badge for a
        // multi-selection. The clone is attached invisibly for a moment: setDragImage needs a
        // rendered element, and the browser captures it on the next frame.
        _setDragImage(ev, rowEl) {
            const nameCellEl = rowEl.querySelector(".o_int_filemanager_name_cell");
            if (!nameCellEl) {
                return;
            }
            const rect = nameCellEl.getBoundingClientRect();
            const offsetX = ev.clientX - rect.left;
            const offsetY = ev.clientY - rect.top;
            if (this._draggedRecords.length <= 1) {
                ev.dataTransfer.setDragImage(nameCellEl, offsetX, offsetY);
                return;
            }
            const ghost = nameCellEl.cloneNode(true);
            ghost.style.position = "fixed";
            ghost.style.top = "-9999px";
            ghost.style.left = "-9999px";
            // The clone hangs outside the flex container that makes long names ellipsize, so it
            // needs the original width (plus room for the badge, which must lie inside the
            // captured box or it is clipped).
            ghost.style.width = `${rect.width + 32}px`;
            ghost.style.pointerEvents = "none";
            const badge = document.createElement("span");
            badge.className = "badge rounded-pill bg-primary";
            badge.textContent = `+${this._draggedRecords.length - 1}`;
            ghost.appendChild(badge);
            document.body.appendChild(ghost);
            ev.dataTransfer.setDragImage(ghost, offsetX, offsetY);
            setTimeout(() => ghost.remove(), 0);
        }

        _isMoveDrag(ev) {
            return (
                Boolean(this._draggedRecords) &&
                Array.from(ev.dataTransfer.types || []).includes(MOVE_DRAG_TYPE)
            );
        }

        _onDragOverRecord(ev) {
            if (!this._isMoveDrag(ev)) {
                return;
            }
            const target = this._dropTargetFromEvent(ev);
            const targetEl = target?.el;
            const valid =
                target && this._isValidDropTarget(this._draggedRecords, target);
            if (this._dropTargetEl && this._dropTargetEl !== targetEl) {
                this._dropTargetEl.classList.remove("o_int_filemanager_drop_target");
                this._dropTargetEl = null;
            }
            if (this._invalidDropTargetEl && this._invalidDropTargetEl !== targetEl) {
                this._invalidDropTargetEl.classList.remove(
                    "o_int_filemanager_drop_invalid"
                );
                this._invalidDropTargetEl = null;
            }
            if (!valid) {
                // Red on anything under the cursor that is not a valid target (a file, the
                // dragged item itself, one of its sub-folders); nothing on empty space.
                if (target && this._invalidDropTargetEl !== targetEl) {
                    targetEl.classList.add("o_int_filemanager_drop_invalid");
                    this._invalidDropTargetEl = targetEl;
                }
                return;
            }
            // PreventDefault is what makes a drop possible at all: without it the browser keeps
            // showing "not allowed", which is exactly right for the invalid targets above.
            ev.preventDefault();
            ev.dataTransfer.dropEffect = "move";
            if (this._dropTargetEl !== targetEl) {
                targetEl.classList.add("o_int_filemanager_drop_target");
                this._dropTargetEl = targetEl;
            }
        }

        async _onDropRecord(ev) {
            if (!this._isMoveDrag(ev)) {
                return;
            }
            const records = this._draggedRecords;
            this._clearDragState();
            const target = this._dropTargetFromEvent(ev);
            if (!target || !this._isValidDropTarget(records, target)) {
                return;
            }
            ev.preventDefault();
            await this.moveRecordsTo(records, target.folderId);
        }

        // Also runs when a drag ends without a drop (Escape): no highlight may stay behind.
        _clearDragState() {
            this._draggedRecords = null;
            if (this._dropTargetEl) {
                this._dropTargetEl.classList.remove("o_int_filemanager_drop_target");
                this._dropTargetEl = null;
            }
            if (this._invalidDropTargetEl) {
                this._invalidDropTargetEl.classList.remove(
                    "o_int_filemanager_drop_invalid"
                );
                this._invalidDropTargetEl = null;
            }
        }
    };
