// The share that the page of the guests shows: its token (from the page), the key that the
// password gave (from the tab), and the addresses of its routes.
import { browser } from "@web/core/browser/browser";

export const SHARE_PATH = "/int_filemanager/share";

export function shareToken() {
    return odoo.int_filemanager_token;
}

/** The key is where the page that asked for the password put it: in the tab, nowhere else. */
export function shareKey() {
    return browser.sessionStorage.getItem(`int_filemanager.share_key.${shareToken()}`) || undefined;
}

/** @returns {string} the address of a route of this share, without the key */
export function shareUrl(path) {
    return `${SHARE_PATH}/${encodeURIComponent(shareToken())}/${path}`;
}
