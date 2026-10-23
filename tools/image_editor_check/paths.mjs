// Where things are. The places in this repository come from the place of this file; what is not in
// the repository is looked for, or named by two environment variables:
//   ODOO_SRC                      the checkout of Odoo 19 (Owl and the viewer of the core come from it)
//   IMAGE_EDITOR_CHECK_MODULES    a folder that has `node_modules` with jsdom and @napi-rs/canvas
//                                 (used when `npm install` was not run in this folder)
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

export const HERE = path.dirname(fileURLToPath(import.meta.url));
export const REPO = path.resolve(HERE, "../..");
export const MODULE_SRC = path.join(REPO, "int_filemanager/static/src");
export const EDITOR_SRC = path.join(MODULE_SRC, "image_editor");
export const VIEWER_SRC = path.join(MODULE_SRC, "int_filemanager/file_viewer");
export const FABRIC = path.join(REPO, "int_filemanager/static/lib/fabric/fabric.js");

/** Where the tests put the pictures they make, so that they can be looked at (not in the repository). */
export const OUT = path.join(os.tmpdir(), "image_editor_check");
fs.mkdirSync(OUT, { recursive: true });

/** @returns {string} the checkout of Odoo, found next to or inside this repository, or named by `ODOO_SRC` */
export function odooRoot() {
    const candidates = [process.env.ODOO_SRC, path.join(REPO, "docs/odoo"), path.resolve(REPO, "../odoo")].filter(Boolean);
    const found = candidates.find((dir) => fs.existsSync(path.join(dir, "addons/web/static/lib/owl/owl.js")));
    if (!found) {
        throw new Error(`No source of Odoo 19 found. Set ODOO_SRC. Looked in: ${candidates.join(", ")}`);
    }
    return found;
}

/** @returns {string} `addons/web/static` of that checkout */
export function odooWeb() {
    return path.join(odooRoot(), "addons/web/static");
}

/** Loads a package from this folder, or from the folder named by `IMAGE_EDITOR_CHECK_MODULES`. */
export function requireModule(name) {
    const bases = [HERE, process.env.IMAGE_EDITOR_CHECK_MODULES].filter(Boolean);
    for (const base of bases) {
        try {
            return createRequire(path.join(base, "anchor.js"))(name);
        } catch (error) {
            if (error.code !== "MODULE_NOT_FOUND") {
                throw error;
            }
        }
    }
    throw new Error(
        `The package ${name} is missing. Run "npm install" in ${HERE}, or set ` +
            "IMAGE_EDITOR_CHECK_MODULES to a folder that has node_modules with jsdom and @napi-rs/canvas."
    );
}
