// What the browser of a guest keeps of his uploads: for each file its receipt (the proof for the
// share that the file is his, see `int.filemanager.share._receipt`) and what the list shows. It
// lives in the `localStorage`, one entry per share (the token is in the key, so two shares do not
// mix). The list is only as good as the browser: other browser, or the site data cleared, and it is
// empty; the files stay in the upload folder.
import { browser } from "@web/core/browser/browser";

const KEY_PREFIX = "int_filemanager.share_uploads.";

function isEntry(entry) {
    return (
        entry &&
        Number.isInteger(entry.id) &&
        typeof entry.receipt === "string" &&
        typeof entry.name === "string"
    );
}

/** @returns {Array<{id: Number, receipt: String, name: String, size: Number, time: String}>} */
export function loadReceipts(token) {
    try {
        const entries = JSON.parse(browser.localStorage.getItem(KEY_PREFIX + token));
        return Array.isArray(entries) ? entries.filter(isEntry) : [];
    } catch {
        return []; // no storage (a private window), or something else was put there
    }
}

export function saveReceipts(token, entries) {
    try {
        browser.localStorage.setItem(KEY_PREFIX + token, JSON.stringify(entries));
    } catch {
        // No storage: the list of the page is gone with the page, the files are kept anyway.
    }
}

/** @returns {Array} the entries of the list with the new one first (the same file once) */
export function withReceipt(entries, entry) {
    return [entry, ...entries.filter((other) => other.id !== entry.id)];
}

/** @returns {Array} the entries of the list without the file */
export function withoutReceipt(entries, id) {
    return entries.filter((entry) => entry.id !== id);
}
