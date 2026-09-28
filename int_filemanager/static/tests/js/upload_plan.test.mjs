// Plain Node tests for turning dropped files into an upload plan.
import assert from "node:assert/strict";
import test from "node:test";

import {
  CONFLICT_ACTIONS,
  planUpload,
} from "../../src/int_filemanager/v2/upload_plan.js";

/** A tiny in-memory tree answering existing_names / create_folder like the server. */
function fakeTree(initial = []) {
  // Initial: [{id, parent, name, is_dir, rev}]
  const nodes = initial.map((n) => ({...n}));
  let nextId = 1000;
  const calls = [];
  return {
    nodes,
    calls,
    deps: {
      newKey: () => `key-${nextId}`,
      call: async (model, method, kwargs) => {
        calls.push({method, kwargs});
        if (method === "existing_names") {
          const wanted = new Set(kwargs.names.map((n) => n.toLowerCase()));
          return nodes
            .filter((n) => n.parent === kwargs.parent_id && wanted.has(n.name.toLowerCase()))
            .map((n) => ({
              id: n.id,
              name: n.name,
              is_dir: n.is_dir,
              current_revision_id: n.rev || false,
            }));
        }
        if (method === "create_folder") {
          const node = {id: nextId++, parent: kwargs.parent_id, name: kwargs.name, is_dir: true};
          nodes.push(node);
          return {node_id: node.id};
        }
        throw new Error(method);
      },
    },
  };
}

const file = (name) => new File(["x"], name);
const never = async () => {
  throw new Error("nobody should be asked");
};

test("plain files into a folder without clashes need no question", async () => {
  const tree = fakeTree();
  const a = file("a.txt");
  const b = file("b.txt");
  const plan = await planUpload(
    [{file: a, path: []}, {file: b, path: []}],
    1,
    tree.deps,
    never
  );
  assert.deepEqual(
    plan.map((p) => [p.name, p.parentId, p.nodeId]),
    [["a.txt", 1, undefined], ["b.txt", 1, undefined]]
  );
});

test("a dropped folder tree is created and its files planned into the right folders", async () => {
  const tree = fakeTree();
  const plan = await planUpload(
    [
      {file: file("1.jpg"), path: ["Photos"]},
      {file: file("2.jpg"), path: ["Photos", "2026"]},
      {file: file("root.txt"), path: []},
    ],
    1,
    tree.deps,
    never
  );
  const folders = tree.nodes.filter((n) => n.is_dir);
  assert.deepEqual(
    folders.map((n) => n.name).sort(),
    ["2026", "Photos"]
  );
  const photos = folders.find((n) => n.name === "Photos");
  const year = folders.find((n) => n.name === "2026");
  assert.equal(year.parent, photos.id);
  const parentOf = Object.fromEntries(plan.map((p) => [p.name, p.parentId]));
  assert.deepEqual(parentOf, {
    "1.jpg": photos.id,
    "2.jpg": year.id,
    "root.txt": 1,
  });
  // Inside brand-new folders nothing can clash: the server is not asked
  assert.equal(
    tree.calls.filter((c) => c.method === "existing_names" && c.kwargs.parent_id === year.id).length,
    0
  );
});

test("an existing folder is merged into, not duplicated", async () => {
  const tree = fakeTree([{id: 50, parent: 1, name: "photos", is_dir: true}]);
  const plan = await planUpload(
    [{file: file("new.jpg"), path: ["Photos"]}],
    1,
    tree.deps,
    never
  );
  assert.equal(plan[0].parentId, 50);
  assert.equal(tree.nodes.filter((n) => n.is_dir).length, 1);
});

test("a file where a folder should go is an error", async () => {
  const tree = fakeTree([{id: 50, parent: 1, name: "Photos", is_dir: false}]);
  await assert.rejects(
    () => planUpload([{file: file("x.jpg"), path: ["Photos"]}], 1, tree.deps, never),
    /already exists/
  );
});

test("conflicts are asked once, all together, and honoured per file", async () => {
  const tree = fakeTree([
    {id: 10, parent: 1, name: "a.txt", is_dir: false, rev: 77},
    {id: 11, parent: 1, name: "b.txt", is_dir: false, rev: 78},
    {id: 12, parent: 1, name: "c.txt", is_dir: false, rev: 79},
  ]);
  const a = file("A.TXT");
  const b = file("b.txt");
  const c = file("c.txt");
  const d = file("d.txt");
  let asked = null;
  const plan = await planUpload(
    [a, b, c, d].map((f) => ({file: f, path: []})),
    1,
    tree.deps,
    async (conflicts) => {
      asked = conflicts;
      return new Map([
        [a, CONFLICT_ACTIONS.replace],
        [b, CONFLICT_ACTIONS.keepBoth],
        [c, CONFLICT_ACTIONS.skip],
      ]);
    }
  );

  assert.deepEqual(
    asked.map((x) => x.name),
    ["A.TXT", "b.txt", "c.txt"]
  );
  const byName = Object.fromEntries(plan.map((p) => [p.name, p]));
  assert.equal(byName["A.TXT"].nodeId, 10);
  assert.equal(byName["A.TXT"].baseRevisionId, 77);
  assert.equal(byName["b (2).txt"].nodeId, undefined);
  assert.ok(!("c.txt" in byName), "skipped files are not planned");
  assert.equal(byName["d.txt"].parentId, 1);
});

test("keep both never picks a name that another file of the same drop also wants", async () => {
  const tree = fakeTree([{id: 10, parent: 1, name: "a.txt", is_dir: false, rev: 1}]);
  const first = file("a.txt");
  const second = file("a (2).txt");
  const plan = await planUpload(
    [first, second].map((f) => ({file: f, path: []})),
    1,
    tree.deps,
    async () => new Map([[first, CONFLICT_ACTIONS.keepBoth]])
  );
  const names = plan.map((p) => p.name);
  assert.equal(new Set(names.map((n) => n.toLowerCase())).size, names.length);
});

test("replacing a folder with a file is not possible: it becomes keep-both", async () => {
  const tree = fakeTree([{id: 10, parent: 1, name: "thing", is_dir: true}]);
  const f = file("thing");
  const plan = await planUpload(
    [{file: f, path: []}],
    1,
    tree.deps,
    async () => new Map([[f, CONFLICT_ACTIONS.replace]])
  );
  assert.equal(plan[0].nodeId, undefined);
  assert.equal(plan[0].name, "thing (2)");
});

test("no answer means skip", async () => {
  const tree = fakeTree([{id: 10, parent: 1, name: "a.txt", is_dir: false, rev: 1}]);
  const plan = await planUpload(
    [{file: file("a.txt"), path: []}],
    1,
    tree.deps,
    async () => new Map()
  );
  assert.deepEqual(plan, []);
});
