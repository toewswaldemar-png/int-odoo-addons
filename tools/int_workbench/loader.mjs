// Hooks for the module loader of Node: the sources of int_workbench run unchanged.
//   - `./name` is `name.js` of the module,
//   - `@odoo/owl` is the real Owl (globalThis.owl, loaded by the check),
//   - `@web/...` are small stand-ins for what the sources use: the list of Odoo, the debounce, the registry, the service hook, `_t`.
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
    // like debounce / useDebounced of web/static/src/core/utils/timing.js: the options immediate (leading) and trailing are the same;
    // with both, the call at the end is made only if there was a call during the wait
    "@web/core/utils/timing": `
        export function useDebounced(callback, delay, { immediate = false, trailing = !immediate } = {}) {
            let handle = null;
            let lastArgs = null;
            globalThis.owl.onWillDestroy(() => clearTimeout(handle));
            return (...args) => {
                if (immediate && !handle) {
                    callback(...args);
                } else {
                    lastArgs = args;
                }
                clearTimeout(handle);
                handle = setTimeout(() => {
                    handle = null;
                    if (trailing && lastArgs) {
                        const last = lastArgs;
                        lastArgs = null;
                        callback(...last);
                    }
                }, delay);
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
