/** @odoo-module **/

// The explorer controller behaviour shared by the list and the kanban view, assembled from
// five parts (each a function of the base class, so JS gets its "multiple inheritance"):
// navigation, mutations, uploads, thumbnails and interaction. Order matters: every part's setup()
// calls super.setup() first and may rely on what the ones before it set up.
import {interactionMixin} from "./controller_interaction.js";
import {mutationsMixin} from "./controller_mutations.js";
import {navigationMixin} from "./controller_navigation.js";
import {previewsMixin} from "./controller_previews.js";
import {uploadsMixin} from "./controller_uploads.js";

export const filemanagerV2Mixin = (Base) =>
    interactionMixin(
        previewsMixin(uploadsMixin(mutationsMixin(navigationMixin(Base))))
    );
