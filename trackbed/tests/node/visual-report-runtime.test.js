"use strict";

// The visual report runtime is a browser script. Its filtering, sorting,
// location, and triage-prompt logic is exported when it loads under Node, so it
// is tested here without a DOM.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const RUNTIME = path.join(
  __dirname,
  "../../shared/visual/assets/report-runtime.js",
);
const runtime = /** @type {any} */ (require(RUNTIME));

/**
 * @param {Record<string, unknown>} overrides
 */
function entry(overrides) {
  return {
    id: "CR-001",
    title: "Export route reads the tenant ID from the query string",
    facets: { severity: "critical", status: "open" },
    location: "src/routes/export.ts:42",
    text: "cr-001 critical open export route reads the tenant id",
    order: 0,
    triageable: true,
    ...overrides,
  };
}

const META = {
  producer: "trackbed:pr:code-review",
  source: "REVIEW_OVERVIEW.md",
  generated: "2026-01-15T14:02:00+01:00",
  commit: "1a2b3c4d5e6f7a8b9c0d",
  root: "/work/project",
  facets: ["severity", "status"],
  followups: ["/trackbed:pr:resolve-review"],
  acceptLabel: "Accept",
  dismissLabel: "Dismiss",
};

test("locations parse a line, a range, a column, or a bare path", () => {
  assert.deepEqual(runtime.parseLocation("src/a.ts:12"), {
    path: "src/a.ts",
    line: 12,
  });
  assert.deepEqual(runtime.parseLocation(" src/a.ts:12-20 "), {
    path: "src/a.ts",
    line: 12,
  });
  assert.deepEqual(runtime.parseLocation("src/a.ts:12:5"), {
    path: "src/a.ts",
    line: 12,
  });
  assert.deepEqual(runtime.parseLocation("docs/guide.md"), {
    path: "docs/guide.md",
    line: null,
  });
  assert.equal(runtime.parseLocation("   "), null);
});

test("editor links join the project root and encode the path", () => {
  const { template } = runtime.EDITORS.vscode;
  const url = (/** @type {string} */ root, /** @type {string} */ location) =>
    runtime.editorUrl(template, root, runtime.parseLocation(location));
  assert.equal(
    url("/work/project/", "src/my file#1.ts:7"),
    "vscode://file/work/project/src/my%20file%231.ts:7",
  );
  assert.equal(url("/work/project", "/abs/a.ts"), "vscode://file/abs/a.ts:1");
  assert.equal(
    url("C:\\work", "src\\a.ts:3"),
    "vscode://file/C:/work/src/a.ts:3",
  );
  assert.equal(url("", "src/a.ts:7"), null);
  assert.equal(
    runtime.editorUrl(
      "myeditor://open?file={path}&line={line}",
      "/work",
      runtime.parseLocation("a.ts:9"),
    ),
    "myeditor://open?file=/work/a.ts&line=9",
  );
});

test("a custom editor template cannot run script or lose the path", () => {
  for (const template of [
    "javascript://x/{path}",
    "JavaScript://%0aalert(1)//{path}",
    "data://text/html,{path}",
    "vscode://file/fixed",
    "{path}",
    "",
  ]) {
    assert.equal(runtime.isEditorTemplate(template), false, template);
    assert.equal(
      runtime.editorUrl(template, "/work", runtime.parseLocation("a.ts:1")),
      null,
      template,
    );
  }
  assert.equal(
    runtime.isEditorTemplate("http://localhost:63342/api/file{path}:{line}"),
    true,
  );
});

test("filters combine across facets and offer alternatives within one", () => {
  const item = entry({});
  assert.equal(runtime.matches(item, {}, "", undefined), true);
  assert.equal(
    runtime.matches(item, { severity: ["high", "critical"] }, "", undefined),
    true,
  );
  assert.equal(
    runtime.matches(
      item,
      { severity: ["critical"], status: ["addressed"] },
      "",
      undefined,
    ),
    false,
  );
  assert.equal(
    runtime.matches(item, { severity: [], status: ["open"] }, "", undefined),
    true,
  );
  assert.equal(
    runtime.matches(item, { reviewer: ["security-reviewer"] }, "", undefined),
    false,
  );
});

test("search needs every term and ignores case", () => {
  const item = entry({});
  assert.equal(runtime.matches(item, {}, "Tenant EXPORT", undefined), true);
  assert.equal(runtime.matches(item, {}, "tenant retry", undefined), false);
  assert.equal(runtime.matches(item, {}, "   ", undefined), true);
});

test("the triage filter reads the reader's decision", () => {
  const item = entry({});
  const accepted = { decision: "accept", note: "" };
  assert.equal(
    runtime.matches(item, { triage: ["undecided"] }, "", undefined),
    true,
  );
  assert.equal(
    runtime.matches(item, { triage: ["undecided"] }, "", accepted),
    false,
  );
  assert.equal(
    runtime.matches(item, { triage: ["accepted", "dismissed"] }, "", accepted),
    true,
  );
  assert.equal(
    runtime.triageValue({ decision: "dismiss", note: "" }),
    "dismissed",
  );
});

test("an entry with triage off matches no triage filter", () => {
  const item = entry({ triageable: false });
  assert.equal(runtime.matches(item, {}, "", undefined), true);
  assert.equal(
    runtime.matches(item, { triage: ["undecided"] }, "", undefined),
    false,
  );
  assert.equal(runtime.matches(item, { triage: [] }, "", undefined), true);
});

test("entries sort by severity scale, natural text, and report order", () => {
  const items = [
    entry({ id: "A", order: 0, facets: { severity: "low", wave: "W10" } }),
    entry({ id: "B", order: 1, facets: { severity: "critical", wave: "W2" } }),
    entry({ id: "C", order: 2, facets: { wave: "W2" }, location: "" }),
    entry({ id: "D", order: 3, facets: { severity: "high" }, location: "a:9" }),
  ];
  const ids = (/** @type {string} */ key) =>
    [...items]
      .sort((a, b) => runtime.compareEntries(a, b, key))
      .map((item) => item.id)
      .join("");
  assert.equal(ids("severity"), "BDAC");
  assert.equal(ids("wave"), "BCAD");
  assert.equal(ids("order"), "ABCD");
  assert.equal(ids("location"), "DABC");
});

test("Next and Previous skip hidden entries and stop at the ends", () => {
  const shown = [true, false, true, true, false];
  assert.equal(runtime.stepIndex(shown, -1, 1), 0);
  assert.equal(runtime.stepIndex(shown, 0, 1), 2);
  assert.equal(runtime.stepIndex(shown, 2, 1), 3);
  assert.equal(runtime.stepIndex(shown, 3, 1), 3);
  assert.equal(runtime.stepIndex(shown, 3, -1), 2);
  assert.equal(runtime.stepIndex(shown, 2, -1), 0);
  assert.equal(runtime.stepIndex(shown, 0, -1), 0);
  assert.equal(runtime.stepIndex(shown, -1, -1), -1);
  assert.equal(runtime.stepIndex([], -1, 1), -1);
  assert.equal(runtime.stepIndex([false, false], -1, 1), -1);
});

test("a filter that hides the current entry moves to the next shown one, then the previous", () => {
  const shown = [true, false, false, true, false];
  assert.equal(runtime.nearestShownIndex(shown, 0), 0);
  assert.equal(runtime.nearestShownIndex(shown, 1), 3);
  assert.equal(runtime.nearestShownIndex(shown, 4), 3);
  assert.equal(runtime.nearestShownIndex([true, false], 1), 0);
  assert.equal(runtime.nearestShownIndex([false, false], 0), -1);
  assert.equal(runtime.nearestShownIndex(shown, -1), -1);
  assert.equal(runtime.nearestShownIndex([], 0), -1);
});

test("Next undecided wraps past the end and reports when nothing waits", () => {
  const waiting = [false, true, false, true];
  assert.equal(runtime.nextWaitingIndex(waiting, -1), 1);
  assert.equal(runtime.nextWaitingIndex(waiting, 1), 3);
  assert.equal(runtime.nextWaitingIndex(waiting, 3), 1);
  assert.equal(runtime.nextWaitingIndex([false, true, false], 1), 1);
  assert.equal(runtime.nextWaitingIndex([false, false], 0), -1);
  assert.equal(runtime.nextWaitingIndex([], -1), -1);
});

test("table cells compare as numbers when both are numbers", () => {
  assert.ok(runtime.compareText("9", "10") < 0);
  assert.ok(runtime.compareText("1,200", "300") > 0);
  assert.ok(runtime.compareText("45%", "5%") > 0);
  assert.ok(runtime.compareText("file2.ts", "file10.ts") < 0);
  assert.ok(runtime.compareText("", "3") < 0);
});

test("facet counts keep severity in scale order and others in report order", () => {
  const items = [
    entry({ facets: { severity: "low", reviewer: "tests" } }),
    entry({ facets: { severity: "critical", reviewer: "security" } }),
    entry({ facets: { severity: "low", reviewer: "tests" } }),
    entry({ facets: {} }),
  ];
  assert.deepEqual(runtime.countBy(items, "severity"), [
    ["critical", 1],
    ["low", 2],
  ]);
  assert.deepEqual(runtime.countBy(items, "reviewer"), [
    ["tests", 2],
    ["security", 1],
  ]);
});

test("the triage prompt names the follow-up, the record, and each decision", () => {
  const entries = [
    entry({}),
    entry({ id: "CR-002", title: "Retry helper hides the error", order: 1 }),
    entry({ id: "CR-003", title: "Duplicate header builder", order: 2 }),
    entry({ id: "CR-004", title: "Rename a variable", order: 3 }),
    entry({ id: "FILTERED-1", title: "Pre-existing", triageable: false }),
  ];
  const triage = {
    "CR-001": { decision: "accept", note: "do this\nfirst" },
    "CR-003": { decision: "dismiss", note: "intentional" },
    "FILTERED-1": { decision: "accept", note: "" },
  };
  assert.equal(
    runtime.buildPrompt(META, entries, triage, "/trackbed:pr:resolve-review"),
    [
      "/trackbed:pr:resolve-review",
      "",
      "Triage of REVIEW_OVERVIEW.md (trackbed:pr:code-review, generated 2026-01-15T14:02:00+01:00, commit 1a2b3c4d5e6f).",
      "REVIEW_OVERVIEW.md is the record for what each entry says; this message only says which entries to act on.",
      "",
      "Act only on the 1 accepted entry:",
      "- CR-001 [critical] Export route reads the tenant ID from the query string (src/routes/export.ts:42)",
      "  Note: do this first",
      "",
      "Leave the 1 dismissed entry alone:",
      "- CR-003 Duplicate header builder",
      "  Reason: intentional",
      "",
      "2 other entries had no decision and should stay unchanged.",
      "",
    ].join("\n"),
  );
});

test("the triage prompt says so when nothing was accepted", () => {
  const prompt = runtime.buildPrompt(
    { ...META, commit: "" },
    [entry({ facets: {}, location: "" })],
    { "CR-001": { decision: "dismiss", note: "" } },
    "",
  );
  assert.equal(
    prompt,
    [
      "Triage of REVIEW_OVERVIEW.md (trackbed:pr:code-review, generated 2026-01-15T14:02:00+01:00).",
      "REVIEW_OVERVIEW.md is the record for what each entry says; this message only says which entries to act on.",
      "",
      "No entries were accepted.",
      "",
      "Leave the 1 dismissed entry alone:",
      "- CR-001 Export route reads the tenant ID from the query string",
      "",
    ].join("\n"),
  );
});

test("the prompt lists the findings each decided fix removes", () => {
  const fixes = {
    ...META,
    producer: "trackbed:code:refactor-opportunities full",
    source: "REFACTOR_OPPORTUNITIES_OVERVIEW.md",
    nounOne: "fix",
    nounMany: "fixes",
  };
  const prompt = runtime.buildPrompt(
    fixes,
    [
      entry({
        id: "FIX-1",
        title: "Model packet readiness in the stock ledger",
        facets: { severity: "high" },
        location: "loans/checkout.ts:24",
        removes: ["RO-001", "RO-002", "RO-003"],
      }),
      entry({
        id: "FIX-2",
        title: "Inline the label forwarding function",
        facets: { severity: "low" },
        location: "catalog/label.ts:12",
        removes: ["RO-004"],
      }),
    ],
    {
      "FIX-1": { decision: "accept", note: "start here" },
      "FIX-2": { decision: "dismiss", note: "" },
    },
    "/trackbed:code:breakdown-findings",
  );
  assert.ok(
    prompt.includes(
      [
        "Act only on the 1 accepted fix:",
        "- FIX-1 [high] Model packet readiness in the stock ledger (loans/checkout.ts:24)",
        "  Removes: RO-001, RO-002, RO-003",
        "  Note: start here",
        "",
        "Leave the 1 dismissed fix alone:",
        "- FIX-2 Inline the label forwarding function",
        "  Removes: RO-004",
      ].join("\n"),
    ),
    prompt,
  );
});

test("a changes page hands back the changes to undo, not the ones to keep", () => {
  const changes = {
    ...META,
    shape: "changes",
    runId: "75bcca93-b9fe-4aa0-88ce-ded812220775",
    producer: "trackbed:code:copy-review --pr --apply",
    source: "COPY_REVIEW_OVERVIEW.md",
    acceptLabel: "Keep",
    dismissLabel: "Revert",
    nounOne: "change",
    nounMany: "changes",
  };
  const entries = [
    entry({
      id: "COPY-001",
      title: "The Remove button no longer repeats its trash icon in words",
      facets: { severity: "high" },
      location: "src/components/PacketRow.tsx:42",
    }),
    entry({
      id: "COPY-002",
      title: "The Settings page no longer opens with a second heading",
      facets: { severity: "high" },
      location: "src/pages/Settings.tsx:12",
      order: 1,
    }),
    entry({
      id: "COPY-003",
      title: "The email field no longer has a placeholder",
      facets: {},
      location: "",
      order: 2,
    }),
    entry({ id: "COPY-004", title: "Left unchanged", triageable: false }),
  ];
  assert.equal(
    runtime.buildPrompt(
      changes,
      entries,
      {
        "COPY-001": { decision: "dismiss", note: "new members\nneed the word" },
        "COPY-002": { decision: "accept", note: "good" },
        "COPY-004": { decision: "dismiss", note: "" },
      },
      "/trackbed:code:copy-review --revert",
    ),
    [
      "/trackbed:code:copy-review --revert",
      "",
      "Decisions on the changes recorded in COPY_REVIEW_OVERVIEW.md (trackbed:code:copy-review --pr --apply, generated 2026-01-15T14:02:00+01:00, commit 1a2b3c4d5e6f).",
      "Apply run: 75bcca93-b9fe-4aa0-88ce-ded812220775",
      "COPY_REVIEW_OVERVIEW.md is the record for what each change did and what was there before; this message only says which changes to undo.",
      "",
      "Undo only the 1 change marked Revert, restoring what the record says was there before:",
      "- COPY-001 [high] The Remove button no longer repeats its trash icon in words (src/components/PacketRow.tsx:42)",
      "  Reason: new members need the word",
      "",
      "Leave the 1 change marked Keep as it is:",
      "- COPY-002 The Settings page no longer opens with a second heading",
      "  Note: good",
      "",
      "1 other change had no decision and should stay as it is.",
      "",
    ].join("\n"),
  );

  const kept = runtime.buildPrompt(
    { ...changes, commit: "", runId: undefined },
    entries,
    {
      "COPY-001": { decision: "accept", note: "" },
      "COPY-002": { decision: "accept", note: "" },
    },
    "",
  );
  assert.equal(
    kept,
    [
      "Decisions on the changes recorded in COPY_REVIEW_OVERVIEW.md (trackbed:code:copy-review --pr --apply, generated 2026-01-15T14:02:00+01:00).",
      "COPY_REVIEW_OVERVIEW.md is the record for what each change did and what was there before; this message only says which changes to undo.",
      "",
      "No changes were marked Revert; undo nothing.",
      "",
      "Leave the 2 changes marked Keep as they are:",
      "- COPY-001 The Remove button no longer repeats its trash icon in words",
      "- COPY-002 The Settings page no longer opens with a second heading",
      "",
      "1 other change had no decision and should stay as it is.",
      "",
    ].join("\n"),
  );
  // A changes page that names no labels still offers Keep and Revert, so its
  // buttons and its prompt agree on what a dismissal means.
  assert.deepEqual(runtime.decisionLabels("changes", undefined, ""), {
    acceptLabel: "Keep",
    dismissLabel: "Revert",
  });
  assert.deepEqual(runtime.decisionLabels("findings", undefined, undefined), {
    acceptLabel: "Accept",
    dismissLabel: "Dismiss",
  });
  assert.deepEqual(runtime.decisionLabels("plan", "Run", "Skip"), {
    acceptLabel: "Run",
    dismissLabel: "Skip",
  });
  assert.ok(
    runtime
      .buildPrompt(
        { ...changes, acceptLabel: "Accept", dismissLabel: "Dismiss" },
        entries,
        { "COPY-001": { decision: "dismiss", note: "" } },
        "",
      )
      .includes("Undo only the 1 change marked Revert,"),
  );
  // Only a changes page reads a dismissal as work to do.
  assert.ok(
    runtime
      .buildPrompt({ ...changes, shape: "findings" }, entries, {}, "")
      .includes("No changes were accepted."),
  );
});

test("the prompt calls entries what the page calls them", () => {
  const plans = {
    ...META,
    source: "PR_PLAN_INDEX.md",
    nounOne: "plan",
    nounMany: "plans",
  };
  const prompt = runtime.buildPrompt(
    plans,
    [
      entry({
        id: "W01A",
        title: "Typed API errors",
        facets: {},
        location: "",
      }),
      entry({ id: "W01B", title: "Dead exports", facets: {}, location: "" }),
      entry({ id: "W02A", title: "Client messages", facets: {}, location: "" }),
    ],
    {
      W01A: { decision: "accept", note: "" },
      W01B: { decision: "dismiss", note: "" },
    },
    "",
  );
  assert.ok(
    prompt.includes(
      "PR_PLAN_INDEX.md is the record for what each plan says; this message only says which plans to act on.",
    ),
  );
  assert.ok(prompt.includes("Act only on the 1 accepted plan:"));
  assert.ok(prompt.includes("Leave the 1 dismissed plan alone:"));
  assert.ok(
    prompt.includes("1 other plan had no decision and should stay unchanged."),
  );
  assert.equal(runtime.noun({}, 1), "entry");
  assert.equal(runtime.noun({}, 3), "entries");
  assert.equal(runtime.noun(plans, 2), "plans");
});

test("a long title or note is flattened and shortened in the prompt", () => {
  const prompt = runtime.buildPrompt(
    META,
    [entry({ title: `${"word ".repeat(60)}end` })],
    { "CR-001": { decision: "accept", note: "" } },
    "",
  );
  const line = prompt
    .split("\n")
    .find((/** @type {string} */ text) => text.startsWith("- CR-001"));
  assert.ok(line && line.length < 230, line);
  assert.ok(line.includes("..."));
});

test("stored triage is reduced to well-formed decisions and clears", () => {
  const time = "2026-01-15T10:00:00.000Z";
  assert.deepEqual(
    runtime.sanitizeTriage({
      a: { decision: "accept", note: "ok", updatedAt: time },
      b: { decision: "dismiss" },
      c: { decision: "delete", note: "x" },
      d: "accept",
      e: null,
      f: { decision: null, updatedAt: time },
      g: { decision: null },
      h: { decision: "accept", updatedAt: "yesterday" },
    }),
    {
      decisions: {
        a: { decision: "accept", note: "ok", updatedAt: time },
        b: { decision: "dismiss", note: "" },
        h: { decision: "accept", note: "" },
      },
      cleared: { f: time },
    },
  );
  const empty = { decisions: {}, cleared: {} };
  assert.deepEqual(runtime.sanitizeTriage("corrupt"), empty);
  assert.deepEqual(runtime.sanitizeTriage(null), empty);
});

/** A localStorage stand-in that two report tabs share. */
function fakeStorage() {
  /** @type {Map<string, string>} */
  const values = new Map();
  return {
    /** @param {string} key */
    getItem: (key) => values.get(key) ?? null,
    /** @param {string} key @param {string} value */
    setItem: (key, value) => {
      values.set(key, value);
    },
  };
}

test("triage entries saved by two report tabs both survive", () => {
  const storage = fakeStorage();
  const key = runtime.storageKey("/work/REVIEW_OVERVIEW.html", "2026-01-15");
  // Both tabs open on an empty store, then each decides a different entry.
  const first = runtime.syncTriage(storage, key, {
    decisions: {
      "CR-001": {
        decision: "accept",
        note: "",
        updatedAt: "2026-01-15T10:00:00.000Z",
      },
    },
    cleared: {},
  });
  const second = runtime.syncTriage(storage, key, {
    decisions: {
      "CR-002": {
        decision: "dismiss",
        note: "Not ours.",
        updatedAt: "2026-01-15T10:01:00.000Z",
      },
    },
    cleared: {},
  });
  assert.deepEqual(Object.keys(second.decisions).sort(), ["CR-001", "CR-002"]);
  // The first tab's next save keeps what the second one stored.
  const again = runtime.syncTriage(storage, key, first);
  assert.deepEqual(again, second);
  assert.deepEqual(
    runtime.sanitizeTriage(JSON.parse(storage.getItem(key) ?? "")),
    second,
  );
});

test("a clear saved by one report tab outlasts an older decision the other tab still holds", () => {
  const storage = fakeStorage();
  const key = runtime.storageKey("/work/REVIEW_OVERVIEW.html", "2026-01-15");
  const stale = runtime.syncTriage(storage, key, {
    decisions: {
      "CR-001": {
        decision: "accept",
        note: "",
        updatedAt: "2026-01-15T10:00:00.000Z",
      },
    },
    cleared: {},
  });
  runtime.syncTriage(storage, key, {
    decisions: {},
    cleared: { "CR-001": "2026-01-15T10:05:00.000Z" },
  });
  // The first tab still holds the accept in memory, then saves again.
  const again = runtime.syncTriage(storage, key, stale);
  assert.deepEqual(again, {
    decisions: {},
    cleared: { "CR-001": "2026-01-15T10:05:00.000Z" },
  });
  assert.deepEqual(JSON.parse(storage.getItem(key) ?? "")["CR-001"], {
    decision: null,
    updatedAt: "2026-01-15T10:05:00.000Z",
  });
});

test("storage that refuses or holds unreadable triage leaves the page's triage standing", () => {
  const key = runtime.storageKey("/work/REVIEW_OVERVIEW.html", "2026-01-15");
  const state = {
    decisions: {
      "CR-001": {
        decision: /** @type {const} */ ("accept"),
        note: "Mine.",
        updatedAt: "2026-01-15T10:00:00.000Z",
      },
    },
    cleared: { "CR-002": "2026-01-15T10:01:00.000Z" },
  };
  const unreadable = fakeStorage();
  unreadable.setItem(key, "{not json");
  assert.deepEqual(runtime.syncTriage(unreadable, key, state), state);
  assert.deepEqual(
    runtime.sanitizeTriage(JSON.parse(unreadable.getItem(key) ?? "")),
    state,
    "the unreadable copy is replaced",
  );
  const refuse = () => {
    throw new Error("SecurityError");
  };
  assert.deepEqual(
    runtime.syncTriage({ getItem: refuse, setItem: refuse }, key, state),
    state,
  );
});

test("a later clear outlasts an older decision from another tab, and a later decision a clear", () => {
  const older = {
    decision: /** @type {const} */ ("accept"),
    note: "",
    updatedAt: "2026-01-15T10:00:00.000Z",
  };
  const merged = runtime.mergeTriage(
    { decisions: { a: older, b: older }, cleared: {} },
    {
      decisions: { b: { ...older, updatedAt: "2026-01-15T10:05:00.000Z" } },
      cleared: { a: "2026-01-15T10:01:00.000Z" },
    },
  );
  assert.deepEqual(merged.cleared, { a: "2026-01-15T10:01:00.000Z" });
  assert.deepEqual(Object.keys(merged.decisions), ["b"]);
  assert.equal(merged.decisions.b.updatedAt, "2026-01-15T10:05:00.000Z");

  const back = runtime.mergeTriage(merged, {
    decisions: { a: { ...older, updatedAt: "2026-01-15T10:02:00.000Z" } },
    cleared: { b: "2026-01-15T10:03:00.000Z" },
  });
  assert.deepEqual(
    Object.keys(back.decisions).sort(),
    ["a", "b"],
    "an older clear loses",
  );
  assert.deepEqual(back.cleared, {});

  // A decision saved before decisions carried a time is older than any edit.
  const legacy = runtime.mergeTriage(
    { decisions: {}, cleared: { a: "2026-01-15T10:01:00.000Z" } },
    runtime.sanitizeTriage({ a: { decision: "dismiss", note: "" } }),
  );
  assert.deepEqual(legacy.decisions, {});
});

test("triage is stored per page and per generation", () => {
  const first = runtime.storageKey("/work/REVIEW_OVERVIEW.html", "2026-01-15");
  assert.notEqual(
    first,
    runtime.storageKey("/work/REVIEW_OVERVIEW.html", "2026-01-16"),
  );
  assert.notEqual(
    first,
    runtime.storageKey("/work/QA_REPORT.html", "2026-01-15"),
  );
});

test("labels read as words", () => {
  assert.equal(runtime.label("silent-failure-hunter"), "silent failure hunter");
  assert.equal(runtime.titleCase("gated_auto"), "Gated auto");
});

test("the runtime makes no network request and cannot close its own element", () => {
  const source = fs.readFileSync(RUNTIME, "utf8");
  for (const forbidden of [
    "fetch(",
    "XMLHttpRequest",
    "sendBeacon",
    "WebSocket",
    "EventSource",
    "importScripts",
    "</script",
  ]) {
    assert.equal(source.includes(forbidden), false, forbidden);
  }
});
