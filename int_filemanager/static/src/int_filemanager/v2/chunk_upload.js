/** @odoo-module **/

// One file on its way to the server: small files in a single request,
// bigger ones as 4 MiB pieces that can be resumed after any interruption.
//
// Everything that touches the outside world is injected (`deps`), so the protocol is
// tested with plain Node against a fake server:
//   call(model, method, kwargs)            -> Promise of the method's result
//   postChunk(uploadId, offset, blob)      -> Promise of {received_size}
//   readBase64(file)                       -> Promise of the file's base64 text
//   sleep(ms)                              -> Promise
// A rejected promise carries `retryable: true` when trying again can help (lost
// connection, gateway timeout) and false when the server refused (rights, name taken).

export const CHUNK_BYTES = 4 * 1024 * 1024;
export const POLL_MS = 2000;
const BACKOFF_MS = [1000, 2000, 4000, 8000, 16000];

export const UPLOAD_STATES = {
  idle: "idle",
  running: "running",
  paused: "paused",
  finishing: "finishing",
  done: "done",
  interrupted: "interrupted",
  failed: "failed",
  cancelled: "cancelled",
};

export class UploadCancelled extends Error {
  constructor() {
    super("Upload cancelled");
    this.name = "UploadCancelled";
  }
}

export class ChunkedUpload {
  /**
   * @param {Object} params
   * @param {File} params.file
   * @param {{parentId?: number, name?: string, nodeId?: number, baseRevisionId?: number}} params.target
   *   a new file (parentId + name) or a new revision of nodeId (from baseRevisionId)
   * @param {String} params.operationKey  the same key on every attempt: makes resuming find the same upload
   * @param {Object} params.deps
   * @param {Function} [params.onChange]  called with a snapshot whenever something changes
   */
  constructor({
    file,
    target,
    operationKey,
    deps,
    onChange = () => undefined,
    chunkBytes = CHUNK_BYTES,
    maxRetries = BACKOFF_MS.length,
  }) {
    this.file = file;
    this.target = target;
    this.operationKey = operationKey;
    this.deps = deps;
    this.onChange = onChange;
    this.chunkBytes = chunkBytes;
    this.maxRetries = maxRetries;
    this.uploadId = null;
    this.sent = 0;
    this.state = UPLOAD_STATES.idle;
    this.error = null;
    this.result = null;
    this._pauseRequested = false;
    this._cancelled = false;
    this._failedPieces = 0;
  }

  get snapshot() {
    return {
      state: this.state,
      sent: this.sent,
      total: this.file.size,
      error: this.error,
      result: this.result,
      uploadId: this.uploadId,
    };
  }

  _setState(state) {
    this.state = state;
    this.onChange(this.snapshot);
  }

  get cancelled() {
    return this._cancelled;
  }

  pause() {
    this._pauseRequested = true;
  }

  cancel() {
    this._cancelled = true;
  }

  _checkCancelled() {
    if (this._cancelled) {
      throw new UploadCancelled();
    }
  }

  async _withRetry(fn) {
    for (let attempt = 0; ; attempt++) {
      this._checkCancelled();
      try {
        return await fn();
      } catch (error) {
        if (!error.retryable || attempt >= this.maxRetries) {
          throw error;
        }
        await this.deps.sleep(BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)]);
      }
    }
  }

  /**
   * Runs (or resumes) the upload. Resolves with the server's result
   * ({node_id, revision_id, sha256}), resolves with null when paused, and rejects when it
   * failed, was cancelled or was interrupted (state says which; `retryable` on the error
   * tells whether calling run() again makes sense).
   */
  async run() {
    this._pauseRequested = false;
    this.error = null;
    this._setState(UPLOAD_STATES.running);
    try {
      const result =
        this.file.size <= this.chunkBytes
          ? await this._runSmall()
          : await this._runChunked();
      if (result === null) {
        this._setState(UPLOAD_STATES.paused);
        return null;
      }
      this.result = result;
      this.sent = this.file.size;
      this._setState(UPLOAD_STATES.done);
      return result;
    } catch (error) {
      this.error = error;
      if (error instanceof UploadCancelled) {
        this._setState(UPLOAD_STATES.cancelled);
      } else {
        this._setState(
          error.retryable ? UPLOAD_STATES.interrupted : UPLOAD_STATES.failed
        );
      }
      throw error;
    }
  }

  async _runSmall() {
    const content = await this.deps.readBase64(this.file);
    const {parentId, name, nodeId, baseRevisionId} = this.target;
    const result = await this._withRetry(() =>
      nodeId
        ? this.deps.call("int_filemanager.node", "create_new_revision", {
            node_id: nodeId,
            base_revision_id: baseRevisionId || false,
            content,
            operation_key: this.operationKey,
            origin: "upload",
          })
        : this.deps.call("int_filemanager.node", "create_file", {
            parent_id: parentId,
            name,
            content,
            operation_key: this.operationKey,
          })
    );
    this.sent = this.file.size;
    return result;
  }

  async _runChunked() {
    const {parentId, name, nodeId, baseRevisionId} = this.target;
    if (!this.uploadId) {
      const init = await this._withRetry(() =>
        this.deps.call("int_filemanager.upload", "init_upload", {
          target_parent_id: nodeId ? false : parentId,
          target_name: nodeId ? false : name,
          target_node_id: nodeId || false,
          base_revision_id: baseRevisionId || false,
          expected_size: this.file.size,
          operation_key: this.operationKey,
        })
      );
      this.uploadId = init.upload_id;
    }
    let status = await this._status();
    if (status.state === "done") {
      return status.result;
    }
    if (status.state === "processing") {
      return this._waitForProcessing();
    }
    if (status.state === "failed") {
      throw this._failure(status);
    }

    let offset = status.received_size;
    this.sent = offset;
    this.onChange(this.snapshot);
    while (offset < this.file.size) {
      if (this._pauseRequested) {
        return null;
      }
      this._checkCancelled();
      const blob = this.file.slice(offset, offset + this.chunkBytes);
      try {
        const reply = await this.deps.postChunk(this.uploadId, offset, blob);
        // The server's count is the truth: a repeated piece answers with what it
        // already has, which can be more than this piece reaches.
        offset = reply.received_size;
        this._failedPieces = 0;
      } catch (error) {
        if (!error.retryable) {
          throw error;
        }
        // The piece may or may not have arrived: ask, then continue from the answer.
        status = await this._resync(error);
        offset = status.received_size;
      }
      this.sent = offset;
      this.onChange(this.snapshot);
    }

    this._setState(UPLOAD_STATES.finishing);
    const finish = await this._withRetry(() =>
      this.deps.call("int_filemanager.upload", "finish_upload", {
        upload_id: this.uploadId,
        operation_key: `${this.operationKey}-finish`,
        target_name: this.target.finishName || false,
      })
    );
    if (finish.state === "processing") {
      return this._waitForProcessing();
    }
    return finish;
  }

  _status() {
    return this._withRetry(() =>
      this.deps.call("int_filemanager.upload", "upload_status", {
        upload_id: this.uploadId,
      })
    );
  }

  /** After a failed piece: wait a little (backoff), then ask the server where it is. */
  async _resync(error) {
    this._failedPieces += 1;
    if (this._failedPieces > this.maxRetries) {
      throw error;
    }
    await this.deps.sleep(
      BACKOFF_MS[Math.min(this._failedPieces - 1, BACKOFF_MS.length - 1)]
    );
    return this._status();
  }

  async _waitForProcessing() {
    this._setState(UPLOAD_STATES.finishing);
    for (;;) {
      this._checkCancelled();
      const status = await this._status();
      if (status.state === "done") {
        return status.result;
      }
      if (status.state === "failed") {
        throw this._failure(status);
      }
      await this.deps.sleep(POLL_MS);
    }
  }

  _failure(status) {
    const error = new Error(status.error || "The upload failed on the server.");
    error.retryable = false;
    return error;
  }

  /** Gives up for good: the server drops the partial data. Safe to call any time. */
  async discard() {
    this.cancel();
    if (this.uploadId && this.state !== UPLOAD_STATES.done) {
      try {
        await this.deps.call("int_filemanager.upload", "cancel_upload", {
          upload_id: this.uploadId,
        });
      } catch {
        // Best effort: the expiry job removes what is left.
      }
    }
  }
}
