// The share of the guest page: its token, the key from the password, and its routes.
import { browser } from "@web/core/browser/browser";

export const SHARE_PATH = "/int_filemanager/share";

export function shareToken() {
    return odoo.int_filemanager_token;
}

/** The key is in the `sessionStorage` of the tab, where the password page put it. */
export function shareKey() {
    return browser.sessionStorage.getItem(`int_filemanager.share_key.${shareToken()}`) || undefined;
}

/** @returns {string} the address of a route of this share, without the key */
export function shareUrl(path) {
    return `${SHARE_PATH}/${encodeURIComponent(shareToken())}/${path}`;
}
