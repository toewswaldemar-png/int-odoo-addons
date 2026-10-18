import { evaluateBooleanExpr } from "@web/core/py_js/py";
import { usePopover } from "@web/core/popover/popover_hook";
import { documentFilesFromRecords } from "../../document_file";
import { DocumentListContextMenu } from "./document_list_context_menu";
import { DocumentListRenderer } from "./document_list_renderer";

// What keeps the menu of the browser: a link, a field, a text that can be edited.
const BROWSER_MENU = "a, input, textarea, select, [contenteditable]";

/**
 * The list of the documents with a menu for the right click on a row (the guests keep
 * `DocumentListRenderer`). The menu opens at the element that was clicked, as the popovers of
 * the core do; it holds the buttons of the head of the list and "View". Like in a file
 * manager, the row of the click is ticked when it is not (the ticked rows are what the buttons
 * act on).
 */
export class DocumentListContextMenuRenderer extends DocumentListRenderer {
    static template = "int_filemanager.DocumentListContextMenuRenderer";

    setup() {
        super.setup();
        this.contextMenu = usePopover(DocumentListContextMenu, {
            // The menu uses the buttons of the view (`onClickViewButton` of the controller).
            env: this.env,
            animation: false,
            arrow: false,
            position: "bottom-start",
            popoverClass: "o-dropdown--menu dropdown-menu mx-0",
            role: "menu",
        });
    }

    /**
     * @param {MouseEvent} ev
     */
    async onContextMenu(ev) {
        const { list } = this.props;
        const row = ev.target.closest?.("tr.o_data_row");
        // A small screen keeps the touch gestures of the core; the rows of the groups of a
        // grouped list are not in `list.records` and keep the menu of the browser.
        const record =
            !this.uiService.isSmall && row && list.records.find((r) => r.id === row.dataset.id);
        if (
            !record ||
            record.isInEdition ||
            !this.canSelectRecord ||
            ev.target.closest(BROWSER_MENU)
        ) {
            return;
        }
        ev.preventDefault();
        const target = ev.target;
        if (!record.selected) {
            for (const other of list.selection) {
                other.toggleSelection(false);
            }
            await record.toggleSelection(true);
        }
        this.contextMenu.open(target, {
            list,
            buttons: this.props.archInfo.headerButtons.filter(
                (button) =>
                    button.display !== "always" &&
                    !evaluateBooleanExpr(button.invisible, list.evalContext)
            ),
            domain: list.domain,
            onView: this.getViewAction(record),
        });
    }

    /**
     * @param {Object} record the row of the click
     * @returns {Function|undefined} shows the file of the row in the viewer, when the row is
     *      the only one ticked and a browser can show the file
     */
    getViewAction(record) {
        const { list } = this.props;
        if (list.selection.length !== 1 || list.selection[0] !== record) {
            return;
        }
        const { file, files } = documentFilesFromRecords(list.records, record);
        if (file.isViewable) {
            return () => this.fileViewer.open(file, files);
        }
    }
}
