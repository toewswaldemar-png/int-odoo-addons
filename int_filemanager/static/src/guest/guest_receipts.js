// The receipts of a guest's uploads (see `int.filemanager.share._receipt`), kept per share.
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
        return []; // no storage (a private window), or foreign data
    }
}

export function saveReceipts(token, entries) {
    try {
        browser.localStorage.setItem(KEY_PREFIX + token, JSON.stringify(entries));
    } catch {
        // no storage: the list is gone with the page
    }
}

export function withReceipt(entries, entry) {
    return [entry, ...entries.filter((other) => other.id !== entry.id)];
}

export function withoutReceipt(entries, id) {
    return entries.filter((entry) => entry.id !== id);
}
