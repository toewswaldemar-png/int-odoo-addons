// Plain Node tests for the download URL and base64 helpers.
import assert from "node:assert/strict";
import test from "node:test";

import {downloadUrl, textToBase64} from "../../src/int_filemanager/v2/utils.js";

test("downloadUrl", () => {
    assert.equal(downloadUrl(5), "/int_filemanager/v2/download/5");
    assert.equal(
        downloadUrl(5, {revisionId: 9, inline: true}),
        "/int_filemanager/v2/download/5?revision_id=9&disposition=inline"
    );
});

test("textToBase64 round-trips unicode and big text", () => {
    const text = "Grüße ✓ \u{1F600}";
    assert.equal(Buffer.from(textToBase64(text), "base64").toString("utf8"), text);
    const big = `${"x".repeat(200000)}ä`;
    assert.equal(Buffer.from(textToBase64(big), "base64").toString("utf8"), big);
});
