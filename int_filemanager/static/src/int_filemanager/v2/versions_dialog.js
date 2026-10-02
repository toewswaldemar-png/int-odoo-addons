/** @odoo-module **/

import {Component, onWillStart, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {deserializeDateTime, formatDateTime} from "@web/core/l10n/dates";
import {_t} from "@web/core/l10n/translation";
import {useService} from "@web/core/utils/hooks";
import {downloadUrl, errorMessage, newOperationKey} from "./utils.js";
import {humanFileSize} from "./size_field.js";

// The revisions of one file. Every saved version stays; restoring one makes a NEW
// version out of the old content (nothing is overwritten), and a stale "current" is
// refused by the server, so two people restoring at once cannot lose an edit.
export class IntFilemanagerV2VersionsDialog extends Component {
    static template = "int_filemanager.v2.VersionsDialog";
    static components = {Dialog};
    static props = {
        nodeId: Number,
        name: String,
        close: Function,
        onChanged: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({revisions: [], currentId: false, loading: true});
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        const [node] = await this.orm.read(
            "int_filemanager.node",
            [this.props.nodeId],
            ["current_revision_id"]
        );
        this.state.currentId = node.current_revision_id
            ? node.current_revision_id[0]
            : false;
        this.state.revisions = await this.orm.searchRead(
            "int_filemanager.revision",
            [["node_id", "=", this.props.nodeId]],
            ["revision_no", "create_date", "create_uid", "size", "origin"],
            {order: "revision_no desc"}
        );
        this.state.loading = false;
    }

    get title() {
        return _t("Versions of %s", this.props.name);
    }

    originLabel(origin) {
        return (
            {
                upload: _t("Upload"),
                webdav: _t("Network drive"),
                office: _t("Office"),
                edit: _t("Edit"),
                restore: _t("Restored"),
                import: _t("Import"),
            }[origin] || origin
        );
    }

    formatDate(value) {
        return formatDateTime(deserializeDateTime(value));
    }

    formatSize(value) {
        return humanFileSize(value) || "0 Bytes";
    }

    downloadHref(revision) {
        return downloadUrl(this.props.nodeId, {revisionId: revision.id});
    }

    async onRestore(revision) {
        try {
            await this.orm.call("int_filemanager.node", "restore_version", [], {
                node_id: this.props.nodeId,
                revision_id: revision.id,
                base_revision_id: this.state.currentId,
                operation_key: newOperationKey(),
            });
            await this.load();
            this.props.onChanged();
        } catch (error) {
            this.notification.add(errorMessage(error), {type: "danger"});
            await this.load();
        }
    }
}
