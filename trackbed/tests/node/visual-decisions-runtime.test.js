"use strict";

// The decision document runtime is a browser script. The rules for the reader's
// record (what a choice is, what an import may change, what an export holds)
// are exported when it loads under Node, so they are tested here without a DOM.
// The same payloads are run through the builder's --choices option in
// tests/python/test_visual_decisions_build.py.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const RUNTIME = path.join(
  __dirname,
  "../../skills/visual:decisions/assets/decisions.js",
);
const runtime = /** @type {any} */ (require(RUNTIME));
const fixture = JSON.parse(
  fs.readFileSync(
    path.join(__dirname, "../fixtures/visual-decisions-choices-cases.json"),
    "utf8",
  ),
);
const catalog = fixture.catalog;
const [first, second, third] = catalog.items;
const NOW = "2026-01-16T10:00:00.000Z";

/**
 * @param {Record<string, unknown>} overrides
 * @returns {Record<string, any>}
 */
function record(overrides) {
  return {
    option: "",
    status: "open",
    notes: "",
    updatedAt: null,
    itemFingerprint: first.fingerprint,
    ...overrides,
  };
}

for (const entry of fixture.cases) {
  test(`choices payload: ${entry.name}`, () => {
    if (entry.expect.error) {
      assert.throws(() => runtime.parsePayload(entry.payload, catalog), Error);
      return;
    }
    const parsed = runtime.parsePayload(entry.payload, catalog);
    const ids = Object.keys(parsed.records);
    /** @param {string} id */
    const review = (id) =>
      runtime.needsReview(
        catalog.items.find(
          (/** @type {{ id: string }} */ item) => item.id === id,
        ),
        parsed.records[id],
      );
    assert.deepEqual(
      {
        carried: ids.filter((id) => !review(id)),
        needsReview: ids.filter(review),
        dropped: parsed.unknown,
      },
      entry.expect,
    );
    for (const [id, expected] of Object.entries(entry.runtime ?? {})) {
      const { option, status, notes, earlier } = parsed.records[id];
      assert.deepEqual({ option, status, notes, earlier }, expected);
    }
  });
}

test("a refused payload names what is wrong in words a reader can act on", () => {
  /** @param {unknown} payload */
  const message = (payload) => {
    try {
      runtime.parsePayload(payload, catalog);
    } catch (error) {
      return error instanceof Error ? error.message : "";
    }
    return "accepted";
  };
  assert.match(message([1, 2]), /not a choices export or a saved copy/);
  assert.match(
    message({
      format: runtime.FORMAT,
      schemaVersion: 1,
      document: { id: "another-doc" },
      decisions: [],
    }),
    /belong to a different document/,
  );
  assert.match(
    message({
      format: runtime.FORMAT,
      schemaVersion: 2,
      document: { id: catalog.documentId },
      decisions: [],
    }),
    /format this document does not read/,
  );
});

test("choosing an approach decides an undecided item, and clearing it reopens the item", () => {
  let current = runtime.emptyRecord(first);
  current = runtime.applyChange(first, current, { option: "swap-b" }, NOW);
  assert.equal(current.option, "swap-b");
  assert.equal(current.status, "decided");
  assert.equal(current.updatedAt, NOW);

  current = runtime.applyChange(first, current, { notes: "Because." }, NOW);
  current = runtime.applyChange(first, current, { option: "" }, NOW);
  assert.equal(current.option, "");
  assert.equal(current.status, "open");
  assert.equal(current.notes, "Because.", "clearing a choice keeps the notes");
});

test("choosing does not override a status the reader set", () => {
  const discussing = record({ status: "discuss", updatedAt: NOW });
  const next = runtime.applyChange(
    first,
    discussing,
    { option: "keep-a" },
    NOW,
  );
  assert.equal(next.status, "discuss");
  const cleared = runtime.applyChange(first, next, { option: "" }, NOW);
  assert.equal(cleared.status, "discuss");
});

test("an item cannot be marked decided without an approach, or given one it does not offer", () => {
  const blank = runtime.emptyRecord(second);
  assert.equal(
    runtime.applyChange(second, blank, { status: "decided" }, NOW).status,
    "open",
  );
  assert.equal(
    runtime.applyChange(second, blank, { option: "no-change" }, NOW).option,
    "",
    "this item does not offer no-change",
  );
  assert.equal(
    runtime.applyChange(second, blank, { option: "custom" }, NOW).option,
    "custom",
  );
  assert.equal(runtime.choiceAllowed(third, "no-change"), true);
  assert.equal(runtime.choiceAllowed(third, "keep-a"), false);
});

test("notes are capped at the length an import accepts", () => {
  const next = runtime.applyChange(
    first,
    runtime.emptyRecord(first),
    { notes: "n".repeat(12000) },
    NOW,
  );
  assert.equal(next.notes.length, 10000);
});

test("a choice made on an earlier version waits for the reader, who can keep it or change it", () => {
  const stale = runtime.parsePayload(
    {
      format: runtime.FORMAT,
      schemaVersion: 1,
      document: { id: catalog.documentId },
      decisions: [
        {
          itemId: "A-1",
          option: "keep-a",
          status: "decided",
          notes: "Fine.",
          updatedAt: "2026-01-10T08:00:00.000Z",
          itemFingerprint: "earlier-version",
          choiceLabel: "Option A · Keep A",
        },
      ],
    },
    catalog,
  ).records["A-1"];
  assert.equal(runtime.needsReview(first, stale), true);
  assert.equal(stale.status, "open", "never counted as decided");
  assert.equal(runtime.countStatuses(catalog, { "A-1": stale }).needsReview, 1);

  const noted = runtime.applyChange(
    first,
    stale,
    { notes: "Still fine." },
    NOW,
  );
  assert.equal(
    runtime.needsReview(first, noted),
    true,
    "editing notes is not a confirmation",
  );

  const kept = runtime.applyChange(first, stale, { confirm: true }, NOW);
  assert.equal(kept.status, "decided");
  assert.equal(kept.itemFingerprint, first.fingerprint);
  assert.equal(kept.earlier, undefined);
  assert.equal(runtime.needsReview(first, kept), false);

  const changed = runtime.applyChange(first, stale, { option: "swap-b" }, NOW);
  assert.equal(changed.status, "decided");
  assert.equal(runtime.needsReview(first, changed), false);
});

test("an import keeps the reader's records unless they choose to replace them", () => {
  const mine = {
    "A-1": record({
      option: "swap-b",
      status: "decided",
      notes: "Mine.",
      updatedAt: NOW,
    }),
  };
  const incoming = {
    "A-1": record({ option: "keep-a", status: "decided", updatedAt: NOW }),
    "A-2": record({
      option: "custom",
      status: "discuss",
      updatedAt: NOW,
      itemFingerprint: second.fingerprint,
    }),
    "A-3": record({
      option: "x",
      status: "open",
      updatedAt: NOW,
      itemFingerprint: "earlier-version",
    }),
  };
  assert.deepEqual(runtime.planImport(catalog, mine, incoming, false), {
    apply: ["A-2", "A-3"],
    kept: ["A-1"],
    review: ["A-3"],
  });
  assert.deepEqual(runtime.planImport(catalog, mine, incoming, true), {
    apply: ["A-1", "A-2", "A-3"],
    kept: [],
    review: ["A-3"],
  });
  assert.equal(mine["A-1"].option, "swap-b", "planning changes nothing");
});

test("what the browser stored and what the file holds merge by the later edit", () => {
  const embedded = {
    "A-1": record({
      option: "keep-a",
      status: "decided",
      updatedAt: "2026-01-10T08:00:00.000Z",
    }),
    "A-2": record({
      notes: "From the file.",
      updatedAt: "2026-01-12T08:00:00.000Z",
    }),
  };
  const stored = {
    "A-1": record({
      option: "swap-b",
      status: "decided",
      updatedAt: "2026-01-11T08:00:00.000Z",
    }),
    "A-2": record({
      notes: "Older, from the browser.",
      updatedAt: "2026-01-09T08:00:00.000Z",
    }),
    "A-3": record({ notes: "Only here.", updatedAt: NOW }),
  };
  const merged = runtime.mergeNewest(embedded, stored);
  assert.equal(merged["A-1"].option, "swap-b");
  assert.equal(merged["A-2"].notes, "From the file.");
  assert.equal(merged["A-3"].notes, "Only here.");
  assert.equal(embedded["A-1"].option, "keep-a", "inputs are left alone");
});

test("a choice the reader cleared outlasts an older record in the file", () => {
  const embedded = {
    "A-1": record({
      option: "keep-a",
      status: "decided",
      updatedAt: "2026-01-10T08:00:00.000Z",
    }),
    "A-2": record({
      notes: "Newer than the clear.",
      updatedAt: "2026-01-12T08:00:00.000Z",
    }),
  };
  const stored = runtime.buildPayload(
    catalog,
    {
      "A-1": runtime.applyChange(
        first,
        embedded["A-1"],
        { option: "" },
        "2026-01-11T08:00:00.000Z",
      ),
      "A-2": record({
        itemFingerprint: second.fingerprint,
        updatedAt: "2026-01-11T08:00:00.000Z",
      }),
    },
    NOW,
  );
  const parsed = runtime.parsePayload(stored, catalog);
  assert.deepEqual(Object.keys(parsed.records), []);
  assert.deepEqual(
    { ...parsed.cleared },
    {
      "A-1": "2026-01-11T08:00:00.000Z",
      "A-2": "2026-01-11T08:00:00.000Z",
    },
  );
  const merged = runtime.mergeNewest(embedded, parsed.records, parsed.cleared);
  assert.equal(merged["A-1"], undefined, "the later clear wins");
  assert.equal(merged["A-2"].notes, "Newer than the clear.");
});

/** A localStorage stand-in that two open tabs share. */
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

const KEY = `${runtime.FORMAT}:v${runtime.SCHEMA_VERSION}:${catalog.documentId}`;

test("two tabs sharing one browser store keep each other's decisions", () => {
  const storage = fakeStorage();
  // Both tabs opened the document before either recorded anything.
  let older = Object.create(null);
  let newer = Object.create(null);
  older["A-1"] = runtime.applyChange(
    first,
    runtime.emptyRecord(first),
    { option: "keep-a" },
    "2026-01-16T09:00:00.000Z",
  );
  older = runtime.syncStore(storage, KEY, catalog, older, NOW);
  newer["A-2"] = runtime.applyChange(
    second,
    runtime.emptyRecord(second),
    { notes: "From the newer tab." },
    "2026-01-16T09:01:00.000Z",
  );
  newer = runtime.syncStore(storage, KEY, catalog, newer, NOW);
  assert.equal(
    newer["A-1"].option,
    "keep-a",
    "the newer tab picks up the older one's choice",
  );
  // The older tab writes again, as it does on an edit or when it is hidden
  // with a save pending.
  older = runtime.syncStore(storage, KEY, catalog, older, NOW);
  assert.equal(older["A-2"].notes, "From the newer tab.");
  const stored = runtime.parsePayload(
    JSON.parse(storage.getItem(KEY) ?? ""),
    catalog,
  ).records;
  assert.equal(stored["A-1"].option, "keep-a");
  assert.equal(stored["A-2"].notes, "From the newer tab.");
});

test("a clear made in one tab outlasts an older record from the other tab", () => {
  const storage = fakeStorage();
  const decided = runtime.applyChange(
    first,
    runtime.emptyRecord(first),
    { option: "keep-a" },
    "2026-01-16T09:00:00.000Z",
  );
  let stale = runtime.syncStore(storage, KEY, catalog, { "A-1": decided }, NOW);
  let clearing = runtime.syncStore(
    storage,
    KEY,
    catalog,
    {
      "A-1": runtime.applyChange(
        first,
        decided,
        { option: "", status: "open" },
        "2026-01-16T09:05:00.000Z",
      ),
    },
    NOW,
  );
  assert.equal(runtime.hasContent(clearing["A-1"]), false);
  // The other tab still holds the decision in memory, then writes.
  stale = runtime.syncStore(storage, KEY, catalog, stale, NOW);
  assert.equal(runtime.hasContent(stale["A-1"]), false, "the clear wins");
  assert.equal(stale["A-1"].updatedAt, "2026-01-16T09:05:00.000Z");
  // The clear stays in the store, so a third copy with the old record loses too.
  const reopened = runtime.absorbStored(
    catalog,
    { "A-1": decided },
    storage.getItem(KEY),
  );
  assert.equal(runtime.hasContent(reopened["A-1"]), false);
  clearing = runtime.syncStore(storage, KEY, catalog, clearing, NOW);
  assert.equal(runtime.hasContent(clearing["A-1"]), false);
});

test("an unreadable store changes nothing, and a refusing store throws for the page to report", () => {
  const records = { "A-1": record({ notes: "Mine.", updatedAt: NOW }) };
  assert.equal(runtime.absorbStored(catalog, records, "{not json"), records);
  assert.equal(runtime.absorbStored(catalog, records, null), records);
  const refusing = {
    getItem: () => null,
    setItem: () => {
      throw new Error("QuotaExceededError");
    },
  };
  assert.throws(() => runtime.syncStore(refusing, KEY, catalog, records, NOW));
});

test("an export lists every item with what a later reader needs, and imports back unchanged", () => {
  const records = {
    "A-1": record({
      option: "swap-b",
      status: "decided",
      notes: "Line one.\n<b>not markup</b>",
      updatedAt: NOW,
    }),
    "A-3": record({
      option: "no-change",
      status: "decided",
      updatedAt: NOW,
      itemFingerprint: third.fingerprint,
    }),
  };
  const payload = runtime.buildPayload(catalog, records, NOW);
  assert.equal(payload.format, "trackbed-decisions");
  assert.equal(payload.schemaVersion, 1);
  assert.deepEqual(payload.document, {
    id: catalog.documentId,
    title: catalog.title,
    fingerprint: catalog.fingerprint,
    generated: catalog.generated,
  });
  assert.deepEqual(payload.summary, {
    total: 3,
    open: 1,
    decided: 2,
    discuss: 0,
    deferred: 0,
    needsReview: 0,
  });
  assert.deepEqual(
    payload.decisions.map((/** @type {{ itemId: string }} */ d) => d.itemId),
    ["A-1", "A-2", "A-3"],
  );
  assert.deepEqual(payload.decisions[0], {
    itemId: "A-1",
    itemTitle: "First item",
    itemFingerprint: first.fingerprint,
    status: "decided",
    statusLabel: "Decided",
    option: "swap-b",
    choiceLabel: "Option B · Swap to B",
    recommendedOption: "keep-a",
    matchesRecommendation: false,
    notes: "Line one.\n<b>not markup</b>",
    updatedAt: NOW,
    needsReview: false,
  });
  assert.equal(payload.decisions[1].option, null);
  assert.equal(payload.decisions[1].status, "open");
  assert.equal(payload.decisions[1].matchesRecommendation, null);
  assert.equal(payload.decisions[2].choiceLabel, "No change · Keep the rule");
  assert.equal(payload.decisions[2].matchesRecommendation, true);

  const back = runtime.parsePayload(
    JSON.parse(JSON.stringify(payload)),
    catalog,
  );
  // The parser builds its map without a prototype, so compare its entries.
  assert.deepEqual({ ...back.records }, records);
  assert.deepEqual(back.unknown, []);
});

test("an export of a record under review says so and survives the round trip", () => {
  const stale = record({
    option: "keep-a",
    status: "open",
    notes: "Fine.",
    updatedAt: NOW,
    itemFingerprint: "earlier-version",
    earlier: { status: "decided", choiceLabel: "Option A · Keep A" },
  });
  const payload = runtime.buildPayload(catalog, { "A-1": stale }, NOW);
  assert.equal(payload.decisions[0].needsReview, true);
  assert.deepEqual(payload.decisions[0].earlier, stale.earlier);
  assert.equal(payload.summary.needsReview, 1);
  assert.equal(payload.summary.decided, 0);
  const back = runtime.parsePayload(
    JSON.parse(JSON.stringify(payload)),
    catalog,
  ).records["A-1"];
  assert.deepEqual(back, stale);
});

test("choice labels read the same in the page, the export, and the builder", () => {
  assert.equal(runtime.choiceLabel(first, "keep-a"), "Option A · Keep A");
  assert.equal(runtime.choiceLabel(first, "custom"), "A different approach");
  assert.equal(
    runtime.choiceLabel(first, "no-change"),
    "No change · No change",
  );
  assert.equal(runtime.choiceLabel(first, ""), "No approach selected");
  assert.deepEqual(runtime.STATUSES, {
    open: "Not decided",
    decided: "Decided",
    discuss: "Needs discussion",
    deferred: "Deferred",
  });
});

test("embedded choices cannot close their own data block, and a saved copy gives them back", () => {
  const hostile = { notes: "</script><script>alert(1)</script>" };
  const block = runtime.safeJson(hostile);
  assert.equal(block.includes("<"), false);
  assert.deepEqual(JSON.parse(block), hostile);
  const page = `<html><script type="application/json" id="trackbed-decisions-state">${block}</script></html>`;
  assert.deepEqual(JSON.parse(runtime.extractState(page)), hostile);
  assert.equal(runtime.extractState('{"plain":"json"}'), '{"plain":"json"}');
});

test("the runtime keeps to the page: no network, no script injection, no markup from records", () => {
  const source = fs.readFileSync(RUNTIME, "utf8");
  for (const forbidden of [
    "fetch(",
    "XMLHttpRequest",
    "WebSocket",
    "sendBeacon",
    "EventSource",
    "innerHTML",
    "insertAdjacentHTML",
    "document.write",
    "eval(",
    "new Function",
  ])
    assert.equal(
      source.includes(forbidden),
      false,
      `runtime uses ${forbidden}`,
    );
  assert.equal(source.toLowerCase().includes("</script"), false);
});
