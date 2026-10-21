import { describe, expect, test } from "@odoo/hoot";

import {
    opensWithDoubleClick,
    waitsForDoubleClick,
} from "@int_filemanager/int_filemanager/views/document_open_mode";

const settings = (mode) => ({ int_filemanager_open_mode_resolved: mode });

describe("the open mode of a view of documents", () => {
    test("only the double mode on a big screen waits for the second click", () => {
        expect(opensWithDoubleClick({}, settings("double"))).toBe(true);
        expect(opensWithDoubleClick({}, settings("single"))).toBe(false);
        expect(opensWithDoubleClick({ isSmall: true }, settings("double"))).toBe(false);
        // The guest page has no settings: one click.
        expect(opensWithDoubleClick({}, {})).toBe(false);
    });

    test("a click of the keyboard does not wait", () => {
        expect(waitsForDoubleClick({}, { detail: 1 }, settings("double"))).toBe(true);
        expect(waitsForDoubleClick({}, { detail: 2 }, settings("double"))).toBe(true);
        expect(waitsForDoubleClick({}, { detail: 0 }, settings("double"))).toBe(false);
        expect(waitsForDoubleClick({}, { detail: 1 }, settings("single"))).toBe(false);
    });
});
