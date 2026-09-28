/** @odoo-module **/

// Small pure helpers of the v2 explorer. No Odoo imports on purpose: they are unit
// tested with plain Node (int_filemanager/static/tests/js).

/**
 * One key per user action; the server answers a repeated key with the stored result
 * instead of doing the work twice, so a retry after a lost response is harmless.
 * @returns {String}
 */
export function newOperationKey() {
  if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  // Not a secure context (plain http on a LAN): randomUUID is missing there.
  const bytes = new Uint8Array(16);
  if (globalThis.crypto && globalThis.crypto.getRandomValues) {
    globalThis.crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i++) {
      bytes[i] = Math.floor(Math.random() * 256);
    }
  }
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

/**
 * Lower-case extension without the dot, "" when there is none.
 * @param {String} name
 * @returns {String}
 */
export function extOf(name) {
  const index = name.lastIndexOf(".");
  return index <= 0 ? "" : name.slice(index + 1).toLowerCase();
}

/**
 * "12.3 MB" style size, the same units Odoo shows for attachments.
 * @param {Number} bytes
 * @returns {String}
 */
export function humanSize(bytes) {
  const units = ["Bytes", "KB", "MB", "GB", "TB"];
  let value = Number(bytes) || 0;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit++;
  }
  if (unit === 0) {
    return `${Math.round(value)} ${units[0]}`;
  }
  return `${value.toFixed(value >= 100 ? 0 : 1)} ${units[unit]}`;
}

/**
 * The server compares names without case and in NFC; do the same here when deciding
 * whether two names clash.
 * @param {String} name
 * @returns {String}
 */
export function nameKey(name) {
  return name.normalize("NFC").toLowerCase();
}

/**
 * "report.txt" -> "report (2).txt", the first free name among *taken* (name keys or
 * names; compared like the server does). Used for "keep both".
 * @param {String} name
 * @param {Iterable<string>} taken
 * @returns {String}
 */
export function uniqueName(name, taken) {
  const takenKeys = new Set(Array.from(taken, nameKey));
  if (!takenKeys.has(nameKey(name))) {
    return name;
  }
  const dot = name.lastIndexOf(".");
  const stem = dot > 0 ? name.slice(0, dot) : name;
  const ext = dot > 0 ? name.slice(dot) : "";
  for (let n = 2; ; n++) {
    const candidate = `${stem} (${n})${ext}`;
    if (!takenKeys.has(nameKey(candidate))) {
      return candidate;
    }
  }
}

/**
 * Only real text inputs count as "typing"; a focused checkbox must not swallow F2 or
 * Escape.
 * @param {Element|null} el
 * @returns {Boolean}
 */
export function isTypingContext(el) {
  if (!el) {
    return false;
  }
  if (el.tagName === "TEXTAREA" || el.isContentEditable) {
    return true;
  }
  const nonText = [
    "checkbox",
    "radio",
    "button",
    "submit",
    "reset",
    "file",
    "image",
    "range",
    "color",
  ];
  return el.tagName === "INPUT" && !nonText.includes(el.type);
}

/**
 * Message of a failed RPC or thrown error, for a notification.
 * @param {Error & {data?: {message?: string}}} error
 * @returns {String}
 */
export function errorMessage(error) {
  return (
    (error && error.data && error.data.message) ||
    (error && error.message) ||
    String(error)
  );
}

/**
 * URL of the download route for a node (current revision) or one of its revisions.
 * @param {Number} nodeId
 * @param {{revisionId?: number, inline?: boolean}} [options]
 * @returns {String}
 */
export function downloadUrl(nodeId, {revisionId, inline} = {}) {
  const params = new URLSearchParams();
  if (revisionId) {
    params.set("revision_id", String(revisionId));
  }
  if (inline) {
    params.set("disposition", "inline");
  }
  const query = params.toString();
  return `/int_filemanager/v2/download/${nodeId}${query ? `?${query}` : ""}`;
}

/**
 * UTF-8 text as base64, the way binary content travels over JSON-RPC. Done in slices:
 * spreading a big byte array into one String.fromCharCode call overflows the stack.
 * @param {String} text
 * @returns {String}
 */
export function textToBase64(text) {
  const bytes = new TextEncoder().encode(text);
  const step = 0x8000;
  let binary = "";
  for (let i = 0; i < bytes.length; i += step) {
    binary += String.fromCharCode(...bytes.subarray(i, i + step));
  }
  return btoa(binary);
}
