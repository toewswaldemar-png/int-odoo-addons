/** @odoo-module **/

// What the explorer controller does to files and folders: create, rename, move, copy,
// delete, download, versions, sharing, opening. Every change goes through one of the
// write methods of int_filemanager.node with a fresh operation key (a retried request is
// then answered from the stored result, never done twice), never through a plain ORM
// write from the browser: the write methods check the rights and the name rules in one
// place.
import {onWillUnmount, useState, useSubEnv} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {useFileViewer} from "@web/core/file_viewer/file_viewer_hook";
import {useService} from "@web/core/utils/hooks";
import {NODE_MODEL} from "./controller_navigation.js";
import {IntFilemanagerV2MoveDialog} from "./move_dialog.js";
import {IntFilemanagerV2TextEditorDialog} from "./text_editor_dialog.js";
import {IntFilemanagerV2TextInputDialog} from "./text_input_dialog.js";
import {IntFilemanagerV2VersionsDialog} from "./versions_dialog.js";
import {
  downloadUrl,
  errorMessage,
  extOf,
  newOperationKey,
  uniqueName,
} from "./utils.js";

const VIDEO_EXTENSIONS = new Set(["mp4", "webm", "ogv"]);
const VIDEO_MIME_TYPES = {mp4: "video/mp4", webm: "video/webm", ogv: "video/ogg"};
// Formats every browser plays without an extra codec (no mov, no wma).
const AUDIO_EXTENSIONS = new Set(["mp3", "wav", "flac", "ogg", "m4a", "aac"]);
const AUDIO_MIME_TYPES = {
  mp3: "audio/mpeg",
  wav: "audio/wav",
  flac: "audio/flac",
  ogg: "audio/ogg",
  m4a: "audio/mp4",
  aac: "audio/aac",
};
// Plain text opens the editor instead of a read-only preview.
const TEXT_EDIT_EXTENSIONS = new Set(["txt", "csv", "log", "md", "json"]);
const PREVIEWABLE_EXTENSIONS = new Set([
  "pdf",
  "png",
  "jpg",
  "jpeg",
  "gif",
  "webp",
  "bmp",
  "svg",
  ...VIDEO_EXTENSIONS,
]);

export const isPreviewable = (name) => PREVIEWABLE_EXTENSIONS.has(extOf(name));

// Formats the browser cannot show have a large preview made by the server, there once
// full_preview_state says so: a picture for TIFF, HEIC and camera RAW, a PDF for office
// documents.
const OFFICE_EXTENSIONS = new Set([
  "doc",
  "docx",
  "odt",
  "rtf",
  "xls",
  "xlsx",
  "ods",
  "ppt",
  "pptx",
  "odp",
]);
const isOffice = (name) => OFFICE_EXTENSIONS.has(extOf(name));

export const largePreviewUrl = (record) => {
  const revision = record.data.current_revision_id;
  if (record.data.full_preview_state !== "ready" || !revision) {
    return "";
  }
  const kind = isOffice(record.data.name) ? "preview_pdf" : "preview";
  return `/int_filemanager/v2/preview/${revision.id}/${kind}`;
};

const canPreview = (record) =>
  isPreviewable(record.data.name) || Boolean(largePreviewUrl(record));

export const mutationsMixin = (Base) =>
  class extends Base {
    setup() {
      super.setup();
      this.fileViewer = useFileViewer();
      this.audioPlayer = useService("int_filemanager.audioPlayer");
      this.busService = useService("bus_service");

      // Inline rename (F2). The <input> lives in the name field widget, at the place of
      // its text; the widget reaches this state through the env. It commits through
      // _performRename like the dialog does, never through Odoo's list inline editing,
      // which would write the field directly and skip the rename rules.
      this.renameState = useState({recordId: null, value: ""});
      useSubEnv({
        filemanagerRename: {
          state: this.renameState,
          commit: (name) => this._commitRename(name),
          cancel: () => {
            this.renameState.recordId = null;
          },
        },
      });

      // A big ZIP is built in the background; the server tells the requester here.
      this._onZipReady = (payload) => this._notifyZip(payload);
      this.busService.subscribe("int_filemanager_zip", this._onZipReady);
      onWillUnmount(() =>
        this.busService.unsubscribe("int_filemanager_zip", this._onZipReady)
      );
    }

    async _call(method, kwargs) {
      return this.orm.call(NODE_MODEL, method, [], kwargs);
    }

    _fail(error) {
      this.notification.add(errorMessage(error), {type: "danger"});
    }

    /**
     * Reloads the list, keeps the selection (Odoo builds new records on every load, which
     * drops it) and refreshes the tree level that is open.
     */
    async reload() {
      const selectedIds = new Set(this.model.root.selection.map((r) => r.resId));
      await this.model.load();
      if (selectedIds.size) {
        for (const record of this.model.root.records) {
          if (selectedIds.has(record.resId)) {
            record.toggleSelection(true);
          }
        }
      }
      await this.refreshTree();
    }

    /** Runs one operation per record, reloads, and reports what failed together. */
    async _forEach(records, operation) {
      const errors = [];
      for (const record of records) {
        try {
          await operation(record);
        } catch (error) {
          errors.push(errorMessage(error));
        }
      }
      this.forgetCrumbs();
      await this.reload();
      if (errors.length) {
        this.notification.add(errors.join("\n"), {type: "danger"});
      }
    }

    // ---------------------------------------------------------------- create

    onNewFolder() {
      if (!this.canCreateHere) {
        return;
      }
      this.dialog.add(IntFilemanagerV2TextInputDialog, {
        title: _t("New folder"),
        label: _t("Name of the new folder"),
        confirmLabel: _t("Create"),
        confirm: async (name) => {
          try {
            await this._call("create_folder", {
              parent_id: this.currentFolderId,
              name,
              operation_key: newOperationKey(),
            });
            await this.reload();
          } catch (error) {
            this._fail(error);
          }
        },
      });
    }

    // ---------------------------------------------------------------- rename

    async _performRename(record, name) {
      if (!name || name === record.data.name) {
        return;
      }
      try {
        await this._call("rename_or_move", {
          node_id: record.resId,
          new_parent_id: false,
          new_name: name,
          operation_key: newOperationKey(),
        });
        this.forgetCrumbs();
        await this.reload();
      } catch (error) {
        this._fail(error);
      }
    }

    onRename(record) {
      this.dialog.add(IntFilemanagerV2TextInputDialog, {
        title: _t("Rename"),
        label: _t("New name"),
        value: record.data.name,
        confirmLabel: _t("Rename"),
        confirm: (name) => this._performRename(record, name),
      });
    }

    // F2 on exactly one selected row; more or none makes no sense.
    onF2Rename() {
      const selection = this.model.root.selection;
      if (selection.length !== 1) {
        return;
      }
      this.renameState.recordId = selection[0].resId;
      this.renameState.value = selection[0].data.name;
    }

    // RecordId is cleared at once, not after the request: the cell goes back to plain text
    // immediately instead of staying editable until the server answers.
    async _commitRename(name) {
      const recordId = this.renameState.recordId;
      this.renameState.recordId = null;
      if (!recordId) {
        return;
      }
      const record = this.model.root.records.find((r) => r.resId === recordId);
      if (record) {
        await this._performRename(record, name);
      }
    }

    // ---------------------------------------------------------------- delete

    onDeleteSelected() {
      const records = this.model.root.selection;
      const count = records.length;
      this.dialog.add(ConfirmationDialog, {
        title: _t("Move to the trash"),
        body:
          count === 1
            ? _t("Move 1 item to the trash?")
            : _t("Move %s items to the trash?", count),
        confirmLabel: _t("Move"),
        confirmClass: "btn-primary",
        confirm: () =>
          this._forEach(records, (record) =>
            this._call("trash", {
              node_id: record.resId,
              operation_key: newOperationKey(),
            })
          ),
      });
    }

    // ---------------------------------------------------------------- move, copy

    /** Whether *target* is one of *records* or lies below one of them (a folder cannot go into itself). */
    async _invalidMoveTarget(records, targetId) {
      for (const record of records) {
        if (record.resId === targetId) {
          return true;
        }
        if (record.data.is_dir) {
          const chain = await this._chainFor(targetId);
          if (chain.some((crumb) => crumb.id === record.resId)) {
            return true;
          }
        }
      }
      return false;
    }

    async moveRecordsTo(records, targetId) {
      if (await this._invalidMoveTarget(records, targetId)) {
        this.notification.add(_t("A folder cannot be moved into itself."), {
          type: "warning",
        });
        return;
      }
      await this._forEach(records, (record) =>
        this._call("rename_or_move", {
          node_id: record.resId,
          new_parent_id: targetId,
          new_name: record.data.name,
          operation_key: newOperationKey(),
        })
      );
    }

    async copyRecordsTo(records, targetId) {
      if (await this._invalidMoveTarget(records, targetId)) {
        this.notification.add(_t("A folder cannot be copied into itself."), {
          type: "warning",
        });
        return;
      }
      await this._forEach(records, async (record) => {
        // A copy into a folder that has the name already gets a free one ("a (2).txt").
        const taken = await this._call("existing_names", {
          parent_id: targetId,
          names: [record.data.name],
        });
        const name = uniqueName(
          record.data.name,
          taken.map((n) => n.name)
        );
        await this._call("copy_node", {
          node_id: record.resId,
          target_parent_id: targetId,
          new_name: name,
          operation_key: newOperationKey(),
        });
      });
    }

    onMoveSelected() {
      const records = [...this.model.root.selection];
      this.dialog.add(IntFilemanagerV2MoveDialog, {
        title: _t("Move to"),
        confirmLabel: _t("Move here"),
        startFolderId: this.currentFolderId,
        confirm: (targetId) => this.moveRecordsTo(records, targetId),
      });
    }

    onCopySelected() {
      const records = [...this.model.root.selection];
      this.dialog.add(IntFilemanagerV2MoveDialog, {
        title: _t("Copy to"),
        confirmLabel: _t("Copy here"),
        startFolderId: this.currentFolderId,
        confirm: (targetId) => this.copyRecordsTo(records, targetId),
      });
    }

    // ---------------------------------------------------------------- download

    /**
     * One file goes straight to the browser's download; a folder or several items become a
     * ZIP: small ones stream at once, big ones are built in the background (the server
     * answers with a job and tells us over the bus when it is ready).
     */
    async onDownloadSelected() {
      const records = this.model.root.selection;
      if (records.length === 1 && !records[0].data.is_dir) {
        this._startDownload(this._urlToDownload(records[0]));
        return;
      }
      try {
        const result = await this.orm.call(
          "int_filemanager.zip_job",
          "request_zip",
          [],
          {
            node_ids: records.map((r) => r.resId),
            operation_key: newOperationKey(),
          }
        );
        if (result.mode === "direct") {
          this._startDownload(result.url);
        } else {
          this.notification.add(
            _t("The download is big and is being prepared. You will be notified."),
            {type: "info"}
          );
        }
      } catch (error) {
        this._fail(error);
      }
    }

    // Asks for the revision the list shows and remembers it as the base of "New version",
    // so a change by somebody else before the edited copy comes back is reported.
    _urlToDownload(record) {
      const revisionId = record.data.current_revision_id
        ? record.data.current_revision_id.id
        : false;
      this.uploads.rememberBase(record.resId, revisionId);
      return downloadUrl(record.resId, {revisionId});
    }

    // A real link click: the browser shows its download UI without leaving the page.
    _startDownload(url) {
      const link = document.createElement("a");
      link.href = url;
      link.download = "";
      document.body.appendChild(link);
      link.click();
      link.remove();
    }

    _notifyZip(payload) {
      if (payload.state === "done") {
        this.notification.add(_t("%s is ready.", payload.name), {
          type: "success",
          sticky: true,
          buttons: [
            {
              name: _t("Download"),
              primary: true,
              onClick: () =>
                this._startDownload(`/int_filemanager/v2/zip/job/${payload.job_id}`),
            },
          ],
        });
      } else if (payload.state === "failed") {
        this.notification.add(_t("%s could not be prepared.", payload.name), {
          type: "danger",
        });
      }
    }

    // ---------------------------------------------------------------- versions, sharing

    onVersions(record) {
      this.dialog.add(IntFilemanagerV2VersionsDialog, {
        nodeId: record.resId,
        name: record.data.name,
        onChanged: () => this.reload(),
      });
    }

    onShare(record) {
      this.actionService.doAction("int_filemanager.action_int_filemanager_node_share", {
        props: {resId: record.resId},
        onClose: () => this.reload(),
      });
    }

    // Tags, status and contact: a plain Odoo form in a dialog, saved through the ORM (these
    // fields carry no naming or rights rules of their own beyond the record rules).
    onEditDetails(record) {
      this.actionService.doAction(
        "int_filemanager.action_int_filemanager_node_details",
        {
          props: {resId: record.resId},
          onClose: () => this.reload(),
        }
      );
    }

    // ---------------------------------------------------------------- opening

    async openRecord(record) {
      if (record.data.is_dir) {
        this.openFolder(record);
        return;
      }
      const name = record.data.name;
      const ext = extOf(name);
      if (TEXT_EDIT_EXTENSIONS.has(ext)) {
        this.onEditText(record);
      } else if (AUDIO_EXTENSIONS.has(ext)) {
        this.onPlayAudio(record);
      } else if (canPreview(record)) {
        this.onPreview(record);
      } else {
        window.open(this._urlToDownload(record), "_blank");
      }
    }

    async onEditText(record) {
      const response = await fetch(downloadUrl(record.resId, {inline: true}));
      if (!response.ok) {
        this._fail(new Error(_t("The file could not be loaded.")));
        return;
      }
      this.dialog.add(IntFilemanagerV2TextEditorDialog, {
        title: record.data.name,
        nodeId: record.resId,
        // The revision that was loaded: the server refuses the save if it moved on.
        baseRevisionId: record.data.current_revision_id
          ? record.data.current_revision_id.id
          : false,
        content: await response.text(),
        onSaved: () => this.reload(),
      });
    }

    toViewerFile(record) {
      const converted = !isPreviewable(record.data.name) && largePreviewUrl(record);
      if (converted) {
        const isPdf = isOffice(record.data.name);
        return {
          resId: record.resId,
          name: record.data.name,
          downloadUrl: downloadUrl(record.resId),
          isImage: !isPdf,
          isPdf,
          isVideo: false,
          isViewable: true,
          defaultSource: isPdf
            ? `/web/static/lib/pdfjs/web/viewer.html?file=${encodeURIComponent(converted)}#pagemode=none`
            : converted,
        };
      }
      const url = downloadUrl(record.resId, {inline: true});
      const ext = extOf(record.data.name);
      const isPdf = ext === "pdf";
      const isVideo = VIDEO_EXTENSIONS.has(ext);
      const isImage = PREVIEWABLE_EXTENSIONS.has(ext) && !isPdf && !isVideo;
      return {
        resId: record.resId,
        name: record.data.name,
        downloadUrl: downloadUrl(record.resId),
        isImage,
        isPdf,
        isVideo,
        mimetype: isVideo ? VIDEO_MIME_TYPES[ext] : undefined,
        isViewable: isPreviewable(record.data.name),
        defaultSource: isPdf
          ? `/web/static/lib/pdfjs/web/viewer.html?file=${encodeURIComponent(url)}#pagemode=none`
          : url,
      };
    }

    onPreview(record) {
      const files = this.model.root.records
        .filter((r) => !r.data.is_dir && canPreview(r))
        .map((r) => this.toViewerFile(r));
      const file = files.find((f) => f.resId === record.resId);
      this.fileViewer.open(file, files);
    }

    // The queue is all audio files of the folder that is loaded now, in list order; the
    // player keeps playing that list when the user navigates on.
    onPlayAudio(record) {
      const files = this.model.root.records
        .filter((r) => !r.data.is_dir && AUDIO_EXTENSIONS.has(extOf(r.data.name)))
        .map((r) => ({
          path: String(r.resId),
          name: r.data.name,
          downloadUrl: downloadUrl(r.resId, {inline: true}),
          mimetype: AUDIO_MIME_TYPES[extOf(r.data.name)],
          title: "",
          artist: "",
          folderPath: r.data.parent_id ? r.data.parent_id.display_name : "",
        }));
      const startIndex = files.findIndex((f) => f.path === String(record.resId));
      this.audioPlayer.playQueue(files, startIndex);
    }

    // ---------------------------------------------------------------- action menu

    getStaticActionMenuItems() {
      const selection = this.model.root.selection;
      const single = () => selection.length === 1;
      return {
        int_download: {
          isAvailable: () => selection.length > 0,
          sequence: 5,
          icon: "fa fa-download",
          description: _t("Download"),
          callback: () => this.onDownloadSelected(),
        },
        int_versions: {
          isAvailable: () => single() && !selection[0].data.is_dir,
          sequence: 8,
          icon: "fa fa-history",
          description: _t("Versions"),
          callback: () => this.onVersions(selection[0]),
        },
        int_new_version: {
          isAvailable: () => single() && !selection[0].data.is_dir,
          sequence: 9,
          icon: "fa fa-upload",
          description: _t("Upload new version"),
          callback: () => this.triggerNewVersionUpload(selection[0]),
        },
        int_details: {
          isAvailable: single,
          sequence: 10,
          icon: "fa fa-tags",
          description: _t("Tags, status, contact"),
          callback: () => this.onEditDetails(selection[0]),
        },
        int_share: {
          isAvailable: () => single() && !selection[0].data.is_dir,
          sequence: 15,
          icon: "fa fa-share-alt",
          description: _t("Share"),
          callback: () => this.onShare(selection[0]),
        },
        int_rename: {
          isAvailable: single,
          sequence: 20,
          icon: "fa fa-pencil",
          description: _t("Rename"),
          callback: () => this.onRename(selection[0]),
        },
        int_move: {
          isAvailable: () => selection.length > 0,
          sequence: 25,
          icon: "fa fa-arrows",
          description: _t("Move to..."),
          callback: () => this.onMoveSelected(),
        },
        int_copy: {
          isAvailable: () => selection.length > 0,
          sequence: 26,
          icon: "fa fa-clone",
          description: _t("Copy to..."),
          callback: () => this.onCopySelected(),
        },
        int_delete: {
          isAvailable: () => selection.length > 0,
          sequence: 90,
          icon: "fa fa-trash-o",
          class: "text-danger",
          description: _t("Delete"),
          callback: () => this.onDeleteSelected(),
        },
      };
    }
  };
