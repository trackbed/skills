// @ts-check
"use strict";

// The workflows whose runs are measured, in report order.
const DECISION_WORKFLOW_SKILLS = [
  "trackbed:linear:issue-to-pr",
  "trackbed:code:plan-to-pr",
];
const KIND_STATE_GATE = "state-gate";
const KIND_BASE_DRIFT = "base-drift";
const KIND_REVIEW_BUDGET = "review-budget";
const KIND_OTHER = "other";
// Report order.
const DECISION_KINDS = [
  KIND_REVIEW_BUDGET,
  KIND_BASE_DRIFT,
  KIND_STATE_GATE,
  KIND_OTHER,
];
const QUESTION_TOOL_NAME = "AskUserQuestion";
// Claude Code gives this model name to messages it writes itself, such as an
// API error or the "No response requested." placeholder after a resumed
// session.
const SYNTHETIC_MODEL = "<synthetic>";
const OPENING_LINES = 3;
// The first line of a decision request: one decision, one of several, or an
// action only the user can take. The shared decision request format
// (`shared/implementation/references/decision-request.md`) owns this wording.
const DECISION_FIRST_LINE =
  /^(?:decision needed|decision \d+ of \d+|action needed)\b/i;
const LINE_DECORATION = /^[\s>#*_`-]+/;
const RESUME_REPLY = /^(?:resume|continue)[.!]?$/i;
// A host cancellation is not always flagged with `is_error`, so its wording
// counts too.
const CANCELLED_RESULT =
  /USER_CANCELLED|cancelled the question|interrupted before a result/i;
// Records that Claude Code or the host writes as user entries without the
// user answering the workflow.
const HOST_ENTRY_PREFIXES = ["<task-notification>", "<local-command-"];
const COMMAND_ENTRY_PREFIXES = ["<command-name>", "<command-message>"];
// Claude Code stores a typed slash command as a `command-message` element that
// repeats the command name, plus `command-name` and `command-args` elements.
const COMMAND_MESSAGE_ELEMENT = /<command-message>[^<]*<\/command-message>/g;
const COMMAND_TAGS = /<\/?command-(?:name|args)>/g;
// The success report of either workflow, or the reviewer summary that closes
// an issue-to-pr report. The wording comes from the report templates in
// `skills/linear:issue-to-pr/SKILL.md` and `skills/code:plan-to-pr/SKILL.md`.
// A run blocked before publication says why no Pull Request was created, so
// its report does not match. A run blocked after its Pull Request opened still
// prints the link and does match; `docs/hooks.md` lists that limit.
const FINAL_REPORT_PATTERNS = [
  /^[ \t>*_`-]*Pull Request:[\s*_`]*(?:https?:\/\/|\[)/im,
  /^[ \t>*_`-]*Pull Request:[\s*_`]*not created \(--ship was not supplied\)/im,
  /^[ \t>*_`-]*Completion disposition:[\s*_`]*success/im,
  /what to focus on in review/i,
];

/**
 * @typedef {{ line: string | null, overlong: boolean }} DecisionLine
 * @typedef {Object} DecisionDeps
 * @property {(file: string) => AsyncIterable<DecisionLine>} readLines
 * @property {(file: string, count: number, reason: string) => void} skipped
 * @property {(file: string, error: unknown) => void} readFailure
 * @property {(text: string) => string[]} promptSkills Plugin skills a user message invokes.
 * @property {(text: string) => string} stripHostInstructions Removes text the host put before the user's own.
 * @typedef {{ sessionId: string, recordedAt: string, kind: string, skill: string, pluginVersion: string }} DecisionUsageRecord
 * @typedef {{ sessionId: string, skill: string, recordedAt: string, pluginVersion: string }} WorkflowRun
 * @typedef {{ since: Date | null, until: Date | null, pluginVersion: string }} RunFilters
 * @typedef {"answered" | "cancelled" | "unanswered"} DialogOutcome
 * @typedef {{ kind: string, outcome: DialogOutcome }} DialogRequest
 * @typedef {{ kind: string, words: number, opensWithDecision: boolean, replyWords: number }} MessageRequest
 * @typedef {Object} RunFacts
 * @property {boolean} started The transcript holds the message that invoked the workflow.
 * @property {DialogRequest[]} dialogs
 * @property {MessageRequest[]} messages
 * @property {number} limitStalls
 * @property {number} reportFollowUps
 * @typedef {{ median: number | null, p90: number | null, max: number | null }} WordStats
 * @typedef {ReturnType<typeof buildRow>} DecisionRow
 */

/**
 * Collects one run per session: its first explicit record of a measured
 * workflow. The recorder appends in order, so the first record seen is the
 * earliest.
 */
function createWorkflowRunSelector() {
  /** @type {Map<string, WorkflowRun>} */
  const runs = new Map();
  return {
    /** @param {DecisionUsageRecord} record */
    add(record) {
      if (
        !record.sessionId ||
        record.kind !== "explicit" ||
        !DECISION_WORKFLOW_SKILLS.includes(record.skill) ||
        runs.has(record.sessionId)
      ) {
        return;
      }
      runs.set(record.sessionId, {
        sessionId: record.sessionId,
        skill: record.skill,
        recordedAt: record.recordedAt,
        pluginVersion: record.pluginVersion,
      });
    },
    /**
     * `since` is inclusive and `until` exclusive. `pluginVersion` is a
     * version, `unknown` for records without one, or `all`.
     * @param {RunFilters} filters
     * @returns {WorkflowRun[]}
     */
    select({ since, until, pluginVersion }) {
      const wantedVersion = pluginVersion === "unknown" ? "" : pluginVersion;
      return [...runs.values()].filter((run) => {
        if (pluginVersion !== "all" && run.pluginVersion !== wantedVersion) {
          return false;
        }
        const recordedAt = Date.parse(run.recordedAt);
        if ((since || until) && !Number.isFinite(recordedAt)) return false;
        if (since && recordedAt < since.getTime()) return false;
        if (until && recordedAt >= until.getTime()) return false;
        return true;
      });
    },
  };
}

/**
 * Sorts a decision request into a kind by what it mentions. Checks the state
 * gate, then base drift, then the review budget; the first match wins and
 * `other` takes the rest. The state gate wording comes from
 * `skills/linear:issue-implement/references/status-transition.md`.
 * @param {string} text
 * @returns {string}
 */
function classifyDecisionKind(text) {
  const lower = text.toLowerCase();
  if (
    lower.includes("proceed with implementation") ||
    lower.includes("move the issue to")
  ) {
    return KIND_STATE_GATE;
  }
  if (
    lower.includes("base drift") ||
    (/\bbehind\b/.test(lower) && /\brebas/.test(lower))
  ) {
    return KIND_BASE_DRIFT;
  }
  if (/\b(?:budget|cycles?|rounds?)\b/.test(lower)) return KIND_REVIEW_BUDGET;
  return KIND_OTHER;
}

/**
 * The lines that say why a message stopped: its opening lines and every line
 * with a question mark. A long message also recaps the run, and classifying
 * the recap would sort most stops under whatever the recap mentions.
 * @param {string} text
 */
function decisionLines(text) {
  return text
    .split("\n")
    .filter((line) => line.replace(LINE_DECORATION, "").trim())
    .filter((line, index) => index < OPENING_LINES || line.includes("?"))
    .join("\n");
}

/**
 * True when one of the first three non-empty lines is a decision request's
 * first line or holds a question mark.
 * @param {string} text
 */
function opensWithDecision(text) {
  return text
    .split("\n")
    .map((line) => line.replace(LINE_DECORATION, "").trim())
    .filter(Boolean)
    .slice(0, OPENING_LINES)
    .some((line) => DECISION_FIRST_LINE.test(line) || line.includes("?"));
}

/**
 * True when a message asks the user for something: it holds a question mark
 * or opens with a decision request's first line.
 * @param {string} text
 */
function asksTheUser(text) {
  return text.includes("?") || opensWithDecision(text);
}

/**
 * True for a workflow's closing report. A message that opens with a decision
 * request's first line is a decision request and never a report, even when it
 * quotes the report.
 * @param {string} text
 */
function isFinalReport(text) {
  return (
    !DECISION_FIRST_LINE.test(text.replace(LINE_DECORATION, "")) &&
    FINAL_REPORT_PATTERNS.some((pattern) => pattern.test(text))
  );
}

/** @param {string} text */
function countWords(text) {
  return text.split(/\s+/).filter(Boolean).length;
}

/**
 * The words the user typed: a slash command counts as its name and arguments,
 * without the elements Claude Code stores around them.
 * @param {string} reply
 */
function countReplyWords(reply) {
  return countWords(
    reply.replace(COMMAND_MESSAGE_ELEMENT, " ").replace(COMMAND_TAGS, " "),
  );
}

/**
 * Reads one transcript record at a time and counts where the run stopped for
 * the user. The measured window opens at the message that invokes `skill` and
 * closes at the workflow's final report.
 * @param {string} skill
 * @param {Pick<DecisionDeps, "promptSkills" | "stripHostInstructions">} deps
 */
function createRunScanner(skill, deps) {
  /** @type {RunFacts} */
  const facts = {
    started: false,
    dialogs: [],
    messages: [],
    limitStalls: 0,
    reportFollowUps: 0,
  };
  /** @type {"before" | "open" | "reported"} */
  let phase = "before";
  // The trailing text of the latest assistant message: what the user sees
  // when the turn ends.
  /** @type {{ messageId: unknown, texts: string[], stall: boolean }} */
  let closing = { messageId: null, texts: [], stall: false };
  /** @type {Map<string, DialogRequest>} */
  const openDialogs = new Map();

  const clearClosing = () => {
    closing = { messageId: null, texts: [], stall: false };
  };

  /** @param {Record<string, unknown>} record */
  const readAssistant = (record) => {
    const message = asRecord(record.message);
    if (!Array.isArray(message.content)) return;
    const stall = message.model === SYNTHETIC_MODEL;
    for (const block of message.content.map(asRecord)) {
      if (block.type === "tool_use") {
        clearClosing();
        if (
          phase === "open" &&
          String(block.name).includes(QUESTION_TOOL_NAME)
        ) {
          /** @type {DialogRequest} */
          const dialog = {
            kind: classifyDecisionKind(dialogText(block.input)),
            outcome: "unanswered",
          };
          facts.dialogs.push(dialog);
          if (typeof block.id === "string") openDialogs.set(block.id, dialog);
        }
        continue;
      }
      const text = block.type === "text" ? stringValue(block.text) : "";
      if (!text.trim() || phase === "before") continue;
      if (closing.messageId !== message.id) {
        closing = { messageId: message.id, texts: [], stall };
      }
      closing.texts.push(text);
      if (phase === "open" && isFinalReport(text)) phase = "reported";
    }
  };

  /** @param {unknown[]} results */
  const readToolResults = (results) => {
    for (const result of results.map(asRecord)) {
      const toolUseId = result.tool_use_id;
      if (typeof toolUseId !== "string") continue;
      const dialog = openDialogs.get(toolUseId);
      if (!dialog) continue;
      dialog.outcome =
        result.is_error === true ||
        CANCELLED_RESULT.test(blockText(result.content))
          ? "cancelled"
          : "answered";
      openDialogs.delete(toolUseId);
    }
  };

  /** @param {string} raw */
  const readHumanMessage = (raw) => {
    if (phase === "before") {
      if (deps.promptSkills(raw).includes(skill)) {
        phase = "open";
        facts.started = true;
      }
      return;
    }

    const closingText = closing.texts.join("\n\n");
    const reply = deps.stripHostInstructions(raw).trim();
    if (phase === "reported") {
      facts.reportFollowUps += 1;
    } else if (!closingText) {
      // The user wrote while the workflow was still working; nothing was
      // waiting for an answer.
    } else if (
      closing.stall ||
      // A bare "resume" answers a message that asks; after any other message
      // it restarts a run that a limit stopped.
      (RESUME_REPLY.test(reply) && !asksTheUser(closingText))
    ) {
      facts.limitStalls += 1;
    } else {
      facts.messages.push({
        kind: classifyDecisionKind(decisionLines(closingText)),
        words: countWords(closingText),
        opensWithDecision: opensWithDecision(closingText),
        replyWords: countReplyWords(reply),
      });
    }
    clearClosing();
  };

  return {
    /** @param {Record<string, unknown>} record */
    read(record) {
      if (record.isSidechain === true) return;
      if (record.type === "assistant") {
        readAssistant(record);
        return;
      }
      if (record.type !== "user") return;
      const content = asRecord(record.message).content;
      const blocks = Array.isArray(content) ? content : [];
      const results = blocks.filter(
        (block) => asRecord(block).type === "tool_result",
      );
      if (results.length > 0) {
        readToolResults(results);
        return;
      }
      if (record.isMeta === true || record.isCompactSummary === true) return;
      const raw = typeof content === "string" ? content : blockText(blocks);
      const start = raw.trimStart();
      if (!start || HOST_ENTRY_PREFIXES.some((p) => start.startsWith(p))) {
        return;
      }
      // A built-in command such as `/compact` answers nothing; a plugin skill
      // typed as a command is the user's reply.
      if (
        COMMAND_ENTRY_PREFIXES.some((p) => start.startsWith(p)) &&
        deps.promptSkills(raw).length === 0
      ) {
        return;
      }
      readHumanMessage(raw);
    },
    /** @returns {RunFacts} */
    finish() {
      return facts;
    },
  };
}

/**
 * The header, question, and option labels of a question dialog. Option
 * descriptions are left out because they explain consequences at length.
 * @param {unknown} input
 */
function dialogText(input) {
  const questions = asRecord(input).questions;
  if (!Array.isArray(questions)) return "";
  return questions
    .map(asRecord)
    .flatMap((question) => [
      stringValue(question.header),
      stringValue(question.question),
      ...(Array.isArray(question.options) ? question.options : []).map(
        (option) =>
          typeof option === "string"
            ? option
            : stringValue(asRecord(option).label),
      ),
    ])
    .join("\n");
}

/** @param {unknown} content A string or a list of content blocks. */
function blockText(content) {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content
    .map(asRecord)
    .filter((block) => block.type === "text")
    .map((block) => stringValue(block.text))
    .join("\n");
}

/**
 * Streams one run's transcript.
 * @param {string | undefined} file
 * @param {string} skill
 * @param {DecisionDeps} deps
 * @returns {Promise<RunFacts | null>} Null when there is no readable transcript.
 */
async function scanRunTranscript(file, skill, deps) {
  if (!file) return null;
  const scanner = createRunScanner(skill, deps);
  let overlongLines = 0;
  let malformedLines = 0;
  let readSucceeded = true;

  try {
    for await (const boundedLine of deps.readLines(file)) {
      if (boundedLine.overlong) {
        overlongLines += 1;
        continue;
      }
      const line = boundedLine.line || "";
      if (!line) continue;
      const record = parseObject(line);
      if (!record) {
        malformedLines += 1;
        continue;
      }
      scanner.read(record);
    }
  } catch (error) {
    readSucceeded = false;
    deps.readFailure(file, error);
  }

  deps.skipped(file, overlongLines, "overlong JSONL");
  deps.skipped(file, malformedLines, "malformed JSONL");
  return readSucceeded ? scanner.finish() : null;
}

/**
 * @param {Array<{ skill: string, facts: RunFacts | null }>} runs
 * @returns {DecisionRow[]} One row per workflow that has runs.
 */
function buildDecisionRows(runs) {
  return DECISION_WORKFLOW_SKILLS.map((skill) =>
    buildRow(
      skill,
      runs.filter((run) => run.skill === skill).map((run) => run.facts),
    ),
  ).filter((row) => row.runs > 0);
}

/** @param {string} skill @param {Array<RunFacts | null>} allFacts */
function buildRow(skill, allFacts) {
  const measured = allFacts.flatMap((facts) =>
    facts && facts.started ? [facts] : [],
  );
  const dialogs = measured.flatMap((facts) => facts.dialogs);
  const messages = measured.flatMap((facts) => facts.messages);
  const requests = dialogs.length + messages.length;

  return {
    skill,
    runs: allFacts.length,
    runsWithTranscript: measured.length,
    runsWithDecisionRequest: countWhere(
      measured,
      (facts) => facts.dialogs.length + facts.messages.length > 0,
    ),
    decisionRequests: requests,
    requestsPerRun:
      measured.length > 0
        ? Math.round((requests / measured.length) * 100) / 100
        : 0,
    byKind: DECISION_KINDS.map((kind) => ({
      kind,
      dialog: countWhere(dialogs, (dialog) => dialog.kind === kind),
      message: countWhere(messages, (message) => message.kind === kind),
    })),
    dialogs: {
      total: dialogs.length,
      answered: countWhere(dialogs, (d) => d.outcome === "answered"),
      cancelled: countWhere(dialogs, (d) => d.outcome === "cancelled"),
      unanswered: countWhere(dialogs, (d) => d.outcome === "unanswered"),
    },
    messages: {
      total: messages.length,
      opensWithDecision: countWhere(messages, (m) => m.opensWithDecision),
      words: wordStats(messages.map((message) => message.words)),
      replyWords: wordStats(messages.map((message) => message.replyWords)),
    },
    limitStalls: sum(measured, (facts) => facts.limitStalls),
    reportFollowUps: sum(measured, (facts) => facts.reportFollowUps),
  };
}

/** @param {number[]} values @returns {WordStats} */
function wordStats(values) {
  if (values.length === 0) return { median: null, p90: null, max: null };
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return {
    median:
      sorted.length % 2 === 1
        ? sorted[middle]
        : (sorted[middle - 1] + sorted[middle]) / 2,
    // Nearest rank: the smallest value with at least 90% of values at or below it.
    p90: sorted[Math.ceil(sorted.length * 0.9) - 1],
    max: sorted[sorted.length - 1],
  };
}

/**
 * @param {DecisionRow[]} rows
 * @param {{ skippedLines: number, readFailures: number }} diagnostics
 * @param {boolean | undefined} json
 * @param {RunFilters} filters
 * @returns {string}
 */
function renderDecisions(rows, diagnostics, json, filters) {
  const degraded = diagnostics.skippedLines > 0 || diagnostics.readFailures > 0;
  if (json) {
    const result = degraded ? { summary: rows, diagnostics } : rows;
    return JSON.stringify(result, null, 2) + "\n";
  }

  const shown = [
    filters.since ? ` since=${filters.since.toISOString()}` : "",
    filters.until ? ` until=${filters.until.toISOString()}` : "",
    filters.pluginVersion !== "all"
      ? ` pluginVersion=${filters.pluginVersion}`
      : "",
  ].join("");
  let output = `Decision requests in local Claude Code transcripts${shown}\n`;
  output +=
    rows.length === 0
      ? "No issue-to-pr or plan-to-pr runs found.\n"
      : rows.map(renderRow).join("");
  if (degraded) {
    output += `diagnostics skippedLines=${diagnostics.skippedLines} readFailures=${diagnostics.readFailures}\n`;
  }
  return output;
}

/** @param {DecisionRow} row */
function renderRow(row) {
  const kindWidth = Math.max(...DECISION_KINDS.map((kind) => kind.length));
  /** @param {WordStats} stats */
  const formatStats = (stats) =>
    [stats.median, stats.p90, stats.max]
      .map((value) => (value == null ? "-" : String(value)))
      .join("/");
  return [
    row.skill,
    `  runs=${row.runs} transcripts=${row.runsWithTranscript} stopped=${row.runsWithDecisionRequest} requests=${row.decisionRequests} perRun=${row.requestsPerRun.toFixed(2)}`,
    `  ${"kind".padEnd(kindWidth)}  dialog  message`,
    ...row.byKind.map(
      (entry) =>
        `  ${entry.kind.padEnd(kindWidth)}  ${String(entry.dialog).padStart(6)}  ${String(entry.message).padStart(7)}`,
    ),
    `  dialogs total=${row.dialogs.total} answered=${row.dialogs.answered} cancelled=${row.dialogs.cancelled} unanswered=${row.dialogs.unanswered}`,
    `  messages total=${row.messages.total} opensWithDecision=${row.messages.opensWithDecision} words(median/p90/max)=${formatStats(row.messages.words)} replyWords(median/p90/max)=${formatStats(row.messages.replyWords)}`,
    `  not counted: limitStalls=${row.limitStalls} reportFollowUps=${row.reportFollowUps}`,
    "",
  ].join("\n");
}

/**
 * @template T
 * @param {T[]} items
 * @param {(item: T) => number} pick
 */
function sum(items, pick) {
  return items.reduce((total, item) => total + pick(item), 0);
}

/**
 * @template T
 * @param {T[]} items
 * @param {(item: T) => boolean} test
 */
function countWhere(items, test) {
  return items.filter(test).length;
}

/** @param {unknown} value */
function stringValue(value) {
  return typeof value === "string" ? value : "";
}

/** @param {string} line @returns {Record<string, unknown> | null} */
function parseObject(line) {
  try {
    return asRecord(JSON.parse(line));
  } catch {
    return null;
  }
}

/** @param {unknown} value @returns {Record<string, unknown>} */
function asRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? /** @type {Record<string, unknown>} */ (value)
    : {};
}

module.exports = {
  DECISION_WORKFLOW_SKILLS,
  buildDecisionRows,
  classifyDecisionKind,
  createRunScanner,
  createWorkflowRunSelector,
  opensWithDecision,
  renderDecisions,
  scanRunTranscript,
};
