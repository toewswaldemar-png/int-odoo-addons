import { _t } from "@web/core/l10n/translation";

export const TILE_SIZE_SETTING = "int_filemanager_tile_size";
export const DEFAULT_TILE_SIZE = "medium";
export const TILE_SIZES = [
    { key: "small", label: _t("Small"), pictureWidth: 256 },
    { key: DEFAULT_TILE_SIZE, label: _t("Medium"), pictureWidth: 256 },
    { key: "large", label: _t("Large"), pictureWidth: 512 },
];

/** @returns {{key: string, label: string, pictureWidth: number}} size of `key`, or the default */
export function tileSizeOf(key) {
    return TILE_SIZES.find((size) => size.key === key) || tileSizeOf(DEFAULT_TILE_SIZE);
}
