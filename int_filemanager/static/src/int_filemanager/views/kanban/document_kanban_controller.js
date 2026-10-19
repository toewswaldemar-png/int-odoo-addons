import { useState, useSubEnv } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { user } from "@web/core/user";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { TILE_SIZE_SETTING, TILE_SIZES, tileSizeOf } from "./document_tile_size";

/** The kanban of documents with a menu for the card size, kept in `res.users.settings`. */
export class DocumentKanbanController extends KanbanController {
    static components = { ...KanbanController.components, Dropdown };

    setup() {
        super.setup();
        this.tile = useState({ size: tileSizeOf(user.settings[TILE_SIZE_SETTING]).key });
        useSubEnv({ documentTile: this.tile });
    }

    /** @override */
    get className() {
        const classes = ["o_int_filemanager_tiles", `o_int_filemanager_tiles_${this.tile.size}`];
        return [super.className, ...classes].filter(Boolean).join(" ");
    }

    get tileSizes() {
        return TILE_SIZES;
    }

    get tileSizeLabel() {
        return tileSizeOf(this.tile.size).label;
    }

    /** @param {string} size the key of one of `tileSizes` */
    async setTileSize(size) {
        if (size === this.tile.size) {
            return;
        }
        this.tile.size = size;
        await user.setUserSettings(TILE_SIZE_SETTING, size);
    }
}
