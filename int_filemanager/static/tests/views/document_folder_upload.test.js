import { describe, expect, test } from "@odoo/hoot";

import {
    allFolders,
    foldersToMake,
} from "@int_filemanager/int_filemanager/views/list/document_folder_upload";

const file = (dir) => ({ file: {}, dir });

describe("the folders of an upload of a folder", () => {
    test("the folders of the files and the empty folders are asked for, not the ones between", () => {
        const tree = { files: [file("A/B/C")], folders: ["A/empty"], unreadable: [] };
        expect(foldersToMake(tree).sort()).toEqual(["A/B/C", "A/empty"]);
        // "A" and "A/B" hold nothing: they are made, as the parents, and need no id.
    });

    test("a folder with files and subfolders is asked for too, its files need its id", () => {
        // The folder "Artikel" holds files and has subfolders: the upload of a file asks for the
        // id of its folder in the answer, which has only the paths that were sent.
        const tree = {
            files: [file("Artikel"), file("Artikel/Archiv"), file("Artikel/Archiv/2024")],
            folders: [],
            unreadable: [],
        };
        const paths = foldersToMake(tree);
        expect(paths.sort()).toEqual(["Artikel", "Artikel/Archiv", "Artikel/Archiv/2024"]);
        for (const { dir } of tree.files) {
            expect(paths).toInclude(dir);
        }
    });

    test("files at the top have no folder to make", () => {
        const tree = { files: [file("")], folders: [], unreadable: [] };
        expect(foldersToMake(tree)).toEqual([]);
        expect([...allFolders(tree)]).toEqual([]);
    });
});
