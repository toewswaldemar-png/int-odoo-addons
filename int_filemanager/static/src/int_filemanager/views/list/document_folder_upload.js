/**
 * Folders of the disk for the upload: a tree is the files, each with the path of its folder
 * relative to the upload (`dir`, "" at the top), and the paths of empty folders.
 * @typedef {{file: File, dir: String}} TreeFile
 * @typedef {{files: TreeFile[], folders: String[], unreadable: String[]}} Tree
 */

// Chrome gives at most a hundred entries per call: `readEntries` reads until none come.
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

/** The folders that were dropped, with everything in them. */
export async function readDroppedFolders(entries) {
    const tree = { files: [], folders: [], unreadable: [] };
    for (const entry of entries) {
        await walk(entry, "", tree);
    }
    return tree;
}

/** The files of an input with `webkitdirectory`; an empty folder is not in the list. */
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

/** Every folder that the tree needs, parents included. */
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
 * The paths to ask the server for: the folder of every file and every empty folder (the top, "",
 * is the folder of the upload itself). The server makes the folders above them. Its answer has the
 * id of the paths asked for only, and a file goes to the folder of its `dir`: a path that is no
 * `dir` of a file and no empty folder is not needed, one that is must be there.
 * @param {Tree} tree
 * @returns {String[]}
 */
export function foldersToMake(tree) {
    const paths = new Set([...tree.files.map((item) => item.dir), ...tree.folders]);
    paths.delete("");
    return [...paths];
}

export function uploadError(xhr) {
    try {
        return JSON.parse(xhr.responseText).error.message || "";
    } catch {
        return "";
    }
}
