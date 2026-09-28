/** @odoo-module **/

// Folder navigation of the v2 explorer lives in the search model, not in the action's
// domain: the folder id (or nothing = the top of the caller's tree) is ANDed onto whatever
// the user searched or filtered. It is the only writer of that part of the domain - the
// list model reloads by itself when the search model notifies (useModel/WithSearch), so
// a second writer would race it.
//
// The folder id is kept in the URL (int_filemanager_folder) so that F5 stays where it was.
import {Domain} from "@web/core/domain";
import {router} from "@web/core/browser/router";
import {SearchModel} from "@web/search/search_model";

const FOLDER_URL_KEY = "int_filemanager_folder";
// Odoo rebuilds the URL on every controller mount and drops keys it does not know
// about, unless they are registered as locked.
router.addLockedKey(FOLDER_URL_KEY);

// The name of the marker filter in the search view (no domain of its own).
const RECURSIVE_FILTER_NAME = "filter_search_recursive";

export class IntFilemanagerV2SearchModel extends SearchModel {
  setup(services) {
    super.setup(services);
    const fromUrl = Number(router.current[FOLDER_URL_KEY]);
    this.folderId = Number.isInteger(fromUrl) && fromUrl > 0 ? fromUrl : false;
  }

  /**
   * Opens a folder (false = the top). replaceState, not pushState: every folder click
   * updates the URL without adding a browser history entry.
   * @param {number|false} folderId
   */
  setFolder(folderId) {
    this.folderId = folderId || false;
    router.replaceState({[FOLDER_URL_KEY]: this.folderId || undefined});
    this._notify();
  }

  _isRecursive() {
    const filterActive = this.query.some(
      (element) =>
        this.searchItems[element.searchItemId]?.name === RECURSIVE_FILTER_NAME
    );
    return filterActive || Boolean(this.globalContext.int_filemanager_recursive);
  }

  _getFolderDomain() {
    const folderId = this.folderId;
    if (this._isRecursive()) {
      // Everything below the folder, not the folder itself.
      return folderId
        ? new Domain(["&", ["id", "child_of", folderId], ["id", "!=", folderId]])
        : new Domain([]);
    }
    return folderId
      ? new Domain([["parent_id", "=", folderId]])
      : new Domain([["is_visible_top", "=", true]]);
  }

  _getDomain(params = {}) {
    const folderDomain = this._getFolderDomain();
    if (params.raw) {
      return Domain.and([super._getDomain(params), folderDomain]);
    }
    return Domain.and([new Domain(super._getDomain(params)), folderDomain]).toList(
      this.domainEvalContext
    );
  }
}
