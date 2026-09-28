// Plain Node tests for reading dropped folders and chosen directories.
import assert from "node:assert/strict";
import test from "node:test";

import {entriesFromFiles, startDropWalk} from "../../src/int_filemanager/v2/folder_walk.js";
import {planUpload} from "../../src/int_filemanager/v2/upload_plan.js";

const fileEntry = (name) => ({
  isFile: true,
  isDirectory: false,
  name,
  file: (ok) => ok(new File(["x"], name)),
});

/** A directory entry whose reader hands out `batchSize` children per call, like browsers. */
const dirEntry = (name, children, batchSize = 2) => ({
  isFile: false,
  isDirectory: true,
  name,
  createReader: () => {
    let position = 0;
    return {
      readEntries: (ok) => {
        const batch = children.slice(position, position + batchSize);
        position += batchSize;
        ok(batch);
      },
    };
  },
});

const item = (entry) => ({kind: "file", webkitGetAsEntry: () => entry, getAsFile: () => null});

test("a chosen directory (webkitRelativePath) becomes folder paths", () => {
  const a = new File(["x"], "a.jpg");
  Object.defineProperty(a, "webkitRelativePath", {value: "Photos/2026/a.jpg"});
  const b = new File(["x"], "b.txt");
  Object.defineProperty(b, "webkitRelativePath", {value: "Photos/b.txt"});
  const c = new File(["x"], "c.txt"); // Plain multi-select: no relative path
  const junk = new File(["x"], ".DS_Store");
  Object.defineProperty(junk, "webkitRelativePath", {value: "Photos/.DS_Store"});

  const entries = entriesFromFiles([a, b, c, junk]);

  assert.deepEqual(
    entries.map((e) => [e.file.name, e.path]),
    [["a.jpg", ["Photos", "2026"]], ["b.txt", ["Photos"]], ["c.txt", []]]
  );
});

test("a dropped folder is walked completely, also past the first reader batch", async () => {
  const tree = dirEntry("Docs", [
    fileEntry("1.txt"),
    fileEntry("2.txt"),
    fileEntry("3.txt"), // Beyond the first batch of two
    dirEntry("sub", [fileEntry("deep.txt")]),
    fileEntry("Thumbs.db"),
  ]);
  const drop = {items: [item(tree), item(fileEntry("loose.txt"))]};

  const entries = await startDropWalk(drop)();

  assert.deepEqual(
    entries.map((e) => [e.file.name, e.path.join("/")]).sort(),
    [
      ["1.txt", "Docs"],
      ["2.txt", "Docs"],
      ["3.txt", "Docs"],
      ["deep.txt", "Docs/sub"],
      ["loose.txt", ""],
    ]
  );
});

test("an empty dropped folder is reported so it can be created", async () => {
  const entries = await startDropWalk({items: [item(dirEntry("Empty", []))]})();
  assert.deepEqual(entries, [{folderOnly: true, path: ["Empty"]}]);
});

test("browsers without entry support fall back to the plain file list", async () => {
  const f = new File(["x"], "plain.txt");
  const drop = {items: [{kind: "file", getAsFile: () => f}], files: [f]};
  const entries = await startDropWalk(drop)();
  assert.equal(entries[0].file, f);
});

test("empty folders flow through the plan and get created", async () => {
  const created = [];
  let next = 100;
  const deps = {
    newKey: () => "k",
    call: async (model, method, kwargs) => {
      if (method === "existing_names") {
        return [];
      }
      created.push(kwargs.name);
      return {node_id: next++};
    },
  };
  const plan = await planUpload(
    [{folderOnly: true, path: ["A", "B"]}],
    1,
    deps,
    async () => new Map()
  );
  assert.deepEqual(created, ["A", "B"]);
  assert.deepEqual(plan, []);
});
