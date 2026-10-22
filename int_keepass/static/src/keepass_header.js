// The part of the password flow that needs no Odoo module, so it can run on its own.

export const HEADER = "X-Int-Keepass-Password";
export const HEADER_EMAIL = "X-Int-Keepass-Email";
export const MODEL_PREFIX = "int.keepass.";
// Asked by the unlock screen before there is a password: it says where the data comes from.
export const OPEN_METHODS = new Set(["get_source_info"]);

/** UTF-8 as base64: a header value must not hold characters above Latin-1. */
export function encodePassword(text) {
    let binary = "";
    for (const byte of new TextEncoder().encode(text)) {
        binary += String.fromCharCode(byte);
    }
    return btoa(binary);
}

export function isKeepassCall(params) {
    return Boolean(params?.model?.startsWith(MODEL_PREFIX));
}

/**
 * Wraps `rpc._rpc`: a call to a model of this module carries the password (and the e-mail address
 * of the Vaultwarden account, if there is one) as headers; without a password it is held back
 * (it never settles, the screen that replaces the view takes its components away) and the
 * unlock screen opens.
 *
 * @param {Function} original
 * @param {{password: string|null, email: string|null, onLocked: Function|null}} keepass
 */
export function wrapRpc(original, keepass) {
    return function (url, params, settings) {
        if (!isKeepassCall(params) || OPEN_METHODS.has(params.method)) {
            return original.call(this, url, params, settings);
        }
        if (!keepass.password) {
            keepass.onLocked?.();
            const held = new Promise(() => {});
            held.abort = () => {};
            return held;
        }
        const headers = { ...settings?.headers, [HEADER]: encodePassword(keepass.password) };
        if (keepass.email) {
            headers[HEADER_EMAIL] = encodePassword(keepass.email);
        }
        return original.call(this, url, params, { ...settings, headers });
    };
}
