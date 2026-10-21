import { onWillStart, useEnv } from "@odoo/owl";
import { user } from "@web/core/user";
import { makeDraggableHook } from "@web/core/utils/draggable_hook_builder_owl";
import { useService } from "@web/core/utils/hooks";
import { pick } from "@web/core/utils/objects";
import { getFoldersSection } from "../list/document_new_folder";
import { makeDragGhost, placeDragGhost } from "./document_drag_ghost";
import { MOVE_MODEL, useMoveDocuments } from "./document_move";

// What keeps its own click or its own pointer: the drag starts at the rest of the row. A field is no
// such thing: the editable ones of a list (`multi_edit`) are no `o_readonly_modifier` either while
// the row shows them; a row in edition is kept out by `preventDrag`.
const IGNORE = "a, button, input, textarea, select, label, .o_list_record_selector";

/**
 * The drag of the core that does not move the dragged element (`followCursor`, as the block
 * selection of the calendar): the picture is a ghost of its own, and no native drag draws the
 * pointer of the system or fades the picture.
 */
const useDocumentDrag = makeDraggableHook({
    name: "useDocumentDrag",
    onComputeParams({ ctx }) {
        ctx.followCursor = false;
    },
    onDragStart: ({ ctx }) => pick(ctx.current, "element"),
    onDrag: ({ ctx }) => pick(ctx.current, "element"),
    onDragEnd: ({ ctx }) => pick(ctx.current, "element"),
    onDrop: ({ ctx }) => pick(ctx.current, "element"),
});

/**
 * @param {{x: number, y: number}} pointer
 * @returns {number|null} the folder of the search panel under the pointer. The folders carry
 *      `data-drop-folder`; one that the panel has scrolled out of sight is none.
 */
function folderUnder({ x, y }) {
    const contains = (el) => {
        const rect = el.getBoundingClientRect();
        return rect.left <= x && x <= rect.right && rect.top <= y && y <= rect.bottom;
    };
    for (const element of document.querySelectorAll("[data-drop-folder]")) {
        const panel = element.closest(".o_search_panel");
        if (panel && contains(panel) && contains(element)) {
            return Number(element.dataset.dropFolder);
        }
    }
    return null;
}

/**
 * Rows or cards that can be dragged to a folder of the search panel (the folders are marked with
 * `data-drop-folder`, see `DocumentSearchPanel`). The ticked rows go together when one of them is
 * dragged, else only the dragged one.
 * @param {Object} params
 * @param {{el: HTMLElement|null}} params.ref the element that holds the rows or cards
 * @param {string} params.elements selector of a row or a card (it has `data-id`)
 * @param {() => Object} params.getList the list of records the view shows
 * @param {(record: Object) => boolean} [params.canDrag] a view that has a drag of its own says
 *      here where this one must stay off
 */
export function useDocumentDragSource({ ref, elements, getList, canDrag = () => true }) {
    const { searchModel } = useEnv();
    const ui = useService("ui");
    const moveDocuments = useMoveDocuments();
    let canMove = false;
    onWillStart(async () => {
        canMove = await user.checkAccessRight(MOVE_MODEL, "create");
    });
    let ghost = null;

    const recordOf = (element) =>
        getList().records.find((record) => record.id === element.dataset.id);

    useDocumentDrag({
        ref,
        elements,
        ignore: IGNORE,
        // The target is in the panel: a list that scrolls at the edges would only get in the way.
        edgeScrolling: { enabled: false },
        // A reader may not move; a small screen keeps the touch gestures of the core.
        enable: () => canMove && !ui.isSmall && Boolean(getFoldersSection(searchModel)),
        preventDrag: (element) => {
            const record = recordOf(element);
            return !record || record.isInEdition || !canDrag(record);
        },
        onDragStart({ element, x, y, addClass, addStyle }) {
            // The kanban tilts a card that is marked as dragged; this one stays where it is.
            addClass(element, "o_draggable_norotate");
            const record = recordOf(element);
            const records = record.selected ? getList().selection : [record];
            searchModel.drag.start(records, ref.el);
            ghost = makeDragGhost(records);
            placeDragGhost(ghost, { x, y });
            addStyle(document.documentElement, { cursor: "grabbing" });
        },
        onDrag({ x, y }) {
            placeDragGhost(ghost, { x, y });
            const folders = getFoldersSection(searchModel);
            const folderId = folderUnder({ x, y });
            // The list shows only the documents of the chosen folder, they are in it already.
            const over = folderId === folders.activeValueId ? null : folderId;
            if (searchModel.drag.over !== over) {
                searchModel.drag.over = over;
            }
        },
        onDrop() {
            const { over, resIds } = searchModel.drag;
            if (over) {
                const folder = getFoldersSection(searchModel).values.get(over);
                moveDocuments([...resIds], over, folder.display_name);
            }
        },
        onDragEnd() {
            ghost?.remove();
            ghost = null;
            searchModel.drag.end();
        },
    });
}
