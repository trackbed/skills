// @ts-check
/*
 * Interview round runtime.
 * scripts/interview-ui.py writes this file into every round page. Never paste
 * it into a page by hand.
 *
 * The page it runs in holds one round of interview questions, written by the
 * helper. This script draws none of it. It keeps what the person enters (in
 * this browser, until the round is sent), turns that into the answers the
 * helper checks, sends them to the helper that served the page or puts them on
 * the clipboard.
 *
 * The rules in the first half are plain functions, exported when this file
 * loads under Node so they are tested without a browser. The helper applies the
 * same rules in Python when it reads the answers.
 */
"use strict";

(function () {
  /**
   * @typedef {"choice" | "rank" | "scale" | "allocate" | "matrix" | "confirm" | "text"} Kind
   * @typedef {{
   *   id: string,
   *   kind: Kind,
   *   options?: string[],
   *   multiple?: boolean,
   *   other?: boolean,
   *   items?: string[],
   *   total?: number,
   *   step?: number,
   *   unit?: string,
   *   steps?: number,
   *   rows?: string[],
   *   columns?: string[],
   * }} Question
   * @typedef {{
   *   session: string,
   *   round: number,
   *   fingerprint: string,
   *   questions: Question[],
   * }} Catalog
   * @typedef {{
   *   unsure: boolean,
   *   note: string,
   *   selected: string[],
   *   otherOn: boolean,
   *   other: string,
   *   order: string[],
   *   confirmed: boolean,
   *   stop: number,
   *   amounts: { [id: string]: number },
   *   cells: { [row: string]: string },
   *   verdict: string,
   *   correction: string,
   *   text: string,
   * }} Draft
   * @typedef {{ [questionId: string]: Draft }} Drafts
   * @typedef {"answered" | "unsure" | "open"} Status
   * @typedef {{ [field: string]: unknown }} Value
   * @typedef {{ id: string, status: Status, value: Value | null, note: string }} Answer
   * @typedef {{ note: string, wrapUp: boolean, now: string }} Meta
   */

  const FORMAT = "trackbed-interview-answers";
  const SCHEMA_VERSION = 1;
  const MAX_NOTE = 2000;
  const MAX_TEXT = 5000;

  // ---------- the rules ----------

  /**
   * A question nobody has touched yet.
   * @param {Question} question
   * @returns {Draft}
   */
  function emptyDraft(question) {
    /** @type {{ [id: string]: number }} */
    const amounts = {};
    for (const id of question.items ?? []) amounts[id] = 0;
    return {
      unsure: false,
      note: "",
      selected: [],
      otherOn: false,
      other: "",
      order: [...(question.items ?? [])],
      confirmed: false,
      stop: 0,
      amounts,
      cells: {},
      verdict: "",
      correction: "",
      text: "",
    };
  }

  /**
   * How much of an allocation is placed so far.
   * @param {Question} question @param {Draft} draft
   */
  function placed(question, draft) {
    return (question.items ?? []).reduce(
      (sum, id) => sum + (draft.amounts[id] ?? 0),
      0,
    );
  }

  /**
   * The complete answer a draft holds, or null while it is incomplete. The
   * helper refuses anything less than complete, so this is the one place that
   * decides what "answered" means on the page.
   * @param {Question} question @param {Draft} draft
   * @returns {Value | null}
   */
  function valueOf(question, draft) {
    switch (question.kind) {
      case "choice": {
        const other =
          question.other && draft.otherOn
            ? draft.other.trim().slice(0, MAX_NOTE)
            : "";
        let selected = (question.options ?? []).filter((id) =>
          draft.selected.includes(id),
        );
        // One answer only: an answer of the person's own stands in for an option.
        if (!question.multiple) selected = other ? [] : selected.slice(0, 1);
        return selected.length || other ? { selected, other } : null;
      }
      case "rank":
        return draft.confirmed ? { order: [...draft.order] } : null;
      case "scale":
        return draft.stop >= 1 && draft.stop <= (question.steps ?? 0)
          ? { value: draft.stop }
          : null;
      case "allocate":
        return placed(question, draft) === question.total
          ? { amounts: { ...draft.amounts } }
          : null;
      case "matrix": {
        const rows = question.rows ?? [];
        const columns = question.columns ?? [];
        /** @type {{ [row: string]: string }} */
        const cells = {};
        for (const row of rows) {
          const column = draft.cells[row];
          if (!column || !columns.includes(column)) return null;
          cells[row] = column;
        }
        return { cells };
      }
      case "confirm": {
        const correction = draft.correction.trim().slice(0, MAX_NOTE);
        if (draft.verdict === "confirm")
          return { verdict: "confirm", correction: "" };
        return draft.verdict === "correct" && correction
          ? { verdict: "correct", correction }
          : null;
      }
      default: {
        const text = draft.text.trim().slice(0, MAX_TEXT);
        return text ? { text } : null;
      }
    }
  }

  /**
   * "Not sure" is an answer in its own right and wins over anything entered.
   * @param {Question} question @param {Draft} draft
   * @returns {Status}
   */
  function statusOf(question, draft) {
    if (draft.unsure) return "unsure";
    return valueOf(question, draft) ? "answered" : "open";
  }

  /**
   * What an open question still needs, in words for the person answering.
   * @param {Question} question @param {Draft} draft
   */
  function missing(question, draft) {
    switch (question.kind) {
      case "choice":
        return draft.otherOn ? "Say what would fit" : "Not answered";
      case "rank":
        return "Confirm the order";
      case "allocate": {
        const left = (question.total ?? 0) - placed(question, draft);
        const unit = question.unit ?? "points";
        return left > 0
          ? `${left} ${unit} left to place`
          : `${-left} ${unit} too many`;
      }
      case "matrix": {
        const rows = question.rows ?? [];
        const left = rows.filter((row) => !draft.cells[row]).length;
        return left === rows.length
          ? "Not answered"
          : `${left} of ${rows.length} rows left`;
      }
      case "confirm":
        return draft.verdict === "correct"
          ? "Say what is right"
          : "Not answered";
      default:
        return "Not answered";
    }
  }

  /**
   * `order` with one item moved a place up (-1) or down (1).
   * @param {string[]} order @param {string} id @param {number} delta
   */
  function moveItem(order, id, delta) {
    const from = order.indexOf(id);
    const to = from + delta;
    if (from < 0 || to < 0 || to >= order.length) return [...order];
    const next = [...order];
    next.splice(to, 0, ...next.splice(from, 1));
    return next;
  }

  /**
   * The amount an item may hold: a multiple of the step, never negative, and
   * never more than what the other items leave of the total.
   * @param {Question} question @param {Draft} draft @param {string} id @param {number} wanted
   */
  function fitAmount(question, draft, id, wanted) {
    const total = question.total ?? 0;
    const step = question.step ?? 1;
    const others = placed(question, draft) - (draft.amounts[id] ?? 0);
    const whole = Number.isFinite(wanted)
      ? Math.round(wanted / step) * step
      : 0;
    return Math.max(0, Math.min(whole, total - others));
  }

  /**
   * @param {Catalog} catalog @param {Drafts} drafts
   * @returns {{ answered: number, unsure: number, open: number }}
   */
  function tally(catalog, drafts) {
    const counts = { answered: 0, unsure: 0, open: 0 };
    for (const question of catalog.questions)
      counts[statusOf(question, draftOf(drafts, question))] += 1;
    return counts;
  }

  /**
   * @param {Drafts} drafts @param {Question} question
   * @returns {Draft}
   */
  function draftOf(drafts, question) {
    return drafts[question.id] ?? emptyDraft(question);
  }

  /**
   * The answers as the helper reads them: one entry per question of the round,
   * a value only where the answer is complete.
   * @param {Catalog} catalog @param {Drafts} drafts @param {Meta} meta
   */
  function buildPayload(catalog, drafts, meta) {
    /** @type {Answer[]} */
    const answers = catalog.questions.map((question) => {
      const draft = draftOf(drafts, question);
      const status = statusOf(question, draft);
      return {
        id: question.id,
        status,
        value: status === "answered" ? valueOf(question, draft) : null,
        note: draft.note.trim().slice(0, MAX_NOTE),
      };
    });
    return {
      format: FORMAT,
      schemaVersion: SCHEMA_VERSION,
      session: catalog.session,
      round: catalog.round,
      fingerprint: catalog.fingerprint,
      submittedAt: meta.now,
      next: meta.wrapUp ? "wrap-up" : "continue",
      note: meta.note.trim().slice(0, MAX_TEXT),
      answers,
    };
  }

  /**
   * @param {unknown} value @param {number} limit
   */
  function asText(value, limit) {
    return typeof value === "string" ? value.slice(0, limit) : "";
  }

  /**
   * Drafts read back from this browser's storage, kept only where they still
   * fit the round: storage is outside the page's control, so nothing in it is
   * trusted to name an option, an item, or a row.
   * @param {Catalog} catalog @param {unknown} stored
   * @returns {Drafts}
   */
  function restoreDrafts(catalog, stored) {
    /** @type {Drafts} */
    const drafts = {};
    const source = /** @type {{ [id: string]: any }} */ (
      stored && typeof stored === "object" ? stored : {}
    );
    for (const question of catalog.questions) {
      const draft = emptyDraft(question);
      const saved = source[question.id];
      drafts[question.id] = draft;
      if (!saved || typeof saved !== "object") continue;
      draft.unsure = saved.unsure === true;
      draft.note = asText(saved.note, MAX_NOTE);
      draft.otherOn = saved.otherOn === true && question.other === true;
      draft.other = asText(saved.other, MAX_NOTE);
      draft.correction = asText(saved.correction, MAX_NOTE);
      draft.text = asText(saved.text, MAX_TEXT);
      if (saved.verdict === "confirm" || saved.verdict === "correct")
        draft.verdict = saved.verdict;
      if (Array.isArray(saved.selected)) {
        const selected = (question.options ?? []).filter((id) =>
          saved.selected.includes(id),
        );
        draft.selected = question.multiple ? selected : selected.slice(0, 1);
      }
      const items = question.items ?? [];
      if (
        Array.isArray(saved.order) &&
        saved.order.length === items.length &&
        items.every((id) => saved.order.includes(id))
      ) {
        draft.order = saved.order.map(String);
        draft.confirmed = saved.confirmed === true;
      }
      if (
        Number.isInteger(saved.stop) &&
        saved.stop >= 1 &&
        saved.stop <= (question.steps ?? 0)
      )
        draft.stop = saved.stop;
      if (saved.amounts && typeof saved.amounts === "object") {
        // All of an allocation or none of it: a part that was cut to fit is not what the person entered.
        const step = question.step ?? 1;
        const amounts = items.map((id) => saved.amounts[id] ?? 0);
        const fits =
          amounts.every(
            (amount) =>
              Number.isInteger(amount) && amount >= 0 && amount % step === 0,
          ) &&
          amounts.reduce((sum, amount) => sum + amount, 0) <=
            (question.total ?? 0);
        if (fits)
          items.forEach((id, index) => {
            draft.amounts[id] = amounts[index];
          });
      }
      if (saved.cells && typeof saved.cells === "object")
        for (const row of question.rows ?? [])
          if ((question.columns ?? []).includes(saved.cells[row]))
            draft.cells[row] = saved.cells[row];
    }
    return drafts;
  }

  const api = {
    FORMAT,
    SCHEMA_VERSION,
    buildPayload,
    emptyDraft,
    fitAmount,
    missing,
    moveItem,
    restoreDrafts,
    statusOf,
    tally,
    valueOf,
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
      throw new Error(`interview page is missing ${selector}`);
    return found;
  }

  /**
   * @template {Element} T
   * @param {ParentNode} root @param {string} selector @param {new () => T} type
   * @returns {T[]}
   */
  function all(root, selector, type) {
    return Array.from(root.querySelectorAll(selector)).filter(
      /** @returns {node is T} */ (node) => node instanceof type,
    );
  }

  /**
   * @param {ParentNode} root @param {string} selector
   */
  function checked(root, selector) {
    return all(root, selector, HTMLInputElement).some((input) => input.checked);
  }

  /**
   * @param {ParentNode} root @param {string} selector
   */
  function typed(root, selector) {
    const field = root.querySelector(selector);
    return field instanceof HTMLTextAreaElement ? field.value : "";
  }

  /**
   * @param {ParentNode} root @param {string} selector @param {string} value
   */
  function type(root, selector, value) {
    const field = root.querySelector(selector);
    if (field instanceof HTMLTextAreaElement) field.value = value;
  }

  /**
   * @param {string} id
   */
  function data(id) {
    return JSON.parse(need(document, `#${id}`, HTMLElement).textContent ?? "");
  }

  function boot() {
    /** @type {Catalog} */
    const catalog = data("trackbed-interview-round");
    /** @type {{ mode: string, key: string, expiresAt: number }} */
    const config = data("trackbed-interview-config");
    const live = config.mode === "live";
    const storageKey = `trackbed-interview:${catalog.session}:${catalog.fingerprint}`;
    const form = need(document, "[data-form]", HTMLFormElement);
    const roundNote = need(form, "[data-round-note]", HTMLTextAreaElement);
    const wrapUp = need(form, "[data-wrap-up]", HTMLInputElement);
    const sendButton = need(form, "[data-send]", HTMLButtonElement);
    const notice = need(document, "[data-notice]", HTMLElement);
    const noticeText = need(notice, "[data-notice-text]", HTMLElement);
    const toast = need(document, "[data-toast]", HTMLElement);
    /** @type {{ [id: string]: Question }} */
    const questions = {};
    for (const question of catalog.questions) questions[question.id] = question;
    /** @type {{ [id: string]: HTMLElement }} */
    const sections = {};
    for (const section of all(form, "[data-question]", HTMLElement))
      sections[section.dataset.question ?? ""] = section;

    /** @type {Drafts} */
    let drafts = restoreDrafts(catalog, null);
    const draftWarning =
      "This browser is not keeping drafts. Send or copy your answers before you close or reload the page.";
    function draftStorage() {
      return live ? sessionStorage : localStorage;
    }
    let storageWorks = true;
    try {
      const stored = JSON.parse(draftStorage().getItem(storageKey) ?? "null");
      if (stored && typeof stored === "object") {
        drafts = restoreDrafts(catalog, stored.drafts);
        roundNote.value = asText(stored.note, MAX_TEXT);
        wrapUp.checked = stored.wrapUp === true;
      }
    } catch {
      storageWorks = false;
    }

    function save() {
      if (!storageWorks) return;
      try {
        draftStorage().setItem(
          storageKey,
          JSON.stringify({
            drafts,
            note: roundNote.value,
            wrapUp: wrapUp.checked,
          }),
        );
      } catch {
        storageWorks = false;
        say(draftWarning);
      }
    }

    /** @param {string} message */
    function say(message) {
      toast.textContent = message;
      toast.hidden = false;
      window.setTimeout(() => {
        if (toast.textContent === message) toast.hidden = true;
      }, 5000);
    }

    /** @param {string} message */
    function warn(message) {
      noticeText.textContent = message;
      notice.hidden = !message;
    }

    /**
     * Copy what the person entered out of a question's controls.
     * @param {HTMLElement} section @param {Question} question @param {Draft} draft
     */
    function read(section, question, draft) {
      draft.unsure = checked(section, "[data-unsure]");
      draft.note = typed(section, "[data-note]");
      switch (question.kind) {
        case "choice":
          draft.selected = all(section, "[data-option]", HTMLInputElement)
            .filter((input) => input.checked)
            .map((input) => input.value);
          draft.otherOn = checked(section, "[data-other]");
          draft.other = typed(section, "[data-other-text]");
          break;
        case "rank":
          draft.confirmed = checked(section, "[data-confirmed]");
          break;
        case "scale": {
          const picked = all(section, "[data-stop]", HTMLInputElement).find(
            (input) => input.checked,
          );
          draft.stop = picked ? Number(picked.value) : 0;
          break;
        }
        case "allocate":
          for (const row of all(section, "[data-item]", HTMLElement)) {
            const id = row.dataset.item ?? "";
            const input = need(row, "[data-amount]", HTMLInputElement);
            draft.amounts[id] = fitAmount(
              question,
              draft,
              id,
              Number(input.value),
            );
          }
          break;
        case "matrix":
          draft.cells = {};
          for (const input of all(section, "[data-row]", HTMLInputElement))
            if (input.checked)
              draft.cells[input.dataset.row ?? ""] = input.value;
          break;
        case "confirm": {
          const picked = all(section, "[data-verdict]", HTMLInputElement).find(
            (input) => input.checked,
          );
          draft.verdict = picked ? picked.value : "";
          draft.correction = typed(section, "[data-correction]");
          break;
        }
        default:
          draft.text = typed(section, "[data-text]");
      }
    }

    /**
     * Put a draft into a question's controls: after a restore, and after a move
     * or a step changed it.
     * @param {HTMLElement} section @param {Question} question @param {Draft} draft
     */
    function write(section, question, draft) {
      for (const input of all(section, "[data-unsure]", HTMLInputElement))
        input.checked = draft.unsure;
      type(section, "[data-note]", draft.note);
      if (draft.note)
        for (const note of all(section, "details", HTMLDetailsElement))
          note.open = true;
      switch (question.kind) {
        case "choice":
          for (const input of all(section, "[data-option]", HTMLInputElement))
            input.checked = draft.selected.includes(input.value);
          for (const input of all(section, "[data-other]", HTMLInputElement))
            input.checked = draft.otherOn;
          type(section, "[data-other-text]", draft.other);
          break;
        case "rank": {
          const list = need(section, "[data-rank]", HTMLElement);
          const rows = all(list, "[data-item]", HTMLElement);
          for (const id of draft.order) {
            const row = rows.find((entry) => entry.dataset.item === id);
            if (row) list.appendChild(row);
          }
          for (const input of all(
            section,
            "[data-confirmed]",
            HTMLInputElement,
          ))
            input.checked = draft.confirmed;
          break;
        }
        case "scale":
          for (const input of all(section, "[data-stop]", HTMLInputElement))
            input.checked = Number(input.value) === draft.stop;
          break;
        case "allocate":
          for (const row of all(section, "[data-item]", HTMLElement))
            need(row, "[data-amount]", HTMLInputElement).value = String(
              draft.amounts[row.dataset.item ?? ""] ?? 0,
            );
          break;
        case "matrix":
          for (const input of all(section, "[data-row]", HTMLInputElement))
            input.checked =
              draft.cells[input.dataset.row ?? ""] === input.value;
          break;
        case "confirm":
          for (const input of all(section, "[data-verdict]", HTMLInputElement))
            input.checked = input.value === draft.verdict;
          type(section, "[data-correction]", draft.correction);
          break;
        default:
          type(section, "[data-text]", draft.text);
      }
    }

    /**
     * Show what a draft amounts to: its state, and the parts of a control that
     * follow from the rest of it.
     * @param {HTMLElement} section @param {Question} question @param {Draft} draft
     */
    function paint(section, question, draft) {
      const status = statusOf(question, draft);
      const label =
        status === "answered"
          ? "Answered"
          : status === "unsure"
            ? "Not sure"
            : missing(question, draft);
      section.dataset.status = status;
      need(section, "[data-state]", HTMLElement).textContent = label;
      for (const mark of all(document, "[data-outline]", HTMLElement))
        if (mark.dataset.outline === question.id) {
          mark.textContent = label;
          mark.dataset.status = status;
        }
      if (question.kind === "choice" || question.kind === "confirm") {
        const shown =
          question.kind === "choice"
            ? draft.otherOn
            : draft.verdict === "correct";
        for (const box of all(section, "[data-own]", HTMLElement))
          box.hidden = !shown;
      }
      if (question.kind === "rank") {
        const rows = all(section, "[data-item]", HTMLElement);
        rows.forEach((row, index) => {
          need(row, "[data-place]", HTMLElement).textContent = String(
            index + 1,
          );
          for (const button of all(row, "[data-move]", HTMLButtonElement))
            button.disabled =
              button.dataset.move === "-1"
                ? index === 0
                : index === rows.length - 1;
        });
      }
      if (question.kind === "allocate") {
        const total = question.total ?? 0;
        const left = total - placed(question, draft);
        const unit = question.unit ?? "points";
        need(section, "[data-left]", HTMLElement).textContent =
          left === 0
            ? `All ${total} ${unit} placed`
            : `${left} of ${total} ${unit} left to place`;
        for (const row of all(section, "[data-item]", HTMLElement)) {
          const amount = draft.amounts[row.dataset.item ?? ""] ?? 0;
          need(row, "[data-share]", HTMLElement).style.width =
            `${total ? (100 * amount) / total : 0}%`;
          for (const button of all(row, "[data-step]", HTMLButtonElement))
            button.disabled =
              button.dataset.step === "-1" ? amount === 0 : left === 0;
        }
      }
    }

    function count() {
      const counts = tally(catalog, drafts);
      const total = catalog.questions.length;
      const done = counts.answered + counts.unsure;
      const text =
        done === total
          ? `All ${total} answered`
          : `${done} of ${total} answered. You can send with some left open.`;
      for (const line of all(document, "[data-count]", HTMLElement))
        line.textContent = text;
    }

    /** @param {string} id */
    function refresh(id) {
      const question = questions[id];
      const section = sections[id];
      if (!question || !section) return;
      paint(section, question, draftOf(drafts, question));
      count();
      save();
    }

    function payload() {
      return buildPayload(catalog, drafts, {
        note: roundNote.value,
        wrapUp: wrapUp.checked,
        now: new Date().toISOString(),
      });
    }

    function showSent() {
      for (const view of all(document, "[data-view]", HTMLElement))
        view.hidden = view.dataset.view !== "sent";
      const heading = document.querySelector('[data-view="sent"] h1');
      if (heading instanceof HTMLElement) heading.focus();
      window.scrollTo(0, 0);
    }

    async function copy() {
      const text = JSON.stringify(payload(), null, 2);
      try {
        await navigator.clipboard.writeText(text);
        say("Answers copied. Paste them into the chat with the agent.");
      } catch {
        const box = need(form, "[data-copy-box]", HTMLElement);
        const field = need(box, "[data-copy-text]", HTMLTextAreaElement);
        field.value = text;
        box.hidden = false;
        field.focus();
        field.select();
        say("Copy the text below and paste it into the chat with the agent.");
      }
    }

    async function send() {
      if (sendButton.disabled) return;
      sendButton.disabled = true;
      if (Date.now() >= config.expiresAt) {
        warn(
          "The wait for this round has ended. Copy your answers and paste them into the chat.",
        );
        return;
      }
      /** @type {Response | null} */
      let response;
      try {
        response = await fetch("/answers", {
          method: "POST",
          redirect: "error",
          headers: {
            "Content-Type": "application/json",
            "X-Trackbed-Key": config.key,
          },
          body: JSON.stringify(payload()),
        });
      } catch {
        response = null;
      }
      if (!response) {
        warn(
          "Delivery could not be confirmed. Copy your answers and return to the chat.",
        );
        return;
      }
      if (response.ok) {
        warn("");
        try {
          draftStorage().removeItem(storageKey);
        } catch {
          storageWorks = false;
        }
        showSent();
        return;
      }
      sendButton.disabled = false;
      /** @type {string[]} */
      let problems = [];
      try {
        const body = await response.json();
        if (Array.isArray(body.problems)) problems = body.problems.map(String);
      } catch {
        problems = [];
      }
      warn(
        `These answers were not accepted. ${problems.join(" ") || "Copy your answers and return to the chat."}`,
      );
    }

    form.addEventListener("input", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const section = target.closest("[data-question]");
      if (!(section instanceof HTMLElement)) {
        save();
        return;
      }
      const id = section.dataset.question ?? "";
      const question = questions[id];
      if (!question) return;
      const draft = draftOf(drafts, question);
      drafts[id] = draft;
      read(section, question, draft);
      refresh(id);
    });
    // A typed amount is corrected once the person leaves the field, not under their fingers.
    form.addEventListener("change", (event) => {
      const target = event.target;
      if (
        !(target instanceof HTMLInputElement) ||
        !target.matches("[data-amount]")
      )
        return;
      const section = target.closest("[data-question]");
      if (!(section instanceof HTMLElement)) return;
      const question = questions[section.dataset.question ?? ""];
      if (question) write(section, question, draftOf(drafts, question));
    });
    form.addEventListener("click", (event) => {
      const target = event.target;
      const button =
        target instanceof Element
          ? target.closest("[data-move], [data-step]")
          : null;
      if (!(button instanceof HTMLButtonElement)) return;
      const section = button.closest("[data-question]");
      const row = button.closest("[data-item]");
      if (!(section instanceof HTMLElement) || !(row instanceof HTMLElement))
        return;
      const id = section.dataset.question ?? "";
      const question = questions[id];
      if (!question) return;
      const draft = draftOf(drafts, question);
      drafts[id] = draft;
      const item = row.dataset.item ?? "";
      if (button.dataset.move) {
        draft.order = moveItem(draft.order, item, Number(button.dataset.move));
        draft.confirmed = true;
      } else {
        const wanted =
          (draft.amounts[item] ?? 0) +
          Number(button.dataset.step) * (question.step ?? 1);
        draft.amounts[item] = fitAmount(question, draft, item, wanted);
      }
      write(section, question, draft);
      refresh(id);
      // The row moved, or the button reached its limit: keep the keyboard where it was.
      if (button.disabled) {
        const other = all(row, "button", HTMLButtonElement).find(
          (entry) => !entry.disabled,
        );
        if (other) other.focus();
      } else button.focus();
    });
    for (const chart of all(form, ".ti-figure-chart", HTMLElement)) {
      const slider = need(chart, 'input[type="range"]', HTMLInputElement);
      const table = need(chart, "table", HTMLTableElement);
      const output = need(chart, "output", HTMLOutputElement);
      const lines = all(chart, ".ti-series", SVGElement);
      function inspectPoint() {
        const index = slider.valueAsNumber;
        const cells = table.rows[index + 1].cells;
        slider.setAttribute("aria-valuetext", cells[0].textContent ?? "");
        output.value = Array.from(cells, (cell, i) =>
          i
            ? table.rows[0].cells[i].textContent + ": " + cell.textContent
            : cell.textContent,
        ).join(" · ");
        for (const line of lines) {
          line.querySelectorAll("circle").forEach((point, j) => {
            point.classList.toggle("ti-point-selected", j === index);
          });
        }
      }
      // Inspecting the evidence must never change the answer to its question.
      slider.addEventListener("input", (event) => {
        event.stopPropagation();
        inspectPoint();
      });
      slider.addEventListener("change", (event) => event.stopPropagation());
      inspectPoint();
    }

    const inspector = need(document, "#ti-inspect", HTMLDialogElement);
    const viewport = need(inspector, ".ti-inspect-scroll", HTMLElement);
    for (const button of all(form, ".ti-enlarge", HTMLButtonElement)) {
      button.addEventListener("click", () => {
        const figure = button.closest("figure");
        if (!figure) return;
        need(inspector, "#ti-inspect-title", HTMLElement).textContent = need(
          figure,
          ".ti-evidence-title",
          HTMLElement,
        ).textContent;
        viewport.replaceChildren(
          need(button, ".ti-capture", HTMLElement).cloneNode(true),
        );
        const notes = figure.querySelector(".ti-callouts");
        if (notes) viewport.append(notes.cloneNode(true));
        inspector.showModal();
        viewport.scrollTo(0, 0);
      });
    }
    need(inspector, ".ti-dismiss", HTMLButtonElement).addEventListener(
      "click",
      () => inspector.close(),
    );
    inspector.addEventListener("close", () => viewport.replaceChildren());

    form.addEventListener("keydown", (event) => {
      const target = event.target;
      if (
        event.key === "Enter" &&
        !event.isComposing &&
        target instanceof HTMLInputElement &&
        target.matches("[data-amount]")
      )
        event.preventDefault();
    });
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (live) void send();
      else void copy();
    });
    for (const button of all(form, "[data-copy]", HTMLButtonElement))
      button.addEventListener("click", () => void copy());

    for (const question of catalog.questions) {
      const section = sections[question.id];
      if (!section) continue;
      const draft = draftOf(drafts, question);
      write(section, question, draft);
      paint(section, question, draft);
    }
    count();
    document.documentElement.classList.replace("no-js", "js");
    if (!storageWorks) say(draftWarning);
  }

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
