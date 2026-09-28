/** @odoo-module **/

// The list of uploads of one explorer session: runs up to `concurrency` files at once,
// keeps what is needed to resume after a reload, and exposes plain snapshots for the UI.
// Logic only - all outside world access is injected, tested with plain Node.

import {ChunkedUpload, UPLOAD_STATES, UploadCancelled} from "./chunk_upload.js";

// The server drops an unfinished upload after a day (int_filemanager.upload expiry);
// remembering the key longer would only resume into nothing.
const KEEP_MS = 24 * 60 * 60 * 1000;

export const ITEM_STATES = {...UPLOAD_STATES, queued: "queued"};

let nextItemId = 1;

function fingerprint(planItem) {
  const {file, parentId, nodeId} = planItem;
  return [parentId, nodeId || "", file.name, file.size, file.lastModified].join("|");
}

export class UploadManager {
  /**
   * @param {Object} params
   * @param {Object} params.deps  call, postChunk, readBase64, sleep, newKey
   * @param {{load: Function, save: Function}} params.storage  resume information
   * @param {Function} params.onChange  called with the array of item snapshots
   * @param {Function} [params.onIdle]  called with the finished snapshots when the queue empties
   */
  constructor({
    deps,
    storage,
    onChange = () => undefined,
    onIdle = () => undefined,
    concurrency = 2,
    now = () => Date.now(),
    chunkBytes,
  }) {
    this.deps = deps;
    this.storage = storage;
    this.onChange = onChange;
    this.onIdle = onIdle;
    this.concurrency = concurrency;
    this.now = now;
    this.chunkBytes = chunkBytes;
    this.items = [];
    this._sinceIdle = [];
    this._prune();
  }

  _prune() {
    const saved = this.storage.load();
    const fresh = {};
    for (const [key, entry] of Object.entries(saved)) {
      // A refusal (rights, a name in use) is final: nothing to resume after a reload.
      if (!entry.failed && this.now() - entry.updatedAt < KEEP_MS) {
        fresh[key] = entry;
      }
    }
    this.storage.save(fresh);
  }

  /** Uploads that were started and never finished (kept across page reloads). */
  unfinished() {
    return Object.values(this.storage.load())
      .filter((entry) => !entry.failed)
      .map((entry) => ({
        name: entry.name,
        size: entry.size,
        parentId: entry.parentId,
      }));
  }

  /** Forgets what earlier page loads left behind; uploads of this session stay. */
  discardUnfinished() {
    const live = new Set(this.items.map((item) => item.fp));
    const saved = this.storage.load();
    for (const fp of Object.keys(saved)) {
      if (!live.has(fp)) {
        delete saved[fp];
      }
    }
    this.storage.save(saved);
    this._emit();
  }

  // Kept while the session lasts, so a failed upload can still be renamed and retried.
  _setFailed(item, failed) {
    const saved = this.storage.load();
    if (saved[item.fp]) {
      saved[item.fp].failed = failed;
      this.storage.save(saved);
    }
  }

  snapshot() {
    return this.items.map((item) => ({
      id: item.id,
      name: item.name,
      size: item.file.size,
      parentId: item.parentId,
      state: item.state,
      sent: item.upload.sent,
      error: item.error,
      result: item.result,
      retryable: Boolean(item.retryable),
    }));
  }

  _emit() {
    this.onChange(this.snapshot());
  }

  /**
   * @param {Array<{file: File, parentId: number, name: string, nodeId?: number, baseRevisionId?: number}>} plan
   */
  add(plan) {
    const saved = this.storage.load();
    for (const planItem of plan) {
      const fp = fingerprint(planItem);
      // Same file to the same place again: continue with the key the server knows.
      const key = saved[fp] ? saved[fp].key : this.deps.newKey();
      saved[fp] = {
        key,
        name: planItem.name,
        size: planItem.file.size,
        parentId: planItem.parentId,
        updatedAt: this.now(),
      };
      const item = {
        id: nextItemId++,
        fp,
        name: planItem.name,
        file: planItem.file,
        parentId: planItem.parentId,
        state: ITEM_STATES.queued,
        error: null,
        result: null,
        retryable: false,
      };
      item.upload = new ChunkedUpload({
        file: planItem.file,
        target: {
          parentId: planItem.parentId,
          name: planItem.name,
          nodeId: planItem.nodeId,
          baseRevisionId: planItem.baseRevisionId,
        },
        operationKey: key,
        deps: this.deps,
        chunkBytes: this.chunkBytes,
        onChange: () => this._emit(),
      });
      this.items.push(item);
    }
    this.storage.save(saved);
    this._emit();
    this._pump();
  }

  _forget(item) {
    const saved = this.storage.load();
    delete saved[item.fp];
    this.storage.save(saved);
  }

  _pump() {
    const running = this.items.filter((i) => i.state === ITEM_STATES.running).length;
    let free = this.concurrency - running;
    for (const item of this.items) {
      if (free <= 0) {
        break;
      }
      if (item.state === ITEM_STATES.queued) {
        free--;
        this._runItem(item);
      }
    }
    this._checkIdle();
  }

  _checkIdle() {
    const busy = this.items.some((i) =>
      [ITEM_STATES.queued, ITEM_STATES.running].includes(i.state)
    );
    if (!busy && this._sinceIdle.length) {
      const finished = this._sinceIdle;
      this._sinceIdle = [];
      this.onIdle(finished);
    }
  }

  async _runItem(item) {
    item.state = ITEM_STATES.running;
    item.error = null;
    this._emit();
    try {
      const result = await item.upload.run();
      if (result === null) {
        item.state = ITEM_STATES.paused;
      } else {
        item.state = ITEM_STATES.done;
        item.result = result;
        this._forget(item);
        this._sinceIdle.push(this.snapshot().find((s) => s.id === item.id));
      }
    } catch (error) {
      // An in-flight piece of a cancelled upload can fail with "no such upload": that is
      // the cancel, not a failure.
      if (error instanceof UploadCancelled || item.upload.cancelled) {
        item.state = ITEM_STATES.cancelled;
      } else {
        item.state = error.retryable ? ITEM_STATES.interrupted : ITEM_STATES.failed;
        item.error = error.message;
        item.retryable = Boolean(error.retryable);
        if (!error.retryable) {
          this._setFailed(item, true);
        }
        this._sinceIdle.push(this.snapshot().find((s) => s.id === item.id));
      }
    }
    this._emit();
    this._pump();
  }

  _find(id) {
    const item = this.items.find((i) => i.id === id);
    if (!item) {
      throw new Error(`no such upload: ${id}`);
    }
    return item;
  }

  pause(id) {
    this._find(id).upload.pause();
  }

  /** Continue a paused, interrupted or failed upload from where the server has it. */
  retry(id) {
    const item = this._find(id);
    if (
      ![ITEM_STATES.paused, ITEM_STATES.interrupted, ITEM_STATES.failed].includes(
        item.state
      )
    ) {
      return;
    }
    if (item.state === ITEM_STATES.failed) {
      this._setFailed(item, false);
    }
    item.state = ITEM_STATES.queued;
    item.error = null;
    this._emit();
    this._pump();
  }

  /** After "a file with this name exists": same bytes, another name. */
  renameAndRetry(id, newName) {
    const item = this._find(id);
    item.name = newName;
    item.upload.target.name = newName;
    item.upload.target.finishName = newName;
    this.retry(id);
  }

  async cancel(id) {
    const item = this._find(id);
    if ([ITEM_STATES.done, ITEM_STATES.cancelled].includes(item.state)) {
      return;
    }
    const wasRunning = item.state === ITEM_STATES.running;
    await item.upload.discard();
    this._forget(item);
    if (!wasRunning) {
      item.state = ITEM_STATES.cancelled;
      this._emit();
      this._pump();
    }
  }

  /** Removes finished, failed-for-good and cancelled entries from the list. */
  clearFinished() {
    this.items = this.items.filter(
      (i) =>
        ![ITEM_STATES.done, ITEM_STATES.cancelled, ITEM_STATES.failed].includes(i.state)
    );
    this._emit();
  }
}
