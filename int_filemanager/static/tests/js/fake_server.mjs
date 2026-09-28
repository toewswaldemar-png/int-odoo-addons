// An in-memory stand-in for the upload endpoints, faithful to the server's rules
// (int_filemanager.upload): init is idempotent per operation key, a chunk must start at
// the received size (a repeat is a no-op, a gap is refused), finish above the threshold
// goes through "processing". Failure injection lives in `faults`.

export function retryable(message) {
  const error = new Error(message);
  error.retryable = true;
  return error;
}

export function fatal(message) {
  const error = new Error(message);
  error.retryable = false;
  return error;
}

export class FakeServer {
  constructor({largeFileThreshold = Infinity} = {}) {
    this.uploads = new Map(); // Id -> upload
    this.byKey = new Map();
    this.calls = [];
    this.nextId = 1;
    this.files = []; // Completed: {name, size, bytes}
    this.largeFileThreshold = largeFileThreshold;
    // Failure injection
    this.faults = {
      // Chunk numbers (0-based, counted over all postChunk calls) to fail before/after applying
      failChunkBefore: new Set(),
      failChunkAfter: new Set(),
      fatalChunk: new Set(),
      callFailures: [], // [{method, error}] consumed in order
    };
    this.chunkCalls = 0;
    this.existingNames = new Set();
  }

  deps({sleepLog = []} = {}) {
    return {
      call: (model, method, kwargs) => this.call(model, method, kwargs),
      postChunk: (uploadId, offset, blob) => this.postChunk(uploadId, offset, blob),
      readBase64: async (file) =>
        Buffer.from(await file.arrayBuffer()).toString("base64"),
      sleep: async (ms) => {
        sleepLog.push(ms);
      },
    };
  }

  _maybeFail(method) {
    const index = this.faults.callFailures.findIndex((f) => f.method === method);
    if (index !== -1) {
      const [{error}] = this.faults.callFailures.splice(index, 1);
      throw error;
    }
  }

  async call(model, method, kwargs) {
    this.calls.push({model, method, kwargs});
    this._maybeFail(method);
    if (model === "int_filemanager.node") {
      return this._nodeCall(method, kwargs);
    }
    return this._uploadCall(method, kwargs);
  }

  _nodeCall(method, kwargs) {
    if (method === "create_file") {
      if (this.existingNames.has(kwargs.name.toLowerCase())) {
        throw fatal("A file or folder named " + kwargs.name + " already exists here.");
      }
      const bytes = Buffer.from(kwargs.content, "base64");
      this.files.push({name: kwargs.name, size: bytes.length, bytes});
      return {node_id: this.files.length, revision_id: 1, sha256: "x"};
    }
    if (method === "create_new_revision") {
      const bytes = Buffer.from(kwargs.content, "base64");
      this.files.push({nodeId: kwargs.node_id, size: bytes.length, bytes});
      return {node_id: kwargs.node_id, revision_id: 2, sha256: "y"};
    }
    throw new Error("unexpected node method " + method);
  }

  _uploadCall(method, kwargs) {
    if (method === "init_upload") {
      const existing = this.byKey.get(kwargs.operation_key);
      if (existing) {
        return {upload_id: existing.id};
      }
      const upload = {
        id: this.nextId++,
        key: kwargs.operation_key,
        size: kwargs.expected_size,
        name: kwargs.target_name,
        nodeId: kwargs.target_node_id,
        chunks: [],
        received: 0,
        state: "open",
        result: null,
        error: false,
      };
      this.uploads.set(upload.id, upload);
      this.byKey.set(upload.key, upload);
      return {upload_id: upload.id};
    }
    const upload = this.uploads.get(kwargs.upload_id);
    if (!upload) {
      throw fatal("This upload does not exist any more.");
    }
    if (method === "upload_status") {
      return {
        upload_id: upload.id,
        state: upload.state,
        received_size: upload.received,
        expected_size: upload.size,
        result: upload.result,
        error: upload.error,
      };
    }
    if (method === "finish_upload") {
      if (upload.state !== "open") {
        throw fatal("This upload is not open.");
      }
      const name = kwargs.target_name || upload.name;
      if (name && this.existingNames.has(name.toLowerCase())) {
        throw fatal("A file or folder named " + name + " already exists here.");
      }
      if (upload.received > this.largeFileThreshold) {
        upload.state = "processing";
        return {upload_id: upload.id, state: "processing"};
      }
      return this._complete(upload, name);
    }
    if (method === "cancel_upload") {
      this.uploads.delete(upload.id);
      this.byKey.delete(upload.key);
      return true;
    }
    throw new Error("unexpected upload method " + method);
  }

  _complete(upload, name) {
    const bytes = Buffer.concat(upload.chunks);
    this.files.push({name, size: bytes.length, bytes});
    upload.state = "done";
    upload.result = {node_id: this.files.length, revision_id: 1, sha256: "z"};
    return upload.result;
  }

  /** What the cron does for a "processing" upload. */
  runCron() {
    for (const upload of this.uploads.values()) {
      if (upload.state === "processing") {
        this._complete(upload, upload.name);
      }
    }
  }

  async postChunk(uploadId, offset, blob) {
    const number = this.chunkCalls++;
    if (this.faults.fatalChunk.has(number)) {
      throw fatal("Access denied");
    }
    if (this.faults.failChunkBefore.has(number)) {
      throw retryable("connection lost");
    }
    const upload = this.uploads.get(uploadId);
    if (!upload) {
      throw fatal("This upload does not exist any more.");
    }
    const data = Buffer.from(await blob.arrayBuffer());
    if (offset > upload.received) {
      throw fatal("This chunk does not continue where the upload left off.");
    }
    if (offset === upload.received) {
      upload.chunks.push(data);
      upload.received += data.length;
    }
    if (this.faults.failChunkAfter.has(number)) {
      throw retryable("connection lost after the server saw the piece");
    }
    return {received_size: upload.received};
  }
}

export function makeFile(size, name = "big.bin") {
  const bytes = Buffer.alloc(size);
  for (let i = 0; i < size; i++) {
    bytes[i] = (i * 31 + 7) % 251;
  }
  return new File([bytes], name);
}
