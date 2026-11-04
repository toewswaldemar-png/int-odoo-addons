// Where things are: the module comes from the place of this file; the checkout of Odoo 19 (the real Owl comes from it) is
// looked for in `docs/odoo`, next to the repository, or named by ODOO_SRC.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const HERE = path.dirname(fileURLToPath(import.meta.url));
export const REPO = path.resolve(HERE, "../..");
export const MODULE_SRC = path.join(REPO, "int_regler/static/src");

export function owlFile() {
    const candidates = [process.env.ODOO_SRC, path.join(REPO, "docs/odoo"), path.resolve(REPO, "../odoo")].filter(Boolean);
    const found = candidates
        .map((dir) => path.join(dir, "addons/web/static/lib/owl/owl.js"))
        .find((file) => fs.existsSync(file));
    if (!found) {
        throw new Error(`No source of Odoo 19 found. Set ODOO_SRC. Looked in: ${candidates.join(", ")}`);
    }
    return found;
}
