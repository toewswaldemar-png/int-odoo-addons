import { describe, expect, test } from "@odoo/hoot";

import { DocumentFile } from "@int_filemanager/int_filemanager/document_file";
import { hitLabel } from "@int_filemanager/int_filemanager/fields/content_hits/document_content_hits_field";

const DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

describe("the file of a document", () => {
    test("an office file is shown as a PDF only when it has a preview", () => {
        const waiting = new DocumentFile({ id: 1, mimetype: DOCX, ocr_checksum: false });
        expect(waiting.isPdf).toBe(false);
        expect(waiting.isViewable).toBe(false);
        const ready = new DocumentFile({ id: 1, mimetype: DOCX, ocr_checksum: "a".repeat(64) });
        expect(ready.isPdf).toBe(true);
        expect(ready.isViewable).toBe(true);
        expect(ready.urlRoute).toBe("/web/content/int.filemanager.document/1/ocr_content");
    });

    test("the download is the original, whatever the viewer shows", () => {
        const file = new DocumentFile({ id: 1, mimetype: DOCX, ocr_checksum: "a".repeat(64) });
        expect(file.downloadUrl).toMatch(/\/1\/content\?/);
    });

    test("the pages of the text are pages of the PDF, except for the blocks of the new formats", () => {
        const docx = new DocumentFile({ id: 1, mimetype: DOCX, ocr_checksum: "a".repeat(64) });
        const xls = new DocumentFile({
            id: 3,
            mimetype: "application/vnd.ms-excel",
            ocr_checksum: "b".repeat(64),
        });
        const pdf = new DocumentFile({ id: 2, mimetype: "application/pdf" });
        expect(docx.hasTextPages).toBe(false);
        expect(xls.hasTextPages).toBe(true);
        expect(pdf.hasTextPages).toBe(true);
        expect(hitLabel(docx, { page: 3 })).toBe("Block 3");
        expect(hitLabel(xls, { page: 3 })).toBe("p. 3");
        expect(hitLabel(pdf, { page: 3 })).toBe("p. 3");
    });
});
