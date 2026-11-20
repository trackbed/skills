"use strict";

// The interview round runtime is a browser script. The rules for what a person
// entered (when a question counts as answered, what the answers hold, what may
// come back out of this browser's storage) are exported when it loads under
// Node, so they are tested here without a DOM. The payloads are the ones
// tests/python/test_interview_ui.py runs through the helper's own check.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const RUNTIME = path.join(
  __dirname,
  "../../skills/discovery:interview/assets/interview-ui.js",
);
const runtime = /** @type {any} */ (require(RUNTIME));
const fixture = JSON.parse(
  fs.readFileSync(
    path.join(__dirname, "../fixtures/interview-ui-answers-cases.json"),
    "utf8",
  ),
);
const catalog = fixture.catalog;

/**
 * @param {string} id
 * @returns {Record<string, any>}
 */
function question(id) {
  return catalog.questions.find(
    (/** @type {{ id: string }} */ entry) => entry.id === id,
  );
}

/**
 * @param {string} id @param {Record<string, unknown>} [changes]
 * @returns {Record<string, any>}
 */
function draft(id, changes) {
  return { ...runtime.emptyDraft(question(id)), ...changes };
}

for (const entry of fixture.cases) {
  test(`answers payload: ${entry.name}`, () => {
    const drafts = runtime.restoreDrafts(catalog, entry.drafts);
    assert.deepEqual(
      runtime.buildPayload(catalog, drafts, {
        ...entry.meta,
        now: fixture.now,
      }),
      entry.payload,
    );
    const statuses = entry.payload.answers.map(
      (/** @type {{ status: string }} */ answer) => answer.status,
    );
    assert.deepEqual(runtime.tally(catalog, drafts), {
      answered: statuses.filter((/** @type {string} */ s) => s === "answered")
        .length,
      unsure: statuses.filter((/** @type {string} */ s) => s === "unsure")
        .length,
      open: statuses.filter((/** @type {string} */ s) => s === "open").length,
    });
  });
}

test("the payload names its round, so answers cannot be given to another one", () => {
  const payload = runtime.buildPayload(catalog, {}, fixture.cases[1].meta);
  assert.equal(payload.format, runtime.FORMAT);
  assert.equal(payload.schemaVersion, runtime.SCHEMA_VERSION);
  assert.equal(payload.session, catalog.session);
  assert.equal(payload.round, catalog.round);
  assert.equal(payload.fingerprint, catalog.fingerprint);
  assert.equal(payload.answers.length, catalog.questions.length);
});

test("nothing counts as answered until the person has entered it", () => {
  for (const entry of catalog.questions) {
    const empty = runtime.emptyDraft(entry);
    assert.equal(runtime.valueOf(entry, empty), null, entry.kind);
    assert.equal(runtime.statusOf(entry, empty), "open", entry.kind);
  }
  // An order is the person's only once they move a row or say it is right.
  const rank = question("edge-order");
  assert.deepEqual(runtime.emptyDraft(rank).order, rank.items);
  assert.equal(runtime.statusOf(rank, draft("edge-order")), "open");
  assert.equal(
    runtime.statusOf(rank, draft("edge-order", { confirmed: true })),
    "answered",
  );
});

test("an open question says what it still needs", () => {
  /** @type {[string, Record<string, unknown>, string][]} */
  const cases = [
    ["code-step", {}, "Not answered"],
    ["code-step", { otherOn: true, other: " " }, "Say what would fit"],
    ["friction", {}, "Not answered"],
    ["edge-order", {}, "Confirm the order"],
    ["scope", {}, "Not answered"],
    ["scope", { cells: { sms: "never" } }, "3 of 4 rows left"],
    ["effort", {}, "100 points left to place"],
    [
      "effort",
      { amounts: { flow: 40, recovery: 30, abuse: 0, settings: 0 } },
      "30 points left to place",
    ],
    [
      "effort",
      { amounts: { flow: 60, recovery: 60, abuse: 0, settings: 0 } },
      "20 points too many",
    ],
    ["session-column", {}, "Not answered"],
    ["session-column", { verdict: "correct" }, "Say what is right"],
    ["worry", {}, "Not answered"],
  ];
  for (const [id, changes, expected] of cases)
    assert.equal(
      runtime.missing(question(id), draft(id, changes)),
      expected,
      `${id} ${JSON.stringify(changes)}`,
    );
});

test("a choice that takes one answer never sends two", () => {
  const single = question("code-step");
  assert.deepEqual(
    runtime.valueOf(
      single,
      draft("code-step", { selected: ["second-screen", "inline"] }),
    ),
    { selected: ["inline"], other: "" },
  );
  const several = { ...single, multiple: true };
  assert.deepEqual(
    runtime.valueOf(
      several,
      draft("code-step", {
        selected: ["second-screen", "inline"],
        otherOn: true,
        other: " both, behind a flag ",
      }),
    ),
    { selected: ["inline", "second-screen"], other: "both, behind a flag" },
  );
  // Text left in the field does not count once "Something else" is unticked,
  // or when the question does not offer it.
  assert.deepEqual(
    runtime.valueOf(
      single,
      draft("code-step", { selected: ["inline"], other: "left over" }),
    ),
    { selected: ["inline"], other: "" },
  );
  assert.equal(
    runtime.valueOf(
      { ...single, other: false },
      draft("code-step", { otherOn: true, other: "not offered" }),
    ),
    null,
  );
});

test("a confirmation needs the correction only when it is not right", () => {
  const confirm = question("session-column");
  assert.deepEqual(
    runtime.valueOf(
      confirm,
      draft("session-column", { verdict: "confirm", correction: "ignored" }),
    ),
    { verdict: "confirm", correction: "" },
  );
  assert.equal(
    runtime.valueOf(confirm, draft("session-column", { verdict: "correct" })),
    null,
  );
});

test("moving a row keeps every item and stops at the ends", () => {
  const order = ["a", "b", "c"];
  assert.deepEqual(runtime.moveItem(order, "c", -1), ["a", "c", "b"]);
  assert.deepEqual(runtime.moveItem(order, "a", 1), ["b", "a", "c"]);
  assert.deepEqual(runtime.moveItem(order, "a", -1), order);
  assert.deepEqual(runtime.moveItem(order, "c", 1), order);
  assert.deepEqual(runtime.moveItem(order, "missing", 1), order);
  assert.notEqual(runtime.moveItem(order, "a", -1), order);
});

test("an amount is a multiple of the step and never takes more than is left", () => {
  const allocate = question("effort");
  const current = draft("effort", {
    amounts: { flow: 40, recovery: 30, abuse: 0, settings: 0 },
  });
  assert.equal(runtime.fitAmount(allocate, current, "abuse", 20), 20);
  assert.equal(runtime.fitAmount(allocate, current, "abuse", 22), 20);
  assert.equal(runtime.fitAmount(allocate, current, "abuse", 23), 25);
  assert.equal(runtime.fitAmount(allocate, current, "abuse", 80), 30);
  assert.equal(runtime.fitAmount(allocate, current, "flow", 100), 70);
  assert.equal(runtime.fitAmount(allocate, current, "flow", -5), 0);
  assert.equal(runtime.fitAmount(allocate, current, "flow", Number.NaN), 0);
});

test("what comes back out of storage is trusted for nothing", () => {
  for (const stored of [null, "drafts", 7, [], { "code-step": "inline" }]) {
    const drafts = runtime.restoreDrafts(catalog, stored);
    assert.deepEqual(Object.keys(drafts), catalog.questions.map(idOf));
    assert.deepEqual(runtime.tally(catalog, drafts), {
      answered: 0,
      unsure: 0,
      open: catalog.questions.length,
    });
  }
  const drafts = runtime.restoreDrafts(catalog, {
    "edge-order": { order: ["late-email", "gone"], confirmed: true },
    effort: { amounts: { flow: 70, recovery: 70 } },
    friction: { stop: 2.5, unsure: "yes", note: 12 },
    worry: { text: "x".repeat(6000) },
  });
  // An order that no longer fits takes its confirmation with it.
  assert.equal(drafts["edge-order"].confirmed, false);
  assert.deepEqual(drafts["edge-order"].order, question("edge-order").items);
  // All of an allocation or none of it.
  assert.deepEqual(drafts.effort.amounts, {
    flow: 0,
    recovery: 0,
    abuse: 0,
    settings: 0,
  });
  assert.deepEqual(
    [drafts.friction.stop, drafts.friction.unsure, drafts.friction.note],
    [0, false, ""],
  );
  assert.equal(drafts.worry.text.length, 5000);
});

/**
 * @param {{ id: string }} entry
 */
function idOf(entry) {
  return entry.id;
}
