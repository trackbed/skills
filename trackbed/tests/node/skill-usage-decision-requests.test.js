"use strict";

const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  DECISION_WORKFLOW_SKILLS,
  buildDecisionRows,
  classifyDecisionKind,
  createRunScanner,
  createWorkflowRunSelector,
  opensWithDecision,
  renderDecisions,
  scanRunTranscript,
} = require("../../scripts/lib/skill-usage-decision-requests.js");

const SCRIPT = path.resolve(__dirname, "../../scripts/skill-usage.js");
const SKILLS_DIR = path.resolve(__dirname, "../../skills");
const [ISSUE_TO_PR, PLAN_TO_PR] = DECISION_WORKFLOW_SKILLS;
const PROMPT_MARKER = "PRIVATE_PROMPT_MARKER";
const QUESTION_MARKER = "PRIVATE_QUESTION_MARKER";
const REQUEST_MARKER = "PRIVATE_REQUEST_MARKER";
const REPLY_MARKER = "PRIVATE_REPLY_MARKER";
const PATH_MARKER = "PRIVATE_PATH_MARKER";
const LIMIT_TEXT = "You've hit your session limit · resets 5pm";
// 28 words; the decision sits on the fourth non-empty line.
const REQUEST_TEXT = [
  `I stopped ABC-1 before shipping. ${REQUEST_MARKER}`,
  "Review used both fix cycles and one finding is open.",
  "Nothing has been pushed.",
  "**Decision needed:** may I run one more cycle?",
].join("\n\n");
const SHIPPED_REPORT =
  "```text\nLinear issue: ABC-1\nPull Request: https://example.test/pull/1\n```";

/** @param {string[]} args @param {NodeJS.ProcessEnv} [overrides] */
function runUsage(args, overrides = {}) {
  const env = { ...process.env };
  delete env.TRACKBED_SKILL_USAGE_FILE;
  delete env.KRAMME_SKILL_USAGE_FILE;
  delete env.CLAUDE_CONFIG_DIR;
  return spawnSync(process.execPath, [SCRIPT, ...args], {
    encoding: "utf8",
    env: { ...env, ...overrides },
  });
}

/** @param {import("node:test").TestContext} t */
async function tempDir(t) {
  const root = await fs.mkdtemp(
    path.join(os.tmpdir(), "skill-usage-decisions-"),
  );
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  return root;
}

/** @param {string} file @param {unknown[]} records */
async function writeJsonl(file, records) {
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(
    file,
    records
      .map((record) =>
        typeof record === "string" ? record : JSON.stringify(record),
      )
      .join("\n") + "\n",
  );
}

/** @param {string} text @param {Record<string, unknown>} [extra] */
function human(text, extra = {}) {
  return { type: "user", message: { role: "user", content: text }, ...extra };
}

/** @param {string} id @param {string} text @param {Record<string, unknown>} [extra] */
function says(id, text, extra = {}) {
  return {
    type: "assistant",
    message: {
      id,
      role: "assistant",
      model: "claude-test",
      content: [{ type: "text", text }],
    },
    ...extra,
  };
}

/** A message Claude Code writes itself. @param {string} id @param {string} text */
function hostSays(id, text) {
  return {
    type: "assistant",
    message: {
      id,
      role: "assistant",
      model: "<synthetic>",
      content: [{ type: "text", text }],
    },
  };
}

/** @param {string} id @param {string} toolId @param {string} name @param {unknown} [input] */
function uses(id, toolId, name, input = {}) {
  return {
    type: "assistant",
    message: {
      id,
      role: "assistant",
      model: "claude-test",
      content: [{ type: "tool_use", id: toolId, name, input }],
    },
  };
}

/** @param {string} id @param {string} toolId @param {string} header @param {string} question @param {string[]} [labels] */
function asks(id, toolId, header, question, labels = []) {
  return uses(id, toolId, "mcp__conductor__AskUserQuestion", {
    questions: [
      { header, question, options: labels.map((label) => ({ label })) },
    ],
  });
}

/** @param {string} toolId @param {string} text @param {Record<string, unknown>} [extra] */
function answers(toolId, text, extra = {}) {
  return {
    type: "user",
    message: {
      role: "user",
      content: [
        {
          type: "tool_result",
          tool_use_id: toolId,
          content: [{ type: "text", text }],
          ...extra,
        },
      ],
    },
  };
}

/**
 * One dialog request, one usage-limit stall, one message request, and one final report.
 * @param {string} [invocation] The user message that starts the run.
 */
function shippedRunTranscript(
  invocation = "/trackbed:linear:issue-to-pr ABC-1 --ship",
) {
  return [
    human(`${PROMPT_MARKER} what does this repository do?`),
    says("m0", "It ships skills."),
    human(invocation),
    human("Base directory for this skill: /plugin", { isMeta: true }),
    asks(
      "m1",
      "tool-1",
      "Base drift",
      `${QUESTION_MARKER} PR #1 is 3 commits behind main. Rebase before fixing CI?`,
      ["Rebase then fix CI", "Skip rebase and fix CI"],
    ),
    answers("tool-1", "User responses:\n1. Skip rebase and fix CI"),
    hostSays("m2", LIMIT_TEXT),
    human("resume"),
    says("m3", "Starting the review."),
    uses("m3", "tool-2", "Bash"),
    answers("tool-2", "ok"),
    says("m4", "Waiting for the review agent."),
    human("<task-notification>agent finished</task-notification>"),
    says("m5", REQUEST_TEXT),
    says("s1", "Should the subagent count?", { isSidechain: true }),
    human(
      `<system_instruction>Host text</system_instruction>\n\none more cycle ${REPLY_MARKER}`,
    ),
    says("m6", SHIPPED_REPORT),
    human("Resolve the deferred findings"),
    asks("m7", "tool-3", "Push now?", "Push the rebased branch?"),
    answers("tool-3", "User responses:\n1. Yes"),
  ];
}

/** @type {import("../../scripts/lib/skill-usage-decision-requests.js").RunFacts} */
const SHIPPED_RUN_FACTS = {
  started: true,
  dialogs: [{ kind: "base-drift", outcome: "answered" }],
  messages: [
    {
      kind: "review-budget",
      words: 28,
      opensWithDecision: false,
      replyWords: 4,
    },
  ],
  limitStalls: 1,
  reportFollowUps: 1,
};

/** @param {string} text */
function fakePromptSkills(text) {
  return [...text.matchAll(/\/(trackbed:[a-z:-]+)/g)].map((match) => match[1]);
}

/** @param {string} text */
function fakeStrip(text) {
  const end = text.lastIndexOf("</system_instruction>");
  return end === -1 ? text : text.slice(end + "</system_instruction>".length);
}

/** @param {unknown[]} records @param {string} [skill] */
function scan(records, skill = ISSUE_TO_PR) {
  const scanner = createRunScanner(skill, {
    promptSkills: fakePromptSkills,
    stripHostInstructions: fakeStrip,
  });
  for (const record of records) {
    scanner.read(/** @type {Record<string, unknown>} */ (record));
  }
  return scanner.finish();
}

/** @param {string} sessionId @param {string} skill @param {string} recordedAt @param {Record<string, string>} [extra] */
function usage(sessionId, skill, recordedAt, extra = {}) {
  return {
    schemaVersion: 1,
    recordedAt,
    sessionId,
    cwd: `/work/${PATH_MARKER}`,
    platform: "claude-code",
    pluginVersion: "1.0.0",
    event: "UserPromptSubmit",
    skill,
    kind: "explicit",
    source: "prompt",
    ...extra,
  };
}

test("classifyDecisionKind checks the state gate, then base drift, then the review budget", () => {
  assert.equal(
    classifyDecisionKind(
      "ABC-1 is in Todo. Proceed with implementation and move the issue to In Progress?",
    ),
    "state-gate",
  );
  assert.equal(
    classifyDecisionKind("PR #1 is 4 commits behind main. Rebase first?"),
    "base-drift",
  );
  assert.equal(
    classifyDecisionKind("How should fix-ci handle the base drift?"),
    "base-drift",
  );
  assert.equal(
    classifyDecisionKind("Approve one more remediation cycle?"),
    "review-budget",
  );
  assert.equal(
    classifyDecisionKind("The 2-round budget is used up."),
    "review-budget",
  );
  assert.equal(
    classifyDecisionKind("Run a third review round?"),
    "review-budget",
  );
  assert.equal(
    classifyDecisionKind("Base drift after the second fix cycle: rebase?"),
    "base-drift",
  );
  assert.equal(
    classifyDecisionKind("Move the issue to In Progress?"),
    "state-gate",
  );
  assert.equal(
    classifyDecisionKind("Both fix cycles are used."),
    "review-budget",
  );
  assert.equal(classifyDecisionKind("Two rounds are used."), "review-budget");
  assert.equal(
    classifyDecisionKind("The branch is behind main; keep rebasing?"),
    "base-drift",
  );
  assert.equal(
    classifyDecisionKind(
      "Proceed with implementation after one more cycle behind a rebase?",
    ),
    "state-gate",
  );
  assert.equal(classifyDecisionKind("Redis or Valkey?"), "other");
  assert.equal(classifyDecisionKind("Rebase onto main first?"), "other");
  assert.equal(
    classifyDecisionKind(
      "The branch is behind schedule and around the lifecycle.",
    ),
    "other",
  );
});

test("opensWithDecision reads the first three non-empty lines", () => {
  assert.equal(
    opensWithDecision("**Decision needed · ABC-1:** run a third cycle\n\nWhy."),
    true,
  );
  assert.equal(
    opensWithDecision("\n\n# Stopped\n\nShould I continue?\n\nDetails."),
    true,
  );
  assert.equal(
    opensWithDecision("Decision 1 of 2 · ABC-1: rebase first\n\nWhy."),
    true,
  );
  assert.equal(
    opensWithDecision("Action needed · ABC-1: grant access\n\nWhy."),
    true,
  );
  assert.equal(opensWithDecision("Decisions were made.\nTwo.\nThree."), false);
  assert.equal(opensWithDecision("No decision needed.\nTwo.\nThree."), false);
  assert.equal(opensWithDecision(REQUEST_TEXT), false);
  assert.equal(opensWithDecision("One.\nTwo.\nThree.\nDecision needed"), false);
  assert.equal(opensWithDecision(""), false);
});

test("run selector keeps each session's first explicit workflow record inside the filters", () => {
  const selector = createWorkflowRunSelector();
  const records = [
    usage("s6", PLAN_TO_PR, "2026-10-14T00:00:00.000Z", {
      kind: "tool",
      source: "tool_input",
    }),
    usage("s1", "trackbed:pr:create", "2026-10-14T00:00:00.000Z"),
    usage("s1", ISSUE_TO_PR, "2026-10-14T00:00:00.000Z"),
    usage("s1", PLAN_TO_PR, "2026-10-15T00:00:00.000Z"),
    usage("s2", PLAN_TO_PR, "2026-10-20T00:00:00.000Z", { pluginVersion: "" }),
    usage("s3", ISSUE_TO_PR, "2026-11-01T00:00:00.000Z", {
      pluginVersion: "1.0.1",
    }),
    usage("", ISSUE_TO_PR, "2026-10-20T00:00:00.000Z"),
    usage("s5", ISSUE_TO_PR, "not a date"),
  ];
  for (const record of records) selector.add(record);

  /** @param {Partial<import("../../scripts/lib/skill-usage-decision-requests.js").RunFilters>} filters */
  const select = (filters) =>
    selector
      .select({ since: null, until: null, pluginVersion: "all", ...filters })
      .map((run) => `${run.sessionId}:${run.skill}`);

  assert.deepEqual(select({}), [
    `s1:${ISSUE_TO_PR}`,
    `s2:${PLAN_TO_PR}`,
    `s3:${ISSUE_TO_PR}`,
    `s5:${ISSUE_TO_PR}`,
  ]);
  assert.deepEqual(
    select({
      since: new Date("2026-10-14T00:00:00.000Z"),
      until: new Date("2026-11-01T00:00:00.000Z"),
    }),
    [`s1:${ISSUE_TO_PR}`, `s2:${PLAN_TO_PR}`],
  );
  assert.deepEqual(select({ since: new Date("2026-10-14T00:00:00.001Z") }), [
    `s2:${PLAN_TO_PR}`,
    `s3:${ISSUE_TO_PR}`,
  ]);
  assert.deepEqual(select({ pluginVersion: "1.0.1" }), [`s3:${ISSUE_TO_PR}`]);
  assert.deepEqual(select({ pluginVersion: "unknown" }), [`s2:${PLAN_TO_PR}`]);
});

test("scanner classifies a dialog request, a limit stall, a message request, and a final report", () => {
  assert.deepEqual(scan(shippedRunTranscript()), SHIPPED_RUN_FACTS);
});

test("scanner treats a blocked report as a request and stops counting at the final report", () => {
  const facts = scan([
    human("/trackbed:linear:issue-to-pr ABC-1 --ship"),
    asks(
      "m1",
      "tool-1",
      "ABC-1 state gate",
      "Proceed with implementation and move the issue to In Progress?",
    ),
    answers(
      "tool-1",
      "User cancelled the question.\nError code: CONDUCTOR_ASK_USER_QUESTION_USER_CANCELLED",
    ),
    asks("m2", "tool-2", "Approach", "Redis or Valkey?"),
    answers("tool-2", "The user rejected this tool use.", { is_error: true }),
    asks("m3", "tool-3", "Review budget", "Approve one more cycle?"),
    says(
      "m4",
      "Linear issue: ABC-1\nPull Request: not created (blocked at review)\n\nShould I continue?",
    ),
    human("/trackbed:linear:issue-to-pr ABC-1 --continue --ship"),
    says(
      "m5",
      "Linear issue: ABC-1\nPull Request: not created (--ship was not supplied)",
    ),
    human("thanks"),
    human("/trackbed:linear:issue-to-pr ABC-2"),
    asks("m6", "tool-4", "Later", "A question after the report?"),
  ]);

  assert.deepEqual(facts.messages, [
    {
      kind: "other",
      words: 13,
      opensWithDecision: true,
      replyWords: 4,
    },
  ]);
  assert.deepEqual(facts.dialogs, [
    { kind: "state-gate", outcome: "cancelled" },
    { kind: "other", outcome: "cancelled" },
    { kind: "review-budget", outcome: "unanswered" },
  ]);
  assert.equal(facts.reportFollowUps, 2);
});

test("scanner keeps a decision request open even when it quotes the report", () => {
  for (const firstLine of [
    "Decision needed · ABC-1: rebase the open Pull Request, or keep it?",
    "Decision 1 of 2 · ABC-1: rebase the open Pull Request, or keep it?",
    "Action needed · ABC-1: grant access to the repository",
  ]) {
    const facts = scan([
      human("/trackbed:linear:issue-to-pr ABC-1 --ship"),
      says("m1", `${firstLine}\n\nPull Request: https://example.test/pull/1`),
      human("2"),
      asks("m2", "tool-1", "Base drift", "Rebase before fixing CI?"),
    ]);

    assert.equal(facts.reportFollowUps, 0, firstLine);
    assert.equal(facts.messages.length, 1, firstLine);
    assert.equal(facts.messages[0].opensWithDecision, true, firstLine);
    assert.equal(facts.dialogs.length, 1, firstLine);
  }
});

test("scanner ignores host entries and tells limit stalls from answers", () => {
  const facts = scan([
    human("/trackbed:linear:issue-to-pr ABC-1"),
    uses("m1", "tool-1", "Bash"),
    answers("tool-1", "ok"),
    human("how is it going?"),
    says("m2", "Which approach should I take?"),
    human("Stop hook feedback: keep going", { isMeta: true }),
    human("<command-name>/compact</command-name>"),
    human("<local-command-stdout>Compacted</local-command-stdout>"),
    human("This session is being continued.", { isCompactSummary: true }),
    human(
      "<command-message>trackbed:pr-rebase</command-message>\n<command-name>/trackbed:pr-rebase</command-name>",
    ),
    hostSays("m3", "No response requested."),
    human("Create the Pull Request"),
    says("m4", "The review is still running."),
    human("Continue."),
    says("m5", "Shall I go on?"),
    human("resume"),
    says("m6", "Still waiting for CI."),
    human("resume"),
    says("m7", "Action needed · ABC-1: grant access to the repository"),
    human("continue"),
    says(
      "m8",
      [
        "The job failed twice.",
        "The logs are attached.",
        "Nothing is pushed.",
        "Should I retry the job?",
      ].join("\n"),
    ),
    human("resume"),
  ]);

  assert.deepEqual(facts.messages, [
    {
      kind: "other",
      words: 5,
      opensWithDecision: true,
      replyWords: 1,
    },
    {
      kind: "other",
      words: 4,
      opensWithDecision: true,
      replyWords: 1,
    },
    {
      kind: "other",
      words: 9,
      opensWithDecision: true,
      replyWords: 1,
    },
    {
      kind: "other",
      words: 16,
      opensWithDecision: false,
      replyWords: 1,
    },
  ]);
  assert.equal(facts.limitStalls, 3);
  assert.equal(facts.reportFollowUps, 0);
});

test("scanner classifies a message by its asking lines and a dialog by its header, question, and labels", () => {
  const facts = scan([
    human("/trackbed:linear:issue-to-pr ABC-1"),
    says(
      "m1",
      [
        "I stopped ABC-1.",
        "Nothing is pushed.",
        "The checks pass.",
        "The branch was rebased because it was behind main.",
        "May I run one more cycle?",
      ].join("\n"),
    ),
    human("yes"),
    says(
      "m1b",
      [
        "Review used both fix cycles.",
        "One finding is open.",
        "Nothing is pushed.",
        "The checks pass.",
        "Which option?",
      ].join("\n"),
    ),
    human("the first"),
    asks("m2", "tool-1", "Base drift", "How should I go on?"),
    asks("m3", "tool-2", "Next step", "How should I go on?", [
      "Run one more cycle",
    ]),
    uses("m4", "tool-3", "mcp__conductor__AskUserQuestion", {
      questions: [
        {
          header: "Next step",
          question: "How should I go on?",
          options: [
            { label: "Go on", description: "Rebase first; it is behind main." },
          ],
        },
      ],
    }),
  ]);

  assert.deepEqual(
    facts.messages.map((message) => message.kind),
    ["review-budget", "review-budget"],
  );
  // The length covers the whole message, not only the lines that set its kind.
  assert.deepEqual(
    facts.messages.map((message) => message.words),
    [24, 17],
  );
  assert.deepEqual(
    facts.dialogs.map((dialog) => dialog.kind),
    ["base-drift", "review-budget", "other"],
  );
});

test("scanner recognizes the report and gate wording the workflow skills ship", async () => {
  /**
   * @param {string} file A skill file, relative to the skills directory.
   * @returns The file's `text` blocks, with a Pull Request link filled in.
   */
  const textBlocks = async (file) =>
    [
      ...(await fs.readFile(path.join(SKILLS_DIR, file), "utf8")).matchAll(
        /^```text\n([\s\S]*?)\n```$/gm,
      ),
    ].map((match) => match[1].replace("{url}", "https://example.test/pull/1"));
  const issueReports = (await textBlocks("linear:issue-to-pr/SKILL.md")).filter(
    (block) => /^Pull Request:/m.test(block),
  );
  const planReports = (await textBlocks("code:plan-to-pr/SKILL.md")).filter(
    (block) => /^Completion disposition: success$/m.test(block),
  );
  const moved =
    "report templates changed: update FINAL_REPORT_PATTERNS and this test";
  assert.equal(issueReports.length, 2, moved);
  assert.equal(planReports.length, 2, moved);

  const reports = [
    ...issueReports.map((report) => ({ skill: ISSUE_TO_PR, report })),
    {
      skill: ISSUE_TO_PR,
      report: "**Needs your attention:** nothing.",
    },
    {
      skill: PLAN_TO_PR,
      report: "**Needs your attention**\n\n1. Check the assumed default.",
    },
    {
      skill: ISSUE_TO_PR,
      report: "**What to focus on in review**\n\nNothing.",
    },
    ...planReports.map((report) => ({ skill: PLAN_TO_PR, report })),
  ];
  for (const { skill, report } of reports) {
    const facts = scan(
      [human(`/${skill} ABC-1`), says("m1", report), human("thanks")],
      skill,
    );
    assert.equal(facts.reportFollowUps, 1, report);
    assert.equal(facts.messages.length, 0, report);
  }

  const issueToPr = await fs.readFile(
    path.join(SKILLS_DIR, "linear:issue-to-pr/SKILL.md"),
    "utf8",
  );
  assert.match(issueToPr, /\*\*Needs your attention\*\*/);
  const planToPr = await fs.readFile(
    path.join(SKILLS_DIR, "code:plan-to-pr/SKILL.md"),
    "utf8",
  );
  assert.match(planToPr, /\*\*Needs your attention\*\*/);
  const gateQuestion = (
    await fs.readFile(
      path.join(
        SKILLS_DIR,
        "linear:issue-implement/references/status-transition.md",
      ),
      "utf8",
    )
  ).match(/this exact question: `([^`]+)`/);
  assert.equal(classifyDecisionKind(gateQuestion?.[1] ?? ""), "state-gate");
});

test("scanner recognizes a decorated or linked Pull Request line as the final report", () => {
  for (const report of [
    "**Pull Request:** https://example.test/pull/1",
    "- Pull Request: [#1](https://example.test/pull/1)",
    "No decision needed.\n\nPull Request: https://example.test/pull/1",
  ]) {
    const facts = scan([
      human("/trackbed:linear:issue-to-pr ABC-1"),
      says("m1", report),
      human("thanks"),
    ]);
    assert.equal(facts.reportFollowUps, 1, report);
    assert.equal(facts.messages.length, 0, report);
  }
});

test("scanner does not take a mid-run mention of the attention label for the report", () => {
  const facts = scan([
    human("/trackbed:linear:issue-to-pr ABC-1"),
    says("m1", "Base drift needs your attention. Rebase now?"),
    human("yes"),
  ]);
  assert.equal(facts.reportFollowUps, 0);
  assert.equal(facts.messages.length, 1);
});

test("scanner recognizes a plan-to-pr completion and reports a run that never started", () => {
  const finished = scan(
    [
      human("/trackbed:code:plan-to-pr PR_PLAN_W01A.md"),
      says("m1", "Completion disposition: success\nBlocker: none"),
      human("What changed?"),
    ],
    PLAN_TO_PR,
  );
  assert.equal(finished.reportFollowUps, 1);
  assert.equal(finished.messages.length, 0);

  const other = scan([
    human("/trackbed:code:plan-to-pr PR_PLAN_W01A.md"),
    says("m1", "Which plan?"),
    human("the first"),
  ]);
  assert.deepEqual(other, {
    started: false,
    dialogs: [],
    messages: [],
    limitStalls: 0,
    reportFollowUps: 0,
  });
});

test("scanRunTranscript reports skipped lines and returns null without a readable transcript", async () => {
  /** @type {string[]} */
  const skipped = [];
  let failures = 0;
  const deps = {
    /** @param {string} file */
    readLines: async function* (file) {
      if (file === "missing") throw new Error("gone");
      yield {
        line: JSON.stringify(human("/trackbed:linear:issue-to-pr A-1")),
        overlong: false,
      };
      yield { line: '{"type":"assistant", broken', overlong: false };
      yield { line: null, overlong: true };
      yield { line: '{"type":"cost-state"}', overlong: false };
    },
    /** @param {string} _file @param {number} count @param {string} reason */
    skipped: (_file, count, reason) => {
      if (count > 0) skipped.push(`${count} ${reason}`);
    },
    readFailure: () => {
      failures += 1;
    },
    promptSkills: fakePromptSkills,
    stripHostInstructions: fakeStrip,
  };

  const facts = await scanRunTranscript("present", ISSUE_TO_PR, deps);
  assert.equal(facts?.started, true);
  assert.deepEqual(skipped, ["1 overlong JSONL", "1 malformed JSONL"]);

  assert.equal(await scanRunTranscript("missing", ISSUE_TO_PR, deps), null);
  assert.equal(await scanRunTranscript(undefined, ISSUE_TO_PR, deps), null);
  assert.equal(failures, 1);
});

test("buildDecisionRows aggregates per workflow in report order", () => {
  /** @param {number} words @param {number} replyWords @param {boolean} [opens] */
  const message = (words, replyWords, opens = false) => ({
    kind: "review-budget",
    words,
    opensWithDecision: opens,
    replyWords,
  });
  const rows = buildDecisionRows([
    { skill: PLAN_TO_PR, facts: null },
    { skill: ISSUE_TO_PR, facts: SHIPPED_RUN_FACTS },
    {
      skill: ISSUE_TO_PR,
      facts: {
        started: true,
        dialogs: [],
        messages: [message(100, 1, true), message(300, 2), message(900, 9)],
        limitStalls: 2,
        reportFollowUps: 0,
      },
    },
    {
      skill: ISSUE_TO_PR,
      facts: { ...SHIPPED_RUN_FACTS, dialogs: [], messages: [] },
    },
    {
      skill: ISSUE_TO_PR,
      facts: { ...SHIPPED_RUN_FACTS, started: false },
    },
    {
      skill: ISSUE_TO_PR,
      facts: {
        started: true,
        dialogs: [{ kind: "other", outcome: "cancelled" }],
        messages: [],
        limitStalls: 0,
        reportFollowUps: 0,
      },
    },
  ]);

  assert.deepEqual(rows, [
    {
      skill: ISSUE_TO_PR,
      runs: 5,
      runsWithTranscript: 4,
      runsWithDecisionRequest: 3,
      decisionRequests: 6,
      requestsPerRun: 1.5,
      byKind: [
        { kind: "review-budget", dialog: 0, message: 4 },
        { kind: "base-drift", dialog: 1, message: 0 },
        { kind: "state-gate", dialog: 0, message: 0 },
        { kind: "other", dialog: 1, message: 0 },
      ],
      dialogs: { total: 2, answered: 1, cancelled: 1, unanswered: 0 },
      messages: {
        total: 4,
        opensWithDecision: 1,
        words: { median: 200, p90: 900, max: 900 },
        replyWords: { median: 3, p90: 9, max: 9 },
      },
      limitStalls: 4,
      reportFollowUps: 2,
    },
    {
      skill: PLAN_TO_PR,
      runs: 1,
      runsWithTranscript: 0,
      runsWithDecisionRequest: 0,
      decisionRequests: 0,
      requestsPerRun: 0,
      byKind: [
        { kind: "review-budget", dialog: 0, message: 0 },
        { kind: "base-drift", dialog: 0, message: 0 },
        { kind: "state-gate", dialog: 0, message: 0 },
        { kind: "other", dialog: 0, message: 0 },
      ],
      dialogs: { total: 0, answered: 0, cancelled: 0, unanswered: 0 },
      messages: {
        total: 0,
        opensWithDecision: 0,
        words: { median: null, p90: null, max: null },
        replyWords: { median: null, p90: null, max: null },
      },
      limitStalls: 0,
      reportFollowUps: 0,
    },
  ]);
});

test("buildDecisionRows reports the median, the nearest-rank 90th percentile, and the maximum", () => {
  const messages = Array.from({ length: 11 }, (_, index) => ({
    kind: "other",
    words: (11 - index) * 10,
    opensWithDecision: false,
    replyWords: 11 - index,
  }));
  const [row] = buildDecisionRows([
    {
      skill: ISSUE_TO_PR,
      facts: {
        started: true,
        dialogs: [],
        messages,
        limitStalls: 0,
        reportFollowUps: 0,
      },
    },
  ]);

  assert.deepEqual(row.messages.words, { median: 60, p90: 100, max: 110 });
  assert.deepEqual(row.messages.replyWords, { median: 6, p90: 10, max: 11 });
});

/**
 * Builds a usage log and a projects tree for the command tests.
 * @param {string} root
 */
async function writeFixture(root) {
  const usageFile = path.join(root, "skill-usage.jsonl");
  const projects = path.join(root, "projects");
  const project = path.join(projects, `-work-${PATH_MARKER}`);

  await writeJsonl(usageFile, [
    usage("s-old", ISSUE_TO_PR, "2026-09-01T10:00:00.000Z"),
    usage("s-run", "kramme:linear:issue-to-pr", "2026-10-20T10:00:00.000Z"),
    usage("s-missing", ISSUE_TO_PR, "2026-10-21T10:00:00.000Z"),
    usage("s-plan", PLAN_TO_PR, "2026-10-22T10:00:00.000Z", {
      pluginVersion: "",
    }),
    usage("s-codex", ISSUE_TO_PR, "2026-10-23T10:00:00.000Z", {
      platform: "codex",
    }),
    usage("s-other", "trackbed:pr:create", "2026-10-24T10:00:00.000Z"),
    usage("s-late", ISSUE_TO_PR, "2026-11-05T10:00:00.000Z", {
      pluginVersion: "1.0.1",
    }),
  ]);
  // Releases before 1.0.0 recorded `kramme:` names, and Conductor puts an
  // instruction block before the typed command.
  await writeJsonl(
    path.join(project, "s-run.jsonl"),
    shippedRunTranscript(
      "<system_instruction>Host text</system_instruction>\n\n/kramme-cc-workflow:kramme:linear:issue-to-pr ABC-1 --ship",
    ),
  );
  await writeJsonl(path.join(project, "s-plan.jsonl"), [
    human("/trackbed:code:plan-to-pr PR_PLAN_W01A.md"),
    says("m1", "Completion disposition: success"),
  ]);
  await writeJsonl(path.join(project, "s-late.jsonl"), [
    human("/trackbed:linear:issue-to-pr ABC-9"),
    asks("m1", "tool-1", "Review budget", "Approve one more cycle?"),
    says("m2", "Rebase first?"),
    // How Claude Code stores a typed slash command.
    human(
      "<command-message>trackbed:pr-rebase</command-message>\n<command-name>/trackbed:pr-rebase</command-name>",
    ),
    '{"type":"assistant", broken',
  ]);
  await writeJsonl(path.join(project, "s-old.jsonl"), shippedRunTranscript());
  await writeJsonl(path.join(project, "s-codex.jsonl"), shippedRunTranscript());

  return { usageFile, projects };
}

test("decisions reports counts per workflow for a date range and keeps transcript text out", async (t) => {
  const root = await tempDir(t);
  const { usageFile, projects } = await writeFixture(root);
  const range = ["--since", "2026-10-01", "--until", "2026-11-01"];

  const json = runUsage([
    "decisions",
    "--file",
    usageFile,
    "--projects",
    projects,
    ...range,
    "--json",
    "--strict",
  ]);
  assert.equal(json.status, 0, json.stderr);
  const rows = JSON.parse(json.stdout);
  assert.deepEqual(
    rows.map((/** @type {{ skill: string }} */ row) => row.skill),
    [ISSUE_TO_PR, PLAN_TO_PR],
  );
  assert.deepEqual(
    {
      runs: rows[0].runs,
      runsWithTranscript: rows[0].runsWithTranscript,
      runsWithDecisionRequest: rows[0].runsWithDecisionRequest,
      decisionRequests: rows[0].decisionRequests,
      requestsPerRun: rows[0].requestsPerRun,
      dialogs: rows[0].dialogs,
      messages: rows[0].messages,
      limitStalls: rows[0].limitStalls,
      reportFollowUps: rows[0].reportFollowUps,
    },
    {
      runs: 2,
      runsWithTranscript: 1,
      runsWithDecisionRequest: 1,
      decisionRequests: 2,
      requestsPerRun: 2,
      dialogs: { total: 1, answered: 1, cancelled: 0, unanswered: 0 },
      messages: {
        total: 1,
        opensWithDecision: 0,
        words: { median: 28, p90: 28, max: 28 },
        replyWords: { median: 4, p90: 4, max: 4 },
      },
      limitStalls: 1,
      reportFollowUps: 1,
    },
  );
  assert.equal(rows[1].runs, 1);
  assert.equal(rows[1].decisionRequests, 0);

  const table = runUsage(
    [
      "decisions",
      `--file=${usageFile}`,
      `--since=${range[1]}`,
      "--until=2026-11-01",
    ],
    { CLAUDE_CONFIG_DIR: path.dirname(projects) },
  );
  assert.equal(table.status, 0, table.stderr);
  assert.equal(
    table.stdout,
    [
      "Decision requests in local Claude Code transcripts since=2026-10-01T00:00:00.000Z until=2026-11-01T00:00:00.000Z",
      ISSUE_TO_PR,
      "  runs=2 transcripts=1 stopped=1 requests=2 perRun=2.00",
      "  kind           dialog  message",
      "  review-budget       0        1",
      "  base-drift          1        0",
      "  state-gate          0        0",
      "  other               0        0",
      "  dialogs total=1 answered=1 cancelled=0 unanswered=0",
      "  messages total=1 opensWithDecision=0 words(median/p90/max)=28/28/28 replyWords(median/p90/max)=4/4/4",
      "  not counted: limitStalls=1 reportFollowUps=1",
      PLAN_TO_PR,
      "  runs=1 transcripts=1 stopped=0 requests=0 perRun=0.00",
      "  kind           dialog  message",
      "  review-budget       0        0",
      "  base-drift          0        0",
      "  state-gate          0        0",
      "  other               0        0",
      "  dialogs total=0 answered=0 cancelled=0 unanswered=0",
      "  messages total=0 opensWithDecision=0 words(median/p90/max)=-/-/- replyWords(median/p90/max)=-/-/-",
      "  not counted: limitStalls=0 reportFollowUps=0",
      "",
    ].join("\n"),
  );

  for (const result of [json, table]) {
    for (const marker of [
      PROMPT_MARKER,
      QUESTION_MARKER,
      REQUEST_MARKER,
      REPLY_MARKER,
      PATH_MARKER,
      root,
    ]) {
      assert.equal(result.stdout.includes(marker), false, marker);
      assert.equal(result.stderr.includes(marker), false, marker);
    }
  }
});

test("decisions filters by plugin version and reports degraded input", async (t) => {
  const root = await tempDir(t);
  const { usageFile, projects } = await writeFixture(root);
  const base = ["decisions", "--file", usageFile, "--projects", projects];

  const late = runUsage([...base, "--plugin-version", "1.0.1", "--json"]);
  assert.equal(late.status, 0, late.stderr);
  const degraded = JSON.parse(late.stdout);
  assert.deepEqual(degraded.diagnostics, { skippedLines: 1, readFailures: 0 });
  assert.equal(degraded.summary.length, 1);
  assert.equal(degraded.summary[0].runs, 1);
  assert.deepEqual(degraded.summary[0].dialogs, {
    total: 1,
    answered: 0,
    cancelled: 0,
    unanswered: 1,
  });
  assert.equal(degraded.summary[0].messages.replyWords.median, 1);
  assert.match(late.stderr, /skipped 1 malformed JSONL line file=/);

  const strict = runUsage([...base, "--plugin-version=1.0.1", "--strict"]);
  assert.equal(strict.status, 1);
  assert.match(strict.stdout, / pluginVersion=1\.0\.1\n/);
  assert.match(strict.stdout, /diagnostics skippedLines=1 readFailures=0\n$/);

  const unknown = runUsage([...base, "--plugin-version", "unknown", "--json"]);
  assert.deepEqual(
    JSON.parse(unknown.stdout).map(
      (/** @type {{ skill: string }} */ row) => row.skill,
    ),
    [PLAN_TO_PR],
  );

  const none = runUsage([...base, "--until", "2026-08-01"]);
  assert.equal(none.status, 0, none.stderr);
  assert.match(none.stdout, /\nNo issue-to-pr or plan-to-pr runs found\.\n$/);

  const invalid = runUsage([...base, "--until", "someday"]);
  assert.equal(invalid.status, 1);
  assert.match(invalid.stderr, /Invalid --until value: someday/);
});

test("renderDecisions prints the empty notice and the degraded JSON shape", () => {
  assert.equal(
    renderDecisions([], { skippedLines: 0, readFailures: 0 }, false, {
      since: null,
      until: null,
      pluginVersion: "all",
    }),
    "Decision requests in local Claude Code transcripts\nNo issue-to-pr or plan-to-pr runs found.\n",
  );
  assert.equal(
    renderDecisions([], { skippedLines: 0, readFailures: 2 }, true, {
      since: null,
      until: null,
      pluginVersion: "unknown",
    }),
    '{\n  "summary": [],\n  "diagnostics": {\n    "skippedLines": 0,\n    "readFailures": 2\n  }\n}\n',
  );
});
