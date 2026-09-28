/** @odoo-module **/

// Turns what a user hands to the browser - a file chooser (with folders) or a drop -
// into the flat list [{file, path}] that upload_plan.js works from; `path` is the list
// of folder names between the upload target and the file. Tested with fakes in Node.

// System litter that nobody means to upload.
const IGNORED_NAMES = new Set([".DS_Store", "Thumbs.db", "desktop.ini"]);

function keep(name) {
  return !IGNORED_NAMES.has(name);
}

/**
 * From an <input type="file" webkitdirectory> or a plain multi-file input.
 * @param {FileList|File[]} files
 * @returns {Array<{file: File, path: string[]}>}
 */
export function entriesFromFiles(files) {
  const entries = [];
  for (const file of files) {
    if (!keep(file.name)) {
      continue;
    }
    const relative = file.webkitRelativePath || "";
    const parts = relative ? relative.split("/") : [];
    entries.push({file, path: parts.slice(0, -1)});
  }
  return entries;
}

function readEntries(reader) {
  return new Promise((resolve, reject) => reader.readEntries(resolve, reject));
}

function fileOf(entry) {
  return new Promise((resolve, reject) => entry.file(resolve, reject));
}

async function walk(entry, path, out) {
  if (entry.isFile) {
    if (keep(entry.name)) {
      out.push({file: await fileOf(entry), path});
    }
    return;
  }
  if (!entry.isDirectory || !keep(entry.name)) {
    return;
  }
  const reader = entry.createReader();
  const inside = [...path, entry.name];
  let hasContent = false;
  // A reader hands out at most ~100 entries per call: ask until it answers empty.
  for (;;) {
    const batch = await readEntries(reader);
    if (!batch.length) {
      break;
    }
    hasContent = true;
    for (const child of batch) {
      await walk(child, inside, out);
    }
  }
  if (!hasContent) {
    out.push({folderOnly: true, path: inside});
  }
}

/**
 * From a drop event's DataTransfer, folders included. The entries must be taken
 * SYNCHRONOUSLY while the event is being handled (the browser invalidates the items
 * afterwards), which is why this splits into a sync and an async half.
 * @param {DataTransfer} dataTransfer
 * @returns {() => Promise<Array<{file?: File, path: string[], folderOnly?: boolean}>>}
 */
export function startDropWalk(dataTransfer) {
  const roots = [];
  for (const item of dataTransfer.items || []) {
    if (item.kind !== "file") {
      continue;
    }
    const entry =
      typeof item.webkitGetAsEntry === "function" ? item.webkitGetAsEntry() : null;
    roots.push(entry || {plainFile: item.getAsFile()});
  }
  const plain = roots.length ? [] : [...(dataTransfer.files || [])];
  return async () => {
    const out = [];
    for (const root of roots) {
      if (root.plainFile) {
        if (keep(root.plainFile.name)) {
          out.push({file: root.plainFile, path: []});
        }
      } else {
        await walk(root, [], out);
      }
    }
    for (const file of plain) {
      if (keep(file.name)) {
        out.push({file, path: []});
      }
    }
    return out;
  };
}
