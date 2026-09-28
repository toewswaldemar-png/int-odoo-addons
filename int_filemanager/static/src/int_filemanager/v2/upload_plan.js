/** @odoo-module **/

// From "what the user dropped" to "what to upload where": folder structure, name
// conflicts and the user's decision on each conflict. Pure logic over injected
// server calls, tested with plain Node.
//
//   entries:  [{file, path: ["Photos", "2026"]}]   path = folders between the target
//                                                   and the file (empty for plain files);
//             [{folderOnly: true, path: [...]}]     an empty folder to create
//   plan:     [{file, parentId, name, nodeId?, baseRevisionId?}]  skipped files are absent
//
// deps.call(model, method, kwargs) and deps.newKey() come from the caller.

import {nameKey, uniqueName} from "./utils.js";

export const CONFLICT_ACTIONS = {
  replace: "replace", // A new version of the existing file
  keepBoth: "keep_both", // The new file gets a free name
  skip: "skip",
};

/**
 * Makes sure every folder path below the target exists and returns the id of each,
 * keyed by the path joined with "/". An existing folder is reused (merged into), a
 * missing one is created. Returns which folders were new: nothing inside those can clash.
 */
async function ensureFolders(entries, targetParentId, deps) {
  const ids = new Map([["", targetParentId]]);
  const created = new Set();
  const paths = new Set();
  for (const entry of entries) {
    for (let depth = 1; depth <= entry.path.length; depth++) {
      paths.add(entry.path.slice(0, depth).join("/"));
    }
  }
  // Shallow first, so a folder's parent id is known when it is needed.
  const ordered = [...paths].sort(
    (a, b) => a.split("/").length - b.split("/").length || a.localeCompare(b)
  );
  for (const path of ordered) {
    const parts = path.split("/");
    const name = parts.at(-1);
    const parentId = ids.get(parts.slice(0, -1).join("/"));
    const existing = created.has(parts.slice(0, -1).join("/"))
      ? []
      : await deps.call("int_filemanager.node", "existing_names", {
          parent_id: parentId,
          names: [name],
        });
    const folder = existing.find((n) => n.is_dir);
    if (folder) {
      ids.set(path, folder.id);
    } else if (existing.length) {
      throw new Error(
        `A file named "${name}" already exists here; a folder cannot take its place.`
      );
    } else {
      const made = await deps.call("int_filemanager.node", "create_folder", {
        parent_id: parentId,
        name,
        operation_key: deps.newKey(),
      });
      ids.set(path, made.node_id);
      created.add(path);
    }
  }
  return {ids, created};
}

/**
 * @param {Array<{file: File, path: string[]}>} entries
 * @param {Number} targetParentId
 * @param {Object} deps  call, newKey
 * @param {(conflicts: Array<{name: string, isDir: boolean, file: File}>) => Promise<Map<File, string>>} resolveConflicts
 *   asks the user; returns a CONFLICT_ACTIONS value per conflicting file
 * @returns {Promise<Array>} the plan
 */
export async function planUpload(entries, targetParentId, deps, resolveConflicts) {
  const {ids, created} = await ensureFolders(entries, targetParentId, deps);

  // Group the files by their folder, then ask the server once per folder. Entries that
  // only stand for an (empty) folder have been created above and carry no file.
  const byFolder = new Map();
  for (const entry of entries.filter((e) => e.file)) {
    const key = entry.path.join("/");
    if (!byFolder.has(key)) {
      byFolder.set(key, []);
    }
    byFolder.get(key).push(entry);
  }

  const planned = [];
  const conflicts = [];
  for (const [key, group] of byFolder) {
    const parentId = ids.get(key);
    const existing = created.has(key)
      ? []
      : await deps.call("int_filemanager.node", "existing_names", {
          parent_id: parentId,
          names: group.map((entry) => entry.file.name),
        });
    const existingByKey = new Map(existing.map((n) => [nameKey(n.name), n]));
    // "Keep both" must not pick a name that another file of this same drop keeps.
    const takenKeys = new Set([
      ...existingByKey.keys(),
      ...group.map((entry) => nameKey(entry.file.name)),
    ]);
    for (const entry of group) {
      const clash = existingByKey.get(nameKey(entry.file.name));
      const item = {
        file: entry.file,
        parentId,
        name: entry.file.name,
        clash,
        takenKeys,
      };
      if (clash) {
        conflicts.push({name: entry.file.name, isDir: clash.is_dir, file: entry.file});
      }
      planned.push(item);
    }
  }

  const decisions = conflicts.length ? await resolveConflicts(conflicts) : new Map();
  const plan = [];
  for (const item of planned) {
    if (!item.clash) {
      plan.push({file: item.file, parentId: item.parentId, name: item.name});
      continue;
    }
    const action = decisions.get(item.file) || CONFLICT_ACTIONS.skip;
    if (action === CONFLICT_ACTIONS.skip) {
      continue;
    }
    // A file may be replaced by a new version only when what is there is a file.
    if (action === CONFLICT_ACTIONS.replace && !item.clash.is_dir) {
      plan.push({
        file: item.file,
        parentId: item.parentId,
        name: item.name,
        nodeId: item.clash.id,
        baseRevisionId: item.clash.current_revision_id,
      });
    } else {
      const name = uniqueName(item.name, item.takenKeys);
      item.takenKeys.add(nameKey(name));
      plan.push({file: item.file, parentId: item.parentId, name});
    }
  }
  return plan;
}
