import { useRef, useState } from "@odoo/owl";
import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";
import { evaluateBooleanExpr } from "@web/core/py_js/py";
import { documentFilesFromRecords } from "../../document_file";
import { getFoldersSection, useNewFolder } from "./document_new_folder";
import { DocumentListRenderer } from "./document_list_renderer";

// Elements that keep the menu of the browser.
const BROWSER_MENU = "a, input, textarea, select, [contenteditable]";

/**
 * The list of documents with a menu for the right click on a row. The core's `Dropdown` is opened
 * by hand, its toggler a point without size moved to the pointer.
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

    async onContextMenu(ev) {
        const { list } = this.props;
        const row = ev.target.closest?.("tr.o_data_row");
        // A small screen keeps the core's touch gestures; group rows keep the browser menu.
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
            // A list without the folders of the panel has no such item.
            newFolder: getFoldersSection(this.env.searchModel)
                ? () => this.newFolder(record.data.folder_id?.id)
                : undefined,
        });
        this.dropdownState.open();
    }

    /** Runs a button of the list head for the ticked rows, as `MultiRecordViewButton` does. */
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

    /** @param {String} icon FontAwesome or Odoo icon of a button of the arch */
    getIconClass(icon) {
        return icon.startsWith("oi-") ? `oi oi-fw ${icon}` : `fa fa-fw ${icon}`;
    }

    /** @returns {Function|undefined} opens the viewer, if the row is the only one ticked */
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
