/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";

export class HmFolderTreeNode extends Component {
    static template = "hm_filemanager.FolderTreeNode";
    static components = { HmFolderTreeNode };
    static props = {
        name: String,
        path: String,
        depth: Number,
        activePath: String,
        onNavigate: Function,
    };

    setup() {
        this.state = useState({
            expanded: false,
            loading: false,
            children: null,
        });
    }

    get isActive() {
        return this.props.path === this.props.activePath;
    }

    async toggle(ev) {
        ev.stopPropagation();
        if (!this.state.expanded && this.state.children === null) {
            await this.loadChildren();
        }
        this.state.expanded = !this.state.expanded;
    }

    async loadChildren() {
        this.state.loading = true;
        try {
            const res = await rpc("/hm_filemanager/tree", { path: this.props.path });
            this.state.children = res.children;
        } finally {
            this.state.loading = false;
        }
    }

    async onClickLabel() {
        this.props.onNavigate(this.props.path);
        if (this.state.children === null) {
            await this.loadChildren();
        }
        this.state.expanded = true;
    }
}

export class HmFolderTree extends Component {
    static template = "hm_filemanager.FolderTree";
    static components = { HmFolderTreeNode };
    static props = {
        activePath: String,
        onNavigate: Function,
    };

    setup() {
        this.state = useState({ children: [] });
        onWillStart(() => this.loadRoot());
    }

    async loadRoot() {
        const res = await rpc("/hm_filemanager/tree", { path: "" });
        this.state.children = res.children;
    }

    onClickRoot() {
        this.props.onNavigate("");
    }

    get isRootActive() {
        return this.props.activePath === "";
    }
}
