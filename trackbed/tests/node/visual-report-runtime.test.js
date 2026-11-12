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

test("stored triage is reduced to well-formed decisions", () => {
  assert.deepEqual(
    runtime.sanitizeTriage({
      a: { decision: "accept", note: "ok" },
      b: { decision: "dismiss" },
      c: { decision: "delete", note: "x" },
      d: "accept",
      e: null,
    }),
    {
      a: { decision: "accept", note: "ok" },
      b: { decision: "dismiss", note: "" },
    },
  );
  assert.deepEqual(runtime.sanitizeTriage("corrupt"), {});
  assert.deepEqual(runtime.sanitizeTriage(null), {});
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
