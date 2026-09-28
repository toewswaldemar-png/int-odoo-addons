/** @odoo-module **/

// The uploads of the session, as an Odoo service: it outlives any one view, so switching
// between list and kanban - or to another app - does not stop what is being sent. The
// protocol and the queue are in chunk_upload.js / upload_manager.js (tested with Node);
// this file only connects them to the browser: RPC, fetch for the pieces, localStorage for
// the resume information, and the notion of "an upload finished, reload the folder".
import {reactive} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {browser} from "@web/core/browser/browser";
import {ConnectionLostError} from "@web/core/network/rpc";
import {planUpload} from "./upload_plan.js";
import {UploadManager} from "./upload_manager.js";
import {newOperationKey} from "./utils.js";

const STORAGE_KEY = "int_filemanager.uploads";
const BASES_KEY = "int_filemanager.bases";
const BASES_KEEP_MS = 30 * 24 * 60 * 60 * 1000;
// A piece that hits a gateway problem or a lost link is worth another try (after the
// server has been asked how far it got); the rest is a refusal.
const RETRYABLE_HTTP_STATUS = new Set([0, 408, 425, 429, 500, 502, 503, 504]);
export const UPLOADS_IDLE_EVENT = "INT_FILEMANAGER:UPLOADS_IDLE";

function readJson(key) {
  try {
    return JSON.parse(browser.localStorage.getItem(key) || "{}");
  } catch {
    return {};
  }
}

function writeJson(key, value) {
  try {
    browser.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage full or blocked (private window): uploads still work, just not resumable
    // after a reload.
  }
}

function toBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

export const uploadsService = {
  dependencies: ["orm"],
  start(env, {orm}) {
    const state = reactive({items: [], unfinished: 0});

    // Odoo's own errors (rights, a name in use) are final; a lost connection is retried.
    const call = async (model, method, kwargs) => {
      try {
        return await orm.silent.call(model, method, [], kwargs);
      } catch (error) {
        error.retryable = error instanceof ConnectionLostError;
        throw error;
      }
    };

    const postChunk = async (uploadId, offset, blob) => {
      const query = new URLSearchParams({
        offset: String(offset),
        csrf_token: odoo.csrf_token,
      });
      let response = null;
      try {
        response = await fetch(
          `/int_filemanager/v2/upload/${uploadId}/chunk?${query}`,
          {
            method: "POST",
            headers: {"Content-Type": "application/octet-stream"},
            body: blob,
            credentials: "same-origin",
          }
        );
      } catch (error) {
        error.retryable = true; // The request never got an answer
        throw error;
      }
      if (!response.ok) {
        const error = new Error(`${response.status} ${response.statusText}`);
        error.retryable = RETRYABLE_HTTP_STATUS.has(response.status);
        throw error;
      }
      return response.json();
    };

    const deps = {
      call,
      postChunk,
      readBase64: toBase64,
      sleep: (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
      newKey: newOperationKey,
    };

    const manager = new UploadManager({
      deps,
      storage: {
        load: () => readJson(STORAGE_KEY),
        save: (value) => writeJson(STORAGE_KEY, value),
      },
      onChange: (items) => {
        state.items = items;
        state.unfinished = manager.unfinished().length;
      },
      onIdle: () => env.bus.trigger(UPLOADS_IDLE_EVENT),
    });
    state.unfinished = manager.unfinished().length;

    return {
      state,
      /** From dropped or chosen files to a plan: folders, name conflicts, decisions. */
      plan: (entries, parentId, resolveConflicts) =>
        planUpload(entries, parentId, deps, resolveConflicts),
      enqueue: (plan) => manager.add(plan),
      pause: (id) => manager.pause(id),
      retry: (id) => manager.retry(id),
      cancel: (id) => manager.cancel(id),
      renameAndRetry: (id, name) => manager.renameAndRetry(id, name),
      clearFinished: () => manager.clearFinished(),
      /**
       * "Edit locally": the revision a file was downloaded from is remembered, so the
       * upload of the edited copy carries it as its base and a change made by somebody
       * else in between is reported instead of overwritten.
       */
      rememberBase(nodeId, revisionId) {
        if (!revisionId) {
          return;
        }
        const bases = readJson(BASES_KEY);
        bases[nodeId] = {revisionId, at: Date.now()};
        writeJson(BASES_KEY, bases);
      },
      takeBase(nodeId) {
        const bases = readJson(BASES_KEY);
        const entry = bases[nodeId];
        if (!entry || Date.now() - entry.at > BASES_KEEP_MS) {
          return false;
        }
        delete bases[nodeId];
        writeJson(BASES_KEY, bases);
        return entry.revisionId;
      },
    };
  },
};

registry.category("services").add("int_filemanager.uploads", uploadsService);
