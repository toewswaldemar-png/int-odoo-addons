// Plain Node tests for the chunked upload protocol against an in-memory server.
import assert from "node:assert/strict";
import test from "node:test";

import {
  ChunkedUpload,
  UPLOAD_STATES,
  UploadCancelled,
} from "../../src/int_filemanager/v2/chunk_upload.js";
import {FakeServer, fatal, makeFile, retryable} from "./fake_server.mjs";

const CHUNK = 1000; // Small pieces keep the tests fast

function upload(server, file, extra = {}) {
  const sleeps = [];
  const snapshots = [];
  const instance = new ChunkedUpload({
    file,
    target: {parentId: 7, name: file.name},
    operationKey: extra.key || "op-1",
    deps: server.deps({sleepLog: sleeps}),
    chunkBytes: CHUNK,
    onChange: (snap) => snapshots.push(snap),
    ...extra,
  });
  return {instance, sleeps, snapshots};
}

test("a small file goes in one request, base64, no upload row", async () => {
  const server = new FakeServer();
  const file = makeFile(500, "small.bin");
  const {instance} = upload(server, file);

  const result = await instance.run();

  assert.equal(result.node_id, 1);
  assert.deepEqual(
    server.calls.map((c) => c.method),
    ["create_file"]
  );
  assert.equal(server.files[0].size, 500);
  assert.equal(instance.state, UPLOAD_STATES.done);
  assert.equal(instance.snapshot.sent, 500);
});

test("an empty file is a small file (the server has no chunk to receive)", async () => {
  const server = new FakeServer();
  const {instance} = upload(server, makeFile(0, "empty.txt"));
  await instance.run();
  assert.equal(server.files[0].size, 0);
  assert.deepEqual(
    server.calls.map((c) => c.method),
    ["create_file"]
  );
});

test("a small new version uses create_new_revision with its base revision", async () => {
  const server = new FakeServer();
  const file = makeFile(10, "v2.bin");
  const instance = new ChunkedUpload({
    file,
    target: {nodeId: 5, baseRevisionId: 42},
    operationKey: "op-rev",
    deps: server.deps(),
    chunkBytes: CHUNK,
  });
  await instance.run();
  assert.equal(server.calls[0].method, "create_new_revision");
  assert.equal(server.calls[0].kwargs.base_revision_id, 42);
});

test("a big file is sent in order and arrives intact", async () => {
  const server = new FakeServer();
  const file = makeFile(3500, "big.bin");
  const {instance, snapshots} = upload(server, file);

  const result = await instance.run();

  assert.equal(result.node_id, 1);
  assert.equal(server.files[0].size, 3500);
  assert.deepEqual(
    server.files[0].bytes,
    Buffer.from(await file.arrayBuffer())
  );
  // 4 pieces: 1000, 1000, 1000, 500
  assert.equal(server.chunkCalls, 4);
  const sent = snapshots.map((s) => s.sent);
  assert.deepEqual(sent, [...sent].sort((a, b) => a - b));
  assert.equal(snapshots.at(-1).state, UPLOAD_STATES.done);
});

test("pause stops after the running piece and resume continues from the server's count", async () => {
  const server = new FakeServer();
  const file = makeFile(5000, "pause.bin");
  const {instance} = upload(server, file);
  // Pause as soon as the second piece is in
  const originalOnChange = instance.onChange;
  let pausedOnce = false;
  instance.onChange = (snap) => {
    originalOnChange(snap);
    if (snap.sent >= 2000 && !pausedOnce) {
      pausedOnce = true;
      instance.pause();
    }
  };

  const first = await instance.run();
  assert.equal(first, null);
  assert.equal(instance.state, UPLOAD_STATES.paused);
  assert.equal(server.uploads.get(1).received, 2000);

  const result = await instance.run();
  assert.equal(result.node_id, 1);
  assert.deepEqual(server.files[0].bytes, Buffer.from(await file.arrayBuffer()));
  // The first two pieces were not sent again
  assert.equal(server.chunkCalls, 5);
});

test("after a lost connection a NEW client resumes with the same key", async () => {
  const server = new FakeServer();
  const file = makeFile(5000, "resume.bin");
  // Pieces 0 and 1 arrive, piece 2 never gets through, every retry fails too
  for (let n = 2; n < 40; n++) {
    server.faults.failChunkBefore.add(n);
  }
  const first = upload(server, file);
  await assert.rejects(() => first.instance.run(), /connection lost/);
  assert.equal(first.instance.state, UPLOAD_STATES.interrupted);
  assert.equal(server.uploads.get(1).received, 2000);
  assert.ok(first.sleeps.length >= 5, "it backed off before giving up");

  // "page reload": all the client keeps is the operation key and the file
  server.faults.failChunkBefore.clear();
  const second = upload(server, file, {key: "op-1"});
  const result = await second.instance.run();

  assert.equal(result.node_id, 1);
  assert.equal(server.uploads.size, 1, "the same upload was continued, not a new one");
  assert.deepEqual(server.files[0].bytes, Buffer.from(await file.arrayBuffer()));
});

test("a piece whose answer got lost is not sent twice", async () => {
  const server = new FakeServer();
  const file = makeFile(3000, "lost-answer.bin");
  server.faults.failChunkAfter.add(1); // Server got piece 1, client never heard
  const {instance} = upload(server, file);

  const result = await instance.run();

  assert.equal(result.node_id, 1);
  assert.deepEqual(server.files[0].bytes, Buffer.from(await file.arrayBuffer()));
  assert.equal(server.chunkCalls, 3, "no piece was sent again");
});

test("a refusal is final: no retries, state failed", async () => {
  const server = new FakeServer();
  server.faults.fatalChunk.add(1);
  const {instance, sleeps} = upload(server, makeFile(4000));

  await assert.rejects(() => instance.run(), /Access denied/);

  assert.equal(instance.state, UPLOAD_STATES.failed);
  assert.equal(sleeps.length, 0);
});

test("a transient failure of init is retried", async () => {
  const server = new FakeServer();
  server.faults.callFailures.push({method: "init_upload", error: retryable("gateway")});
  const {instance, sleeps} = upload(server, makeFile(3000));

  const result = await instance.run();

  assert.equal(result.node_id, 1);
  assert.equal(sleeps.length, 1);
});

test("cancel raises UploadCancelled and discard tells the server", async () => {
  const server = new FakeServer();
  const {instance} = upload(server, makeFile(5000));
  instance.onChange = (snap) => {
    if (snap.sent >= 1000) {
      instance.cancel();
    }
  };

  await assert.rejects(() => instance.run(), UploadCancelled);
  assert.equal(instance.state, UPLOAD_STATES.cancelled);
  await instance.discard();

  assert.equal(server.uploads.size, 0);
  assert.ok(server.calls.some((c) => c.method === "cancel_upload"));
});

test("a big file finished by the cron is polled until it is done", async () => {
  const server = new FakeServer({largeFileThreshold: 100});
  const {instance, sleeps} = upload(server, makeFile(3000));
  // The "cron" runs after the second poll
  const deps = instance.deps;
  const originalCall = deps.call;
  let polls = 0;
  deps.call = async (model, method, kwargs) => {
    if (method === "upload_status" && instance.state === UPLOAD_STATES.finishing) {
      polls++;
      if (polls === 2) {
        server.runCron();
      }
    }
    return originalCall(model, method, kwargs);
  };

  const result = await instance.run();

  assert.equal(result.node_id, 1);
  assert.ok(sleeps.length >= 1, "it waited between polls");
});

test("a name conflict at finish can be resolved with a new name, no byte re-sent", async () => {
  const server = new FakeServer();
  server.existingNames.add("clash.bin");
  const file = makeFile(3000, "clash.bin");
  const {instance} = upload(server, file);

  await assert.rejects(() => instance.run(), /already exists/);
  assert.equal(instance.state, UPLOAD_STATES.failed);
  assert.equal(server.chunkCalls, 3);

  instance.target.finishName = "clash (2).bin";
  const result = await instance.run();

  assert.equal(result.node_id, 1);
  assert.equal(server.files[0].name, "clash (2).bin");
  assert.equal(server.chunkCalls, 3, "nothing was sent again");
});

test("a failed asynchronous finish surfaces the server's reason", async () => {
  const server = new FakeServer({largeFileThreshold: 100});
  const {instance} = upload(server, makeFile(3000));
  const deps = instance.deps;
  const originalCall = deps.call;
  deps.call = async (model, method, kwargs) => {
    const reply = await originalCall(model, method, kwargs);
    if (method === "upload_status" && instance.state === UPLOAD_STATES.finishing) {
      const stored = server.uploads.get(kwargs.upload_id);
      stored.state = "failed";
      stored.error = "Destination folder is in the trash";
      return {...reply, state: "failed", error: stored.error};
    }
    return reply;
  };

  await assert.rejects(() => instance.run(), /in the trash/);
  assert.equal(instance.state, UPLOAD_STATES.failed);
});

test("a fatal error class is not retryable by default", () => {
  assert.equal(fatal("x").retryable, false);
  assert.equal(retryable("x").retryable, true);
});
