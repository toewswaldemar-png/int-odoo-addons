// Runs the checks of the picture editor: `node run.mjs` runs all, `node run.mjs viewer cursors` some.
// Every check is a script of its own (they share what is made in `env.mjs`); this counts its lines
// "PASS" and "FAIL", and a script that stops with an error counts as failed as well.
import { spawnSync } from "node:child_process";
import { HERE } from "./paths.mjs";

// name, file, environment: REAL_OWL mounts the components with the Owl of Odoo, REAL_CORE_VIEWER
// loads the viewer of the core in place of a stand-in.
const CHECKS = [
    ["logic", "logic.check.mjs", {}],
    ["component", "component.check.mjs", {}],
    ["templates", "templates.check.mjs", { REAL_OWL: "1" }],
    ["svg", "svg_import.check.mjs", {}],
    ["viewer", "viewer.check.mjs", { REAL_OWL: "1", REAL_CORE_VIEWER: "1" }],
    ["cursors", "cursors.check.mjs", {}],
    ["sharpness", "sharpness.check.mjs", {}],
    ["text", "text_handles.check.mjs", {}],
];

const wanted = process.argv.slice(2);
const unknown = wanted.filter((name) => !CHECKS.some(([known]) => known === name));
if (unknown.length) {
    console.error(`Unknown: ${unknown.join(", ")}. Known: ${CHECKS.map(([name]) => name).join(", ")}`);
    process.exit(2);
}

let failed = 0;
for (const [name, file, extra] of CHECKS) {
    if (wanted.length && !wanted.includes(name)) {
        continue;
    }
    const run = spawnSync(process.execPath, ["--import", "./register.mjs", file], {
        cwd: HERE,
        env: { ...process.env, ...extra },
        encoding: "utf8",
        maxBuffer: 64 * 1024 * 1024,
        timeout: 180_000,
    });
    const lines = (run.stdout || "").split("\n");
    const passes = lines.filter((line) => line.startsWith("PASS ")).length;
    const fails = lines.filter((line) => line.startsWith("FAIL "));
    const broke = run.status !== 0 || run.error;
    console.log(`${broke || fails.length ? "FAIL" : "ok  "} ${name.padEnd(10)} ${passes} passed, ${fails.length} failed`);
    for (const line of fails) {
        console.log(`       ${line.slice(0, 200)}`);
    }
    if (broke) {
        const message = (run.stderr || String(run.error || "")).split("\n").filter(Boolean).slice(-6).join("\n       ");
        console.log(`       stopped with status ${run.status}:\n       ${message}`);
    }
    failed += fails.length + (broke ? 1 : 0);
}
console.log(failed ? `\n${failed} problem(s)` : "\nAll checks passed");
process.exit(failed ? 1 : 0);
