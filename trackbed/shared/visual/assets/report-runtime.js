// @ts-check
/*
 * Visual report runtime.
 * scripts/visual-report.py copies this file into the page's runtime script element.
 * Never paste it into a page by hand. The page contract is in
 * shared/visual/references/visual-report.md.
 *
 * The page it runs in is a snapshot of a Markdown report. Its job is to help a
 * person read that report: an outline of every entry, ways to move from one
 * entry to the next, filters that narrow what is shown, and a triage prompt to
 * hand the reader's decisions back. Everything here reads the page, never the
 * network: the injected Content-Security-Policy allows no requests, and triage
 * decisions stay in this browser's localStorage.
 */
"use strict";

(function () {
  /**
   * @typedef {{ path: string, line: number | null }} ReportLocation
   * @typedef {{ decision: "accept" | "dismiss", note: string }} Decision
   * @typedef {{
   *   id: string,
   *   title: string,
   *   facets: Record<string, string>,
   *   location: string,
   *   text: string,
   *   order: number,
   *   triageable: boolean,
   * }} EntryData
   * @typedef {{
   *   producer: string,
   *   source: string,
   *   generated: string,
   *   commit: string,
   *   root: string,
   *   facets: string[],
   *   followups: string[],
   *   acceptLabel: string,
   *   dismissLabel: string,
   *   nounOne?: string,
   *   nounMany?: string,
   * }} ReportMeta
   * @typedef {{ theme: "auto" | "light" | "dark", editor: string, custom: string, keys: boolean }} Settings
   */

  const SEVERITIES = ["critical", "high", "medium", "low", "suggestion"];
  const TRIAGE_FACET = "triage";
  const TRIAGE_VALUES = ["accepted", "dismissed", "undecided"];
  /** @type {Record<string, { label: string, template: string }>} */
  const EDITORS = {
    vscode: { label: "VS Code", template: "vscode://file{path}:{line}" },
    cursor: { label: "Cursor", template: "cursor://file{path}:{line}" },
    zed: { label: "Zed", template: "zed://file{path}:{line}" },
    windsurf: { label: "Windsurf", template: "windsurf://file{path}:{line}" },
  };
  const BLOCKED_SCHEMES = ["javascript", "data", "vbscript", "blob"];
  const SETTINGS_KEY = "trackbed-report:settings";

  // ---------- Pure helpers (exported for tests) ----------

  /**
   * @param {string} value
   * @returns {string}
   */
  function label(value) {
    return value.replace(/[-_]+/g, " ").trim();
  }

  /**
   * @param {string} value
   * @returns {string}
   */
  function titleCase(value) {
    const text = label(value);
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  /**
   * Reads `path`, `path:line`, `path:start-end`, or `path:line:column`.
   * @param {string} text
   * @returns {ReportLocation | null}
   */
  function parseLocation(text) {
    const value = text.trim();
    if (!value) return null;
    const match = /^(.*?):(\d+)(?:[-:]\d+)*$/.exec(value);
    if (match && match[1]) return { path: match[1], line: Number(match[2]) };
    return { path: value, line: null };
  }

  /**
   * @param {string} template
   * @returns {boolean}
   */
  function isEditorTemplate(template) {
    const match = /^([a-z][a-z0-9+.-]*):\/\//i.exec(template.trim());
    if (!match) return false;
    return (
      !BLOCKED_SCHEMES.includes(match[1].toLowerCase()) &&
      template.includes("{path}")
    );
  }

  /**
   * @param {string} template
   * @param {string} root
   * @param {ReportLocation | null} location
   * @returns {string | null}
   */
  function editorUrl(template, root, location) {
    if (!location || !root || !isEditorTemplate(template)) return null;
    const isAbsolute =
      location.path.startsWith("/") || /^[A-Za-z]:[\\/]/.test(location.path);
    const joined = isAbsolute
      ? location.path
      : `${root.replace(/[\\/]+$/, "")}/${location.path}`;
    // Every editor template expects the path to start with one slash, including `C:/...`.
    const absolute = `/${joined.replace(/\\/g, "/").replace(/^\/+/, "")}`;
    const encoded = encodeURI(absolute).replace(/[?#]/g, (ch) =>
      encodeURIComponent(ch),
    );
    return template
      .trim()
      .replace(/\{path\}/g, encoded)
      .replace(/\{line\}/g, String(location.line ?? 1));
  }

  /**
   * @param {string} a
   * @param {string} b
   * @returns {number}
   */
  function compareText(a, b) {
    const left = Number(a.replace(/[,%\s]/g, ""));
    const right = Number(b.replace(/[,%\s]/g, ""));
    if (a.trim() && b.trim() && Number.isFinite(left) && Number.isFinite(right))
      return left - right;
    return a.localeCompare(b, undefined, {
      numeric: true,
      sensitivity: "base",
    });
  }

  /**
   * @param {string} value
   * @returns {number}
   */
  function severityRank(value) {
    const rank = SEVERITIES.indexOf(value);
    return rank === -1 ? SEVERITIES.length : rank;
  }

  /**
   * @param {EntryData} a
   * @param {EntryData} b
   * @param {string} key `order`, `location`, or a facet name
   * @returns {number}
   */
  function compareEntries(a, b, key) {
    let result = 0;
    if (key === "severity") {
      result =
        severityRank(a.facets.severity ?? "") -
        severityRank(b.facets.severity ?? "");
    } else if (key === "location") {
      result = compareMissingLast(a.location, b.location);
    } else if (key !== "order") {
      result = compareMissingLast(a.facets[key] ?? "", b.facets[key] ?? "");
    }
    return result || a.order - b.order;
  }

  /**
   * @param {string} a
   * @param {string} b
   * @returns {number}
   */
  function compareMissingLast(a, b) {
    if (!a || !b) return a === b ? 0 : a ? -1 : 1;
    return compareText(a, b);
  }

  /**
   * @param {Decision | undefined} decision
   * @returns {string}
   */
  function triageValue(decision) {
    if (!decision) return "undecided";
    return decision.decision === "accept" ? "accepted" : "dismissed";
  }

  /**
   * Values within one facet are alternatives; facets and search terms all have to match.
   * @param {EntryData} entry
   * @param {Record<string, string[]>} filters
   * @param {string} query
   * @param {Decision | undefined} decision
   * @returns {boolean}
   */
  function matches(entry, filters, query, decision) {
    for (const [facet, selected] of Object.entries(filters)) {
      if (selected.length === 0) continue;
      // An entry with triage off has no decision to filter by, not an undecided one.
      if (facet === TRIAGE_FACET && !entry.triageable) return false;
      const value =
        facet === TRIAGE_FACET
          ? triageValue(decision)
          : (entry.facets[facet] ?? "");
      if (!selected.includes(value)) return false;
    }
    const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
    return terms.every((term) => entry.text.includes(term));
  }

  /**
   * @param {EntryData[]} entries
   * @param {string} facet
   * @returns {[string, number][]} in severity order for `severity`, otherwise in report order
   */
  function countBy(entries, facet) {
    /** @type {Map<string, number>} */
    const counts = new Map();
    for (const entry of entries) {
      const value = entry.facets[facet];
      if (value) counts.set(value, (counts.get(value) ?? 0) + 1);
    }
    const pairs = [...counts.entries()];
    if (facet === "severity")
      pairs.sort((a, b) => severityRank(a[0]) - severityRank(b[0]));
    return pairs;
  }

  /**
   * The next shown entry in one direction, or `current` when there is none.
   * Positions follow the order entries have on the page.
   * @param {boolean[]} shown
   * @param {number} current -1 when the reader is on no entry yet
   * @param {1 | -1} direction
   * @returns {number}
   */
  function stepIndex(shown, current, direction) {
    for (
      let index = current + direction;
      index >= 0 && index < shown.length;
      index += direction
    ) {
      if (shown[index]) return index;
    }
    return current;
  }

  /**
   * Where the reader lands when a filter hides the entry they are on: that
   * entry when it is still shown, else the next shown one, else the previous
   * shown one, else -1.
   * @param {boolean[]} shown
   * @param {number} current
   * @returns {number}
   */
  function nearestShownIndex(shown, current) {
    if (current < 0 || current >= shown.length) return -1;
    if (shown[current]) return current;
    const after = stepIndex(shown, current, 1);
    if (after !== current) return after;
    const before = stepIndex(shown, current, -1);
    return before !== current ? before : -1;
  }

  /**
   * The next shown entry that still needs a decision, wrapping past the end, or -1.
   * @param {boolean[]} waiting whether each position is shown, triageable, and undecided
   * @param {number} current
   * @returns {number}
   */
  function nextWaitingIndex(waiting, current) {
    for (let offset = 1; offset <= waiting.length; offset += 1) {
      const index = (current + offset + waiting.length) % waiting.length;
      if (waiting[index]) return index;
    }
    return -1;
  }

  /**
   * @param {string} pathname
   * @param {string} generated
   * @returns {string}
   */
  function storageKey(pathname, generated) {
    return `trackbed-report:v1:${pathname}:${generated}`;
  }

  /**
   * @param {unknown} raw
   * @returns {Record<string, Decision>}
   */
  function sanitizeTriage(raw) {
    /** @type {Record<string, Decision>} */
    const clean = {};
    if (!raw || typeof raw !== "object") return clean;
    for (const [id, value] of Object.entries(raw)) {
      if (!value || typeof value !== "object") continue;
      const decision = /** @type {Record<string, unknown>} */ (value).decision;
      const note = /** @type {Record<string, unknown>} */ (value).note;
      if (decision !== "accept" && decision !== "dismiss") continue;
      clean[id] = { decision, note: typeof note === "string" ? note : "" };
    }
    return clean;
  }

  /**
   * @param {string} text
   * @returns {string}
   */
  function oneLine(text) {
    const flat = text.replace(/\s+/g, " ").trim();
    return flat.length > 160 ? `${flat.slice(0, 157)}...` : flat;
  }

  /**
   * The text the reader pastes back to the agent. It names entries; the Markdown
   * report stays the record for what each entry says.
   * @param {ReportMeta} meta
   * @param {EntryData[]} entries
   * @param {Record<string, Decision>} triage
   * @param {string} followup
   * @returns {string}
   */
  function buildPrompt(meta, entries, triage, followup) {
    const triageable = entries.filter((entry) => entry.triageable);
    const accepted = triageable.filter(
      (entry) => triage[entry.id]?.decision === "accept",
    );
    const dismissed = triageable.filter(
      (entry) => triage[entry.id]?.decision === "dismiss",
    );
    const undecided = triageable.length - accepted.length - dismissed.length;
    const commit = meta.commit ? `, commit ${meta.commit.slice(0, 12)}` : "";
    const lines = [];
    if (followup) lines.push(followup, "");
    lines.push(
      `Triage of ${meta.source} (${meta.producer}, generated ${meta.generated}${commit}).`,
      `${meta.source} is the record for what each ${noun(meta, 1)} says; this message only says which ${noun(meta, 2)} to act on.`,
      "",
    );
    if (accepted.length === 0) {
      lines.push(`No ${noun(meta, 2)} were accepted.`);
    } else {
      lines.push(
        `Act only on the ${accepted.length} accepted ${noun(meta, accepted.length)}:`,
      );
      for (const entry of accepted) {
        const severity = entry.facets.severity
          ? ` [${entry.facets.severity}]`
          : "";
        const location = entry.location ? ` (${entry.location})` : "";
        lines.push(
          `- ${entry.id}${severity} ${oneLine(entry.title)}${location}`,
        );
        const note = oneLine(triage[entry.id].note);
        if (note) lines.push(`  Note: ${note}`);
      }
    }
    if (dismissed.length > 0) {
      lines.push(
        "",
        `Leave the ${dismissed.length} dismissed ${noun(meta, dismissed.length)} alone:`,
      );
      for (const entry of dismissed) {
        lines.push(`- ${entry.id} ${oneLine(entry.title)}`);
        const note = oneLine(triage[entry.id].note);
        if (note) lines.push(`  Reason: ${note}`);
      }
    }
    if (undecided > 0) {
      lines.push(
        "",
        `${undecided} other ${noun(meta, undecided)} had no decision and should stay unchanged.`,
      );
    }
    return `${lines.join("\n")}\n`;
  }

  /**
   * What the page calls its entries: "finding", "plans", "questions".
   * @param {Pick<ReportMeta, "nounOne" | "nounMany">} meta
   * @param {number} count
   * @returns {string}
   */
  function noun(meta, count) {
    return count === 1 ? meta.nounOne || "entry" : meta.nounMany || "entries";
  }

  const api = {
    SEVERITIES,
    noun,
    EDITORS,
    label,
    titleCase,
    parseLocation,
    isEditorTemplate,
    editorUrl,
    compareText,
    compareEntries,
    triageValue,
    matches,
    countBy,
    stepIndex,
    nearestShownIndex,
    nextWaitingIndex,
    storageKey,
    sanitizeTriage,
    buildPrompt,
  };

  if (typeof module === "object" && module && module.exports)
    module.exports = api;
  if (typeof document === "undefined") return;

  // ---------- Page wiring ----------

  /**
   * @template {keyof HTMLElementTagNameMap} K
   * @param {K} tag
   * @param {Record<string, string>} [attrs] `class` and `text` set the class name and text content
   * @param {(Node | string)[]} [children]
   * @returns {HTMLElementTagNameMap[K]}
   */
  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    for (const [name, value] of Object.entries(attrs ?? {})) {
      if (name === "class") node.className = value;
      else if (name === "text") node.textContent = value;
      else node.setAttribute(name, value);
    }
    for (const child of children ?? []) node.append(child);
    return node;
  }

  /**
   * @param {string} key
   * @returns {unknown}
   */
  function readStore(key) {
    try {
      const raw = window.localStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  /**
   * @param {string} key
   * @param {unknown} value
   */
  function writeStore(key, value) {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Private browsing or a full quota: the page still works for this visit.
    }
  }

  /**
   * @param {string} text
   * @returns {Promise<boolean>}
   */
  async function copyText(text) {
    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch {
      // Fall through to the selection-based copy.
    }
    const area = el("textarea", { class: "tr-sr", "aria-hidden": "true" });
    area.value = text;
    document.body.append(area);
    area.select();
    let copied = false;
    try {
      copied = document.execCommand("copy");
    } catch {
      copied = false;
    }
    area.remove();
    return copied;
  }

  /**
   * @param {HTMLElement} button
   * @param {string} text
   */
  function wireCopy(button, text) {
    const idle = button.textContent ?? "copy";
    button.addEventListener("click", async () => {
      const copied = await copyText(text);
      button.textContent = copied ? "copied" : "copy failed";
      window.setTimeout(() => {
        button.textContent = idle;
      }, 1400);
    });
  }

  function boot() {
    const main = document.querySelector("main[data-report]");
    if (!(main instanceof HTMLElement) || main.dataset.trackbedReady) return;
    main.dataset.trackbedReady = "true";

    /** @type {ReportMeta} */
    const meta = {
      producer: main.dataset.producer ?? "",
      source: main.dataset.source ?? "",
      generated: main.dataset.generated ?? "",
      commit: main.dataset.commit ?? "",
      root: main.dataset.root ?? "",
      facets: (main.dataset.facets ?? "").split(/\s+/).filter(Boolean),
      followups: [
        ...document.querySelectorAll('meta[name="trackbed-followup"]'),
      ]
        .map((node) => node.getAttribute("content") ?? "")
        .filter(Boolean),
      acceptLabel: main.dataset.acceptLabel || "Accept",
      dismissLabel: main.dataset.dismissLabel || "Dismiss",
      nounOne: (main.dataset.noun ?? "").trim().split(/\s+/)[0] || "entry",
      nounMany: (main.dataset.noun ?? "").trim().split(/\s+/)[1] || "entries",
    };
    // What an entry is called once decided: the default verbs read better in the past tense.
    const acceptedLabel =
      meta.acceptLabel === "Accept" ? "Accepted" : meta.acceptLabel;
    const dismissedLabel =
      meta.dismissLabel === "Dismiss" ? "Dismissed" : meta.dismissLabel;

    const triageKey = storageKey(window.location.pathname, meta.generated);
    const triage = sanitizeTriage(readStore(triageKey));
    const stored = /** @type {Partial<Settings> | null} */ (
      readStore(SETTINGS_KEY)
    );
    /** @type {Settings} */
    const settings = {
      theme:
        stored?.theme === "light" || stored?.theme === "dark"
          ? stored.theme
          : "auto",
      editor: typeof stored?.editor === "string" ? stored.editor : "none",
      custom: typeof stored?.custom === "string" ? stored.custom : "",
      keys: stored?.keys !== false,
    };
    /** @type {{ filters: Record<string, string[]>, query: string, sort: string }} */
    const view = { filters: {}, query: "", sort: "order" };
    /** Index into `items` of the entry the reader is on, or -1. */
    let current = -1;

    // The page states where it came from even when its author forgot to.
    const header = main.querySelector("[data-report-header]");
    if (header) {
      const provenance = el("p", { class: "tr-provenance" });
      /**
       * @param {string} name
       * @param {Node | string} value
       */
      const fact = (name, value) => {
        provenance.append(
          el("span", {}, [el("b", { text: name }), " ", value]),
        );
      };
      const isRelative =
        !/^[a-z][a-z0-9+.-]*:/i.test(meta.source) &&
        !meta.source.startsWith("/");
      fact("Producer", meta.producer);
      fact(
        "Source",
        isRelative
          ? el("a", { href: encodeURI(meta.source), text: meta.source })
          : meta.source,
      );
      fact("Generated", meta.generated.replace("T", " "));
      if (meta.commit) fact("Commit", meta.commit.slice(0, 12));
      header.append(
        provenance,
        el("p", {
          class: "tr-snapshot",
          text: `Snapshot of ${meta.source}, which stays the record. Later changes to that file do not appear here, and triage decisions are saved only in this browser.`,
        }),
      );
    }

    function applyTheme() {
      if (settings.theme === "auto")
        document.documentElement.removeAttribute("data-theme");
      else document.documentElement.setAttribute("data-theme", settings.theme);
    }
    applyTheme();

    // Read every entry before the page is decorated, so search text and copy
    // text never include the controls added below.
    const entryNodes = /** @type {HTMLElement[]} */ ([
      ...main.querySelectorAll("[data-entry]"),
    ]);
    /** @type {EntryData[]} */
    const entries = entryNodes.map((node, order) => {
      /** @type {Record<string, string>} */
      const facets = {};
      for (const facet of meta.facets) {
        const value = node.getAttribute(`data-${facet}`);
        if (value) facets[facet] = value;
      }
      const id = node.dataset.id ?? `entry-${order + 1}`;
      const title = node.querySelector("h3")?.textContent?.trim() || id;
      const location =
        node.querySelector("[data-loc]")?.textContent?.trim() ?? "";
      // The severity label is shown on the badge the runtime adds later, so it is not in textContent yet.
      const text =
        `${id} ${Object.values(facets).join(" ")} ${node.dataset.severityLabel ?? ""} ${node.textContent ?? ""}`.toLowerCase();
      const triageable = !node.closest('[data-triage="off"]');
      return { id, title, facets, location, text, order, triageable };
    });
    const triageable = entries.filter((entry) => entry.triageable);
    // Filters and the summary use the report's own word for a severity level.
    /** @type {Record<string, string>} */
    const severityLabels = {};
    for (const node of entryNodes) {
      const value = node.dataset.severity;
      if (value && !severityLabels[value])
        severityLabels[value] = node.dataset.severityLabel || value;
    }
    // The triage words follow the page's own labels: "2 to run", not "2 accepted", on a plan page.
    const triageWords = {
      accepted:
        meta.acceptLabel === "Accept"
          ? "accepted"
          : `to ${meta.acceptLabel.toLowerCase()}`,
      dismissed:
        meta.dismissLabel === "Dismiss"
          ? "dismissed"
          : `to ${meta.dismissLabel.toLowerCase()}`,
      undecided: "undecided",
    };
    /**
     * @param {string} facet
     * @param {string} value
     * @returns {string}
     */
    const shown = (facet, value) => {
      if (facet === "severity") return severityLabels[value] ?? value;
      if (facet === TRIAGE_FACET)
        return (
          triageWords[/** @type {keyof typeof triageWords} */ (value)] ?? value
        );
      return value;
    };

    function saveTriage() {
      writeStore(triageKey, triage);
    }

    // ---------- Copy blocks and locations ----------

    for (const block of /** @type {HTMLElement[]} */ ([
      ...main.querySelectorAll("[data-copy], pre"),
    ])) {
      if (
        block.matches("pre") &&
        block.closest("[data-copy]") &&
        !block.hasAttribute("data-copy")
      )
        continue;
      const name = block.getAttribute("data-copy") || "block";
      const button = el("button", {
        type: "button",
        class: "tr-mini",
        "aria-label": `Copy ${name}`,
        text: "copy",
      });
      wireCopy(button, (block.textContent ?? "").trim());
      if (block.tagName === "CODE") {
        block.after(button);
      } else {
        block.classList.add("tr-copy-block");
        block.append(button);
      }
    }

    /** @type {{ location: ReportLocation | null, link: HTMLAnchorElement }[]} */
    const openLinks = [];
    for (const node of /** @type {HTMLElement[]} */ ([
      ...main.querySelectorAll("[data-loc]"),
    ])) {
      const text = (node.textContent ?? "").trim();
      node.classList.add("tr-loc");
      const copy = el("button", {
        type: "button",
        class: "tr-mini",
        "aria-label": `Copy ${text}`,
        text: "copy",
      });
      wireCopy(copy, text);
      const link = el("a", {
        class: "tr-mini",
        "aria-label": `Open ${text} in the editor`,
        text: "open",
      });
      link.hidden = true;
      if (node.closest("[data-where]")) {
        // An entry's own location line keeps its buttons in view.
        node.after(copy, link);
      } else {
        // In running text a button after every path would bury the sentence, so
        // the buttons wait above the path until it is pointed at or focused.
        node.classList.add("tr-loc-quiet");
        node.tabIndex = 0;
        node.append(el("span", { class: "tr-loc-actions" }, [copy, link]));
      }
      openLinks.push({ location: parseLocation(text), link });
    }

    function applyEditor() {
      const template =
        settings.editor === "custom"
          ? settings.custom
          : (EDITORS[settings.editor]?.template ?? "");
      for (const { location, link } of openLinks) {
        const url = editorUrl(template, meta.root, location);
        link.hidden = !url;
        if (url) link.href = url;
        else link.removeAttribute("href");
      }
    }

    // ---------- Sections: a title that folds, and the content under it ----------

    /**
     * @typedef {{
     *   node: HTMLElement,
     *   title: string,
     *   body: HTMLElement | null,
     *   fold: HTMLButtonElement | null,
     *   count: HTMLElement,
     *   empty: HTMLElement,
     *   navLink: HTMLAnchorElement,
     *   navCount: HTMLElement,
     *   navList: HTMLOListElement,
     * }} SectionItem
     */
    /** @type {SectionItem[]} */
    const sections = [];
    const sectionNodes = /** @type {HTMLElement[]} */ ([
      ...main.querySelectorAll("[data-section]"),
    ]);

    /**
     * @param {SectionItem} section
     * @param {boolean} folded
     */
    const setFolded = (section, folded) => {
      if (!section.body || !section.fold) return;
      section.body.hidden = folded;
      section.fold.setAttribute("aria-expanded", String(!folded));
      section.node.classList.toggle("tr-folded", folded);
    };

    sectionNodes.forEach((node, index) => {
      if (!node.id) node.id = `section-${index + 1}`;
      const heading = node.querySelector("h2");
      const title = (heading?.textContent ?? node.id).trim();
      const count = el("span", { class: "tr-section-count" });
      const empty = el("p", {
        class: "tr-section-empty",
        text: `No ${meta.nounMany} match the current filters.`,
      });
      empty.hidden = true;
      /** @type {HTMLElement | null} */
      let body = null;
      /** @type {HTMLButtonElement | null} */
      let fold = null;
      if (heading && heading.parentElement === node) {
        body = el("div", { class: "tr-section-body", id: `${node.id}-body` });
        for (const child of [...node.childNodes]) {
          if (child !== heading) body.append(child);
        }
        body.prepend(empty);
        node.append(body);
        fold = el("button", {
          type: "button",
          class: "tr-fold",
          "aria-controls": body.id,
        });
        while (heading.firstChild) fold.append(heading.firstChild);
        heading.append(fold, count);
      } else if (heading) {
        heading.append(count);
        heading.after(empty);
      }
      const navCount = el("span");
      const navLink = el(
        "a",
        { class: "tr-nav-section", href: `#${node.id}` },
        [el("span", { text: title }), navCount],
      );
      const navList = el("ol", { class: "tr-nav-entries" });
      /** @type {SectionItem} */
      const section = {
        node,
        title,
        body,
        fold,
        count,
        empty,
        navLink,
        navCount,
        navList,
      };
      fold?.addEventListener("click", () =>
        setFolded(section, !section.body?.hidden),
      );
      navLink.addEventListener("click", () => setFolded(section, false));
      setFolded(section, node.hasAttribute("data-collapsed"));
      sections.push(section);
    });

    // ---------- Entries ----------

    /**
     * @typedef {{
     *   node: HTMLElement,
     *   data: EntryData,
     *   body: HTMLElement,
     *   setOpen: (open: boolean) => void,
     *   navLink: HTMLAnchorElement,
     *   section: SectionItem | null,
     *   decide: ((decision: "accept" | "dismiss") => void) | null,
     *   refresh: () => void,
     * }} EntryItem
     */
    /** @type {EntryItem[]} */
    const items = [];

    entryNodes.forEach((node, index) => {
      const data = entries[index];
      if (!node.id)
        node.id = `entry-${data.id.replace(/[^A-Za-z0-9_-]+/g, "-")}`;
      node.tabIndex = -1;
      const heading =
        node.querySelector("h3") ?? el("h3", { text: data.title });
      const where = node.querySelector("[data-where]");
      const body = el("div", { class: "tr-entry-body", id: `${node.id}-body` });
      while (node.firstChild) body.append(node.firstChild);

      // Above the title: what kind of entry this is. Under it: where it is.
      const eyebrow = el("p", { class: "tr-eyebrow" }, [
        el("span", { class: "tr-id", text: data.id }),
      ]);
      if (data.facets.severity) {
        eyebrow.append(
          el("span", {
            class: "tr-sev",
            text: titleCase(shown("severity", data.facets.severity)),
          }),
        );
      }
      for (const facet of meta.facets) {
        if (facet === "severity" || !data.facets[facet]) continue;
        eyebrow.append(
          el("span", {
            class: "tr-tag",
            title: titleCase(facet),
            text: label(data.facets[facet]),
          }),
        );
      }
      const decided = el("span", { class: "tr-decision" });
      decided.hidden = true;
      eyebrow.append(decided);
      const title = el("div", { class: "tr-entry-title" }, [eyebrow, heading]);
      if (where instanceof HTMLElement) {
        where.classList.add("tr-where");
        title.append(where);
      }
      const toggle = el("button", {
        type: "button",
        class: "tr-toggle",
        "aria-controls": body.id,
      });
      const head = el("div", { class: "tr-entry-head" }, [toggle, title]);
      node.append(head, body);

      /** @param {boolean} open */
      const setOpen = (open) => {
        body.hidden = !open;
        toggle.setAttribute("aria-expanded", String(open));
        toggle.setAttribute(
          "aria-label",
          `${open ? "Collapse" : "Expand"} ${data.id}`,
        );
      };
      setOpen(!node.hasAttribute("data-collapsed"));
      toggle.addEventListener("click", () => setOpen(Boolean(body.hidden)));
      head.addEventListener("click", (event) => {
        const target = event.target;
        if (
          target instanceof Element &&
          target.closest("a, button, input, select, textarea, code")
        )
          return;
        if (window.getSelection()?.toString()) return;
        setOpen(Boolean(body.hidden));
      });
      node.addEventListener("click", () => {
        pinned = index;
        setCurrent(index);
      });

      const mark = el("span", { class: "tr-nav-mark" });
      const navLink = el(
        "a",
        { class: "tr-nav-entry", href: `#${node.id}`, title: data.title },
        [
          el("span", { class: "tr-nav-dot" }),
          el("span", { class: "tr-nav-text", text: data.title }),
          mark,
        ],
      );
      if (data.facets.severity)
        navLink.setAttribute("data-severity", data.facets.severity);
      navLink.addEventListener("click", (event) => {
        event.preventDefault();
        go(index);
      });
      const section =
        sections.find((candidate) => candidate.node.contains(node)) ?? null;
      section?.navList.append(el("li", {}, [navLink]));

      /** @type {EntryItem} */
      const item = {
        node,
        data,
        body,
        setOpen,
        navLink,
        section,
        decide: null,
        refresh: () => {},
      };
      items.push(item);
      if (!data.triageable) return;

      const accept = el("button", {
        type: "button",
        class: "tr-btn",
        text: meta.acceptLabel,
      });
      const dismiss = el("button", {
        type: "button",
        class: "tr-btn",
        "data-tone": "dismiss",
        text: meta.dismissLabel,
      });
      const note = el("input", {
        type: "text",
        "aria-label": `Note for ${data.id}`,
        placeholder: "Note for the agent (optional)",
      });
      item.refresh = () => {
        const decision = triage[data.id];
        const state = triageValue(decision);
        accept.setAttribute("aria-pressed", String(state === "accepted"));
        dismiss.setAttribute("aria-pressed", String(state === "dismissed"));
        node.classList.toggle("tr-accepted", state === "accepted");
        node.classList.toggle("tr-dismissed", state === "dismissed");
        decided.hidden = !decision;
        decided.textContent =
          state === "accepted" ? acceptedLabel : dismissedLabel;
        navLink.setAttribute("data-triage", state);
        mark.textContent = state === "accepted" ? "\u2713" : "";
        note.hidden = !decision;
        note.value = decision?.note ?? "";
      };
      item.decide = (decision) => {
        if (triage[data.id]?.decision === decision) delete triage[data.id];
        else triage[data.id] = { decision, note: triage[data.id]?.note ?? "" };
        // A dismissed entry closes, so what is left to read stands out.
        if (triage[data.id]?.decision === "dismiss") setOpen(false);
        saveTriage();
        item.refresh();
        update();
      };
      accept.addEventListener("click", () => item.decide?.("accept"));
      dismiss.addEventListener("click", () => item.decide?.("dismiss"));
      note.addEventListener("input", () => {
        if (!triage[data.id]) return;
        triage[data.id].note = note.value;
        saveTriage();
      });
      node.append(el("div", { class: "tr-triage" }, [accept, dismiss, note]));
      item.refresh();
    });

    // ---------- Tables ----------

    for (const table of /** @type {HTMLTableElement[]} */ ([
      ...main.querySelectorAll("table"),
    ])) {
      const wrap = el("div", { class: "tr-table-wrap" });
      table.replaceWith(wrap);
      wrap.append(table);
      if (
        !table.hasAttribute("data-sortable") ||
        !table.tHead ||
        !table.tBodies[0]
      )
        continue;
      const headers = [...table.tHead.querySelectorAll("th")];
      headers.forEach((columnHeader, column) => {
        columnHeader.classList.add("tr-sortable");
        columnHeader.tabIndex = 0;
        const sort = () => {
          const ascending =
            columnHeader.getAttribute("aria-sort") !== "ascending";
          for (const other of headers) other.removeAttribute("aria-sort");
          columnHeader.setAttribute(
            "aria-sort",
            ascending ? "ascending" : "descending",
          );
          const tbody = table.tBodies[0];
          const rows = [...tbody.rows];
          rows.sort((a, b) => {
            const result = compareText(
              a.cells[column]?.textContent ?? "",
              b.cells[column]?.textContent ?? "",
            );
            return ascending ? result : -result;
          });
          tbody.append(...rows);
        };
        columnHeader.addEventListener("click", sort);
        columnHeader.addEventListener("keydown", (event) => {
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          sort();
        });
      });
    }

    // ---------- Summary and filters ----------
    // What the reader needs first stays in view: how many entries, how severe,
    // and a search box. Every other filter and option is one click away.

    const deck = el("section", {
      class: "tr-deck",
      "aria-label": "Summary and filters",
    });
    const reference = entries.length - triageable.length;
    const total =
      triageable.length > 0 && reference > 0
        ? `${triageable.length} ${noun(meta, triageable.length)} to decide, ${reference} for reference`
        : `${entries.length} ${noun(meta, entries.length)}`;
    const deckTop = el("div", { class: "tr-deck-top" }, [
      el("span", { class: "tr-total", text: total }),
    ]);
    const more = el("div", { class: "tr-deck-more", id: "tr-deck-more" });
    more.hidden = true;

    const severityCounts = countBy(entries, "severity");
    if (meta.facets.includes("severity") && severityCounts.length > 0) {
      const summary = severityCounts
        .map(([value, count]) => `${count} ${label(shown("severity", value))}`)
        .join(", ");
      const bar = el("div", {
        class: "tr-bar",
        role: "img",
        "aria-label": `Severity: ${summary}`,
      });
      for (const [value, count] of severityCounts) {
        const segment = el("span", {
          "data-severity": value,
          title: `${count} ${label(shown("severity", value))}`,
        });
        segment.style.flexGrow = String(count);
        bar.append(segment);
      }
      deck.append(bar);
    }
    deck.append(deckTop);

    /** @type {{ facet: string, value: string, chip: HTMLButtonElement, count: HTMLElement }[]} */
    const chips = [];
    /**
     * @param {string} facet
     * @param {[string, number][]} values
     * @returns {HTMLElement | null}
     */
    const facetRow = (facet, values) => {
      if (values.length === 0) return null;
      const row = el(
        "div",
        {
          class: "tr-facet",
          role: "group",
          "aria-label": `Filter by ${label(facet)}`,
        },
        [el("span", { class: "tr-facet-name", text: titleCase(facet) })],
      );
      for (const [value, count] of values) {
        const counter = el("b", { text: String(count) });
        const chip = el(
          "button",
          { type: "button", class: "tr-chip", "aria-pressed": "false" },
          [titleCase(shown(facet, value)), counter],
        );
        if (facet === "severity") chip.setAttribute("data-severity", value);
        chip.addEventListener("click", () => {
          const selected = view.filters[facet] ?? [];
          view.filters[facet] = selected.includes(value)
            ? selected.filter((selectedValue) => selectedValue !== value)
            : [...selected, value];
          update();
        });
        chips.push({ facet, value, chip, count: counter });
        row.append(chip);
      }
      return row;
    };
    for (const facet of meta.facets) {
      const row = facetRow(facet, countBy(entries, facet));
      if (!row) continue;
      // The facet the page lists first is the one its reader reaches for most:
      // severity for findings, wave for plans. It sits beside the total.
      if (facet === meta.facets[0]) {
        row.classList.add("tr-facet-lead");
        deckTop.append(row);
      } else {
        more.append(row);
      }
    }
    if (triageable.length > 0) {
      const row = facetRow(
        TRIAGE_FACET,
        TRIAGE_VALUES.map((value) => [value, 0]),
      );
      if (row) more.append(row);
    }

    const search = el("input", {
      type: "search",
      placeholder: `Search ${meta.nounMany} (press /)`,
      "aria-label": `Search ${meta.nounMany}`,
    });
    search.addEventListener("input", () => {
      view.query = search.value;
      update();
    });

    const sortSelect = el("select", { "aria-label": "Sort entries" }, [
      el("option", { value: "order", text: "Report order" }),
      ...meta.facets.map((facet) =>
        el("option", { value: facet, text: titleCase(facet) }),
      ),
      el("option", { value: "location", text: "Location" }),
    ]);
    sortSelect.addEventListener("change", () => {
      view.sort = sortSelect.value;
      sortEntries();
    });

    const expandAll = el("button", {
      type: "button",
      class: "tr-btn",
      text: "Expand all",
    });
    expandAll.addEventListener("click", () => {
      for (const section of sections) setFolded(section, false);
      for (const item of items) item.setOpen(true);
    });
    const collapseAll = el("button", {
      type: "button",
      class: "tr-btn",
      text: "Collapse all",
    });
    collapseAll.addEventListener("click", () => {
      for (const item of items) item.setOpen(false);
    });

    const themeButton = el("button", { type: "button", class: "tr-btn" });
    const showTheme = () => {
      themeButton.textContent = `Theme: ${settings.theme}`;
    };
    themeButton.addEventListener("click", () => {
      settings.theme =
        settings.theme === "auto"
          ? "light"
          : settings.theme === "light"
            ? "dark"
            : "auto";
      writeStore(SETTINGS_KEY, settings);
      applyTheme();
      showTheme();
    });
    showTheme();

    const toolbar = el("div", { class: "tr-toolbar" });
    if (entries.length > 0) {
      toolbar.append(
        el("label", {}, ["Sort", sortSelect]),
        expandAll,
        collapseAll,
      );
    }
    toolbar.append(themeButton);

    if (meta.root && openLinks.length > 0) {
      const editorSelect = el(
        "select",
        { "aria-label": "Editor for open links" },
        [
          el("option", { value: "none", text: "No editor" }),
          ...Object.entries(EDITORS).map(([value, editor]) =>
            el("option", { value, text: editor.label }),
          ),
          el("option", { value: "custom", text: "Custom URL" }),
        ],
      );
      const custom = el("input", {
        type: "text",
        "aria-label": "Editor URL with {path} and {line}",
        placeholder: "myeditor://open?file={path}&line={line}",
      });
      editorSelect.value = editorSelect.querySelector(
        `option[value="${CSS.escape(settings.editor)}"]`,
      )
        ? settings.editor
        : "none";
      settings.editor = editorSelect.value;
      custom.value = settings.custom;
      custom.hidden = settings.editor !== "custom";
      editorSelect.addEventListener("change", () => {
        settings.editor = editorSelect.value;
        custom.hidden = settings.editor !== "custom";
        writeStore(SETTINGS_KEY, settings);
        applyEditor();
      });
      custom.addEventListener("input", () => {
        settings.custom = custom.value;
        writeStore(SETTINGS_KEY, settings);
        applyEditor();
      });
      toolbar.append(el("label", {}, ["Open in", editorSelect]), custom);
    }
    applyEditor();
    more.append(toolbar);

    const moreButton = el("button", {
      type: "button",
      class: "tr-btn",
      "aria-controls": "tr-deck-more",
      "aria-expanded": "false",
    });
    moreButton.addEventListener("click", () => {
      more.hidden = !more.hidden;
      moreButton.setAttribute("aria-expanded", String(!more.hidden));
    });
    const deckFind = el("div", { class: "tr-deck-find" });
    if (entries.length > 0) deckFind.append(search);
    deckFind.append(moreButton);
    deck.append(deckFind, more);

    const resultText = el("span");
    const clearFilters = el("button", {
      type: "button",
      class: "tr-btn",
      text: "Clear filters",
    });
    function resetFilters() {
      view.filters = {};
      view.query = "";
      search.value = "";
      update();
    }
    clearFilters.addEventListener("click", resetFilters);
    const result = el("p", { class: "tr-result", role: "status" }, [
      resultText,
      clearFilters,
    ]);

    const slot = main.querySelector("[data-controls]");
    if (slot) slot.append(deck, result);
    else if (sectionNodes[0]) sectionNodes[0].before(deck, result);
    else main.append(deck, result);

    // ---------- Outline: every section and the entries in it ----------

    const nav = el("nav", { class: "tr-nav", "aria-label": "Report outline" }, [
      el("p", { class: "tr-nav-title", text: "In this report" }),
    ]);
    // Folded sections are reference material: they come last in the outline, under their own label.
    /** @param {SectionItem} section */
    const isReference = (section) => section.node.matches("[data-collapsed]");
    const decisionSections = sections.filter(
      (section) => !isReference(section),
    );
    const referenceSections = sections.filter(isReference);
    for (const section of decisionSections) {
      nav.append(section.navLink);
      if (section.navList.childElementCount > 0) nav.append(section.navList);
    }
    if (decisionSections.length > 0 && referenceSections.length > 0) {
      nav.append(el("p", { class: "tr-nav-divider", text: "Reference" }));
    }
    for (const section of referenceSections) {
      if (decisionSections.length > 0)
        section.navLink.classList.add("tr-nav-reference");
      nav.append(section.navLink);
      if (section.navList.childElementCount > 0) nav.append(section.navList);
    }
    const wideNav = window.matchMedia("(min-width: 1180px)");
    if (sections.length > 1 || entries.length > 1) {
      document.body.prepend(nav);
      document.body.classList.add("tr-has-nav");
    }

    // ---------- Bottom bar: move between entries, hand the triage back ----------

    const previous = el("button", {
      type: "button",
      class: "tr-btn",
      "aria-label": `Previous ${meta.nounOne}`,
      text: "\u2191 Previous",
    });
    const next = el("button", {
      type: "button",
      class: "tr-btn",
      "aria-label": `Next ${meta.nounOne}`,
      text: "\u2193 Next",
    });
    const nextWaiting = el("button", {
      type: "button",
      class: "tr-btn",
      text: "Next undecided",
    });
    const position = el("span", { class: "tr-position", role: "status" });
    previous.addEventListener("click", () => step(-1));
    next.addEventListener("click", () => step(1));
    nextWaiting.addEventListener("click", () => goWaiting());

    const triageCounts = el("span", { class: "tr-triage-counts" });
    const status = el("span", { class: "tr-status", role: "status" });
    const manualArea = el("textarea", {
      readonly: "",
      "aria-label": "Triage prompt",
    });
    const manual = el("div", { class: "tr-manual" }, [manualArea]);
    manual.hidden = true;
    const followupSelect = el(
      "select",
      { "aria-label": "Follow-up command" },
      meta.followups.map((command) =>
        el("option", { value: command, text: command }),
      ),
    );
    const copyPrompt = el("button", {
      type: "button",
      class: "tr-btn tr-primary",
      text: "Copy prompt",
    });
    copyPrompt.addEventListener("click", async () => {
      const prompt = buildPrompt(meta, entries, triage, followupSelect.value);
      const copied = await copyText(prompt);
      status.textContent = copied
        ? "Copied."
        : "Copy failed: select the text below.";
      manual.hidden = copied;
      if (!copied) {
        manualArea.value = prompt;
        manualArea.select();
      }
    });
    const clearTriage = el("button", {
      type: "button",
      class: "tr-btn",
      text: "Clear triage",
    });
    clearTriage.addEventListener("click", () => {
      for (const id of Object.keys(triage)) delete triage[id];
      saveTriage();
      for (const item of items) item.refresh();
      status.textContent = "";
      manual.hidden = true;
      update();
    });

    /**
     * @param {string} key
     * @param {string} meaning
     * @returns {HTMLElement}
     */
    const shortcut = (key, meaning) =>
      el("div", {}, [
        el("dt", {}, [el("kbd", { text: key })]),
        el("dd", { text: meaning }),
      ]);
    const keysToggle = el("input", { type: "checkbox", id: "tr-keys-toggle" });
    keysToggle.checked = settings.keys;
    keysToggle.addEventListener("change", () => {
      settings.keys = keysToggle.checked;
      writeStore(SETTINGS_KEY, settings);
    });
    const helpKeys = el("dl", { class: "tr-keys" }, [
      shortcut("j", `Next ${meta.nounOne}`),
      shortcut("k", `Previous ${meta.nounOne}`),
      shortcut("o", `Open or close the ${meta.nounOne}`),
      shortcut("/", "Search"),
      shortcut("?", "Show or hide this help"),
    ]);
    if (triageable.length > 0) {
      helpKeys.append(
        shortcut("u", `Next undecided ${meta.nounOne}`),
        shortcut("a", `${meta.acceptLabel} the ${meta.nounOne}`),
        shortcut("d", `${meta.dismissLabel} the ${meta.nounOne}`),
      );
    }
    const help = el("div", { class: "tr-help", id: "tr-help" }, [
      helpKeys,
      el("label", { for: "tr-keys-toggle" }, [
        keysToggle,
        " Use these single-key shortcuts",
      ]),
    ]);
    help.hidden = true;
    const helpButton = el("button", {
      type: "button",
      class: "tr-btn",
      "aria-controls": "tr-help",
      "aria-expanded": "false",
      text: "Shortcuts",
    });
    const toggleHelp = () => {
      help.hidden = !help.hidden;
      helpButton.setAttribute("aria-expanded", String(!help.hidden));
    };
    helpButton.addEventListener("click", toggleHelp);

    if (entries.length > 0) {
      const moves = el("div", { class: "tr-bar-group" }, [
        previous,
        next,
        position,
      ]);
      const bar = el(
        "div",
        {
          class: "tr-triage-bar",
          role: "region",
          "aria-label": "Move between entries and triage",
        },
        [moves],
      );
      if (triageable.length > 0) {
        moves.append(nextWaiting);
        const hand = el("div", { class: "tr-bar-group" }, [triageCounts]);
        if (meta.followups.length > 1)
          hand.append(el("label", {}, ["Prompt for ", followupSelect]));
        else if (meta.followups.length === 1)
          hand.append(el("code", { text: meta.followups[0] }));
        hand.append(copyPrompt, clearTriage, status);
        bar.append(hand);
      }
      bar.append(
        el("div", { class: "tr-bar-group tr-bar-end" }, [helpButton]),
        manual,
        help,
      );
      document.body.append(bar);
    }

    // ---------- Moving between entries ----------

    /** @returns {number[]} indexes into `items`, in the order entries have on the page */
    const pageOrder = () => {
      /** @type {Map<Element, number>} */
      const byNode = new Map(items.map((item, index) => [item.node, index]));
      return [...main.querySelectorAll("[data-entry]")]
        .map((node) => byNode.get(node) ?? -1)
        .filter((index) => index >= 0);
    };

    function showPosition() {
      const order = pageOrder().filter((index) => !items[index].node.hidden);
      const place = order.indexOf(current);
      position.textContent =
        place === -1
          ? `${order.length} ${noun(meta, order.length)}`
          : `${place + 1} of ${order.length}`;
      previous.disabled = order.length === 0;
      next.disabled = order.length === 0;
    }

    /** @param {number} index */
    function setCurrent(index) {
      if (index === current) return;
      if (items[current]) {
        items[current].node.classList.remove("tr-current");
        items[current].navLink.removeAttribute("aria-current");
      }
      current = index;
      const item = items[current];
      if (item) {
        item.node.classList.add("tr-current");
        item.navLink.setAttribute("aria-current", "true");
        // Keep the outline in step with the text. Only the fixed sidebar scrolls
        // on its own; the narrow bar would drag the whole page with it.
        if (wideNav.matches) item.navLink.scrollIntoView({ block: "nearest" });
      }
      showPosition();
    }

    /** @param {number} index */
    function go(index) {
      const item = items[index];
      if (!item) return;
      // A link can name an entry the filters hide; show everything so the jump lands.
      if (item.node.hidden) resetFilters();
      if (item.section) setFolded(item.section, false);
      jumpedAt = performance.now();
      pinned = index;
      setCurrent(index);
      item.node.scrollIntoView({ block: "start" });
      item.node.focus({ preventScroll: true });
    }

    /** @param {1 | -1} direction */
    function step(direction) {
      const order = pageOrder();
      const target = stepIndex(
        order.map((index) => !items[index].node.hidden),
        order.indexOf(current),
        direction,
      );
      if (order[target] !== undefined) go(order[target]);
    }

    function goWaiting() {
      const order = pageOrder();
      const waiting = order.map((index) => {
        const item = items[index];
        return (
          !item.node.hidden && item.data.triageable && !triage[item.data.id]
        );
      });
      const target = nextWaitingIndex(waiting, order.indexOf(current));
      if (target === -1) {
        status.textContent = "Every shown entry has a decision.";
        return;
      }
      go(order[target]);
    }

    // While the reader scrolls, the first entry still crossing the top of the
    // window is the one being read; the outline follows it.
    const TOP_EDGE = 28;
    let jumpedAt = -Infinity;
    /** The entry the reader chose with the outline, the keyboard, or a click, or -1. */
    let pinned = -1;
    function followScroll() {
      const reading = sections.find(
        (section) => section.node.getBoundingClientRect().bottom > TOP_EDGE,
      );
      for (const section of sections) {
        if (section === reading)
          section.navLink.setAttribute("aria-current", "true");
        else section.navLink.removeAttribute("aria-current");
      }
      // An entry the reader chose stays the current one while it is on screen,
      // even when the page is too short to bring it to the top.
      if (pinned !== -1) {
        const chosen = items[pinned].node.getBoundingClientRect();
        const onScreen =
          chosen.bottom > TOP_EDGE && chosen.top < window.innerHeight;
        if (onScreen || performance.now() - jumpedAt < 1000) return;
        pinned = -1;
      }
      for (const index of pageOrder()) {
        const item = items[index];
        if (item.node.hidden || item.section?.body?.hidden) continue;
        const box = item.node.getBoundingClientRect();
        if (box.bottom <= TOP_EDGE) continue;
        if (box.top < window.innerHeight * 0.6) setCurrent(index);
        return;
      }
    }
    let scrollQueued = false;
    window.addEventListener(
      "scroll",
      () => {
        if (scrollQueued) return;
        scrollQueued = true;
        window.requestAnimationFrame(() => {
          scrollQueued = false;
          followScroll();
        });
      },
      { passive: true },
    );

    // ---------- Updates ----------

    function sortEntries() {
      /** @type {Map<Node, EntryItem[]>} */
      const groups = new Map();
      for (const item of items) {
        const parent = item.node.parentNode;
        if (!parent) continue;
        const group = groups.get(parent) ?? [];
        group.push(item);
        groups.set(parent, group);
      }
      for (const [parent, group] of groups) {
        const sorted = [...group].sort((a, b) =>
          compareEntries(a.data, b.data, view.sort),
        );
        // Keep each group where its first entry sits, so headings and prose stay put.
        const anchor = el("span");
        parent.insertBefore(anchor, group[0].node);
        for (const item of sorted) parent.insertBefore(item.node, anchor);
        anchor.remove();
      }
      // The outline lists entries in the order the page now has them.
      for (const index of pageOrder()) {
        const link = items[index].navLink.parentElement;
        if (link) items[index].section?.navList.append(link);
      }
      showPosition();
    }

    function update() {
      let visibleCount = 0;
      for (const item of items) {
        const visible = matches(
          item.data,
          view.filters,
          view.query,
          triage[item.data.id],
        );
        item.node.hidden = !visible;
        const row = item.navLink.parentElement;
        if (row) row.hidden = !visible;
        if (visible) visibleCount += 1;
      }
      // When a filter hides the entry being read, the shortcuts move to the
      // entry that took its place, never act on one the reader cannot see.
      if (items[current]?.node.hidden) {
        const order = pageOrder();
        const place = nearestShownIndex(
          order.map((index) => !items[index].node.hidden),
          order.indexOf(current),
        );
        const next = place === -1 ? -1 : order[place];
        pinned = next;
        setCurrent(next);
      }
      const filtered =
        view.query.trim() !== "" ||
        Object.values(view.filters).some((values) => values.length > 0);
      resultText.textContent = filtered
        ? `Showing ${visibleCount} of ${entries.length} ${noun(meta, entries.length)}`
        : "";
      clearFilters.hidden = !filtered;
      result.hidden = !filtered;
      const tucked = Object.entries(view.filters)
        .filter(([facet]) => facet !== meta.facets[0])
        .reduce((sum, [, values]) => sum + values.length, 0);
      moreButton.textContent =
        tucked > 0
          ? `Filters and options (${tucked} on)`
          : "Filters and options";

      const accepted = triageable.filter(
        (entry) => triage[entry.id]?.decision === "accept",
      ).length;
      const dismissed = triageable.filter(
        (entry) => triage[entry.id]?.decision === "dismiss",
      ).length;
      const undecided = triageable.length - accepted - dismissed;
      /** @type {Record<string, number>} */
      const triageTotals = { accepted, dismissed, undecided };
      for (const { facet, value, chip, count } of chips) {
        chip.setAttribute(
          "aria-pressed",
          String((view.filters[facet] ?? []).includes(value)),
        );
        if (facet !== TRIAGE_FACET) continue;
        count.textContent = String(triageTotals[value]);
        chip.dataset.empty = String(triageTotals[value] === 0);
      }
      triageCounts.textContent = `${accepted} ${triageWords.accepted} \u00b7 ${dismissed} ${triageWords.dismissed} \u00b7 ${undecided} undecided`;
      copyPrompt.disabled = accepted + dismissed === 0;
      clearTriage.disabled = accepted + dismissed === 0;
      nextWaiting.disabled = undecided === 0;

      for (const section of sections) {
        const inside = items.filter((item) => item.section === section);
        const visible = inside.filter((item) => !item.node.hidden).length;
        section.count.textContent =
          inside.length === 0
            ? ""
            : filtered
              ? `${visible} of ${inside.length}`
              : String(inside.length);
        section.navCount.textContent =
          inside.length === 0 ? "" : String(visible);
        section.empty.hidden = inside.length === 0 || visible > 0;
        // A filter that finds something in a folded section opens it.
        if (filtered && visible > 0) setFolded(section, false);
      }
      showPosition();
    }

    function openTarget() {
      const id = decodeURIComponent(window.location.hash.slice(1));
      if (!id) return;
      const index = items.findIndex((candidate) => candidate.node.id === id);
      if (index !== -1) {
        items[index].setOpen(true);
        go(index);
        return;
      }
      const section = sections.find((candidate) => candidate.node.id === id);
      if (section) setFolded(section, false);
    }

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !help.hidden) {
        toggleHelp();
        return;
      }
      const target = event.target;
      const typing =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement;
      if (
        !settings.keys ||
        typing ||
        event.metaKey ||
        event.ctrlKey ||
        event.altKey
      )
        return;
      const item = items[current];
      if (event.key === "j") step(1);
      else if (event.key === "k") step(-1);
      else if (event.key === "u" && triageable.length > 0) goWaiting();
      else if (event.key === "a" && item?.decide) item.decide("accept");
      else if (event.key === "d" && item?.decide) item.decide("dismiss");
      else if (event.key === "o" && item)
        item.setOpen(Boolean(item.body.hidden));
      else if (event.key === "/") search.focus();
      else if (event.key === "?") toggleHelp();
      else return;
      event.preventDefault();
    });
    window.addEventListener("hashchange", openTarget);
    // A link to an entry, from the verdict or from another entry, goes there
    // even when the address already names it.
    main.addEventListener("click", (event) => {
      const link =
        event.target instanceof Element
          ? event.target.closest('a[href^="#"]')
          : null;
      const id = decodeURIComponent(link?.getAttribute("href")?.slice(1) ?? "");
      const index = items.findIndex(
        (candidate) =>
          candidate.node.id === id || `entry-${candidate.data.id}` === id,
      );
      if (index === -1) return;
      event.preventDefault();
      event.stopPropagation();
      items[index].setOpen(true);
      go(index);
    });

    update();
    openTarget();
    followScroll();
  }

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
