// `node --import ./register.mjs check.mjs`: lets the sources of the module run as they are, with
// their `@int_filemanager/...` and `@web/...` imports (see loader.mjs).
import { register } from "node:module";

register("./loader.mjs", import.meta.url);
