// @ts-check
"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const { spawnSync } = require("node:child_process");
const {
  compareResults,
  loadSuite,
  main,
  parseOptions,
  renderCandidate,
  renderComparison,
  runnerArguments,
  summarizeArm,
  toolchainWrapperDir,
} = require("../../scripts/skill-eval-compare");

/**
 * @param {import("node:test").TestContext} t
 * @returns {string}
 */
function tempDir(t) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "skill-eval-test-"));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  return directory;
}

/**
 * One `claude plugin eval` run: `checks` maps a grader name to whether it
 * passed.
 *
 * @param {Record<string, boolean>} checks
 * @param {Record<string, unknown>} [extra]
 */
function run(checks, extra = {}) {
  return {
    costUsd: 0.5,
    judgeCostUsd: 0.1,
    durationSeconds: 40,
    error: null,
    skippedPaidGraders: false,
    graders: Object.entries(checks).map(([name, passed]) => ({ name, passed })),
    ...extra,
  };
}

/**
 * @param {Record<string, unknown[]>} cases Runs by case name.
 * @param {Record<string, unknown>} [extra]
 */
function result(cases, extra = {}) {
  return {
    partial: false,
    cases: Object.entries(cases).map(([name, runs]) => ({
      name,
      arms: { with: runs },
    })),
    ...extra,
  };
}

/**
 * @param {boolean[]} outcomes One run per entry, each with a single check.
 */
function runsOf(outcomes) {
  return outcomes.map((passed) => run({ check: passed }));
}

test("options default to a three-run comparison and accept every documented flag", () => {
  assert.deepEqual(parseOptions(["pr-generate-description"]), {
    suite: "pr-generate-description",
    base: null,
    candidateOnly: false,
    runs: 3,
    caseGlob: null,
    model: null,
    judgeModel: null,
    maxCostUsd: null,
    concurrency: 1,
    out: null,
    keepTemp: false,
    help: false,
  });
  const options = parseOptions([
    "demo",
    "--base",
    "origin/main",
    "--runs",
    "5",
    "--case",
    "demo-*",
    "--model",
    "claude-test",
    "--judge-model",
    "claude-judge",
    "--max-cost-usd",
    "12.5",
    "--concurrency",
    "4",
    "--out",
    "results",
    "--keep-temp",
  ]);
  assert.equal(options.base, "origin/main");
  assert.equal(options.runs, 5);
  assert.equal(options.caseGlob, "demo-*");
  assert.equal(options.model, "claude-test");
  assert.equal(options.judgeModel, "claude-judge");
  assert.equal(options.maxCostUsd, 12.5);
  assert.equal(options.concurrency, 4);
  assert.equal(options.out, "results");
  assert.equal(options.keepTemp, true);
  assert.equal(parseOptions(["--help"]).help, true);
});

test("options reject input that would start a wrong or unbounded run", () => {
  assert.throws(() => parseOptions([]), /exactly one eval suite/);
  assert.throws(() => parseOptions(["a", "b"]), /exactly one eval suite/);
  assert.throws(() => parseOptions(["Demo"]), /lowercase/);
  assert.throws(() => parseOptions(["demo", "--unknown"]), /Unknown option/);
  assert.throws(() => parseOptions(["demo", "--base"]), /requires a value/);
  assert.throws(
    () => parseOptions(["demo", "--base", "--runs"]),
    /requires a value/,
  );
  assert.throws(() => parseOptions(["demo", "--runs", "0"]), /1 to 50/);
  assert.throws(() => parseOptions(["demo", "--runs", "2.5"]), /whole number/);
  assert.throws(() => parseOptions(["demo", "--concurrency", "9"]), /1 to 8/);
  assert.throws(
    () => parseOptions(["demo", "--max-cost-usd", "free"]),
    /positive number/,
  );
  assert.throws(
    () => parseOptions(["demo", "--candidate-only", "--base", "main"]),
    /drop --base/,
  );
});

test("a suite's grants load from suite.json and malformed files are refused", (t) => {
  const plugin = tempDir(t);
  /** @param {string} suite @param {string} content */
  const write = (suite, content) => {
    fs.mkdirSync(path.join(plugin, "evals", suite), { recursive: true });
    fs.writeFileSync(path.join(plugin, "evals", suite, "suite.json"), content);
  };
  write("full", '{"allow_tools": ["Bash", "Write"], "scaffold": true}');
  write("empty", "{}");
  write("broken", "{");
  write("list", "[]");
  write("extra", '{"model": "x"}');
  write("tools", '{"allow_tools": "Bash"}');
  write("blank", '{"allow_tools": [" "]}');
  write("flag", '{"scaffold": "yes"}');
  assert.deepEqual(loadSuite(plugin, "full"), {
    allowTools: ["Bash", "Write"],
    scaffold: true,
  });
  assert.deepEqual(loadSuite(plugin, "empty"), {
    allowTools: [],
    scaffold: false,
  });
  assert.throws(() => loadSuite(plugin, "missing"), /No eval suite "missing"/);
  assert.throws(() => loadSuite(plugin, "broken"), /not valid JSON/);
  assert.throws(() => loadSuite(plugin, "list"), /JSON object/);
  assert.throws(() => loadSuite(plugin, "extra"), /unknown keys: model/);
  assert.throws(() => loadSuite(plugin, "tools"), /list of tool names/);
  assert.throws(() => loadSuite(plugin, "blank"), /list of tool names/);
  assert.throws(() => loadSuite(plugin, "flag"), /true or false/);
});

test("runner arguments request one unpublished arm and put tool grants last", () => {
  const options = parseOptions(["demo"]);
  assert.deepEqual(
    runnerArguments(
      "/snap/plugin",
      "/out/base",
      options,
      { allowTools: [], scaffold: false },
      null,
    ),
    [
      "plugin",
      "eval",
      "/snap/plugin",
      "--tag",
      "demo",
      "--runs",
      "3",
      "--ablation",
      "none",
      "--threshold",
      "0",
      "--trust-plugin",
      "--no-publish",
      "--output-dir",
      "/out/base",
    ],
  );
  const full = runnerArguments(
    "/snap/plugin",
    "/out/base",
    parseOptions([
      "demo",
      "--case",
      "demo-*",
      "--model",
      "claude-test",
      "--judge-model",
      "claude-judge",
      "--concurrency",
      "2",
      "--keep-temp",
    ]),
    { allowTools: ["Bash", "Write"], scaffold: true },
    7.5,
  );
  assert.deepEqual(full.slice(15), [
    "--case",
    "demo-*",
    "--model",
    "claude-test",
    "--judge-model",
    "claude-judge",
    "--max-cost-usd",
    "7.5",
    "--concurrency",
    "2",
    "--scaffold",
    "--keep-temp",
    "--allow-tools",
    "Bash",
    "Write",
  ]);
});

test("a version's summary leaves ungraded runs out of every check", () => {
  const summary = summarizeArm(
    "base",
    result({
      demo: [
        run({ check: true }),
        run({ check: false }, { costUsd: 1.5, durationSeconds: 80 }),
        // An API error leaves no grader results.
        run({}, { error: "rate limited", costUsd: undefined }),
        // A cost ceiling skipped the judge, so the score is not comparable.
        run({ check: true }, { skippedPaidGraders: true }),
      ],
    }),
  );
  assert.deepEqual(summary.cases.get("demo")?.get("check"), {
    passes: 1,
    runs: 2,
  });
  assert.equal(summary.runCount, 4);
  assert.deepEqual(summary.errors, [
    { arm: "base", caseName: "demo", run: 3, error: "rate limited" },
  ]);
  // (0.6 + 1.6 + 0.6) / 3 runs that reported a cost.
  assert.ok(Math.abs((summary.costPerRun || 0) - 2.8 / 3) < 1e-9);
  assert.equal(summary.secondsPerRun, 50);
  assert.equal(summary.partialReason, null);
  assert.equal(
    summarizeArm("base", { partial: true, partialReason: "cost_ceiling" })
      .partialReason,
    "cost_ceiling",
  );
  assert.equal(summarizeArm("base", { partial: true }).costPerRun, null);
});

test("a check changes only when its pass rate moves by more than half its runs", () => {
  /** @param {boolean[]} before @param {boolean[]} after */
  const status = (before, after) =>
    compareResults(
      result({ demo: runsOf(before) }),
      result({ demo: runsOf(after) }),
    ).rows[0];
  assert.equal(
    status([false, false, false], [true, true, true]).status,
    "improved",
  );
  assert.equal(
    status([false, false, true], [true, true, true]).status,
    "improved",
  );
  assert.equal(
    status([true, true, true], [true, false, false]).status,
    "regressed",
  );
  const noisy = status([true, true, false], [true, true, true]);
  assert.equal(noisy.status, "unchanged");
  assert.equal(noisy.unstable, true);
  const steady = status([true, true, true], [true, true, true]);
  assert.equal(steady.status, "unchanged");
  assert.equal(steady.unstable, false);
  // Five runs: three of five is not more than half.
  assert.equal(
    status(
      [false, false, false, false, false],
      [true, true, false, false, false],
    ).status,
    "unchanged",
  );
  assert.equal(
    status(
      [false, false, false, false, false],
      [true, true, true, false, false],
    ).status,
    "improved",
  );
  // Two graded runs are too few for a verdict.
  assert.equal(status([false, false], [true, true]).status, "not-compared");
});

test("the verdict follows the changed checks and totals count compared checks only", () => {
  const base = result({
    one: [
      run({ a: false, b: true, c: true }),
      run({ a: false, b: true, c: true }),
      run({ a: false, b: true, c: true }),
    ],
    gone: runsOf([true, true, true]),
  });
  const better = compareResults(
    base,
    result({
      one: [
        run({ a: true, b: true, c: true }),
        run({ a: true, b: true, c: true }),
        run({ a: true, b: true, c: true }),
      ],
      added: runsOf([true, true, true]),
    }),
  );
  assert.equal(better.verdict, "better");
  assert.deepEqual(better.totals, {
    base: { passes: 6, runs: 9 },
    candidate: { passes: 9, runs: 9 },
  });
  // A case that exists on one version only is listed but never decides.
  assert.deepEqual(
    better.rows
      .filter((row) => row.status === "not-compared")
      .map((row) => `${row.caseName}:${row.base ? "base" : "candidate"}`)
      .sort(),
    ["added:candidate", "gone:base"],
  );

  const mixedCandidate = result({
    one: [
      run({ a: true, b: false, c: true }),
      run({ a: true, b: false, c: true }),
      run({ a: true, b: false, c: true }),
    ],
  });
  assert.equal(compareResults(base, mixedCandidate).verdict, "mixed");
  assert.equal(compareResults(mixedCandidate, base).verdict, "mixed");
  const worseCandidate = result({
    one: [
      run({ a: false, b: false, c: true }),
      run({ a: false, b: false, c: true }),
      run({ a: false, b: false, c: true }),
    ],
  });
  assert.equal(compareResults(base, worseCandidate).verdict, "worse");
  assert.equal(compareResults(base, base).verdict, "no-difference");
});

test("a comparison is incomplete when a run stopped early or nothing is comparable", () => {
  const complete = result({ demo: runsOf([true, true, true]) });
  const partial = compareResults(
    complete,
    result(
      { demo: runsOf([true, true, true]) },
      { partial: true, partialReason: "cost_ceiling" },
    ),
  );
  assert.equal(partial.verdict, "incomplete");
  assert.match(partial.incompleteReason || "", /cost_ceiling/);
  const sparse = compareResults(
    result({ demo: runsOf([true]) }),
    result({ demo: runsOf([true]) }),
  );
  assert.equal(sparse.verdict, "incomplete");
  assert.match(sparse.incompleteReason || "", /3 graded runs/);
});

test("the report leads with the verdict and lists changed, unstable, and skipped checks", () => {
  const comparison = compareResults(
    result({
      demo: [
        run({ fixed: false, broke: true, noisy: true }, { costUsd: 0.4 }),
        run({ fixed: false, broke: true, noisy: false }, { costUsd: 0.4 }),
        run({ fixed: false, broke: true, noisy: true }, { costUsd: 0.4 }),
      ],
      sparse: runsOf([true]),
    }),
    result({
      demo: [
        run({ fixed: true, broke: false, noisy: true }, { error: "timed out" }),
        run({ fixed: true, broke: false, noisy: true }),
        run({ fixed: true, broke: false, noisy: true }),
      ],
      sparse: runsOf([true]),
    }),
  );
  const report = renderComparison("demo-suite", comparison, {
    base: "origin/main (abc12345)",
    candidate: "the working tree at def67890",
    runs: 3,
    reports: ["/out/base/report.html", "/out/candidate/report.html"],
  });
  const lines = report.split("\n");
  assert.equal(lines[0], "# Skill eval: demo-suite");
  assert.equal(
    lines[2],
    "**Verdict: mixed.** 1 check improved and 1 check got worse.",
  );
  assert.match(
    report,
    /Base is origin\/main \(abc12345\)\. Candidate is the working tree at def67890\. Each ran 2 cases 3 times\./,
  );
  assert.match(
    report,
    /\| Checks passed \| 5 of 9 \(56%\) \| 6 of 9 \(67%\) \| \+11 points \|/,
  );
  assert.match(report, /\| Cost per run \| \$0\.53 \| \$0\.60 \| \+14% \|/);
  assert.match(report, /\| `demo` \| `fixed` \| 0\/3 \| 3\/3 \| improved \|/);
  assert.match(report, /\| `demo` \| `broke` \| 3\/3 \| 0\/3 \| got worse \|/);
  assert.match(
    report,
    /## Unstable checks[\s\S]*\| `demo` \| `noisy` \| 2\/3 \| 3\/3 \|/,
  );
  assert.match(
    report,
    /## Not compared[\s\S]*\| `sparse` \| `check` \| 1\/1 \| 1\/1 \|/,
  );
  assert.match(
    report,
    /## Run errors\n\n- candidate, `demo`, run 1: timed out/,
  );
  assert.match(report, /more than half its runs/);
  assert.match(
    report,
    /Full reports: `\/out\/base\/report\.html` and `\/out\/candidate\/report\.html`\n$/,
  );
});

test("each verdict has its own opening sentence", () => {
  const details = {
    base: "base",
    candidate: "candidate",
    runs: 3,
    reports: ["a", "b"],
  };
  /** @param {boolean[]} before @param {boolean[]} after */
  const opening = (before, after) =>
    renderComparison(
      "demo",
      compareResults(
        result({ demo: runsOf(before) }),
        result({ demo: runsOf(after) }),
      ),
      details,
    ).split("\n")[2];
  assert.equal(
    opening([false, false, false], [true, true, true]),
    "**Verdict: better.** 1 check improved and none got worse.",
  );
  assert.equal(
    opening([true, true, true], [false, false, false]),
    "**Verdict: worse.** 1 check got worse and none improved.",
  );
  assert.equal(
    opening([true, true, true], [true, true, true]),
    "**Verdict: no detectable difference.** No check moved by more than half its runs.",
  );
  assert.match(
    opening([true], [true]),
    /^\*\*Verdict: incomplete\.\*\* There is no comparison because no check has 3 graded runs/,
  );
});

test("a candidate-only report lists every check without a verdict", () => {
  const summary = summarizeArm(
    "candidate",
    result(
      { demo: [run({ first: true, second: false })] },
      { partial: true, partialReason: "cost_ceiling" },
    ),
  );
  const report = renderCandidate("demo-suite", summary, {
    candidate: "the working tree at def67890",
    runs: 1,
    reports: ["/out/candidate/report.html"],
  });
  assert.match(
    report,
    /Ran the working tree at def67890 alone, 1 case 1 time\. There is no verdict/,
  );
  assert.match(report, /The run stopped early \(cost_ceiling\)\./);
  assert.match(report, /Checks passed: 1 of 2 \(50%\)\. Cost per run: \$0\.60/);
  assert.match(report, /\| `demo` \| `first` \| 1\/1 \|/);
  assert.match(report, /\| `demo` \| `second` \| 0\/1 \|/);
  assert.doesNotMatch(report, /Verdict/);
});

test("toolchain wrappers are written only for the macOS launcher and forward their arguments", (t) => {
  const root = tempDir(t);
  const toolchain = path.join(root, "toolchain with space");
  fs.mkdirSync(path.join(toolchain, "not-a-tool"), { recursive: true });
  fs.writeFileSync(
    path.join(toolchain, "git"),
    '#!/bin/sh\necho "real git: $*"\n',
    { mode: 0o755 },
  );
  fs.writeFileSync(path.join(toolchain, "notes.txt"), "not executable\n", {
    mode: 0o644,
  });
  const realGit = path.join(toolchain, "git");
  const wrappers = path.join(root, "bin");
  assert.equal(
    toolchainWrapperDir(wrappers, "linux", {}, () => realGit),
    null,
  );
  assert.equal(
    toolchainWrapperDir(wrappers, "darwin", {}, () => null),
    null,
  );
  assert.equal(fs.existsSync(wrappers), false);
  assert.equal(
    toolchainWrapperDir(wrappers, "darwin", {}, () => realGit),
    wrappers,
  );
  assert.deepEqual(fs.readdirSync(wrappers), ["git"]);
  const forwarded = spawnSync(path.join(wrappers, "git"), ["log", "a b"], {
    encoding: "utf8",
  });
  assert.equal(forwarded.stdout, "real git: log a b\n");
  // Without an injected lookup the real one runs; off macOS it finds nothing.
  if (process.platform !== "darwin")
    assert.equal(toolchainWrapperDir(wrappers, "darwin", {}), null);
});

/**
 * Builds a Git repository holding a tiny plugin whose only skill says OLD,
 * then changes the working tree: the skill says NEW and an untracked eval
 * suite appears. The fake runner passes its one check when the skill it was
 * given says NEW, so the base fails it and the candidate passes it.
 *
 * @param {import("node:test").TestContext} t
 */
function comparisonSandbox(t) {
  const root = fs.realpathSync(tempDir(t));
  const plugin = path.join(root, "plugin");
  /** @param {string[]} args */
  const git = (args) => {
    const done = spawnSync("git", args, { cwd: root, encoding: "utf8" });
    assert.equal(done.status, 0, done.stderr);
    return done.stdout.trim();
  };
  /** @param {string} relative @param {string} content @param {number} [mode] */
  const write = (relative, content, mode = 0o644) => {
    const file = path.join(root, relative);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, content, { mode });
  };
  git(["init", "--quiet", "--initial-branch=main"]);
  git(["config", "user.name", "Test"]);
  git(["config", "user.email", "test@example.invalid"]);
  git(["config", "commit.gpgsign", "false"]);
  write("plugin/skills/demo/SKILL.md", "OLD\n");
  write("plugin/evals/stale/prompt.md", "A case only the base commit has.\n");
  write(".gitignore", "ignored/\n");
  git(["add", "--all"]);
  git(["commit", "--quiet", "--message", "Base"]);
  const baseSha = git(["rev-parse", "HEAD"]);

  write("plugin/skills/demo/SKILL.md", "NEW\n");
  write("plugin/ignored/secret.txt", "never copied\n");
  write(
    "plugin/evals/demo-suite/suite.json",
    '{"allow_tools": ["Bash"], "scaffold": true}\n',
  );
  write("plugin/evals/demo-suite/demo-case/prompt.md", "Do the thing.\n");
  write("plugin/evals/demo-suite/demo-case/scaffold.sh", "#!/bin/sh\n", 0o755);
  fs.rmSync(path.join(plugin, "evals", "stale"), { recursive: true });

  const fake = path.join(root, "fake-claude.js");
  write(
    "fake-claude.js",
    `#!/usr/bin/env node
const fs = require("node:fs");
const path = require("node:path");
const args = process.argv.slice(2);
const pluginPath = args[2];
const out = args[args.indexOf("--output-dir") + 1];
const read = (relative) => {
  try { return fs.readFileSync(path.join(pluginPath, relative), "utf8"); } catch { return null; }
};
const scaffold = path.join(pluginPath, "evals/demo-suite/demo-case/scaffold.sh");
fs.mkdirSync(out, { recursive: true });
fs.writeFileSync(path.join(out, "seen.json"), JSON.stringify({
  args,
  pathHead: (process.env.PATH || "").split(path.delimiter)[0],
  staleCase: read("evals/stale/prompt.md") !== null,
  ignored: read("ignored/secret.txt") !== null,
  scaffoldExecutable: fs.existsSync(scaffold) && (fs.statSync(scaffold).mode & 0o111) !== 0,
}));
if (process.env.FAKE_CLAUDE_MODE === "silent") process.exit(1);
process.exitCode = process.env.FAKE_CLAUDE_MODE === "complains" ? 1 : 0;
const passed = (read("skills/demo/SKILL.md") || "").includes("NEW");
const run = { costUsd: 0.2, durationSeconds: 10, error: null, graders: [{ name: "says-new", passed }] };
fs.writeFileSync(path.join(out, "aggregate-result.json"), JSON.stringify({
  partial: process.env.FAKE_CLAUDE_MODE === "partial",
  partialReason: "cost_ceiling",
  cases: [{ name: "demo-case", arms: { with: [run, run, run] } }],
}));
`,
    0o755,
  );
  return { root, plugin, baseSha, fake };
}

/**
 * @param {ReturnType<typeof comparisonSandbox>} sandbox
 * @param {string[]} argv
 * @param {Record<string, string>} [extraEnv]
 */
function runMain(sandbox, argv, extraEnv = {}) {
  /** @type {string[]} */
  const printed = [];
  const exitCode = main(argv, {
    pluginDir: sandbox.plugin,
    env: {
      ...process.env,
      SKILL_EVAL_CLAUDE_BIN: sandbox.fake,
      ...extraEnv,
    },
    platform: "linux",
    print: (text) => printed.push(text),
    now: () => new Date("2026-11-11T10:00:00.000Z"),
  });
  return { exitCode, output: printed.join("") };
}

/** @param {string} file */
function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

test("a comparison runs the candidate's cases against the base commit and the working tree", (t) => {
  const sandbox = comparisonSandbox(t);
  const { exitCode, output } = runMain(sandbox, [
    "demo-suite",
    "--base",
    "HEAD",
    "--max-cost-usd",
    "10",
  ]);
  assert.equal(exitCode, 0);
  assert.match(
    output,
    /\*\*Verdict: better\.\*\* 1 check improved and none got worse\./,
  );
  assert.match(
    output,
    new RegExp(
      `Base is HEAD \\(${sandbox.baseSha.slice(0, 8)}\\)\\. Candidate is the working tree at ${sandbox.baseSha.slice(0, 7)}[0-9a-f]* with uncommitted changes\\.`,
    ),
  );
  assert.match(
    output,
    /\| `demo-case` \| `says-new` \| 0\/3 \| 3\/3 \| improved \|/,
  );

  const out = path.join(
    sandbox.root,
    ".context",
    "skill-evals",
    "demo-suite",
    "2026-11-11T10-00-00-000Z",
  );
  assert.equal(
    fs.readFileSync(path.join(out, "comparison.md"), "utf8"),
    output,
  );
  const saved = readJson(path.join(out, "comparison.json"));
  assert.equal(saved.verdict, "better");
  assert.equal(saved.base.sha, sandbox.baseSha);
  assert.deepEqual(saved.totals, {
    base: { passes: 0, runs: 3 },
    candidate: { passes: 3, runs: 3 },
  });

  const base = readJson(path.join(out, "base", "seen.json"));
  const candidate = readJson(path.join(out, "candidate", "seen.json"));
  // Both versions get the candidate's cases, so the base's own are gone.
  assert.equal(base.staleCase, false);
  assert.equal(base.scaffoldExecutable, true);
  assert.equal(candidate.scaffoldExecutable, true);
  // Ignored files never reach a snapshot.
  assert.equal(candidate.ignored, false);
  // The cost ceiling is split between the two versions.
  assert.deepEqual(base.args.slice(-5), [
    "--max-cost-usd",
    "5",
    "--scaffold",
    "--allow-tools",
    "Bash",
  ]);
  assert.deepEqual(base.args.slice(3, 5), ["--tag", "demo-suite"]);
  assert.notEqual(base.args[2], candidate.args[2]);
  // The snapshots are removed once the comparison is written.
  assert.equal(fs.existsSync(base.args[2]), false);
  assert.equal(fs.existsSync(candidate.args[2]), false);
});

test("candidate-only runs skip the base and report without a verdict", (t) => {
  const sandbox = comparisonSandbox(t);
  const out = path.join(sandbox.root, "results");
  const { exitCode, output } = runMain(sandbox, [
    "demo-suite",
    "--candidate-only",
    "--runs",
    "1",
    "--out",
    out,
  ]);
  assert.equal(exitCode, 0);
  assert.match(output, /There is no verdict without a base version\./);
  assert.match(output, /\| `demo-case` \| `says-new` \| 3\/3 \|/);
  assert.equal(fs.existsSync(path.join(out, "base")), false);
  assert.equal(fs.existsSync(path.join(out, "comparison.json")), false);
});

test("an early stop exits 2 and a runner that writes nothing is an error", (t) => {
  const sandbox = comparisonSandbox(t);
  const stopped = runMain(sandbox, ["demo-suite", "--base", "HEAD"], {
    FAKE_CLAUDE_MODE: "partial",
  });
  assert.equal(stopped.exitCode, 2);
  assert.match(stopped.output, /\*\*Verdict: incomplete\.\*\*/);
  const candidateOnly = runMain(sandbox, ["demo-suite", "--candidate-only"], {
    FAKE_CLAUDE_MODE: "partial",
  });
  assert.equal(candidateOnly.exitCode, 2);
  // The runner fails when a case does not load; the report must say so.
  const complained = runMain(sandbox, ["demo-suite", "--base", "HEAD"], {
    FAKE_CLAUDE_MODE: "complains",
  });
  assert.equal(complained.exitCode, 2);
  assert.match(complained.output, /\*\*Verdict: better\.\*\*/);
  assert.match(
    complained.output,
    /Warning: `claude plugin eval` exited 1 for the base version: a case failed to load or a run ended on an error\./,
  );
  assert.match(complained.output, /exited 1 for the candidate version/);
  const complainedAlone = runMain(sandbox, ["demo-suite", "--candidate-only"], {
    FAKE_CLAUDE_MODE: "complains",
  });
  assert.equal(complainedAlone.exitCode, 2);
  assert.match(
    complainedAlone.output,
    /Warning: `claude plugin eval` exited 1/,
  );
  assert.throws(
    () =>
      runMain(sandbox, ["demo-suite", "--base", "HEAD"], {
        FAKE_CLAUDE_MODE: "silent",
      }),
    /wrote no result for the base version \(exit 1\)/,
  );
  assert.throws(
    () =>
      runMain(sandbox, ["demo-suite"], {
        SKILL_EVAL_CLAUDE_BIN: path.join(sandbox.root, "missing-claude"),
      }),
    /Could not find where this branch left origin\/main\. Pass --base <ref>\./,
  );
  assert.throws(
    () =>
      runMain(sandbox, ["demo-suite", "--base", "HEAD"], {
        SKILL_EVAL_CLAUDE_BIN: path.join(sandbox.root, "missing-claude"),
      }),
    /Could not start .*missing-claude/,
  );
  assert.throws(
    () => runMain(sandbox, ["demo-suite", "--base", "no-such-ref"]),
    /--base no-such-ref is not a commit in this repository\./,
  );
});

test("help prints the usage text without touching the repository", () => {
  /** @type {string[]} */
  const printed = [];
  assert.equal(main(["--help"], { print: (text) => printed.push(text) }), 0);
  assert.match(
    printed.join(""),
    /^Usage: node scripts\/skill-eval-compare\.js <suite>/,
  );
});
