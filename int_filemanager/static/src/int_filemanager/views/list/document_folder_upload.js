/**
 * Folders of the disk for the upload: reading what the browser hands over, and sorting out the
 * folders that have to be made first.
 *
 * A tree is a list of files, each with the path of the folder it lies in relative to the folder
 * of the upload (`dir`, "" for a file at the top), and the paths of the folders that have nothing
 * in them. Nothing here talks to the server.
 *
 * @typedef {{file: File, dir: String}} TreeFile
 * @typedef {{files: TreeFile[], folders: String[], unreadable: String[]}} Tree
 */

// The browser gives at most a hundred entries of a folder per call (Chrome): read until none come.
function readBatch(reader) {
    return new Promise((resolve, reject) => reader.readEntries(resolve, reject));
}

async function readEntries(directory) {
    const reader = directory.createReader();
    const entries = [];
    for (;;) {
        const batch = await readBatch(reader);
        if (!batch.length) {
            return entries;
        }
        entries.push(...batch);
    }
}

function readFile(entry) {
    return new Promise((resolve, reject) => entry.file(resolve, reject));
}

async function walk(entry, dir, tree) {
    const path = dir ? `${dir}/${entry.name}` : entry.name;
    if (entry.isFile) {
        try {
            tree.files.push({ file: await readFile(entry), dir });
        } catch {
            tree.unreadable.push(path);
        }
        return;
    }
    let entries;
    try {
        entries = await readEntries(entry);
    } catch {
        tree.unreadable.push(path);
        return;
    }
    if (!entries.length) {
        tree.folders.push(path);
    }
    for (const child of entries) {
        await walk(child, path, tree);
    }
}

/**
 * The folders that were dropped, with everything in them. The entries come from
 * `item.webkitGetAsEntry()`, which has to be called while the drop is going on: the items are
 * gone after the first `await`.
 * @param {FileSystemEntry[]} entries
 * @returns {Promise<Tree>}
 */
export async function readDroppedFolders(entries) {
    const tree = { files: [], folders: [], unreadable: [] };
    for (const entry of entries) {
        await walk(entry, "", tree);
    }
    return tree;
}

/**
 * The files that an input with `webkitdirectory` gives: each knows its path from the chosen
 * folder (`webkitRelativePath`, "Photos/2025/a.jpg"). An empty folder is not in the list.
 * @param {File[]} files
 * @returns {Tree}
 */
export function readChosenFolder(files) {
    return {
        files: files.map((file) => {
            const parts = (file.webkitRelativePath || file.name).split("/");
            return { file, dir: parts.slice(0, -1).join("/") };
        }),
        folders: [],
        unreadable: [],
    };
}

/**
 * Every folder that the tree needs, parents included, for the number the user is told.
 * @param {Tree} tree
 * @returns {Set<String>}
 */
export function allFolders(tree) {
    const folders = new Set();
    for (const path of [...tree.files.map((item) => item.dir), ...tree.folders]) {
        const parts = path ? path.split("/") : [];
        for (let depth = 1; depth <= parts.length; depth++) {
            folders.add(parts.slice(0, depth).join("/"));
        }
    }
    return folders;
}

/**
 * The paths to make on the server: the deepest ones suffice, the server makes the folders above.
 * @param {Tree} tree
 * @returns {String[]}
 */
export function foldersToMake(tree) {
    const all = allFolders(tree);
    const parents = new Set([...all].map((path) => path.split("/").slice(0, -1).join("/")));
    return [...all].filter((path) => !parents.has(path));
}

/**
 * The reason that the route of the upload gave for a failure, as the text it sent.
 * @param {XMLHttpRequest} xhr
 * @returns {String}
 */
export function uploadError(xhr) {
    try {
        return JSON.parse(xhr.responseText).error.message || "";
    } catch {
        return "";
    }
}
