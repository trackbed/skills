// @ts-check
/*
 * Decision document runtime.
 * scripts/build-decisions.py writes this file into every decision document.
 * Never paste it into a page by hand.
 *
 * The page it runs in holds items a person has to decide on. The builder writes
 * all of the content; this script only keeps the reader's record: one choice,
 * a status, and notes per item. It saves that record in this browser, writes
 * it into a downloaded copy of the page, and exports and imports it as JSON.
 * It stays inside the page: the Content-Security-Policy the builder writes lets
 * nothing load or leave, and this script changes nothing but that record.
 *
 * The record rules in the first half are plain functions, exported when this
 * file loads under Node so they are tested without a browser. The builder's
 * `--choices` option applies the same rules in Python.
 */
"use strict";

(function () {
  /**
   * @typedef {"open" | "decided" | "discuss" | "deferred"} Status
   * @typedef {{ id: string, name: string, letter: string }} OptionInfo
   * @typedef {{
   *   id: string,
   *   title: string,
   *   fingerprint: string,
   *   options: OptionInfo[],
   *   noChange: string,
   *   recommended: string,
   * }} ItemInfo
   * @typedef {{
   *   documentId: string,
   *   title: string,
   *   fingerprint: string,
   *   generated: string,
   *   nounOne: string,
   *   nounMany: string,
   *   items: ItemInfo[],
   * }} Catalog
   * @typedef {{ status: Status, choiceLabel: string }} Earlier
   * @typedef {{
   *   option: string,
   *   status: Status,
   *   notes: string,
   *   updatedAt: string | null,
   *   itemFingerprint: string,
   *   earlier?: Earlier,
   * }} DecisionRecord
   * @typedef {{ [itemId: string]: DecisionRecord }} Records
   * @typedef {{ option?: string, status?: Status, notes?: string, confirm?: boolean }} Change
   * @typedef {{ records: Records, unknown: string[], cleared: { [itemId: string]: string } }} Parsed
   * @typedef {{ apply: string[], kept: string[], review: string[] }} ImportPlan
   */

  const FORMAT = "trackbed-decisions";
  const SCHEMA_VERSION = 1;
  const CUSTOM = "custom";
  const NO_CHANGE = "no-change";
  const MAX_NOTES = 10000;
  const MAX_LABEL = 300;
  const MAX_DECISIONS = 5000;
  const MAX_IMPORT_BYTES = 80 * 1024 * 1024;
  /** @type {Record<Status, string>} */
  const STATUSES = {
    open: "Not decided",
    decided: "Decided",
    discuss: "Needs discussion",
    deferred: "Deferred",
  };

  /** @param {unknown} value @returns {value is Record<string, unknown>} */
  function isObject(value) {
    return typeof value === "object" && value !== null && !Array.isArray(value);
  }

  /** @param {unknown} value @returns {value is Status} */
  function isStatus(value) {
    return typeof value === "string" && Object.hasOwn(STATUSES, value);
  }

  /** @param {unknown} value @returns {value is string} */
  function isTimestamp(value) {
    if (typeof value !== "string" || value.length !== 24) return false;
    const time = Date.parse(value);
    return Number.isFinite(time) && new Date(time).toISOString() === value;
  }

  /** @param {ItemInfo} item @returns {DecisionRecord} */
  function emptyRecord(item) {
    return {
      option: "",
      status: "open",
      notes: "",
      updatedAt: null,
      itemFingerprint: item.fingerprint,
    };
  }

  /**
   * Whether the reader has recorded anything. An earlier choice waiting for
   * review counts, even when its option is gone and it has no notes.
   * @param {{ option: string, status: string, notes: string, earlier?: unknown }} record
   */
  function hasContent(record) {
    return Boolean(
      record.option ||
      record.status !== "open" ||
      record.notes ||
      record.earlier,
    );
  }

  /** @param {ItemInfo} item @param {string} option */
  function choiceAllowed(item, option) {
    if (option === "" || option === CUSTOM) return true;
    if (option === NO_CHANGE) return Boolean(item.noChange);
    return item.options.some((candidate) => candidate.id === option);
  }

  /** @param {ItemInfo} item @param {string} option */
  function choiceLabel(item, option) {
    if (option === CUSTOM) return "A different approach";
    if (option === NO_CHANGE) return `No change · ${item.noChange}`;
    const found = item.options.find((candidate) => candidate.id === option);
    return found
      ? `Option ${found.letter} · ${found.name}`
      : "No approach selected";
  }

  /**
   * A record made on an earlier version of its item is kept, never trusted:
   * it is shown, and counted, as waiting for the reader to look again.
   * @param {ItemInfo} item @param {DecisionRecord} record
   */
  function needsReview(item, record) {
    return hasContent(record) && record.itemFingerprint !== item.fingerprint;
  }

  /**
   * True or false once the reader has chosen and a recommendation exists.
   * @param {ItemInfo} item @param {DecisionRecord} record
   * @returns {boolean | null}
   */
  function matchesRecommendation(item, record) {
    if (!record.option || !item.recommended) return null;
    return record.option === item.recommended;
  }

  /**
   * Read a choices payload: an export, the block embedded in a page, or what
   * this browser stored. Throws an Error a reader can act on, before anything
   * is changed, when the payload is not for this document or any record in it
   * is unusable. Records for items this document does not have are set aside.
   * @param {unknown} input @param {Catalog} catalog @returns {Parsed}
   */
  function parsePayload(input, catalog) {
    if (!isObject(input) || input.format !== FORMAT)
      throw new Error(
        "That file is not a choices export or a saved copy of a decision document.",
      );
    if (input.schemaVersion !== SCHEMA_VERSION)
      throw new Error(
        "Those choices were saved in a format this document does not read.",
      );
    const source = isObject(input.document) ? input.document.id : undefined;
    if (source !== catalog.documentId)
      throw new Error(
        "Those choices belong to a different document. Nothing was changed.",
      );
    const list = input.decisions;
    if (!Array.isArray(list) || list.length > MAX_DECISIONS)
      throw new Error("That file holds no usable list of choices.");

    const byId = new Map(catalog.items.map((item) => [item.id, item]));
    /** @type {Records} */
    const records = Object.create(null);
    /** @type {string[]} */
    const unknown = [];
    // When the reader cleared each item, so a clear outlasts an older record.
    /** @type {{ [itemId: string]: string }} */
    const cleared = Object.create(null);
    const seen = new Set();
    const broken = new Error(
      "A record in that file is damaged. Nothing was changed.",
    );
    for (const raw of list) {
      if (!isObject(raw) || typeof raw.itemId !== "string" || !raw.itemId)
        throw broken;
      if (seen.has(raw.itemId)) throw broken;
      seen.add(raw.itemId);
      const option = raw.option ?? "";
      if (typeof option !== "string" || option.length > 64) throw broken;
      if (!isStatus(raw.status)) throw broken;
      if (typeof raw.notes !== "string" || raw.notes.length > MAX_NOTES)
        throw broken;
      if (raw.status === "decided" && !option) throw broken;
      const candidate = {
        option,
        status: raw.status,
        notes: raw.notes,
        earlier: raw.earlier,
      };
      if (!hasContent(candidate)) {
        if (isTimestamp(raw.updatedAt) && byId.has(raw.itemId))
          cleared[raw.itemId] = raw.updatedAt;
        continue;
      }
      if (!isTimestamp(raw.updatedAt)) throw broken;
      const fingerprint = raw.itemFingerprint;
      if (
        typeof fingerprint !== "string" ||
        !fingerprint ||
        fingerprint.length > 64
      )
        throw broken;
      const label = raw.choiceLabel;
      if (
        label !== undefined &&
        label !== null &&
        (typeof label !== "string" || label.length > MAX_LABEL)
      )
        throw broken;
      /** @type {Earlier | undefined} */
      let earlier;
      if (raw.earlier !== undefined && raw.earlier !== null) {
        const before = raw.earlier;
        if (
          !isObject(before) ||
          !isStatus(before.status) ||
          typeof before.choiceLabel !== "string" ||
          before.choiceLabel.length > MAX_LABEL
        )
          throw broken;
        earlier = { status: before.status, choiceLabel: before.choiceLabel };
      }
      const item = byId.get(raw.itemId);
      if (!item) {
        unknown.push(raw.itemId);
        continue;
      }
      /** @type {DecisionRecord} */
      const record = {
        option,
        status: raw.status,
        notes: raw.notes,
        updatedAt: raw.updatedAt,
        itemFingerprint: fingerprint,
      };
      if (fingerprint === item.fingerprint) {
        // Same version of the item, so the option must be one it offers.
        if (!choiceAllowed(item, option)) throw broken;
      } else {
        // The item changed since this was recorded. Keep the notes and, when it
        // still exists, the option, but never as a standing decision.
        record.earlier = earlier ?? {
          status: raw.status,
          choiceLabel:
            typeof label === "string" && label
              ? label
              : choiceAllowed(item, option)
                ? choiceLabel(item, option)
                : option,
        };
        if (!choiceAllowed(item, option)) record.option = "";
        if (record.status === "decided") record.status = "open";
      }
      records[item.id] = record;
    }
    return { records, unknown, cleared };
  }

  /**
   * Fold stored records into the current ones, keeping the later edit of each.
   * An item the reader cleared after the current record was made stays cleared.
   * @param {Records} current @param {Records} incoming
   * @param {{ [itemId: string]: string }} [cleared] @returns {Records}
   */
  function mergeNewest(current, incoming, cleared = {}) {
    /** @type {Records} */
    const merged = Object.assign(Object.create(null), current);
    for (const [id, record] of Object.entries(incoming)) {
      const held = merged[id];
      if (
        !held ||
        !held.updatedAt ||
        (record.updatedAt && record.updatedAt > held.updatedAt)
      )
        merged[id] = record;
    }
    for (const [id, time] of Object.entries(cleared)) {
      const held = merged[id];
      if (held && (!held.updatedAt || time > held.updatedAt)) delete merged[id];
    }
    return merged;
  }

  /**
   * Fold a stored payload into the page's records, keeping the later edit of
   * each item. A later clear stays as an empty record with its time, so it
   * still outlasts an older record after this page writes. An unreadable
   * payload changes nothing; the next write replaces it.
   * @param {Catalog} catalog @param {Records} records @param {string | null} stored
   * @returns {Records}
   */
  function absorbStored(catalog, records, stored) {
    if (!stored) return records;
    /** @type {Parsed} */
    let parsed;
    try {
      parsed = parsePayload(JSON.parse(stored), catalog);
    } catch {
      return records;
    }
    const merged = mergeNewest(records, parsed.records, parsed.cleared);
    for (const item of catalog.items) {
      const time = parsed.cleared[item.id];
      if (time && !merged[item.id])
        merged[item.id] = { ...emptyRecord(item), updatedAt: time };
    }
    return merged;
  }

  /**
   * The one way records reach this browser's storage. Another tab may have
   * written since this page last looked, so read what is stored, merge both
   * ways, write the result, and hand it back for the page to show. Throws when
   * the storage refuses, so the page can say it is not saving.
   * @param {Pick<Storage, "getItem" | "setItem">} storage @param {string} key
   * @param {Catalog} catalog @param {Records} records @param {string} now
   * @returns {Records}
   */
  function syncStore(storage, key, catalog, records, now) {
    const merged = absorbStored(catalog, records, storage.getItem(key));
    storage.setItem(key, JSON.stringify(buildPayload(catalog, merged, now)));
    return merged;
  }

  /**
   * Which imported records would be written. By default a record the reader
   * already has is kept; replacing is the reader's explicit choice.
   * @param {Catalog} catalog @param {Records} current @param {Records} incoming @param {boolean} replace
   * @returns {ImportPlan}
   */
  function planImport(catalog, current, incoming, replace) {
    /** @type {ImportPlan} */
    const plan = { apply: [], kept: [], review: [] };
    for (const item of catalog.items) {
      const record = incoming[item.id];
      if (!record) continue;
      const held = current[item.id];
      if (!replace && held && hasContent(held)) {
        plan.kept.push(item.id);
        continue;
      }
      plan.apply.push(item.id);
      if (needsReview(item, record)) plan.review.push(item.id);
    }
    return plan;
  }

  /**
   * One edit by the reader. Choosing an approach on an undecided item decides
   * it; clearing the approach of a decided item reopens it; any choice or
   * status the reader sets is made on the current version of the item.
   * @param {ItemInfo} item @param {DecisionRecord} record @param {Change} change @param {string} now
   * @returns {DecisionRecord}
   */
  function applyChange(item, record, change, now) {
    /** @type {DecisionRecord} */
    const next = { ...record, updatedAt: now };
    if (change.notes !== undefined)
      next.notes = change.notes.slice(0, MAX_NOTES);
    if (change.option !== undefined && choiceAllowed(item, change.option)) {
      next.option = change.option;
      if (next.option && next.status === "open") next.status = "decided";
      if (!next.option && next.status === "decided") next.status = "open";
    }
    if (change.status !== undefined)
      next.status =
        change.status === "decided" && !next.option ? "open" : change.status;
    if (change.confirm && record.earlier && next.option)
      next.status = record.earlier.status;
    if (
      change.option !== undefined ||
      change.status !== undefined ||
      change.confirm
    ) {
      next.itemFingerprint = item.fingerprint;
      delete next.earlier;
    }
    if (!hasContent(next)) {
      next.itemFingerprint = item.fingerprint;
      delete next.earlier;
    }
    return next;
  }

  /** @param {Catalog} catalog @param {Records} records */
  function countStatuses(catalog, records) {
    const counts = {
      total: catalog.items.length,
      open: 0,
      decided: 0,
      discuss: 0,
      deferred: 0,
      needsReview: 0,
    };
    for (const item of catalog.items) {
      const record = records[item.id] ?? emptyRecord(item);
      counts[record.status] += 1;
      if (needsReview(item, record)) counts.needsReview += 1;
    }
    return counts;
  }

  /**
   * The export: every item in document order, with enough beside each choice
   * for a later reader, human or agent, to act on it without the page.
   * @param {Catalog} catalog @param {Records} records @param {string} now
   */
  function buildPayload(catalog, records, now) {
    return {
      format: FORMAT,
      schemaVersion: SCHEMA_VERSION,
      document: {
        id: catalog.documentId,
        title: catalog.title,
        fingerprint: catalog.fingerprint,
        generated: catalog.generated,
      },
      exportedAt: now,
      summary: countStatuses(catalog, records),
      decisions: catalog.items.map((item) => {
        const record = records[item.id] ?? emptyRecord(item);
        const review = needsReview(item, record);
        return {
          itemId: item.id,
          itemTitle: item.title,
          itemFingerprint: record.itemFingerprint,
          status: record.status,
          statusLabel: STATUSES[record.status],
          option: record.option || null,
          choiceLabel: choiceLabel(item, record.option),
          recommendedOption: item.recommended || null,
          matchesRecommendation: matchesRecommendation(item, record),
          notes: record.notes,
          updatedAt: record.updatedAt,
          needsReview: review,
          ...(review && record.earlier ? { earlier: record.earlier } : {}),
        };
      }),
    };
  }

  /** JSON for a data block: no `<`, so nothing in it can close the element. @param {unknown} value */
  function safeJson(value) {
    return JSON.stringify(value).replace(/</g, "\\u003c");
  }

  /**
   * The choices inside a saved copy of a decision document, or the text itself.
   * @param {string} text
   */
  function extractState(text) {
    const match =
      /<script type="application\/json" id="trackbed-decisions-state">([\s\S]*?)<\/script>/.exec(
        text,
      );
    return match ? match[1] : text;
  }

  const api = {
    FORMAT,
    SCHEMA_VERSION,
    STATUSES,
    CUSTOM,
    NO_CHANGE,
    absorbStored,
    applyChange,
    buildPayload,
    choiceAllowed,
    choiceLabel,
    countStatuses,
    emptyRecord,
    extractState,
    hasContent,
    matchesRecommendation,
    mergeNewest,
    needsReview,
    parsePayload,
    planImport,
    safeJson,
    syncStore,
  };
  if (typeof module === "object" && module && module.exports)
    module.exports = api;
  if (typeof document === "undefined") return;

  // ---------- the page ----------

  /**
   * @template {Element} T
   * @param {ParentNode} root @param {string} selector @param {new () => T} type
   * @returns {T}
   */
  function need(root, selector, type) {
    const found = root.querySelector(selector);
    if (!(found instanceof type))
      throw new Error(`decision document is missing ${selector}`);
    return found;
  }

  /**
   * @template {Element} T
   * @param {ParentNode} root @param {string} selector @param {new () => T} type
   * @returns {T[]}
   */
  function all(root, selector, type) {
    /** @type {T[]} */
    const found = [];
    root.querySelectorAll(selector).forEach((node) => {
      if (node instanceof type) found.push(node);
    });
    return found;
  }

  function boot() {
    /** @type {Catalog} */
    const catalog = JSON.parse(
      need(document, "#trackbed-decisions-catalog", HTMLScriptElement)
        .textContent ?? "",
    );
    const stateBlock = need(
      document,
      "#trackbed-decisions-state",
      HTMLScriptElement,
    );
    const storageKey = `${FORMAT}:v${SCHEMA_VERSION}:${catalog.documentId}`;
    const byId = new Map(catalog.items.map((item) => [item.id, item]));
    const views = all(document, "[data-view]", HTMLElement);
    const articles = new Map(
      all(document, "[data-item]", HTMLElement).map((node) => [
        node.dataset.item ?? "",
        node,
      ]),
    );
    const sidebar = need(document, "[data-sidebar]", HTMLElement);
    const browse = need(document, "[data-browse]", HTMLButtonElement);
    const toast = need(document, "[data-toast]", HTMLElement);
    const message = need(document, "[data-message]", HTMLElement);
    const baseTitle = document.title;

    /** @type {Records} */
    let records = Object.create(null);
    let storageWorks = true;
    let unsaved = false;
    let lastStamp = 0;
    /** @type {number | undefined} */
    let saveTimer;
    /** @type {number | undefined} */
    let toastTimer;
    let currentIndex = 0;

    document.documentElement.classList.replace("no-js", "js");

    /** @param {ItemInfo} item */
    const recordOf = (item) => records[item.id] ?? emptyRecord(item);

    function stamp() {
      lastStamp = Math.max(Date.now(), lastStamp + 1);
      return new Date(lastStamp).toISOString();
    }

    /** @param {string} text @param {boolean} [failed] */
    function saveStatus(text, failed) {
      for (const node of all(document, "[data-save-status]", HTMLElement)) {
        node.textContent = text;
        node.dataset.failed = String(Boolean(failed));
      }
    }

    /** @param {string} text @param {boolean} [failed] */
    function announce(text, failed) {
      message.textContent = text;
      message.dataset.failed = String(Boolean(failed));
      toast.textContent = text;
      toast.dataset.failed = String(Boolean(failed));
      toast.hidden = false;
      window.clearTimeout(toastTimer);
      toastTimer = window.setTimeout(() => {
        toast.hidden = true;
      }, 9000);
    }

    // Every write goes through here, so a tab never erases what another saved.
    function persist() {
      window.clearTimeout(saveTimer);
      saveTimer = undefined;
      try {
        records = syncStore(
          localStorage,
          storageKey,
          catalog,
          records,
          new Date().toISOString(),
        );
        render();
        storageWorks = true;
        unsaved = false;
        const time = new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });
        saveStatus(`Saved in this browser at ${time}`);
        return true;
      } catch {
        storageWorks = false;
        saveStatus(
          "Not saved: this browser is not storing choices. Use Save a copy or Export choices before you close this page.",
          true,
        );
        return false;
      }
    }

    // ---------- showing the record ----------

    /** @param {HTMLElement} node @param {Status} status @param {boolean} review */
    function badge(node, status, review) {
      node.textContent = review ? "Needs review" : STATUSES[status];
      node.dataset.status = review ? "review" : status;
    }

    function render() {
      const counts = countStatuses(catalog, records);
      for (const item of catalog.items) {
        const record = recordOf(item);
        const review = needsReview(item, record);
        const label = choiceLabel(item, record.option);
        const article = articles.get(item.id);
        if (!article) continue;

        for (const input of all(article, "[data-choice]", HTMLInputElement))
          input.checked = input.value === record.option;
        for (const card of all(article, "[data-option]", HTMLElement)) {
          const chosen = card.dataset.option === record.option;
          card.dataset.selected = String(chosen);
          const mark = card.querySelector("[data-yours]");
          if (mark instanceof HTMLElement) mark.hidden = !chosen;
        }
        const status = need(
          article,
          "[data-decision-status]",
          HTMLSelectElement,
        );
        const decided = need(
          status,
          'option[value="decided"]',
          HTMLOptionElement,
        );
        decided.disabled = !record.option;
        status.value = record.status;
        const notes = need(article, "[data-notes]", HTMLTextAreaElement);
        if (notes.value !== record.notes) notes.value = record.notes;
        need(article, "[data-clear]", HTMLButtonElement).disabled =
          !record.option;
        need(article, "[data-status-help]", HTMLElement).hidden = Boolean(
          record.option,
        );
        const line = `${STATUSES[record.status]} · ${label}`;
        need(article, "[data-choice-summary]", HTMLElement).textContent = line;
        need(article, "[data-print-choice]", HTMLElement).textContent = line;
        need(article, "[data-print-notes]", HTMLElement).textContent =
          record.notes;

        const notice = need(article, "[data-review]", HTMLElement);
        notice.hidden = !review;
        if (review) {
          const earlier = record.earlier;
          const before =
            earlier && earlier.choiceLabel
              ? ` Earlier you recorded: ${STATUSES[earlier.status]} · ${earlier.choiceLabel}.`
              : "";
          need(notice, "[data-review-text]", HTMLElement).textContent =
            `This ${catalog.nounOne} or its options changed after you recorded your choice, so it is not counted as decided.${before} Read it again, then keep or change your choice.`;
          const confirm = need(notice, "[data-confirm]", HTMLButtonElement);
          confirm.textContent = record.option
            ? `Keep my earlier choice: ${label}`
            : "Keep my notes as they are";
        }

        const nav = need(
          document,
          `[data-nav-state="${CSS.escape(item.id)}"]`,
          HTMLElement,
        );
        nav.hidden = !hasContent(record);
        nav.dataset.status = review ? "review" : record.status;
        nav.textContent = review
          ? "Needs review"
          : record.status === "open"
            ? "Draft"
            : STATUSES[record.status];

        const cell = need(
          document,
          `[data-index-choice="${CSS.escape(item.id)}"]`,
          HTMLElement,
        );
        const cellBadge = document.createElement("span");
        cellBadge.className = "td-badge";
        badge(cellBadge, record.status, review);
        const cellLabel = document.createElement("span");
        cellLabel.className = "td-approach";
        cellLabel.textContent = label;
        cell.replaceChildren(cellBadge, cellLabel);

        const row = need(
          document,
          `[data-choice-row="${CSS.escape(item.id)}"]`,
          HTMLElement,
        );
        row.dataset.status = review ? "review" : record.status;
        need(row, "[data-row-approach]", HTMLElement).textContent = label;
        const match = matchesRecommendation(item, record);
        need(row, "[data-row-versus]", HTMLElement).textContent =
          match === null
            ? ""
            : match
              ? "Same as the recommendation"
              : `Recommended: ${choiceLabel(item, item.recommended)}`;
        badge(
          need(row, "[data-row-status]", HTMLElement),
          record.status,
          review,
        );
        need(row, "[data-row-notes]", HTMLElement).textContent = record.notes;
      }
      for (const node of all(document, "[data-status-count]", HTMLElement)) {
        const key = node.dataset.statusCount;
        node.textContent = String(isStatus(key) ? counts[key] : 0);
      }
      for (const node of all(document, "[data-progress-short]", HTMLElement))
        node.textContent = `${counts.decided}/${counts.total}`;
      const reviewCount = need(document, "[data-review-count]", HTMLElement);
      reviewCount.hidden = counts.needsReview === 0;
      reviewCount.textContent =
        counts.needsReview === 0
          ? ""
          : `${counts.needsReview} of your earlier choices need review, because what they were about has changed.`;
      filterChoices();
      filterIndex();
    }

    /** @param {string} id @param {Change} change @param {boolean} [typing] */
    function update(id, change, typing) {
      const item = byId.get(id);
      if (!item) return;
      records[id] = applyChange(item, recordOf(item), change, stamp());
      unsaved = true;
      render();
      window.clearTimeout(saveTimer);
      if (typing && storageWorks) {
        saveStatus("Saving in this browser");
        saveTimer = window.setTimeout(persist, 400);
      } else persist();
    }

    // ---------- finding your way ----------

    /** @param {string} hash */
    function parseRoute(hash) {
      let key = "";
      try {
        key = decodeURIComponent(hash.replace(/^#/, ""));
      } catch {
        key = "";
      }
      const [target = "", part = ""] = key.split("/");
      const itemId = target.startsWith("item-") ? target.slice(5) : "";
      if (itemId && byId.has(itemId)) return { view: "item", itemId, part };
      const view = views.some((node) => node.dataset.view === target)
        ? target
        : "overview";
      return {
        view: view === "item" ? "overview" : view,
        itemId: "",
        part: "",
      };
    }

    function show() {
      const route = parseRoute(location.hash);
      for (const view of views) view.hidden = view.dataset.view !== route.view;
      for (const [id, article] of articles)
        article.hidden = id !== route.itemId;
      const current = route.itemId ? `#item-${route.itemId}` : `#${route.view}`;
      for (const link of all(document, "a[data-route]", HTMLAnchorElement)) {
        const here =
          (link.getAttribute("href") ?? "").split("/")[0] === current;
        if (here && link.closest("nav"))
          link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
      }
      sidebar.dataset.expanded = "false";
      browse.setAttribute("aria-expanded", "false");

      /** @type {HTMLElement | null} */
      let target = null;
      const item = byId.get(route.itemId);
      if (item) {
        const article = articles.get(item.id) ?? null;
        currentIndex = catalog.items.indexOf(item);
        need(document, "[data-pager-count]", HTMLElement).textContent =
          `${catalog.nounOne.charAt(0).toUpperCase()}${catalog.nounOne.slice(1)} ${currentIndex + 1} of ${catalog.items.length}`;
        need(document, "[data-previous]", HTMLButtonElement).disabled =
          currentIndex === 0;
        need(document, "[data-next]", HTMLButtonElement).disabled =
          currentIndex === catalog.items.length - 1;
        document.title = `${item.id} · ${item.title}`;
        const part =
          article && route.part
            ? article.querySelector(`[data-part="${CSS.escape(route.part)}"]`)
            : null;
        const heading = (part ?? article)?.querySelector("[tabindex='-1']");
        target = heading instanceof HTMLElement ? heading : article;
        if (part instanceof HTMLElement) {
          part.scrollIntoView({ block: "start", behavior: "instant" });
        } else window.scrollTo({ top: 0, behavior: "instant" });
        const link = document.querySelector(".td-item-nav [aria-current]");
        if (link instanceof HTMLElement && link.offsetParent)
          link.scrollIntoView({ block: "nearest" });
      } else {
        document.title = baseTitle;
        const view = views.find((node) => node.dataset.view === route.view);
        const heading = view?.querySelector("[data-heading]");
        target = heading instanceof HTMLElement ? heading : null;
        window.scrollTo({ top: 0, behavior: "instant" });
      }
      return target;
    }

    /** @param {string} hash */
    function go(hash) {
      if (location.hash !== hash) {
        try {
          history.pushState(null, "", hash);
        } catch {
          // Some browsers refuse this for a local file; the hash change still fires popstate.
          location.hash = hash;
          return;
        }
      }
      show()?.focus({ preventScroll: true });
    }

    document.addEventListener("click", (event) => {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      )
        return;
      const link =
        event.target instanceof Element
          ? event.target.closest("a[data-route]")
          : null;
      const href = link?.getAttribute("href");
      if (!href) return;
      event.preventDefault();
      go(href);
    });
    window.addEventListener("popstate", () => {
      show()?.focus({ preventScroll: true });
    });
    browse.addEventListener("click", () => {
      const expanded = sidebar.dataset.expanded !== "true";
      sidebar.dataset.expanded = String(expanded);
      browse.setAttribute("aria-expanded", String(expanded));
    });
    need(document, "[data-previous]", HTMLButtonElement).addEventListener(
      "click",
      () => {
        if (currentIndex > 0) go(`#item-${catalog.items[currentIndex - 1].id}`);
      },
    );
    need(document, "[data-next]", HTMLButtonElement).addEventListener(
      "click",
      () => {
        if (currentIndex < catalog.items.length - 1)
          go(`#item-${catalog.items[currentIndex + 1].id}`);
      },
    );

    // ---------- recording a choice ----------

    for (const [id, article] of articles) {
      for (const input of all(article, "[data-choice]", HTMLInputElement))
        input.addEventListener("change", () => {
          if (input.checked) update(id, { option: input.value });
        });
      need(
        article,
        "[data-decision-status]",
        HTMLSelectElement,
      ).addEventListener("change", (event) => {
        const value =
          event.target instanceof HTMLSelectElement ? event.target.value : "";
        if (isStatus(value)) update(id, { status: value });
      });
      need(article, "[data-notes]", HTMLTextAreaElement).addEventListener(
        "input",
        (event) => {
          if (event.target instanceof HTMLTextAreaElement)
            update(id, { notes: event.target.value }, true);
        },
      );
      need(article, "[data-clear]", HTMLButtonElement).addEventListener(
        "click",
        () => update(id, { option: "" }),
      );
      need(article, "[data-confirm]", HTMLButtonElement).addEventListener(
        "click",
        () => update(id, { confirm: true }),
      );
    }

    // ---------- evidence ----------

    for (const gallery of all(document, "[data-gallery]", HTMLElement)) {
      const figures = all(gallery, "[data-figure]", HTMLElement);
      const tabs = all(gallery, "[data-shot]", HTMLButtonElement);
      /** @param {string} index */
      const pick = (index) => {
        for (const figure of figures)
          figure.dataset.active = String(figure.dataset.figure === index);
        for (const tab of tabs)
          tab.setAttribute("aria-pressed", String(tab.dataset.shot === index));
      };
      for (const tab of tabs)
        tab.addEventListener("click", () => pick(tab.dataset.shot ?? "0"));
      pick("0");
    }

    const zoom = need(document, "[data-zoom-dialog]", HTMLDialogElement);
    const zoomImage = need(zoom, "[data-zoom-image]", HTMLImageElement);
    const fit = need(zoom, "[data-fit]", HTMLButtonElement);
    const actual = need(zoom, "[data-actual]", HTMLButtonElement);
    /** @param {boolean} original */
    function zoomMode(original) {
      zoomImage.classList.toggle("td-original", original);
      fit.setAttribute("aria-pressed", String(!original));
      actual.setAttribute("aria-pressed", String(original));
    }
    fit.addEventListener("click", () => zoomMode(false));
    actual.addEventListener("click", () => zoomMode(true));
    for (const button of all(document, "[data-zoom]", HTMLButtonElement))
      button.addEventListener("click", () => {
        const image = button.querySelector("img");
        const caption = button.closest("figure")?.querySelector("figcaption");
        if (!image) return;
        zoomImage.src = image.src;
        zoomImage.alt = image.alt;
        need(zoom, "[data-zoom-caption]", HTMLElement).textContent =
          caption?.textContent ?? "";
        zoomMode(false);
        zoom.showModal();
      });
    for (const dialog of all(document, "dialog", HTMLDialogElement)) {
      for (const button of all(dialog, "[data-close]", HTMLButtonElement))
        button.addEventListener("click", () => dialog.close());
      // A click on the backdrop lands on the dialog element itself.
      dialog.addEventListener("click", (event) => {
        if (event.target === dialog) dialog.close();
      });
    }

    // ---------- the index and the choices table ----------

    const filters = all(document, "[data-filter]", HTMLElement);
    /** @param {string} name */
    function filterValue(name) {
      const control = filters.find((node) => node.dataset.filter === name);
      return control instanceof HTMLInputElement ||
        control instanceof HTMLSelectElement
        ? control.value
        : "";
    }
    function filterIndex() {
      const query = filterValue("search").trim().toLowerCase();
      const label = filterValue("label");
      const status = filterValue("status");
      let shown = 0;
      for (const row of all(document, "[data-index-row]", HTMLElement)) {
        const item = byId.get(row.dataset.indexRow ?? "");
        /** @type {unknown} */
        let labels = [];
        try {
          labels = JSON.parse(row.dataset.labels ?? "[]");
        } catch {
          labels = [];
        }
        const visible =
          (!query || (row.dataset.search ?? "").includes(query)) &&
          (!label || (Array.isArray(labels) && labels.includes(label))) &&
          (!status || (item !== undefined && recordOf(item).status === status));
        row.hidden = !visible;
        if (visible) shown += 1;
      }
      const total = catalog.items.length;
      need(document, "[data-filter-count]", HTMLElement).textContent =
        shown === total
          ? `${total} ${total === 1 ? catalog.nounOne : catalog.nounMany}`
          : `${shown} of ${total} ${catalog.nounMany}`;
      need(document, "[data-filter-empty]", HTMLElement).hidden = shown !== 0;
      need(document, "[data-index-table]", HTMLElement).hidden = shown === 0;
      need(document, "[data-filter-clear]", HTMLButtonElement).hidden =
        !query && !label && !status;
    }
    for (const control of filters)
      control.addEventListener(
        control instanceof HTMLInputElement ? "input" : "change",
        filterIndex,
      );
    need(document, "[data-filter-clear]", HTMLButtonElement).addEventListener(
      "click",
      () => {
        for (const control of filters)
          if (
            control instanceof HTMLInputElement ||
            control instanceof HTMLSelectElement
          )
            control.value = "";
        filterIndex();
      },
    );

    const choiceFilter = need(
      document,
      "[data-choice-filter]",
      HTMLSelectElement,
    );
    function filterChoices() {
      const wanted = choiceFilter.value;
      let shown = 0;
      for (const row of all(document, "[data-choice-row]", HTMLElement)) {
        const item = byId.get(row.dataset.choiceRow ?? "");
        const record = item ? recordOf(item) : undefined;
        const visible =
          !wanted ||
          (item !== undefined &&
            record !== undefined &&
            (wanted === "review"
              ? needsReview(item, record)
              : record.status === wanted));
        row.hidden = !visible;
        if (visible) shown += 1;
      }
      need(document, "[data-choice-count]", HTMLElement).textContent =
        `Showing ${shown} of ${catalog.items.length}`;
    }
    choiceFilter.addEventListener("change", filterChoices);

    // ---------- keeping and moving the record ----------

    /** @param {string} contents @param {string} type @param {string} name */
    function download(contents, type, name) {
      const url = URL.createObjectURL(new Blob([contents], { type }));
      const link = document.createElement("a");
      link.href = url;
      link.download = name;
      document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    }

    function saveCopy() {
      persist();
      const root = document.documentElement.cloneNode(true);
      if (!(root instanceof HTMLElement)) return;
      // The copy opens the way a new document does; only the choices differ.
      need(root, "#trackbed-decisions-state", HTMLScriptElement).textContent =
        safeJson(buildPayload(catalog, records, new Date().toISOString()));
      root.classList.replace("js", "no-js");
      for (const node of all(root, "[data-view], [data-item]", HTMLElement))
        node.hidden = false;
      for (const dialog of all(root, "dialog", HTMLDialogElement))
        dialog.removeAttribute("open");
      need(root, "[data-zoom-image]", HTMLImageElement).removeAttribute("src");
      need(root, "[data-toast]", HTMLElement).hidden = true;
      need(root, "[data-message]", HTMLElement).textContent = "";
      download(
        `<!doctype html>\n${root.outerHTML}\n`,
        "text/html;charset=utf-8",
        `${catalog.documentId}-with-choices.html`,
      );
      unsaved = false;
      announce(
        "Downloading a copy of this document with your choices and notes inside it. Open that file to carry on from it.",
      );
    }
    for (const button of all(document, "[data-save-copy]", HTMLButtonElement))
      button.addEventListener("click", saveCopy);

    need(document, "[data-export]", HTMLButtonElement).addEventListener(
      "click",
      () => {
        persist();
        const payload = buildPayload(
          catalog,
          records,
          new Date().toISOString(),
        );
        download(
          `${JSON.stringify(payload, null, 2)}\n`,
          "application/json;charset=utf-8",
          `${catalog.documentId}-choices.json`,
        );
        unsaved = false;
        announce(
          "Downloading your choices and notes as a JSON file. Hand it to the agent, or import it here later.",
        );
      },
    );

    const importDialog = need(
      document,
      "[data-import-dialog]",
      HTMLDialogElement,
    );
    const importFile = need(document, "[data-import-file]", HTMLInputElement);
    const importReplace = need(
      importDialog,
      'input[value="replace"]',
      HTMLInputElement,
    );
    const importConfirm = need(
      importDialog,
      "[data-import-confirm]",
      HTMLButtonElement,
    );
    /** @type {Parsed | undefined} */
    let pending;

    function previewImport() {
      if (!pending) return;
      const plan = planImport(
        catalog,
        records,
        pending.records,
        importReplace.checked,
      );
      const parts = [`${plan.apply.length} will be imported.`];
      if (plan.kept.length)
        parts.push(`${plan.kept.length} of your own will be kept.`);
      if (plan.review.length)
        parts.push(
          `${plan.review.length} were made on an earlier version of their ${catalog.nounOne} and will come in marked for review, not as decided.`,
        );
      need(importDialog, "[data-import-preview]", HTMLElement).textContent =
        parts.join(" ");
      importConfirm.disabled = plan.apply.length === 0;
    }
    for (const radio of all(
      importDialog,
      'input[name="td-import-mode"]',
      HTMLInputElement,
    ))
      radio.addEventListener("change", previewImport);

    need(document, "[data-import]", HTMLButtonElement).addEventListener(
      "click",
      () => {
        importFile.value = "";
        importFile.click();
      },
    );
    importFile.addEventListener("change", async () => {
      const file = importFile.files?.[0];
      if (!file) return;
      pending = undefined;
      try {
        if (file.size > MAX_IMPORT_BYTES)
          throw new Error("That file is too large to be a choices export.");
        /** @type {unknown} */
        let parsed;
        try {
          parsed = JSON.parse(extractState(await file.text()));
        } catch {
          throw new Error(
            "That file is not a choices export or a saved copy of a decision document.",
          );
        }
        // Everything is checked here, before the reader is asked anything.
        const result = parsePayload(parsed, catalog);
        const count = Object.keys(result.records).length;
        if (count === 0) {
          announce(
            result.unknown.length
              ? `Nothing to import: the ${result.unknown.length} choices in that file are for ${catalog.nounMany} this document no longer has.`
              : "Nothing to import: that file holds no recorded choices or notes.",
          );
          return;
        }
        pending = result;
        const skipped = result.unknown.length
          ? ` ${result.unknown.length} more are for ${catalog.nounMany} this document does not have and will be left out.`
          : "";
        need(
          importDialog,
          "[data-import-description]",
          HTMLElement,
        ).textContent =
          `"${file.name}" holds choices for ${count} of the ${catalog.items.length} ${catalog.nounMany} here.${skipped}`;
        need(importDialog, 'input[value="keep"]', HTMLInputElement).checked =
          true;
        previewImport();
        importDialog.showModal();
      } catch (error) {
        announce(
          `${error instanceof Error ? error.message : "That file could not be read."} Your current choices are unchanged.`,
          true,
        );
      }
    });
    importConfirm.addEventListener("click", () => {
      if (!pending) return;
      const plan = planImport(
        catalog,
        records,
        pending.records,
        importReplace.checked,
      );
      // An import is the reader's latest edit, so it must outlast older embedded choices on reload.
      for (const id of plan.apply)
        records[id] = { ...pending.records[id], updatedAt: stamp() };
      pending = undefined;
      importDialog.close();
      render();
      const saved = persist();
      announce(
        `Imported choices for ${plan.apply.length} ${plan.apply.length === 1 ? catalog.nounOne : catalog.nounMany}.` +
          (plan.kept.length ? ` Kept ${plan.kept.length} of your own.` : "") +
          (saved
            ? ""
            : " They are not saved in this browser: use Save a copy to keep them."),
      );
    });
    importDialog.addEventListener("close", () => {
      pending = undefined;
    });

    // ---------- printing ----------

    // ---------- skipping to the content ----------

    // A plain hash change would route "#main" to the overview; move focus instead.
    need(document, "[data-skip]", HTMLAnchorElement).addEventListener(
      "click",
      (event) => {
        event.preventDefault();
        need(document, "#main", HTMLElement).focus();
      },
    );

    need(document, "[data-print]", HTMLButtonElement).addEventListener(
      "click",
      () => window.print(),
    );

    // ---------- leaving ----------

    window.addEventListener("pagehide", () => {
      if (saveTimer !== undefined) persist();
    });
    document.addEventListener("visibilitychange", () => {
      if (document.hidden && saveTimer !== undefined) persist();
    });
    window.addEventListener("beforeunload", (event) => {
      // Only when this browser cannot keep the choices and no copy was taken.
      if (!storageWorks && unsaved) event.preventDefault();
    });
    // Another tab saved. Its write already holds this page's last save, so
    // merging is enough; a pending save here merges again before it writes.
    window.addEventListener("storage", (event) => {
      if (event.key !== storageKey) return;
      records = absorbStored(catalog, records, event.newValue);
      render();
    });

    // ---------- start ----------

    let restored = 0;
    try {
      records = parsePayload(
        JSON.parse(stateBlock.textContent ?? ""),
        catalog,
      ).records;
      restored = Object.keys(records).length;
    } catch {
      announce(
        "The choices stored inside this file could not be read, so it starts without them.",
        true,
      );
    }
    try {
      records = absorbStored(
        catalog,
        records,
        localStorage.getItem(storageKey),
      );
      const probe = `${storageKey}:probe`;
      localStorage.setItem(probe, "1");
      localStorage.removeItem(probe);
      restored = Object.values(records).filter(hasContent).length;
      saveStatus(
        restored
          ? `Restored your choices for ${restored} ${restored === 1 ? catalog.nounOne : catalog.nounMany}. Changes are saved in this browser.`
          : "Changes are saved in this browser as you make them.",
      );
    } catch {
      storageWorks = false;
      saveStatus(
        "This browser is not storing choices. Use Save a copy or Export choices to keep what you record.",
        true,
      );
    }
    render();
    show();
  }

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
