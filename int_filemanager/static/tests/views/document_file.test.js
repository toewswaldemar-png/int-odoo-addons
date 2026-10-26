import { describe, expect, test } from "@odoo/hoot";

import { DocumentFile } from "@int_filemanager/int_filemanager/document_file";

const DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

describe("the file of a document", () => {
    test("an office file is shown as a PDF only when it has a preview", () => {
        const waiting = new DocumentFile({ id: 1, mimetype: DOCX, viewer_pdf_checksum: false });
        expect(waiting.isPdf).toBe(false);
        expect(waiting.isViewable).toBe(false);
        const ready = new DocumentFile({ id: 1, mimetype: DOCX, viewer_pdf_checksum: "a".repeat(64) });
        expect(ready.isPdf).toBe(true);
        expect(ready.isViewable).toBe(true);
        expect(ready.urlRoute).toBe("/web/content/int.filemanager.document/1/viewer_pdf_content");
    });

    test("the download is the original, whatever the viewer shows", () => {
        const file = new DocumentFile({ id: 1, mimetype: DOCX, viewer_pdf_checksum: "a".repeat(64) });
        expect(file.downloadUrl).toMatch(/\/1\/content\?/);
    });
});
