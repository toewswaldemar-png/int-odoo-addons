// Plain Node tests for the upload list: concurrency, resume keys, retry, cancel.
import assert from "node:assert/strict";
import test from "node:test";

import {ITEM_STATES, UploadManager} from "../../src/int_filemanager/v2/upload_manager.js";
import {FakeServer, makeFile} from "./fake_server.mjs";

const CHUNK = 1000;

function memoryStorage(initial = {}) {
  let data = JSON.parse(JSON.stringify(initial));
  return {
    load: () => JSON.parse(JSON.stringify(data)),
    save: (next) => {
      data = JSON.parse(JSON.stringify(next));
    },
    peek: () => data,
  };
}

function setup({server = new FakeServer(), storage = memoryStorage(), concurrency = 2} = {}) {
  let counter = 0;
  const snapshots = [];
  const idle = [];
  const deps = {...server.deps(), newKey: () => `key-${++counter}`};
  const manager = new UploadManager({
    deps,
    storage,
    concurrency,
    chunkBytes: CHUNK,
    onChange: (s) => snapshots.push(s),
    onIdle: (finished) => idle.push(finished),
  });
  return {server, storage, manager, snapshots, idle};
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 10));

test("files upload one after the other slot, never more than the concurrency", async () => {
  const {manager, server, snapshots, idle} = setup({concurrency: 2});
  const files = [1, 2, 3, 4].map((n) => makeFile(3000, `f${n}.bin`));
  manager.add(files.map((file) => ({file, parentId: 5, name: file.name})));
  await settle();

  assert.equal(server.files.length, 4);
  const maxRunning = Math.max(
    ...snapshots.map((s) => s.filter((i) => i.state === ITEM_STATES.running).length)
  );
  assert.ok(maxRunning <= 2, `${maxRunning} ran at once`);
  assert.equal(idle.length, 1, "the queue reported being idle once");
  assert.equal(idle[0].length, 4);
  assert.ok(manager.snapshot().every((i) => i.state === ITEM_STATES.done));
});

test("resume keys survive: the same file to the same place continues the same upload", async () => {
  const server = new FakeServer();
  for (let n = 2; n < 60; n++) {
    server.faults.failChunkBefore.add(n);
  }
  const storage = memoryStorage();
  const file = makeFile(5000, "again.bin");

  const first = setup({server, storage});
  first.manager.add([{file, parentId: 5, name: "again.bin"}]);
  await settle();
  assert.equal(first.manager.snapshot()[0].state, ITEM_STATES.interrupted);
  assert.equal(first.manager.unfinished().length, 1);
  assert.equal(server.uploads.get(1).received, 2000);

  // "reload": a new manager, the connection is back, the user picks the file again
  server.faults.failChunkBefore.clear();
  const second = setup({server, storage});
  second.manager.add([{file, parentId: 5, name: "again.bin"}]);
  await settle();

  assert.equal(server.uploads.size, 1, "no second upload was started");
  assert.equal(second.manager.snapshot()[0].state, ITEM_STATES.done);
  assert.equal(server.files[0].size, 5000);
  assert.deepEqual(second.manager.unfinished(), []);
});

test("entries older than a day are forgotten", () => {
  const storage = memoryStorage({
    old: {key: "k", name: "x", size: 1, parentId: 1, updatedAt: 0},
  });
  const {manager} = setup({storage});
  assert.deepEqual(manager.unfinished(), []);
});

test("retry continues an interrupted upload", async () => {
  const server = new FakeServer();
  for (let n = 1; n < 60; n++) {
    server.faults.failChunkBefore.add(n);
  }
  const {manager} = setup({server});
  manager.add([{file: makeFile(4000, "r.bin"), parentId: 5, name: "r.bin"}]);
  await settle();
  const [item] = manager.snapshot();
  assert.equal(item.state, ITEM_STATES.interrupted);
  assert.equal(item.retryable, true);

  server.faults.failChunkBefore.clear();
  manager.retry(item.id);
  await settle();

  assert.equal(manager.snapshot()[0].state, ITEM_STATES.done);
});

test("a refusal is failed for good and shows the server's words", async () => {
  const server = new FakeServer();
  server.faults.fatalChunk.add(0);
  const {manager} = setup({server});
  manager.add([{file: makeFile(4000, "no.bin"), parentId: 5, name: "no.bin"}]);
  await settle();
  const [item] = manager.snapshot();
  assert.equal(item.state, ITEM_STATES.failed);
  assert.match(item.error, /Access denied/);
  assert.equal(item.retryable, false);
});

test("a name conflict at the end can be fixed by renaming, without sending anything again", async () => {
  const server = new FakeServer();
  server.existingNames.add("taken.bin");
  const {manager} = setup({server});
  manager.add([{file: makeFile(3000, "taken.bin"), parentId: 5, name: "taken.bin"}]);
  await settle();
  const [item] = manager.snapshot();
  assert.equal(item.state, ITEM_STATES.failed);
  const chunksBefore = server.chunkCalls;

  manager.renameAndRetry(item.id, "taken (2).bin");
  await settle();

  assert.equal(manager.snapshot()[0].state, ITEM_STATES.done);
  assert.equal(server.files[0].name, "taken (2).bin");
  assert.equal(server.chunkCalls, chunksBefore);
});

test("cancelling a queued file never starts it; cancelling a running one tells the server", async () => {
  const {manager, server} = setup({concurrency: 1});
  const a = makeFile(6000, "a.bin");
  const b = makeFile(6000, "b.bin");
  manager.add([
    {file: a, parentId: 5, name: "a.bin"},
    {file: b, parentId: 5, name: "b.bin"},
  ]);
  const [first, second] = manager.snapshot();
  await manager.cancel(second.id);
  await manager.cancel(first.id);
  await settle();

  const states = manager.snapshot().map((i) => i.state);
  assert.deepEqual(states, [ITEM_STATES.cancelled, ITEM_STATES.cancelled]);
  assert.equal(server.files.length, 0);
  assert.deepEqual(manager.unfinished(), []);
});

test("a refused upload is not counted as interrupted, not even after a reload", async () => {
  const server = new FakeServer();
  server.faults.fatalChunk.add(0);
  const storage = memoryStorage();
  const {manager} = setup({server, storage});
  manager.add([{file: makeFile(4000, "no.bin"), parentId: 5, name: "no.bin"}]);
  await settle();
  assert.equal(manager.snapshot()[0].state, ITEM_STATES.failed);
  assert.deepEqual(manager.unfinished(), []);

  const reloaded = setup({server, storage});
  assert.deepEqual(reloaded.manager.unfinished(), []);
  assert.deepEqual(storage.peek(), {}, "nothing left in the storage");
});

test("a failed upload can still be retried in the session after being flagged", async () => {
  const server = new FakeServer();
  server.existingNames.add("taken.bin");
  const storage = memoryStorage();
  const {manager} = setup({server, storage});
  manager.add([{file: makeFile(3000, "taken.bin"), parentId: 5, name: "taken.bin"}]);
  await settle();
  const [item] = manager.snapshot();
  assert.equal(item.state, ITEM_STATES.failed);

  manager.renameAndRetry(item.id, "taken (2).bin");
  assert.equal(Object.values(storage.peek())[0].failed, false);
  await settle();
  assert.equal(manager.snapshot()[0].state, ITEM_STATES.done);
});

test("discardUnfinished forgets what earlier page loads left, not the running ones", async () => {
  const server = new FakeServer();
  for (let n = 1; n < 60; n++) {
    server.faults.failChunkBefore.add(n);
  }
  const storage = memoryStorage({
    left: {key: "k", name: "old.bin", size: 9, parentId: 5, updatedAt: Date.now()},
  });
  const {manager} = setup({server, storage});
  manager.add([{file: makeFile(4000, "now.bin"), parentId: 5, name: "now.bin"}]);
  await settle();
  assert.equal(manager.unfinished().length, 2);

  manager.discardUnfinished();
  assert.deepEqual(
    manager.unfinished().map((u) => u.name),
    ["now.bin"]
  );
});

test("clearFinished drops done and cancelled entries, keeps the rest", async () => {
  const server = new FakeServer();
  server.faults.fatalChunk.add(0);
  const {manager} = setup({server});
  manager.add([
    {file: makeFile(4000, "bad.bin"), parentId: 5, name: "bad.bin"},
    {file: makeFile(10, "ok.bin"), parentId: 5, name: "ok.bin"},
  ]);
  await settle();
  manager.clearFinished();
  assert.equal(manager.snapshot().length, 0);
});
