import { registry } from "@web/core/registry";

const FORM_TABS = [
    "text",
    "numbers",
    "dates",
    "choices",
    "relations",
    "lines",
    "properties",
    "files",
    "data",
    "layout",
];

const COMPONENT_TABS = [
    "bootstrap",
    "odoo",
    "inputs",
    "selectors",
    "menus",
    "dialogs",
    "numpad",
    "numpad_native",
    "dashboard",
    "views",
];

function waitFor(trigger) {
    return { trigger, run: () => {} };
}

registry.category("web_tour.tours").add("int_ui_showcase_views", {
    steps: () => [
        waitFor(".o_kanban_view .o_kanban_record"),
        { trigger: ".o_switch_view.o_pivot", run: "click" },
        waitFor(".o_pivot_view .o_pivot_cell_value"),
        { trigger: ".o_switch_view.o_graph", run: "click" },
        waitFor(".o_graph_view canvas"),
        { trigger: ".o_switch_view.o_calendar", run: "click" },
        waitFor(".o_calendar_view .fc-view"),
        { trigger: ".o_switch_view.o_activity", run: "click" },
        waitFor(".o_activity_view"),
        { trigger: ".o_switch_view.o_list", run: "click" },
        waitFor(".o_list_view .o_data_row"),
        { trigger: ".o_data_row:first-child .o_data_cell[name='name']", run: "click" },
        waitFor(".o_form_view .o_notebook"),
        ...FORM_TABS.flatMap((name) => [
            { trigger: `.o_notebook_headers .nav-link[name='${name}']`, run: "click" },
            waitFor(`.o_notebook_headers .nav-link.active[name='${name}']`),
        ]),
        { trigger: ".o_form_view button[name='action_notify']", run: "click" },
        waitFor(".o_notification"),
        { trigger: ".o_form_view button:contains('Open Dialog')", run: "click" },
        waitFor(".modal-content .o_form_view"),
        { trigger: ".modal-footer button:contains('Cancel')", run: "click" },
        waitFor(".o_form_view .o_notebook"),
    ],
});

const ROOT = ".o_ui_showcase_components";

function openTab(name) {
    return [
        { trigger: `${ROOT} .nav-link[name='${name}']`, run: "click" },
        waitFor(`${ROOT} .nav-link.active[name='${name}']`),
    ];
}

function press(trigger, key) {
    return { trigger, run: `press ${key}` };
}

registry.category("web_tour.tours").add("int_ui_showcase_components", {
    steps: () => [
        waitFor(`${ROOT} .nav-link.active[name='bootstrap']`),
        { trigger: `${ROOT} button:contains('Top')`, run: "hover" },

        // === Odoo styles === //
        ...openTab("odoo"),
        { trigger: `${ROOT} button:contains('Rainbow man')`, run: "click" },
        waitFor(".o_reward"),
        { trigger: `${ROOT} button:contains('Success')`, run: "click" },
        waitFor(".o_notification"),

        // === Inputs === //
        ...openTab("inputs"),
        { trigger: `${ROOT} .o_datetime_input:first`, run: "click" },
        waitFor(".o_datetime_picker"),
        press(".o_datetime_picker", "Escape"),
        { trigger: `${ROOT} input[placeholder='Type a fruit']`, run: "edit Ap" },
        waitFor(".o-autocomplete--dropdown-menu"),
        { trigger: `${ROOT} button:contains('Toggle dropzone')`, run: "click" },
        waitFor(".o-Dropzone"),
        { trigger: `${ROOT} button:contains('Toggle dropzone')`, run: "click" },
        { trigger: `${ROOT} button:contains('File viewer')`, run: "click" },
        waitFor(".o-FileViewer"),
        press(".o-FileViewer", "Escape"),
        { trigger: `${ROOT} button:contains('Emoji')`, run: "click" },
        waitFor(".o-EmojiPicker"),
        { trigger: `${ROOT} button:contains('Signature dialog')`, run: "click" },
        waitFor(".modal-content"),
        { trigger: ".modal-footer .btn-secondary", run: "click" },
        { trigger: `${ROOT} .o_select_menu_toggler:first`, run: "click" },
        waitFor(".o_select_menu_menu"),
        press(".o_select_menu_menu", "Escape"),

        // === Selectors === //
        ...openTab("selectors"),
        { trigger: `${ROOT} .o_model_field_selector_value:first`, run: "click" },
        waitFor(".o_popover"),
        press(".o_popover", "Escape"),
        { trigger: `${ROOT} button:contains('Domain dialog')`, run: "click" },
        waitFor(".modal-content"),
        { trigger: ".modal-footer .btn-secondary", run: "click" },
        { trigger: `${ROOT} button:contains('Expression editor dialog')`, run: "click" },
        waitFor(".modal-content"),
        { trigger: ".modal-footer .btn-secondary", run: "click" },

        // === Menus and overlays === //
        ...openTab("menus"),
        { trigger: `${ROOT} button:contains('Simple')`, run: "click" },
        waitFor(".o-dropdown--menu"),
        { trigger: ".o-dropdown--menu .dropdown-item:contains('First')", run: "click" },
        waitFor(`${ROOT} b:contains('First')`),
        { trigger: `${ROOT} button:contains('Nested')`, run: "click" },
        waitFor(".o-dropdown--menu"),
        press(".o-dropdown--menu", "Escape"),
        { trigger: `${ROOT} button:contains('Checkbox and accordion')`, run: "click" },
        waitFor(".o-dropdown--menu"),
        press(".o-dropdown--menu", "Escape"),
        { trigger: `${ROOT} button:contains('From items')`, run: "click" },
        waitFor(".o-dropdown--menu"),
        press(".o-dropdown--menu", "Escape"),
        { trigger: `${ROOT} button:contains('Popover')`, run: "click" },
        waitFor(".o_popover"),
        { trigger: `${ROOT} .nav-link:contains('Two')`, run: "click" },

        // === Dialogs === //
        ...openTab("dialogs"),
        { trigger: `${ROOT} button:contains('Alert')`, run: "click" },
        waitFor(".modal-content"),
        { trigger: ".modal-footer .btn-primary", run: "click" },
        { trigger: `${ROOT} button:contains('Confirmation')`, run: "click" },
        waitFor(".modal-content"),
        { trigger: ".modal-footer .btn-primary", run: "click" },
        { trigger: `${ROOT} button:contains('Form view dialog')`, run: "click" },
        waitFor(".modal-content .o_form_view"),
        { trigger: ".modal-footer button:contains('Discard')", run: "click" },
        { trigger: `${ROOT} button:contains('Select records dialog')`, run: "click" },
        waitFor(".modal-content .o_list_view"),
        { trigger: ".modal-footer .btn-secondary", run: "click" },
        { trigger: `${ROOT} button:contains('Custom xl')`, run: "click" },
        waitFor(".modal-content"),
        { trigger: ".modal-footer .btn-primary", run: "click" },
        { trigger: `${ROOT} button:contains('Sticky with button')`, run: "click" },
        waitFor(".o_notification"),
        { trigger: `${ROOT} button:contains('Markup')`, run: "click" },
        { trigger: `${ROOT} button:contains('Rainbow slow')`, run: "click" },

        // === Numpad === //
        ...openTab("numpad"),
        ...["1", "2", "3", "4"].map((digit) => ({
            trigger: `${ROOT} .o_ui_numpad_key:contains('${digit}')`,
            run: "click",
        })),
        waitFor(".o_ui_numpad_row_active .o_ui_numpad_title:contains('Lobe den Herren')"),
        { trigger: `${ROOT} .o_ui_numpad_key[aria-label='Backspace']`, run: "click" },
        waitFor(".o_ui_numpad_row_active .o_ui_numpad_title:contains('Nun danket alle Gott')"),
        { trigger: `${ROOT} .o_ui_numpad_show`, run: "click" },
        waitFor(".o_ui_numpad_beamer:contains('123')"),
        { trigger: `${ROOT} .o_ui_numpad_row[data-target='choir']`, run: "click" },
        waitFor(`${ROOT} .o_ui_showcase_numpad .alert-info`),
        { trigger: `${ROOT} button:contains('Reset everything')`, run: "click" },
        waitFor(".modal-content"),
        { trigger: ".modal-footer .btn-primary", run: "click" },
        waitFor(`${ROOT} .o_ui_showcase_numpad:not(:has(.alert-info))`),

        // === Numpad (native) === //
        ...openTab("numpad_native"),
        waitFor(`${ROOT} .o_ui_native_keys .o_ui_native_key.btn-secondary:nth-child(11)`),
        waitFor(`${ROOT} .o_ui_native_keys:not(:has(.o_ui_native_key:nth-child(12)))`),
        ...["1", "2", "3"].map((digit) => ({
            trigger: `${ROOT} .o_ui_native_key:contains('${digit}')`,
            run: "click",
        })),
        waitFor(".o_ui_numpad_row_active .o_ui_numpad_title:contains('Nun danket alle Gott')"),
        { trigger: `${ROOT} .o_ui_native_key[aria-label='Backspace']`, run: "click" },
        waitFor(".o_ui_numpad_row_active .o_ui_numpad_title:contains('Großer Gott')"),
        { trigger: `${ROOT} .o_ui_numpad_show`, run: "click" },
        waitFor(".o_ui_numpad_beamer:contains('12')"),
        { trigger: `${ROOT} .o_ui_numpad_row[data-target='choir']`, run: "click" },
        { trigger: `${ROOT} .o_ui_native_key:disabled:contains('5')` },
        { trigger: `${ROOT} .o_ui_native_key[aria-label='Backspace']:enabled` },

        // === Dashboard === //
        ...openTab("dashboard"),
        waitFor(`${ROOT} .o_ui_icecast_demo`),
        waitFor(`${ROOT} .o_ui_icecast_mount:nth-child(3)`),
        waitFor(`${ROOT} .o_ui_icecast_sources:contains('3')`),
        { trigger: `${ROOT} .o_ui_icecast_refresh`, run: "click" },
        { trigger: `${ROOT} .o_ui_icecast_auto`, run: "click" },
        ...["1", "2"].map((digit) => ({
            trigger: `${ROOT} .o_ui_numpad_key:contains('${digit}')`,
            run: "click",
        })),
        waitFor(`${ROOT} .o_ui_numpad_row_active .o_ui_numpad_title:contains('Großer Gott')`),

        // === Embedded views === //
        ...openTab("views"),
        waitFor(`${ROOT} .o_list_view`),
        ...["kanban", "graph", "pivot", "calendar", "form"].flatMap((type) => [
            { trigger: `${ROOT} button:contains('${type}')`, run: "click" },
            waitFor(`${ROOT} .o_${type}_view`),
        ]),
    ],
});
