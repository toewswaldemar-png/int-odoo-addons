import { useRef, useState } from "@odoo/owl";
import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";
import { _t } from "@web/core/l10n/translation";
import { evaluateBooleanExpr } from "@web/core/py_js/py";
import { documentFilesFromRecords } from "../../document_file";
import { getFoldersSection, useFolderRights, useNewFolder } from "./document_new_folder";
import { DocumentListRenderer } from "./document_list_renderer";

// Elements that keep the menu of the browser.
const BROWSER_MENU = "a, input, textarea, select, [contenteditable]";

/**
 * The list of documents with a menu for the right click on a row. The core's `Dropdown` is opened
 * by hand, its toggler a point without size moved to the pointer.
 */
export class DocumentListContextMenuRenderer extends DocumentListRenderer {
    static template = "int_filemanager.DocumentListContextMenuRenderer";
    static props = [...DocumentListRenderer.props, "contextMenuItems?"];
    static defaultProps = { contextMenuItems: [] };

    setup() {
        super.setup();
        this.anchorRef = useRef("contextMenuAnchor");
        this.dropdownState = useDropdownState();
        this.contextMenu = useState({ sections: [] });
        this.newFolder = useNewFolder();
        this.folderRights = useFolderRights();
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
        this.contextMenu.sections = this.getSections(record);
        this.dropdownState.open();
    }

    /**
     * The items of the menu in sections by theme (a divider lies between two sections): open,
     * pass on (the buttons of the head of the list), put elsewhere.
     * @returns {Object[][]} the sections that have an item, an item being
     *      `{key, icon, description, onSelected}`
     */
    getSections(record) {
        const { list } = this.props;
        const open = [];
        const onView = this.getViewAction(record);
        if (onView) {
            open.push({
                key: "view",
                icon: "fa fa-eye",
                description: _t("View"),
                onSelected: onView,
            });
        }
        const onProperties = this.getPropertiesAction(record);
        if (onProperties) {
            open.push({
                key: "properties",
                icon: "fa fa-pencil",
                description: _t("Properties"),
                onSelected: onProperties,
            });
        }
        const passOn = this.props.archInfo.headerButtons
            .filter(
                (button) =>
                    button.display !== "always" &&
                    !evaluateBooleanExpr(button.invisible, list.evalContext)
            )
            .map((button) => ({
                key: button.id,
                icon: button.icon && this.getIconClass(button.icon),
                description: button.string,
                onSelected: () => this.onButtonSelected(button),
            }));
        const putElsewhere = this.props.contextMenuItems.map((item) => ({
            key: item.key,
            icon: item.icon,
            description: item.description,
            onSelected: () => item.callback(),
        }));
        // A list without the folders of the panel has no such item, nor for a reader.
        if (this.folderRights.create && getFoldersSection(this.env.searchModel)) {
            putElsewhere.push({
                key: "new_folder",
                icon: "fa fa-folder",
                description: _t("New folder"),
                onSelected: () => this.newFolder(record.data.folder_id?.id),
            });
        }
        return [open, passOn, putElsewhere].filter((section) => section.length);
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
        return icon.startsWith("oi-") ? `oi ${icon}` : `fa ${icon}`;
    }

    /**
     * @returns {Function|undefined} opens the form as a click on a row does (the pager runs over
     * the rows of the page), if the row is the only one ticked
     */
    getPropertiesAction(record) {
        const { list } = this.props;
        if (list.selection.length === 1 && list.selection[0] === record) {
            return () => this.props.openRecord(record);
        }
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
