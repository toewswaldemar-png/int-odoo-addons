// Plain Node tests for the remembered download revisions.
import assert from "node:assert/strict";
import test from "node:test";

import {DownloadBases} from "../../src/int_filemanager/v2/download_bases.js";

function memoryStorage() {
    let value = {};
    return {
        load: () => JSON.parse(JSON.stringify(value)),
        save: (v) => {
            value = JSON.parse(JSON.stringify(v));
        },
    };
}

test("a remembered revision is handed out once", () => {
    const bases = new DownloadBases(memoryStorage());
    bases.remember(7, 42);
    assert.equal(bases.take(7), 42);
    assert.equal(bases.take(7), false);
});

test("bases of different files do not mix", () => {
    const bases = new DownloadBases(memoryStorage());
    bases.remember(7, 42);
    bases.remember(8, 50);
    assert.equal(bases.take(8), 50);
    assert.equal(bases.take(7), 42);
});

test("downloading again replaces the earlier base", () => {
    const bases = new DownloadBases(memoryStorage());
    bases.remember(7, 42);
    bases.remember(7, 43);
    assert.equal(bases.take(7), 43);
});

test("nothing is remembered without a revision, and nothing is known for other files", () => {
    const bases = new DownloadBases(memoryStorage());
    bases.remember(7, false);
    assert.equal(bases.take(7), false);
    assert.equal(bases.take(99), false);
});

test("a base older than 30 days is dropped", () => {
    let now = 1000;
    const bases = new DownloadBases(memoryStorage(), () => now);
    bases.remember(7, 42);
    now += 31 * 24 * 60 * 60 * 1000;
    assert.equal(bases.take(7), false);
});
