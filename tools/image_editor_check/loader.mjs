// Hooks for the module loader of Node. They let the sources of the module run unchanged:
//   - `@int_filemanager/<path>` is a file of `int_filemanager/static/src/`, `@int_filemanager_image_editor/<path>`
//     one of `int_filemanager_image_editor/static/src/`,
//   - `./picture` in the component is the shim (shim_picture.mjs),
//   - `@web/...`, `@odoo/...`, `@mail/...` are stand-ins that hold what the sources use,
//   - with REAL_OWL the stand-in for `@odoo/owl` hands out the real Owl (`globalThis.owl`, loaded by
//     the check), with REAL_CORE_VIEWER the viewer of the core is the real file of the Odoo source.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { EDITOR_MODULE_SRC, MODULE_SRC, odooWeb } from "./paths.mjs";

const SHIM = new URL("./shim_picture.mjs", import.meta.url).href;
const REAL_FILES = [MODULE_SRC, EDITOR_MODULE_SRC].map((dir) => dir.replaceAll("\\", "/"));

export async function resolve(specifier, context, next) {
    if (specifier === "./picture" && context.parentURL?.endsWith("document_image_editor.js")) {
        return { url: SHIM, shortCircuit: true };
    }
    if (process.env.REAL_CORE_VIEWER && specifier === "@web/core/file_viewer/file_viewer") {
        const file = path.join(odooWeb(), "src/core/file_viewer/file_viewer.js");
        return { url: pathToFileURL(file).href, shortCircuit: true };
    }
    if (specifier === "@int_filemanager/int_filemanager/views/list/document_list_controller") {
        return { url: "stub:upload_route", shortCircuit: true };
    }
    if (specifier.startsWith("@int_filemanager_image_editor/")) {
        const file = path.join(EDITOR_MODULE_SRC, `${specifier.slice("@int_filemanager_image_editor/".length)}.js`);
        return { url: pathToFileURL(file).href, shortCircuit: true };
    }
    if (specifier.startsWith("@int_filemanager/")) {
        const file = path.join(MODULE_SRC, `${specifier.slice("@int_filemanager/".length)}.js`);
        return { url: pathToFileURL(file).href, shortCircuit: true };
    }
    if (specifier.startsWith("@web/") || specifier.startsWith("@odoo/") || specifier.startsWith("@mail/")) {
        return { url: `stub:${specifier}`, shortCircuit: true };
    }
    if ((specifier.startsWith("./") || specifier.startsWith("../")) && !path.extname(specifier)) {
        const parent = fileURLToPath(context.parentURL);
        return { url: pathToFileURL(path.resolve(path.dirname(parent), `${specifier}.js`)).href, shortCircuit: true };
    }
    return next(specifier, context);
}

const OWL_STUB = `
    const o = globalThis.owl;
    export const { Component, useState, useRef, onMounted, onWillDestroy, useExternalListener, useEnv, xml, App,
        mount, EventBus, reactive, useEffect, onWillStart, onWillUpdateProps, onPatched, markup, useSubEnv,
        useComponent } = o;
`;

const DROPDOWN_STUB = `
    const o = globalThis.owl;
    export class Dropdown extends o.Component {
        static template = o.xml\`<div class="stub-dropdown"><t t-slot="default"/><t t-slot="content"/></div>\`;
    }
    export class DropdownItem extends o.Component {
        static template = o.xml\`<div class="stub-dropdown-item" t-att="props.attrs"
            t-on-click="() => props.onSelected and props.onSelected()"><t t-slot="default"/></div>\`;
    }
`;

const DIALOG_STUB = `
    const o = globalThis.owl;
    export class Dialog extends o.Component {
        static template = o.xml\`<div class="stub-dialog"><div class="stub-dialog-title" t-esc="props.title"/>
            <t t-slot="default"/><t t-slot="footer"/></div>\`;
    }
`;

const PLAIN_STUB = `
    export const _t = (s) => s;
    export const registry = { category: () => ({ add() {}, get() {}, remove() {} }) };
    export class Component { constructor(props) { this.props = props; this.setup(); } setup() {} }
    export const useState = (x) => x;
    export const useRef = (name) => globalThis.__refs[name];
    export const onMounted = () => {};
    export const onWillDestroy = () => {};
    export const useExternalListener = () => {};
    export const useService = (name) => globalThis.__services[name];
    export const useEnv = () => ({ services: {} });
    export const FileModelMixin = (Base) => class extends Base {
        get defaultSource() { return this.src || ""; }
        get isViewable() { return true; }
        get urlQueryParams() { return {}; }
    };
    export const imageUrl = () => "";
    export const url = () => "";
    export const LazyComponent = {};
    export const routerBus = new EventTarget();
    export const Dialog = {};
    export const downloadFile = () => {};
    export const useAutofocus = () => {};
    export const hidePDFJSButtons = () => {};
    export const localization = { direction: "ltr" };
    export const browser = {
        setTimeout: (...a) => setTimeout(...a),
        clearTimeout: (...a) => clearTimeout(...a),
    };
    export const DEFAULT_COLORS = [];
    export const Dropdown = {};
    export const DropdownItem = {};
    export const CheckBox = {};
    export const useDropdownState = () => ({});
    export const ConfirmationDialog = {};
    export const MODEL = "int.filemanager.document";
    export const UPLOAD_ROUTE = "/x";
`;

export async function load(url, context, next) {
    if (url === "stub:upload_route") {
        return { format: "module", shortCircuit: true, source: `export const UPLOAD_ROUTE = "/int_filemanager/upload";` };
    }
    if (process.env.REAL_OWL) {
        if (url === "stub:@odoo/owl") {
            return { format: "module", shortCircuit: true, source: OWL_STUB };
        }
        if (url === "stub:@web/core/dropdown/dropdown" || url === "stub:@web/core/dropdown/dropdown_item") {
            return { format: "module", shortCircuit: true, source: DROPDOWN_STUB };
        }
        if (url === "stub:@web/core/dialog/dialog") {
            return { format: "module", shortCircuit: true, source: DIALOG_STUB };
        }
    }
    if (url.startsWith("stub:")) {
        return { format: "module", shortCircuit: true, source: PLAIN_STUB };
    }
    // The sources are modules, but their folders have no package.json that says so (they are files of
    // an Odoo module): say it here, so that Node does not guess and warn.
    if (url.startsWith("file:") && url.endsWith(".js")) {
        const file = fileURLToPath(url).replaceAll("\\", "/");
        const odoo = odooWeb().replaceAll("\\", "/");
        if (REAL_FILES.some((dir) => file.startsWith(dir)) || file.startsWith(odoo)) {
            return { format: "module", shortCircuit: true, source: fs.readFileSync(file, "utf8") };
        }
    }
    return next(url, context);
}
