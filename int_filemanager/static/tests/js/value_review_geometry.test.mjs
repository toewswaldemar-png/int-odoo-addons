// Plain Node tests for the geometry helpers of the value review.
import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_PAGE_SIZE,
  markers,
  pageSize,
  relativeBox,
  shownFields,
  wrapIndex,
} from "../../src/int_filemanager/v2/value_review/value_review_geometry.js";

const SIZES = {1: [200, 400], 2: [100, 100]};

function suggestion(extra = {}) {
  return {page: 1, x0: 20, top: 40, x1: 100, bottom: 80, ...extra};
}

test("a page without a size is taken as A4", () => {
  assert.deepEqual(pageSize(SIZES, 1), [200, 400]);
  assert.deepEqual(pageSize(SIZES, 3), DEFAULT_PAGE_SIZE);
  assert.deepEqual(pageSize(undefined, 1), DEFAULT_PAGE_SIZE);
  assert.deepEqual(pageSize({1: [0, 10]}, 1), DEFAULT_PAGE_SIZE);
});

test("a box is given as shares of its page", () => {
  assert.deepEqual(relativeBox(suggestion(), SIZES), {
    page: 1,
    left: 0.1,
    top: 0.1,
    width: 0.4,
    height: 0.1,
  });
});

test("a box outside the page is cut to it, an empty one is none", () => {
  const cut = relativeBox(suggestion({x1: 500, bottom: 900}), SIZES);
  assert.equal(cut.left + cut.width, 1);
  assert.equal(cut.top + cut.height, 1);
  assert.equal(relativeBox(suggestion({x1: 20}), SIZES), null);
  assert.equal(relativeBox(suggestion({page: 0}), SIZES), null);
  assert.equal(relativeBox(undefined, SIZES), null);
});

test("only the best suggestion of a field with a place is drawn", () => {
  const fields = [
    {field_id: 1, name: "A", suggestions: [suggestion(), suggestion({page: 2})]},
    {field_id: 2, name: "B", suggestions: []},
    {field_id: 3, name: "C", suggestions: [suggestion({page: 0})]},
  ];
  const found = markers(fields, SIZES);
  assert.equal(found.length, 1);
  assert.equal(found[0].fieldId, 1);
  assert.equal(found[0].box.page, 1);
});

test("fields without suggestion or confirmed value stay hidden", () => {
  const fields = [
    {field_id: 1, suggestions: [suggestion()], confirmed: false},
    {field_id: 2, suggestions: [], confirmed: "4711"},
    {field_id: 3, suggestions: [], confirmed: false},
  ];
  assert.deepEqual(
    shownFields(fields).map((f) => f.field_id),
    [1, 2]
  );
});

test("the pager wraps around", () => {
  assert.equal(wrapIndex(3, 3), 0);
  assert.equal(wrapIndex(-1, 3), 2);
  assert.equal(wrapIndex(1, 3), 1);
  assert.equal(wrapIndex(5, 0), 0);
});
