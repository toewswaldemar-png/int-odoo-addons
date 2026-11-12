// Hooks for the module loader of Node: the sources of int_workbench run unchanged.
//   - `./name` is `name.js` of the module,
//   - `@odoo/owl` is the real Owl (globalThis.owl, loaded by the check),
//   - `@web/...` are small stand-ins for what the sources use: the action registry, the service hook, `_t`, the user.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { MODULE_SRC } from "./paths.mjs";

const SRC = MODULE_SRC.replaceAll("\\", "/");

const STUBS = {
    "@odoo/owl": `
        const o = globalThis.owl;
        export const { Component, onMounted, onPatched, onWillDestroy, onWillStart, onWillUnmount, useRef, useState } = o;
    `,
    // the list of Odoo and what the list of process values takes from it: only the parts it uses
    "@web/views/list/list_controller": `export const ListController = globalThis.__ListController;`,
    "@web/views/list/list_view": `export const listView = { type: "list", Controller: globalThis.__ListController };`,
    "@web/views/fields/standard_field_props": `
        export const standardFieldProps = { name: String, record: Object, readonly: { type: Boolean, optional: true } };
    `,
    // the number of the user: the decimal point is a comma here, so that the check shows that the widget uses the format of the user and
    // not the point of JavaScript
    "@web/views/fields/formatters": `
        export function formatFloat(value, options = {}) {
            const digits = options.digits ? options.digits[1] : 2;
            let text = (Math.round(value * 10 ** digits) / 10 ** digits).toFixed(digits);
            if (options.trailingZeros === false && text.includes(".")) {
                text = text.replace(/0+$/, "").replace(/[.]$/, "");
            }
            return text.replace(".", ",");
        }
    `,
    "@web/views/fields/parsers": `
        export class InvalidNumberError extends Error {}
        export function parseFloat(value) {
            const text = String(value).trim().replace(",", ".");
            if (!/^-?[0-9]+([.][0-9]+)?$/.test(text)) {
                throw new InvalidNumberError(value + " is not a correct number");
            }
            return Number(text);
        }
    `,
    // the popover of Odoo: the component is mounted into the page with the props it is given and a close() (the core adds the position,
    // Escape and the click away, which a check without a browser does not play). The templates are those of the popover.
    "@web/core/popover/popover_hook": `
        export function usePopover(Component, options = {}) {
            let current = null;
            const close = () => {
                if (current) {
                    current.app.destroy();
                    current.root.remove();
                    current = null;
                }
            };
            globalThis.owl.onWillDestroy(close);
            return {
                open(target, props) {
                    close();
                    const root = document.createElement("div");
                    root.className = "o_popover";
                    document.body.appendChild(root);
                    const app = new globalThis.owl.App(Component, { env: {}, props: { ...props, close }, dev: true });
                    app.addTemplates(globalThis.__popoverTemplates);
                    current = { app, root, target, options };
                    globalThis.__popoverOpened.push({ target, props, options });
                    return app.mount(root);
                },
                close,
                get isOpen() {
                    return !!current;
                },
            };
        }
    `,
    // the decimal key of the numpad: nothing to do without a browser keyboard
    "@web/views/fields/numpad_decimal_hook": `export function useNumpadDecimal() {}`,
    "@web/core/utils/timing": `
        export function useDebounced(callback, delay) {
            let timer = null;
            globalThis.owl.onWillDestroy(() => clearTimeout(timer));
            return (...args) => {
                clearTimeout(timer);
                timer = setTimeout(() => callback(...args), delay);
            };
        }
    `,
    "@web/core/registry": `
        export const registry = {
            category: (name) => ({ add: (key, value) => globalThis.__registered.push({ category: name, key, value }) }),
        };
    `,
    "@web/core/utils/hooks": `
        export const useService = (name) => globalThis.__services[name];
    `,
    // the user of Odoo: only the groups are asked
    "@web/core/user": `
        export const user = { hasGroup: (group) => globalThis.__user.hasGroup(group) };
    `,
    // like the _t of Odoo: %s in order, or %(name)s from an object
    "@web/core/l10n/translation": `
        export function _t(source, ...subs) {
            if (subs.length === 1 && subs[0] && typeof subs[0] === "object" && !Array.isArray(subs[0])) {
                return source.replace(/%\\((\\w+)\\)s/g, (_, key) => String(subs[0][key]));
            }
            let i = 0;
            return source.replace(/%s/g, () => String(subs[i++]));
        }
    `,
};

export async function resolve(specifier, context, next) {
    if (specifier in STUBS) {
        return { url: `stub:${specifier}`, shortCircuit: true };
    }
    if (specifier.startsWith("@odoo/") || specifier.startsWith("@web/")) {
        throw new Error(`The source imports ${specifier}, which this check does not stand in for`);
    }
    if ((specifier.startsWith("./") || specifier.startsWith("../")) && !path.extname(specifier)) {
        const parent = fileURLToPath(context.parentURL);
        return { url: pathToFileURL(path.resolve(path.dirname(parent), `${specifier}.js`)).href, shortCircuit: true };
    }
    return next(specifier, context);
}

export async function load(url, context, next) {
    if (url.startsWith("stub:")) {
        return { format: "module", shortCircuit: true, source: STUBS[url.slice(5)] };
    }
    // the sources are modules, but their folder has no package.json that says so (it is a folder of an Odoo module)
    if (url.startsWith("file:") && url.endsWith(".js") && fileURLToPath(url).replaceAll("\\", "/").startsWith(SRC)) {
        return { format: "module", shortCircuit: true, source: fs.readFileSync(fileURLToPath(url), "utf8") };
    }
    return next(url, context);
}
