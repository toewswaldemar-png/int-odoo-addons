// Plain Node tests for the pure helpers of the v2 explorer:
//   node --test int_filemanager/static/tests/js
import assert from "node:assert/strict";
import test from "node:test";

import {
    errorMessage,
    extOf,
    humanSize,
    isTypingContext,
    nameKey,
    newOperationKey,
    uniqueName,
} from "../../src/int_filemanager/v2/utils.js";

test("operation keys are unique and long enough to never clash", () => {
    const keys = new Set(Array.from({length: 500}, () => newOperationKey()));
    assert.equal(keys.size, 500);
    for (const key of keys) {
        assert.ok(key.length >= 32);
    }
});

test("operation key works without randomUUID (insecure context)", () => {
    const original = globalThis.crypto.randomUUID;
    Object.defineProperty(globalThis.crypto, "randomUUID", {
        value: undefined,
        configurable: true,
    });
    try {
        const key = newOperationKey();
        assert.match(key, /^[0-9a-f]{32}$/);
    } finally {
        Object.defineProperty(globalThis.crypto, "randomUUID", {
            value: original,
            configurable: true,
        });
    }
});

test("extOf", () => {
    assert.equal(extOf("a.TXT"), "txt");
    assert.equal(extOf("archive.tar.gz"), "gz");
    assert.equal(extOf("noext"), "");
    assert.equal(extOf(".hidden"), "");
    assert.equal(extOf("trailing."), "");
});

test("humanSize", () => {
    assert.equal(humanSize(0), "0 Bytes");
    assert.equal(humanSize(512), "512 Bytes");
    assert.equal(humanSize(1024), "1.0 KB");
    assert.equal(humanSize(1536), "1.5 KB");
    assert.equal(humanSize(5 * 1024 * 1024), "5.0 MB");
    assert.equal(humanSize(3 * 1024 ** 3), "3.0 GB");
    assert.equal(humanSize(200 * 1024 ** 2), "200 MB");
    assert.equal(humanSize(undefined), "0 Bytes");
});

test("nameKey ignores case and normalises NFC", () => {
    assert.equal(nameKey("Rückblick.TXT"), nameKey("Rückblick.txt"));
});

test("uniqueName keeps a free name and numbers a taken one", () => {
    assert.equal(uniqueName("a.txt", []), "a.txt");
    assert.equal(uniqueName("a.txt", ["A.TXT"]), "a (2).txt");
    assert.equal(uniqueName("a.txt", ["a.txt", "a (2).txt"]), "a (3).txt");
    assert.equal(uniqueName("folder", ["Folder"]), "folder (2)");
    assert.equal(uniqueName(".env", [".env"]), ".env (2)");
    assert.equal(uniqueName("x.tar.gz", ["x.tar.gz"]), "x.tar (2).gz");
});

test("isTypingContext", () => {
    assert.equal(isTypingContext(null), false);
    assert.equal(isTypingContext({tagName: "TEXTAREA"}), true);
    assert.equal(isTypingContext({tagName: "DIV", isContentEditable: true}), true);
    assert.equal(isTypingContext({tagName: "INPUT", type: "text"}), true);
    assert.equal(isTypingContext({tagName: "INPUT", type: "checkbox"}), false);
    assert.equal(isTypingContext({tagName: "DIV"}), false);
});

test("errorMessage prefers the server message", () => {
    assert.equal(errorMessage({data: {message: "server said"}, message: "x"}), "server said");
    assert.equal(errorMessage(new Error("plain")), "plain");
    assert.equal(errorMessage("text"), "text");
});
