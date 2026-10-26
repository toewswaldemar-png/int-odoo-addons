import { Chatter } from "@mail/chatter/web_portal/chatter";
import { useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { router } from "@web/core/browser/router";
import { ResizablePanel } from "@web/core/resizable_panel/resizable_panel";
import { SIZES } from "@web/core/ui/ui_service";
import { useDebounced } from "@web/core/utils/timing";
import { FormController } from "@web/views/form/form_controller";
import { documentFileFromRecord } from "../../document_file";
import { DocumentPreview } from "../../file_viewer/document_preview";
import { useDocumentFileViewer } from "../../file_viewer/document_file_viewer";

// What the side panel shows ("details", "chatter" or "none") and its width per part are kept.
const PANEL_KEY = "int_filemanager.document_panel";
const WIDTH_KEY = "int_filemanager.document_panel_width_";
// The chatter minimum is mail's `$o-mail-Chatter-minWidth`: below it the buttons
// above the messages need a scrollbar.
const WIDTHS = {
    details: { first: 480, min: 320 },
    chatter: { first: 530, min: 530 },
};
const KEEP_DELAY = 300;

function readSetting(key) {
    try {
        return browser.localStorage.getItem(key);
    } catch {
        return null; // No storage (private window).
    }
}

function writeSetting(key, value) {
    try {
        browser.localStorage.setItem(key, value);
    } catch {
        // No storage (private window).
    }
}

/**
 * The form of a document as a file manager's page: the file, large, with a panel at its side
 * for the form or the chatter. Buttons next to the pager choose what the panel shows.
 */
export class DocumentFormController extends FormController {
    static template = "int_filemanager.DocumentFormController";
    static components = {
        ...FormController.components,
        Chatter,
        DocumentPreview,
        ResizablePanel,
    };

    setup() {
        super.setup();
        this.fileViewer = useDocumentFileViewer();
        // Optional, like for the viewer: the service of the picture editor is that of a module of its own.
        const imageEditor = this.env.services["int_filemanager.image_editor"];
        this.onEdit = imageEditor && ((file) => imageEditor.open(file));
        const kept = readSetting(PANEL_KEY);
        // The details are open where there is room for them, the chatter only on request.
        this.panel = useState({
            part: kept ? kept in WIDTHS && kept : this.ui.size >= SIZES.LG && "details",
        });
        this.widths = {};
        for (const [part, { first }] of Object.entries(WIDTHS)) {
            this.widths[part] = Number(readSetting(WIDTH_KEY + part)) || first;
        }
        this.keepWidth = useDebounced(
            (part, width) => writeSetting(WIDTH_KEY + part, Math.round(width)),
            KEEP_DELAY
        );
    }

    get file() {
        return documentFileFromRecord(this.model.root);
    }

    get chatterProps() {
        const { resId, resModel } = this.model.root;
        return {
            threadModel: resModel,
            threadId: resId,
            record: this.model.root,
            saveRecord: () => this.save(),
            has_activities: this.archInfo.has_activities,
            highlightMessageId: router.current.highlight_message_id,
        };
    }

    get panelMinWidth() {
        return WIDTHS[this.panel.part].min;
    }

    get panelStartWidth() {
        return Math.max(this.widths[this.panel.part], this.panelMinWidth);
    }

    togglePanel(part) {
        this.panel.part = this.panel.part === part ? false : part;
        writeSetting(PANEL_KEY, this.panel.part || "none");
    }

    onPanelResize(width) {
        this.widths[this.panel.part] = width;
        this.keepWidth(this.panel.part, width);
    }

    onFullScreen() {
        this.fileViewer.open(this.file);
    }
}
