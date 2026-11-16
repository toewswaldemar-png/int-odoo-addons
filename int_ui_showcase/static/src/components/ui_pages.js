import { Component, markup, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ActionSwiper } from "@web/core/action_swiper/action_swiper";
import { AutoComplete } from "@web/core/autocomplete/autocomplete";
import { CheckBox } from "@web/core/checkbox/checkbox";
import { CodeEditor } from "@web/core/code_editor/code_editor";
import { ColorList } from "@web/core/colorlist/colorlist";
import { useCommand } from "@web/core/commands/command_hook";
import {
    AlertDialog,
    ConfirmationDialog,
} from "@web/core/confirmation_dialog/confirmation_dialog";
import { CopyButton } from "@web/core/copy_button/copy_button";
import { DateTimeInput } from "@web/core/datetime/datetime_input";
import { Dialog } from "@web/core/dialog/dialog";
import { Dropzone } from "@web/core/dropzone/dropzone";
import { DomainSelector } from "@web/core/domain_selector/domain_selector";
import { DomainSelectorDialog } from "@web/core/domain_selector_dialog/domain_selector_dialog";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { AccordionItem } from "@web/core/dropdown/accordion_item";
import { CheckboxItem } from "@web/core/dropdown/checkbox_item";
import { DropdownGroup } from "@web/core/dropdown/dropdown_group";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { useEmojiPicker } from "@web/core/emoji_picker/emoji_picker";
import { ExpressionEditorDialog } from "@web/core/expression_editor_dialog/expression_editor_dialog";
import { FileModel } from "@web/core/file_viewer/file_model";
import { useFileViewer } from "@web/core/file_viewer/file_viewer_hook";
import { FileInput } from "@web/core/file_input/file_input";
import { browser } from "@web/core/browser/browser";
import { hasTouch } from "@web/core/browser/feature_detection";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { ModelFieldSelector } from "@web/core/model_field_selector/model_field_selector";
import { ModelSelector } from "@web/core/model_selector/model_selector";
import { rpc } from "@web/core/network/rpc";
import { Notebook } from "@web/core/notebook/notebook";
import { Pager } from "@web/core/pager/pager";
import { usePopover } from "@web/core/popover/popover_hook";
import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";
import { RecordSelector } from "@web/core/record_selectors/record_selector";
import { ResizablePanel } from "@web/core/resizable_panel/resizable_panel";
import { SelectMenu } from "@web/core/select_menu/select_menu";
import { SignatureDialog } from "@web/core/signature/signature_dialog";
import { TagsList } from "@web/core/tags_list/tags_list";
import { TimePicker } from "@web/core/time_picker/time_picker";
import { useService } from "@web/core/utils/hooks";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";
import { View } from "@web/views/view";

const { DateTime } = luxon;

const RES_MODEL = "int.ui.showcase";

// === HELPERS === //

/** Popover content shown by the popover demo. */
class DemoPopover extends Component {
    static template = "int_ui_showcase.DemoPopover";
    static props = ["*"];
}

/** Dialog with a footer and a configurable size. */
class DemoDialog extends Component {
    static template = "int_ui_showcase.DemoDialog";
    static components = { Dialog };
    static props = { close: Function, size: { type: String, optional: true } };
}

// === BOOTSTRAP === //

export class BootstrapPage extends Component {
    static template = "int_ui_showcase.BootstrapPage";
    static props = ["*"];

    setup() {
        this.variants = [
            "primary",
            "secondary",
            "success",
            "danger",
            "warning",
            "info",
            "light",
            "dark",
        ];
    }
}

// === ODOO STYLES === //

export class OdooPage extends Component {
    static template = "int_ui_showcase.OdooPage";
    static components = { ColorList, TagsList };
    static props = ["*"];

    setup() {
        this.notification = useService("notification");
        this.effect = useService("effect");
        this.state = useState({ color: 3 });
        this.colors = Array.from({ length: ColorList.COLORS.length }, (_, index) => index);
        this.tagColors = Array.from({ length: 12 }, (_, index) => index);
        this.tags = [
            { id: 1, text: _t("Red"), colorIndex: 1 },
            { id: 2, text: _t("Orange"), colorIndex: 2 },
            { id: 3, text: _t("Green"), colorIndex: 10 },
            { id: 4, text: _t("Violet"), colorIndex: 11 },
            { id: 5, text: _t("Cyan"), colorIndex: 4 },
        ];
        this.icons = [
            "fa-star",
            "fa-heart",
            "fa-user",
            "fa-cog",
            "fa-bell",
            "fa-envelope",
            "fa-phone",
            "fa-calendar",
            "fa-clock-o",
            "fa-trash",
            "fa-pencil",
            "fa-search",
            "fa-download",
            "fa-upload",
            "fa-lock",
            "fa-check",
            "fa-times",
            "fa-plus",
            "fa-minus",
            "fa-refresh",
        ];
        this.oiIcons = [
            "oi-arrow-right",
            "oi-arrow-left",
            "oi-arrow-up",
            "oi-arrow-down",
            "oi-view-list",
            "oi-view-kanban",
            "oi-view-pivot",
            "oi-apps",
            "oi-settings-adjust",
            "oi-search",
            "oi-launch",
            "oi-voip",
        ];
    }

    notify(type) {
        this.notification.add(_t("This is a %s notification.", type), { type });
    }

    showRainbow(fadeout) {
        this.effect.add({
            type: "rainbow_man",
            message: _t("Well done!"),
            fadeout,
        });
    }
}

// === INPUTS === //

export class InputsPage extends Component {
    static template = "int_ui_showcase.InputsPage";
    static components = {
        AutoComplete,
        CheckBox,
        CodeEditor,
        CopyButton,
        DateTimeInput,
        Dropzone,
        FileInput,
        SelectMenu,
        TimePicker,
    };
    static props = ["*"];

    setup() {
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.dropTarget = useRef("dropTarget");
        this.fileViewer = useFileViewer();
        this.emojiRef = useRef("emojiButton");
        this.emojiPicker = useEmojiPicker(this.emojiRef, {
            onSelect: (emoji) => {
                this.state.emoji += emoji;
            },
        });
        this.state = useState({
            checked: true,
            indeterminate: false,
            showDropzone: false,
            date: DateTime.now(),
            datetime: DateTime.now(),
            range: [DateTime.now(), DateTime.now().plus({ days: 3 })],
            time: "12:30",
            text: "",
            emoji: "",
            code: "def hello():\n    return 'world'\n",
            choice: "b",
            multiChoice: ["a", "c"],
        });
        this.choices = [
            { value: "a", label: _t("Alpha") },
            { value: "b", label: _t("Beta") },
            { value: "c", label: _t("Gamma") },
        ];
        this.groupedChoices = [
            { label: _t("Letters"), choices: this.choices },
            {
                label: _t("Numbers"),
                choices: [
                    { value: "1", label: _t("One") },
                    { value: "2", label: _t("Two") },
                ],
            },
        ];
        this.sources = [
            {
                options: (request) =>
                    ["Apple", "Apricot", "Banana", "Cherry", "Grape"]
                        .filter((label) => label.toLowerCase().includes(request.toLowerCase()))
                        .map((label) => ({
                            label,
                            onSelect: () => {
                                this.state.text = label;
                            },
                        })),
            },
        ];
    }

    onDateChange(key, value) {
        this.state[key] = value;
    }

    onTimeChange(time) {
        this.state.time = time ? time.toString() : "";
    }

    onUpload(files) {
        this.notification.add(_t("%s file(s) uploaded.", files.length), { type: "success" });
    }

    onDrop(ev) {
        this.state.showDropzone = false;
        this.notification.add(_t("%s file(s) dropped.", ev.dataTransfer.files.length), {
            type: "success",
        });
    }

    async openFileViewer() {
        const attachments = await this.orm.searchRead(
            "ir.attachment",
            [["mimetype", "=", "image/png"], ["res_model", "=", false]],
            ["name", "mimetype"],
            { limit: 5 }
        );
        const files = attachments.map((attachment) => Object.assign(new FileModel(), attachment));
        if (files.length) {
            this.fileViewer.open(files[0], files);
        } else {
            this.notification.add(_t("No image attachment found."), { type: "warning" });
        }
    }

    showSignature() {
        this.dialog.add(SignatureDialog, {
            defaultName: "John Doe",
            nameAndSignatureProps: { mode: "draw" },
            uploadSignature: ({ name }) =>
                this.notification.add(_t("Signed by %s.", name), { type: "success" }),
        });
    }
}

// === SELECTORS === //

export class SelectorsPage extends Component {
    static template = "int_ui_showcase.SelectorsPage";
    static components = {
        DomainSelector,
        ModelFieldSelector,
        ModelSelector,
        MultiRecordSelector,
        RecordSelector,
    };
    static props = ["*"];

    setup() {
        this.dialog = useService("dialog");
        this.field = useService("field");
        this.notification = useService("notification");
        this.state = useState({
            model: "res.partner",
            path: "name",
            domain: "[('name', 'ilike', 'a')]",
            resId: false,
            resIds: [],
        });
        this.resModel = RES_MODEL;
    }

    onModelSelected(model) {
        this.state.model = model.technical;
    }

    onDomainUpdate(domain) {
        this.state.domain = domain;
    }

    onPathUpdate(path) {
        this.state.path = path;
    }

    onRecordUpdate(value) {
        this.state.resId = Array.isArray(value) ? (value[0]?.id ?? false) : (value?.id ?? value);
    }

    onRecordsUpdate(values) {
        this.state.resIds = (values || []).map((value) => value?.id ?? value);
    }

    showDomainDialog() {
        this.dialog.add(DomainSelectorDialog, {
            resModel: this.state.model,
            domain: this.state.domain,
            readonly: false,
            isDebugMode: true,
            onConfirm: (domain) => {
                this.state.domain = domain;
            },
        });
    }

    async showExpressionDialog() {
        const fields = await this.field.loadFields("res.partner");
        this.dialog.add(ExpressionEditorDialog, {
            resModel: "res.partner",
            fields,
            expression: "True",
            onConfirm: (expression) =>
                this.notification.add(_t("Expression: %s", expression), { type: "info" }),
        });
    }
}

// === MENUS AND OVERLAYS === //

export class MenusPage extends Component {
    static template = "int_ui_showcase.MenusPage";
    static components = {
        AccordionItem,
        ActionSwiper,
        CheckboxItem,
        Dropdown,
        DropdownGroup,
        DropdownItem,
        Notebook,
        Pager,
        ResizablePanel,
    };
    static props = ["*"];

    setup() {
        this.notification = useService("notification");
        this.state = useState({
            last: "",
            checked: false,
            pager: { offset: 0, limit: 5 },
            width: 0,
        });
        this.popover = usePopover(DemoPopover, { position: "bottom" });
        this.positions = ["bottom-start", "bottom-end", "top-start", "top-end", "right", "left"];
        useCommand(_t("Showcase: say hello"), () =>
            this.notification.add(_t("Hello from the command palette."), { type: "info" })
        );
        useHotkey("alt+shift+h", () =>
            this.notification.add(_t("Hotkey alt+shift+h pressed."), { type: "info" })
        );
    }

    get leftSwipe() {
        return { action: () => this.select("Swiped left"), icon: "fa-trash", bgColor: "bg-danger" };
    }

    get rightSwipe() {
        return { action: () => this.select("Swiped right"), icon: "fa-check", bgColor: "bg-success" };
    }

    select(label) {
        this.state.last = label;
    }

    onPagerUpdate({ offset, limit }) {
        Object.assign(this.state.pager, { offset, limit });
    }

    showPopover(ev) {
        this.popover.open(ev.currentTarget, { text: _t("This is a popover.") });
    }
}

// === DIALOGS AND NOTIFICATIONS === //

export class DialogsPage extends Component {
    static template = "int_ui_showcase.DialogsPage";
    static props = ["*"];

    setup() {
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.effect = useService("effect");
        this.notificationTypes = ["info", "success", "warning", "danger"];
        this.sizes = ["sm", "md", "lg", "xl", "fullscreen"];
    }

    notify(type) {
        this.notification.add(_t("This is a %s notification.", type), { type });
    }

    notifySticky() {
        this.notification.add(_t("A sticky notification with a title and a button."), {
            title: _t("Sticky"),
            sticky: true,
            type: "info",
            buttons: [
                {
                    name: _t("Do it"),
                    primary: true,
                    onClick: () => this.notify("success"),
                },
            ],
        });
    }

    notifyHtml() {
        this.notification.add(markup("<b>Bold</b> and <i>italic</i> content"), {
            type: "warning",
        });
    }

    showAlert() {
        this.dialog.add(AlertDialog, { title: _t("Alert"), body: _t("This is an alert dialog.") });
    }

    showConfirmation() {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Confirmation"),
            body: _t("Do you want to continue?"),
            confirmLabel: _t("Yes"),
            cancelLabel: _t("No"),
            confirm: () => this.notify("success"),
            cancel: () => this.notify("warning"),
        });
    }

    showCustom(size) {
        this.dialog.add(DemoDialog, { size });
    }

    showFormDialog() {
        this.dialog.add(FormViewDialog, { resModel: RES_MODEL, title: _t("Form in a dialog") });
    }

    showSelectDialog() {
        this.dialog.add(SelectCreateDialog, {
            resModel: RES_MODEL,
            title: _t("Select records"),
            multiSelect: true,
            onSelected: (resIds) =>
                this.notification.add(_t("%s record(s) selected.", resIds.length), {
                    type: "success",
                }),
        });
    }

    showRainbow(fadeout) {
        this.effect.add({ type: "rainbow_man", message: _t("Well done!"), fadeout });
    }
}

// === EMBEDDED VIEWS === //

export class ViewsPage extends Component {
    static template = "int_ui_showcase.ViewsPage";
    static components = { View };
    static props = ["*"];

    setup() {
        this.resModel = RES_MODEL;
        this.viewTypes = ["list", "kanban", "graph", "pivot", "calendar", "form"];
        this.state = useState({ type: "list" });
    }

    get viewProps() {
        return {
            type: this.state.type,
            resModel: this.resModel,
            display: { controlPanel: this.state.type === "list" },
            noBreadcrumbs: true,
        };
    }
}

// === NUMPAD === //

const MAX_DIGITS = 4;
const TITLES = {
    hymn: {
        1: "Befiehl du deine Wege",
        12: "Großer Gott, wir loben dich",
        123: "Nun danket alle Gott",
        1234: "Lobe den Herren",
    },
    choir: { 1: "Chorstück Eins", 12: "Chorstück Zwölf" },
};

/**
 * Numpad built from Odoo blocks: big square touch keys, a hotkey per key, a title lookup,
 * a preview of what is typed against what is shown on the beamer, notifications and a dialog.
 */
export class NumpadPage extends Component {
    static template = "int_ui_showcase.NumpadPage";
    static props = ["*"];

    setup() {
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.hasTouch = hasTouch();
        // typed: the number being typed; shown: the number the beamer shows
        this.state = useState({
            target: "hymn",
            typed: { hymn: "", choir: "" },
            shown: { hymn: "", choir: "" },
        });
        this.targets = [
            { id: "hymn", label: _t("Hymn") },
            { id: "choir", label: _t("Choir") },
        ];
        this.digits = ["1", "2", "3", "4", "5", "6", "7", "8", "9"];
        for (const digit of [...this.digits, "0"]) {
            useHotkey(digit, () => this.onDigit(digit));
        }
        useHotkey("backspace", () => this.onBackspace());
        useHotkey("enter", () => this.onShow());
    }

    get otherTarget() {
        return this.state.target === "hymn" ? "choir" : "hymn";
    }

    /** The digit keys are locked while the other number is being typed. */
    get locked() {
        return this.state.typed[this.otherTarget].length > 0;
    }

    get number() {
        return this.state.typed[this.state.target];
    }

    /** While the keys are locked, backspace and clear act on the number that locks them. */
    get editedTarget() {
        return this.number || !this.locked ? this.state.target : this.otherTarget;
    }

    title(target) {
        return TITLES[target][Number(this.state.typed[target])] || "";
    }

    setTarget(target) {
        this.state.target = target;
    }

    onDigit(digit) {
        if (this.locked || this.number.length >= MAX_DIGITS) {
            return;
        }
        this.state.typed[this.state.target] += digit;
    }

    onBackspace() {
        const key = this.editedTarget;
        this.state.typed[key] = this.state.typed[key].slice(0, -1);
    }

    onClear() {
        this.state.typed[this.editedTarget] = "";
    }

    onShow() {
        const target = this.state.target;
        if (!this.number) {
            return;
        }
        if (!this.title(target)) {
            this.notification.add(_t("Unknown number %s.", this.number), { type: "warning" });
            return;
        }
        this.state.shown[target] = this.number;
    }

    onReset() {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Reset"),
            body: _t("Clear the typed and the shown numbers?"),
            confirm: () => {
                for (const target of ["hymn", "choir"]) {
                    this.state.typed[target] = "";
                    this.state.shown[target] = "";
                }
            },
            cancel: () => {},
        });
    }
}

// === DASHBOARD === //

const ICECAST_URL = "/int_ui_showcase/icecast/status";
const REFRESH_MS = 5000;
const HISTORY_LENGTH = 24;
const SPARK_WIDTH = 100;
const SPARK_HEIGHT = 30;
const SPARK_MIN_SPAN = 10;

/**
 * Icecast overview: totals and one row per mount, read through the server and refreshed on a timer.
 */
export class IcecastPanel extends Component {
    static template = "int_ui_showcase.IcecastPanel";
    static props = ["*"];

    setup() {
        this.state = useState({
            data: null,
            error: null,
            history: [],
            auto: true,
            loading: false,
        });
        onMounted(() => {
            this.refresh();
            this.interval = browser.setInterval(() => {
                if (this.state.auto) {
                    this.refresh();
                }
            }, REFRESH_MS);
        });
        onWillUnmount(() => browser.clearInterval(this.interval));
    }

    get checkedAt() {
        return this.state.data
            ? DateTime.fromSeconds(this.state.data.checked_at).toFormat("HH:mm:ss")
            : "";
    }

    /** The listener history as the points of an SVG polyline. */
    get sparkline() {
        const values = this.state.history;
        if (values.length < 2) {
            return "";
        }
        const low = Math.min(...values);
        // A small span would blow a change of one listener up to the full height.
        const span = Math.max(Math.max(...values) - low, SPARK_MIN_SPAN);
        const step = SPARK_WIDTH / (values.length - 1);
        return values
            .map((value, index) => {
                const y = SPARK_HEIGHT - 2 - ((value - low) / span) * (SPARK_HEIGHT - 4);
                return `${(index * step).toFixed(1)},${y.toFixed(1)}`;
            })
            .join(" ");
    }

    async refresh() {
        this.state.loading = true;
        try {
            const data = await rpc(ICECAST_URL);
            this.state.data = data;
            this.state.error = data.error;
            if (!data.error) {
                this.state.history = [...this.state.history, data.listeners].slice(-HISTORY_LENGTH);
            }
        } catch (error) {
            this.state.error = error.data?.message || error.message || String(error);
        } finally {
            this.state.loading = false;
        }
    }
}

/** Hymn control and Icecast overview side by side: two independent panels on one page. */
export class DashboardPage extends Component {
    static template = "int_ui_showcase.DashboardPage";
    static components = { IcecastPanel, NumpadPage };
    static props = ["*"];
}

// === NUMPAD (NATIVE) === //

/** Keys as data, in the shape of the point_of_sale Numpad: ``value`` plus an optional ``class``. */
const NATIVE_KEYS = [
    ...Array.from("123456789", (value) => ({ value })),
    { value: "0", class: "o_ui_native_key_wide" },
    { value: "Backspace", icon: "fa-long-arrow-left", label: "Backspace" },
];

/**
 * The numpad again, with the Bootstrap classes Odoo itself uses (``btn btn-secondary btn-lg``)
 * and the keys rendered from a list. The logic is the one of NumpadPage.
 */
export class NativeNumpadPage extends NumpadPage {
    static template = "int_ui_showcase.NativeNumpadPage";

    setup() {
        super.setup();
        this.keys = NATIVE_KEYS;
    }

    isDisabled(key) {
        return key.value !== "Backspace" && this.locked;
    }

    onKey(key) {
        if (key.value === "Backspace") {
            this.onBackspace();
        } else {
            this.onDigit(key.value);
        }
    }
}
