// Plain Node tests for the rows of the value review.
import assert from "node:assert/strict";
import test from "node:test";

import {
  chooseSuggestion,
  initialRows,
  isDirty,
  pickSelection,
  removeRow,
  rowMarkers,
  typeText,
  valuesToSave,
} from "../../src/int_filemanager/v2/value_review/value_review_edits.js";

function suggestion(text, start, ruleId = 5) {
  return {source_text: text, start, rule_id: ruleId, value: {value_text: text}};
}

const FIELDS = [
  {
    field_id: 1,
    name: "Invoice",
    value_type: "number",
    confirmed: false,
    suggestions: [suggestion("4711", 10), suggestion("4712", 40)],
  },
  {field_id: 2, name: "Date", value_type: "date", confirmed: "2024-01-01", suggestions: []},
  {field_id: 3, name: "Hidden", value_type: "number", confirmed: false, suggestions: []},
];

test("only fields with a suggestion or a stored value get a row", () => {
  const rows = initialRows(FIELDS);
  assert.deepEqual(
    rows.map((r) => [r.fieldId, r.text, r.source]),
    [
      [1, "4711", "rule"],
      [2, "2024-01-01", "manual"],
    ]
  );
});

test("saving confirms a suggestion left alone and leaves a stored value alone", () => {
  const values = valuesToSave(initialRows(FIELDS));
  assert.deepEqual(values, [
    {field_id: 1, text: "4711", source: "rule", rule_id: 5, start: 10},
  ]);
});

test("a typed text is manual and forgets the place", () => {
  const rows = initialRows(FIELDS);
  typeText(rows[0], "999");
  typeText(rows[1], "2024-02-02");
  assert.deepEqual(valuesToSave(rows), [
    {field_id: 1, text: "999", source: "manual", rule_id: false, start: false},
    {field_id: 2, text: "2024-02-02", source: "manual", rule_id: false, start: false},
  ]);
});

test("another suggestion keeps its rule and its place", () => {
  const rows = initialRows(FIELDS);
  chooseSuggestion(rows[0], rows[0].suggestions[1]);
  assert.deepEqual(valuesToSave(rows)[0], {
    field_id: 1,
    text: "4712",
    source: "rule",
    rule_id: 5,
    start: 40,
  });
});

test("removing drops a suggestion and empties a stored value", () => {
  const rows = initialRows(FIELDS);
  removeRow(rows[0]);
  removeRow(rows[1]);
  assert.deepEqual(valuesToSave(rows), [{field_id: 2, text: ""}]);
});

test("a stored value emptied by hand is removed, an empty suggestion is skipped", () => {
  const rows = initialRows(FIELDS);
  typeText(rows[0], "  ");
  typeText(rows[1], "");
  assert.deepEqual(
    valuesToSave(rows).map((v) => [v.field_id, v.text]),
    [[2, ""]]
  );
});

test("nothing is dirty until the user touched something", () => {
  const rows = initialRows(FIELDS);
  assert.equal(isDirty(rows), false);
  assert.equal(isDirty(rows, {changedTags: true}), true);
  typeText(rows[0], "1");
  assert.equal(isDirty(rows), true);
});

test("the uncertain rows come first, in their order", () => {
  const fields = [
    {field_id: 1, name: "A", suggestions: [{...suggestion("1", 1), tier: 1}]},
    {field_id: 2, name: "B", suggestions: [{...suggestion("2", 2), tier: 3}]},
    {field_id: 3, name: "C", suggestions: [{...suggestion("3", 3), tier: 0}]},
    {field_id: 4, name: "D", suggestions: [{...suggestion("4", 4), tier: 4}]},
    {field_id: 5, name: "E", confirmed: "5", suggestions: []},
  ];
  const rows = initialRows(fields);
  assert.deepEqual(
    rows.map((r) => r.fieldId),
    [2, 4, 1, 3, 5]
  );
  assert.deepEqual(
    rows.map((r) => r.uncertain),
    [true, true, false, false, false]
  );
});

test("a click on words takes the place of the read text and keeps it for learning", () => {
  const rows = initialRows(FIELDS);
  const picked = {...suggestion("99", 77), x0: 1, top: 1, x1: 9, bottom: 5, page: 1};
  pickSelection(rows[0], picked);
  assert.deepEqual(valuesToSave(rows)[0], {
    field_id: 1,
    text: "99",
    source: "manual",
    rule_id: false,
    start: 77,
  });
  const boxes = rowMarkers(rows, {1: [100, 100]});
  assert.equal(boxes.length, 1);
  assert.equal(boxes[0].box.left, 0.01);
});

test("typing over a clicked value takes its outline away", () => {
  const rows = initialRows(FIELDS);
  pickSelection(rows[0], {...suggestion("99", 77), page: 1, x0: 1, top: 1, x1: 9, bottom: 5});
  typeText(rows[0], "100");
  assert.deepEqual(rowMarkers(rows, {}), []);
});
