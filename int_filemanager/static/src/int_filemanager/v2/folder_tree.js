/** @odoo-module **/

// The sidebar folder tree. It loads exactly ONE level per call (node.tree_children), when a
// folder is opened: what a click costs grows with the size of that level, never with the
// number of folders in the system. Odoo's own search-panel category tree was measured
// several seconds slow at 69k folders because it resolves whole ancestor chains.
import {Component, onMounted, onWillUpdateProps, useState} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {useService} from "@web/core/utils/hooks";

export const ROOT_KEY = "root";

function makeNode(id, name, hasChildren) {
  return {
    id,
    name,
    hasChildren,
    expanded: false,
    loaded: false,
    loading: false,
    children: [],
  };
}

function keyOf(id) {
  return id ? String(id) : ROOT_KEY;
}

export class IntFilemanagerV2FolderTree extends Component {
  static template = "int_filemanager.v2.FolderTree";
  static props = {
    activeId: {type: [Number, Boolean]},
    onSelectFolder: {type: Function},
    registerApi: {type: Function, optional: true},
  };

  setup() {
    this.actionService = useService("action");
    this.orm = useService("orm");
    this.nodes = useState({
      [ROOT_KEY]: makeNode(false, _t("All folders"), true),
    });
    onMounted(() => {
      this.props.registerApi?.({
        invalidate: (id) => this.invalidate(id),
        refresh: (id) => this.refresh(id),
      });
      this.ensureExpandedTo(this.props.activeId);
    });
    onWillUpdateProps((nextProps) => {
      if (nextProps.activeId !== this.props.activeId) {
        this.ensureExpandedTo(nextProps.activeId);
      }
    });
  }

  /** Loads the direct sub-folders of a node unless that already happened. */
  async ensureLoaded(key) {
    const node = this.nodes[key];
    if (!node || node.loaded || node.loading) {
      return;
    }
    node.loading = true;
    try {
      const children = await this.orm.call("int_filemanager.node", "tree_children", [
        node.id,
      ]);
      for (const child of children) {
        const childKey = keyOf(child.id);
        const existing = this.nodes[childKey];
        if (existing) {
          // Known from before (e.g. a reload after a change): refresh what the
          // server owns, keep whether the child itself is open.
          existing.name = child.name;
          existing.hasChildren = child.has_children;
        } else {
          this.nodes[childKey] = makeNode(child.id, child.name, child.has_children);
        }
      }
      node.children = children.map((child) => keyOf(child.id));
      node.loaded = true;
    } finally {
      node.loading = false;
    }
  }

  /**
   * Opens the whole chain of ancestors of a folder, loading only levels not known yet:
   * a jump deep into the tree (breadcrumb, double click, F5) costs one call per unknown
   * level, never the whole tree.
   */
  async ensureExpandedTo(folderId) {
    this.nodes[ROOT_KEY].expanded = true;
    await this.ensureLoaded(ROOT_KEY);
    if (!folderId) {
      return;
    }
    let chain = [];
    try {
      chain = await this.orm.call("int_filemanager.node", "breadcrumb", [folderId]);
    } catch {
      return; // A folder that is gone or unreadable: the tree just stays as it is
    }
    let parentKey = ROOT_KEY;
    for (const crumb of chain) {
      const parent = this.nodes[parentKey];
      if (!parent) {
        return;
      }
      parent.expanded = true;
      await this.ensureLoaded(parentKey);
      parentKey = keyOf(crumb.id);
    }
    const node = this.nodes[parentKey];
    if (node && node.hasChildren) {
      node.expanded = true;
      await this.ensureLoaded(parentKey);
    }
  }

  /**
   * Forgets what was loaded for a node (after creating, renaming, deleting, moving); the
   * next time it is opened it is fetched again.
   */
  invalidate(id) {
    const node = this.nodes[keyOf(id)];
    if (node) {
      node.loaded = false;
    }
  }

  async refresh(id) {
    this.invalidate(id);
    const node = this.nodes[keyOf(id)];
    if (!node?.expanded) {
      return;
    }
    try {
      await this.ensureLoaded(keyOf(id));
    } catch {
      // Best effort: a failing refresh must not break the list reload that called it.
    }
  }

  /**
   * One click target does both, like Odoo's own category tree: it navigates and it
   * opens/closes. A node that is already active AND open closes; every other click opens.
   */
  async onClickNode(node) {
    const wasActive =
      node.id === this.props.activeId || (!node.id && !this.props.activeId);
    if (node.hasChildren) {
      if (node.expanded && wasActive) {
        node.expanded = false;
      } else {
        node.expanded = true;
        await this.ensureLoaded(keyOf(node.id));
      }
    }
    if (!wasActive) {
      this.props.onSelectFolder(node.id, node.hasChildren);
    }
  }

  caretLabel(node) {
    return node.expanded ? _t("Collapse folder") : _t("Expand folder");
  }

  isActive(node) {
    return node.id === this.props.activeId || (!node.id && !this.props.activeId);
  }

  onClickTrash() {
    this.actionService.doAction("int_filemanager.action_int_filemanager_node_trash");
  }
}
