// `node --import ./register.mjs components.check.mjs`: lets the sources of the module run as they are, with their
// `@odoo/owl` and `@web/...` imports (see loader.mjs).
import { register } from "node:module";

register("./loader.mjs", import.meta.url);
