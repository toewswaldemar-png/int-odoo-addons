/** @odoo-module **/

// EXPERIMENT (branch experiment/native-listview): does a real Odoo list view,
// bound directly to int_filemanager.file, work well as a file browser? Only
// override needed: clicking a folder row reloads the same list with a new
// domain instead of opening a (non-existent) form view - see ListRenderer's
// onCellClicked -> this.props.openRecord(record) in list_renderer.js, which
// comes from ListController.openRecord (list_controller.js). Everything else
// (sort, optional columns incl. Properties splitting, selection, ActionMenus,
// pager, breadcrumbs) is untouched native ListView behaviour.
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";

export class IntFilemanagerListController extends ListController {
    setup() {
        super.setup();
        this.currentPath = "";
        // Everything already on the stack when this controller was created (normally
        // just the "Dateimanager (nativ, Test)" action entry itself) stays as-is; folder
        // levels get appended after it. Breadcrumbs.xml always renders the LAST array
        // entry as the current (bold, non-clickable) one and everything before it as a
        // real link - so no special-casing needed for "which crumb is active".
        this.rootBreadcrumbCount = this.env.config.breadcrumbs.length;
    }

    async openRecord(record) {
        if (record.data.is_dir) {
            await this.goToFolder(record.data.path);
            return;
        }
        window.open(`/int_filemanager/download?path=${encodeURIComponent(record.data.path)}`, "_blank");
    }

    async goToFolder(path) {
        this.currentPath = path;
        await this.model.load({ domain: [["folder_path", "=", path || false]] });
        this.updateBreadcrumbs(path);
    }

    updateBreadcrumbs(path) {
        const crumbs = this.env.config.breadcrumbs;
        crumbs.length = this.rootBreadcrumbCount;
        let acc = "";
        for (const part of path ? path.split("/").filter(Boolean) : []) {
            acc = acc ? `${acc}/${part}` : part;
            const target = acc;
            crumbs.push({
                jsId: `int_filemanager_crumb_${target}`,
                name: part,
                isFormView: false,
                url: "#",
                onSelected: () => this.goToFolder(target),
            });
        }
    }
}

registry.category("views").add("int_filemanager_list", {
    ...listView,
    Controller: IntFilemanagerListController,
});
