// Plain Node tests for the pure logic of the hymn display pages.
import assert from "node:assert/strict";
import test from "node:test";

import { FONTS, fontCss } from "../../src/common/fonts.js";
import {
    fitFontSize,
    formatDate,
    formatTime,
    gapPixels,
    heightBudget,
} from "../../src/common/layout_math.js";
import {
    backspaceTarget,
    canTypeDigit,
    hymnChange,
    isNumpadLocked,
} from "../../src/common/numpad_logic.js";
import { nextStart, remainingFraction } from "../../src/common/reset_timer.js";

test("the choir control is locked while a hymn number stands", () => {
    assert.equal(isNumpadLocked("choir", "123", "123"), true);
    assert.equal(isNumpadLocked("choir", "", ""), false);
    assert.equal(isNumpadLocked("choir", "", "88"), false);
});

test("the hymn control is locked only by a different choir number", () => {
    assert.equal(isNumpadLocked("hymn", "", "88"), true);
    assert.equal(isNumpadLocked("hymn", "123", "123"), false);
    assert.equal(isNumpadLocked("hymn", "12", "88"), true);
    assert.equal(isNumpadLocked("hymn", "", ""), false);
});

test("backspace goes to the number that locks the keys", () => {
    assert.equal(backspaceTarget("hymn", false), "hymn");
    assert.equal(backspaceTarget("choir", false), "choir");
    assert.equal(backspaceTarget("choir", true), "hymn");
    assert.equal(backspaceTarget("hymn", true), "choir");
});

test("at most four digits are typed", () => {
    assert.equal(canTypeDigit(""), true);
    assert.equal(canTypeDigit("123"), true);
    assert.equal(canTypeDigit("1234"), false);
});

test("the change of the hymn number is told apart", () => {
    assert.equal(hymnChange("", "1"), "input");
    assert.equal(hymnChange("12", "1"), "backspace");
    assert.equal(hymnChange("12", "12"), "same");
    assert.equal(hymnChange("12", "34"), "same");
});

test("the remaining share runs from one to zero and stays in range", () => {
    const start = 1_000_000;
    assert.equal(remainingFraction(start, start, 5), 1);
    assert.equal(remainingFraction(start, start + 150_000, 5), 0.5);
    assert.equal(remainingFraction(start, start + 300_000, 5), 0);
    assert.equal(remainingFraction(start, start + 900_000, 5), 0);
    assert.equal(remainingFraction(start, start - 5_000, 5), 1);
    assert.equal(remainingFraction(start, start, 0), 0);
});

test("a new digit restarts the idle time, a deleted one keeps it", () => {
    assert.equal(nextStart("input", 100, 50, 900), 900);
    assert.equal(nextStart("backspace", 100, 50, 900), 100);
    assert.equal(nextStart("backspace", null, 50, 900), 50);
});

test("a state from the server continues the stored idle time", () => {
    assert.equal(nextStart("same", null, 50, 900), 50);
    assert.equal(nextStart("same", 100, 50, 900), 100);
    assert.equal(nextStart("same", null, null, 900), 900);
});

test("the font size fills the share of the width the setting asks for", () => {
    // The text is 400px wide at a reference size of 1000px; the container is 800px wide.
    assert.equal(fitFontSize(1000, 800, 400, 100), 2000);
    assert.equal(fitFontSize(1000, 800, 400, 50), 1000);
    assert.equal(fitFontSize(1000, 800, 400, 75), 1500);
});

test("the font size never exceeds the height limit", () => {
    assert.equal(fitFontSize(1000, 800, 400, 100, 540), 540);
    assert.equal(fitFontSize(1000, 800, 400, 10, 540), 200);
});

test("nothing is fitted before the text can be measured", () => {
    assert.equal(fitFontSize(1000, 800, 0, 100), null);
    assert.equal(fitFontSize(1000, 0, 400, 100), null);
});

test("the height budget splits the screen as the settings ask", () => {
    assert.deepEqual(heightBudget(1000, 75, 75), { clockMode: 500, number: 500, subClock: 500 });
    assert.deepEqual(heightBudget(1000, 75, 25), { clockMode: 500, number: 750, subClock: 250 });
    assert.deepEqual(heightBudget(1000, 0, 0), { clockMode: 500, number: 500, subClock: 500 });
});

test("the gap is a share of what the two lines leave over", () => {
    assert.equal(gapPixels(1000, 300, 200, 0), 0);
    assert.equal(gapPixels(1000, 300, 200, 50), 250);
    assert.equal(gapPixels(1000, 300, 200, 100), 500);
    assert.equal(gapPixels(1000, 700, 600, 50), 0);
    assert.equal(gapPixels(1000, 0, 200, 50), null);
});

test("time and date are written like the old display wrote them", () => {
    const date = new Date(2026, 9, 3, 7, 5);
    assert.equal(formatTime(date), "07:05");
    assert.equal(formatDate(date), "03.10.2026");
});

test("every font has a key, a label and a CSS value, and unknown keys fall back", () => {
    for (const font of FONTS) {
        assert.ok(font.key && font.label && font.css);
    }
    assert.equal(fontCss("georgia"), "Georgia, serif");
    assert.equal(fontCss("unknown"), FONTS[0].css);
});
