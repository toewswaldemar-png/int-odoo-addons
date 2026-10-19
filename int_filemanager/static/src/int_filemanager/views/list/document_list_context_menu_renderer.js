import { useRef, useState } from "@odoo/owl";
import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";
import { evaluateBooleanExpr } from "@web/core/py_js/py";
import { documentFilesFromRecords } from "../../document_file";
import { getFoldersSection, useNewFolder } from "./document_new_folder";
import { DocumentListRenderer } from "./document_list_renderer";

// What keeps the menu of the browser: a link, a field, a text that can be edited.
const BROWSER_MENU = "a, input, textarea, select, [contenteditable]";

/**
 * The list of the documents with a menu for the right click on a row (the guests keep
 * `DocumentListRenderer`). The menu is the core's `Dropdown`, opened by hand (`manual`); it
 * holds the buttons of the head of the list, as items like those of the action menu of the core
 * (`action_menus.xml`), "View" for the viewer, which is no button, and "New folder", set off by
 * a divider as the core's menus set off a group. Like in a file manager,
 * the row of the click is ticked when it is not (the ticked rows are what the buttons act on).
 *
 * A dropdown opens at its toggler, an element. Here the toggler is a point without size that
 * is moved to the pointer before the menu opens.
 */
export class DocumentListContextMenuRenderer extends DocumentListRenderer {
    static template = "int_filemanager.DocumentListContextMenuRenderer";

    setup() {
        super.setup();
        this.anchorRef = useRef("contextMenuAnchor");
        this.dropdownState = useDropdownState();
        this.contextMenu = useState({ buttons: [], onView: undefined, newFolder: undefined });
        this.newFolder = useNewFolder();
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
        const { clientX, clientY } = ev;
        if (!record.selected) {
            for (const other of list.selection) {
                other.toggleSelection(false);
            }
            await record.toggleSelection(true);
        }
        this.dropdownState.close();
        Object.assign(this.anchorRef.el.style, { left: `${clientX}px`, top: `${clientY}px` });
        Object.assign(this.contextMenu, {
            buttons: this.props.archInfo.headerButtons.filter(
                (button) =>
                    button.display !== "always" &&
                    !evaluateBooleanExpr(button.invisible, list.evalContext)
            ),
            onView: this.getViewAction(record),
            // The folder of the file is the default parent, as in a file manager; a list
            // without the folders of the panel (the documents of a record) has no such item.
            newFolder: getFoldersSection(this.env.searchModel)
                ? () => this.newFolder(record.data.folder_id?.id)
                : undefined,
        });
        this.dropdownState.open();
    }

    /**
     * The button of the head of the list for the ticked rows: the same call as the core's
     * `MultiRecordViewButton` makes.
     * @param {Object} button the button of the arch
     */
    async onButtonSelected(button) {
        const { list } = this.props;
        const resIds = await list.getResIds(true);
        this.env.onClickViewButton({
            clickParams: {
                ...button.clickParams,
                buttonContext: {
                    active_domain: list.domain,
                    active_ids: resIds,
                    active_model: list.resModel,
                },
            },
            getResParams: () => ({
                context: list.context,
                evalContext: list.evalContext,
                resModel: list.resModel,
                resIds,
            }),
        });
    }

    /**
     * @param {String} icon the icon of a button of the arch: a class of FontAwesome or of Odoo
     * @returns {String} its classes
     */
    getIconClass(icon) {
        return icon.startsWith("oi-") ? `oi oi-fw ${icon}` : `fa fa-fw ${icon}`;
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
