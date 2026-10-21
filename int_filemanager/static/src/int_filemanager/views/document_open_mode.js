import { user } from "@web/core/user";

// The choice of the user or the default of the filemanager, settled by the server (see
// `int_filemanager_open_mode_resolved` of `res.users.settings`). The guest page has no user
// settings: its rows and cards open with one click.
export const OPEN_MODE_SETTING = "int_filemanager_open_mode_resolved";
export const DOUBLE_CLICK = "double";

/**
 * @param {Object} env the environment of a row or a card
 * @param {Object} [settings] the settings of the user
 * @returns {boolean} whether a double click opens (a small screen has no double click to rely on)
 */
export function opensWithDoubleClick(env, settings = user.settings) {
    return settings[OPEN_MODE_SETTING] === DOUBLE_CLICK && !env.isSmall;
}

/**
 * Whether a click on a row or a card must wait for the second one. A click that the keyboard makes
 * (`detail` 0: the Enter of the kanban clicks the card) opens at once.
 * @param {Object} env the environment of a row or a card
 * @param {MouseEvent} ev
 * @param {Object} [settings] the settings of the user
 */
export function waitsForDoubleClick(env, ev, settings = user.settings) {
    return opensWithDoubleClick(env, settings) && ev.detail > 0;
}
