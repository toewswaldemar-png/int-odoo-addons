import { _t } from "@web/core/l10n/translation";

// The field of the user settings that holds the choice (`res.users.settings`).
export const TILE_SIZE_SETTING = "int_filemanager_tile_size";
export const DEFAULT_TILE_SIZE = "medium";
export const TILE_SIZES = [
    { key: "small", label: _t("Small"), pictureWidth: 256 },
    { key: DEFAULT_TILE_SIZE, label: _t("Medium"), pictureWidth: 256 },
    // The big card shows the picture larger than the 256 pixels of the others.
    { key: "large", label: _t("Large"), pictureWidth: 512 },
];

/**
 * @param {string} key a value of the setting, maybe missing or unknown
 * @returns {{key: string, label: string, pictureWidth: number}} the size, the default for an unknown key
 */
export function tileSizeOf(key) {
    return TILE_SIZES.find((size) => size.key === key) || tileSizeOf(DEFAULT_TILE_SIZE);
}
