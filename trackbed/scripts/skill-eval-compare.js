#!/usr/bin/env node
// @ts-check
"use strict";

// Runs one eval suite against two versions of this plugin with
// `claude plugin eval` and reports which checks changed. The base version is a
// Git commit, the candidate is the working tree, and both run the candidate's
// cases so the only difference between the two sets of runs is the plugin.

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const PLUGIN_DIR = path.resolve(__dirname, "..");
const EVAL_DIR = "evals";
const DEFAULT_BASE_BRANCH = "origin/main";
const DEFAULT_RUNS = 3;
// With fewer runs than this, one stray result decides a check.
const MIN_RUNS_FOR_VERDICT = 3;
// A check counts as changed when its pass rate moves by more than this.
const CHANGE_THRESHOLD = 0.5;
const USAGE = `Usage: node scripts/skill-eval-compare.js <suite> [options]

Runs evals/<suite>/ against a base commit and the working tree, then reports
which checks improved, got worse, or stayed within noise.

Options:
  --base <ref>           Base commit (default: merge-base of HEAD and ${DEFAULT_BASE_BRANCH})
  --candidate-only       Run the working tree alone and list its check results
  --runs <n>             Runs per case per version, 1-50 (default: ${DEFAULT_RUNS})
  --case <glob>          Only run cases whose name matches
  --model <model>        Model for the runs under test
  --judge-model <model>  Model for llm graders
  --max-cost-usd <usd>   Cost ceiling for the whole comparison, split across versions
  --concurrency <n>      Parallel runs, 1-8 (default: 1)
  --out <dir>            Output directory (default: .context/skill-evals/<suite>/<time>/)
  --keep-temp            Keep the plugin snapshots and each run's sandbox directory
  --help                 Show this message`;

/**
 * @typedef {Object} Options
 * @property {string} suite
 * @property {string | null} base
 * @property {boolean} candidateOnly
 * @property {number} runs
 * @property {string | null} caseGlob
 * @property {string | null} model
 * @property {string | null} judgeModel
 * @property {number | null} maxCostUsd
 * @property {number} concurrency
 * @property {string | null} out
 * @property {boolean} keepTemp
 * @property {boolean} help
 *
 * @typedef {{ allowTools: string[], scaffold: boolean }} Suite
 * @typedef {{ passes: number, runs: number }} Tally
 * @typedef {{ arm: string, caseName: string, run: number, error: string }} RunError
 *
 * @typedef {Object} ArmSummary
 * @property {Map<string, Map<string, Tally>>} cases Check tallies by case name.
 * @property {number | null} costPerRun
 * @property {number | null} secondsPerRun
 * @property {number} runCount
 * @property {RunError[]} errors
 * @property {string | null} partialReason
 *
 * @typedef {"improved" | "regressed" | "unchanged" | "not-compared"} CheckStatus
 * @typedef {Object} CheckRow
 * @property {string} caseName
 * @property {string} check
 * @property {Tally | null} base
 * @property {Tally | null} candidate
 * @property {CheckStatus} status
 * @property {boolean} unstable
 *
 * @typedef {"better" | "worse" | "mixed" | "no-difference" | "incomplete"} Verdict
 * @typedef {Object} Comparison
 * @property {Verdict} verdict
 * @property {string | null} incompleteReason
 * @property {CheckRow[]} rows
 * @property {{ base: Tally, candidate: Tally }} totals Over compared checks only.
 * @property {ArmSummary} base
 * @property {ArmSummary} candidate
 *
 * @typedef {Object} Dependencies
 * @property {string} [pluginDir]
 * @property {NodeJS.ProcessEnv} [env]
 * @property {NodeJS.Platform} [platform]
 * @property {(text: string) => void} [print]
 * @property {() => Date} [now]
 */

/**
 * @param {string[]} argv
 * @returns {Options}
 */
function parseOptions(argv) {
  const switches = new Set(["--candidate-only", "--keep-temp", "--help"]);
  const valued = new Set([
    "--base",
    "--runs",
    "--case",
    "--model",
    "--judge-model",
    "--max-cost-usd",
    "--concurrency",
    "--out",
  ]);
  /** @type {Map<string, string>} */
  const values = new Map();
  /** @type {Set<string>} */
  const flags = new Set();
  /** @type {string[]} */
  const positional = [];
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (switches.has(argument)) flags.add(argument);
    else if (valued.has(argument)) {
      const value = argv[(index += 1)];
      if (value === undefined || value.startsWith("--"))
        throw new Error(`${argument} requires a value. Use --help.`);
      values.set(argument, value);
    } else if (argument.startsWith("--"))
      throw new Error(`Unknown option ${argument}. Use --help.`);
    else positional.push(argument);
  }
  const help = flags.has("--help");
  if (!help && positional.length !== 1)
    throw new Error("Name exactly one eval suite. Use --help.");
  const suite = positional[0] || "";
  if (!help && !/^[a-z][a-z0-9-]*$/.test(suite))
    throw new Error(
      `Suite name "${suite}" must be lowercase letters, digits, and hyphens.`,
    );
  const candidateOnly = flags.has("--candidate-only");
  if (candidateOnly && values.has("--base"))
    throw new Error("--candidate-only runs no base; drop --base.");
  const maxCost = values.get("--max-cost-usd");
  return {
    suite,
    base: values.get("--base") || null,
    candidateOnly,
    runs: integerOption(values, "--runs", DEFAULT_RUNS, 1, 50),
    caseGlob: values.get("--case") || null,
    model: values.get("--model") || null,
    judgeModel: values.get("--judge-model") || null,
    maxCostUsd: maxCost === undefined ? null : positiveNumber(maxCost),
    concurrency: integerOption(values, "--concurrency", 1, 1, 8),
    out: values.get("--out") || null,
    keepTemp: flags.has("--keep-temp"),
    help,
  };
}

/**
 * @param {Map<string, string>} values
 * @param {string} name
 * @param {number} fallback
 * @param {number} minimum
 * @param {number} maximum
 */
function integerOption(values, name, fallback, minimum, maximum) {
  const raw = values.get(name);
  if (raw === undefined) return fallback;
  const value = Number(raw);
  if (!Number.isInteger(value) || value < minimum || value > maximum)
    throw new Error(
      `${name} must be a whole number from ${minimum} to ${maximum}.`,
    );
  return value;
}

/** @param {string} raw */
function positiveNumber(raw) {
  const value = Number(raw);
  if (!Number.isFinite(value) || value <= 0)
    throw new Error("--max-cost-usd must be a positive number.");
  return value;
}

/**
 * Reads the operator grants a suite needs. They live beside the cases because
 * `claude plugin eval` never lets a case widen its own tool or script access.
 *
 * @param {string} pluginDir
 * @param {string} suite
 * @returns {Suite}
 */
function loadSuite(pluginDir, suite) {
  const file = path.join(pluginDir, EVAL_DIR, suite, "suite.json");
  if (!fs.existsSync(file))
    throw new Error(
      `No eval suite "${suite}": ${path.relative(pluginDir, file)} is missing.`,
    );
  /** @type {unknown} */
  let parsed;
  try {
    parsed = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    throw new Error(`${file} is not valid JSON.`);
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed))
    throw new Error(`${file} must hold a JSON object.`);
  const config = /** @type {Record<string, unknown>} */ (parsed);
  const unknown = Object.keys(config).filter(
    (key) => key !== "allow_tools" && key !== "scaffold",
  );
  if (unknown.length)
    throw new Error(`${file} has unknown keys: ${unknown.join(", ")}.`);
  const allowTools = config.allow_tools === undefined ? [] : config.allow_tools;
  if (
    !Array.isArray(allowTools) ||
    !allowTools.every((tool) => typeof tool === "string" && tool.trim() !== "")
  )
    throw new Error(`${file}: allow_tools must be a list of tool names.`);
  const scaffold = config.scaffold === undefined ? false : config.scaffold;
  if (typeof scaffold !== "boolean")
    throw new Error(`${file}: scaffold must be true or false.`);
  return { allowTools, scaffold };
}

/**
 * @param {string[]} args
 * @param {string} cwd
 * @returns {string}
 */
function git(args, cwd) {
  const result = spawnSync("git", args, {
    cwd,
    encoding: "utf8",
    maxBuffer: 1 << 28,
  });
  if (result.status !== 0)
    throw new Error(
      `git ${args[0]} failed: ${(result.stderr || "").trim() || "no output"}`,
    );
  return result.stdout;
}

/**
 * @param {string} repoRoot
 * @param {string | null} requested
 * @returns {{ label: string, sha: string }}
 */
function resolveBase(repoRoot, requested) {
  if (requested) {
    try {
      const sha = git(
        ["rev-parse", "--verify", "--quiet", `${requested}^{commit}`],
        repoRoot,
      );
      return { label: requested, sha: sha.trim() };
    } catch {
      throw new Error(
        `--base ${requested} is not a commit in this repository.`,
      );
    }
  }
  try {
    const sha = git(["merge-base", "HEAD", DEFAULT_BASE_BRANCH], repoRoot);
    return { label: `merge-base with ${DEFAULT_BASE_BRANCH}`, sha: sha.trim() };
  } catch {
    throw new Error(
      `Could not find where this branch left ${DEFAULT_BASE_BRANCH}. Pass --base <ref>.`,
    );
  }
}

/**
 * @param {string} source
 * @param {string} target
 */
function copyEntry(source, target) {
  const stat = fs.lstatSync(source);
  if (stat.isSymbolicLink()) {
    fs.symlinkSync(fs.readlinkSync(source), target);
  } else if (stat.isDirectory()) {
    fs.mkdirSync(target, { recursive: true });
    for (const name of fs.readdirSync(source))
      copyEntry(path.join(source, name), path.join(target, name));
  } else if (stat.isFile()) {
    fs.copyFileSync(source, target);
    fs.chmodSync(target, stat.mode);
  }
}

/**
 * Copies the plugin as it is on disk: tracked and untracked files, without
 * ignored ones, so uncommitted edits are part of the candidate.
 *
 * @param {string} repoRoot
 * @param {string} pluginRel
 * @param {string} destination
 */
function snapshotWorkingTree(repoRoot, pluginRel, destination) {
  const listing = git(
    [
      "ls-files",
      "-z",
      "--cached",
      "--others",
      "--exclude-standard",
      "--",
      pluginRel,
    ],
    repoRoot,
  );
  for (const relative of listing.split("\0")) {
    if (!relative) continue;
    const source = path.join(repoRoot, relative);
    // A tracked file deleted from the working tree is still listed.
    if (!fs.existsSync(source) && !isSymlink(source)) continue;
    const target = path.join(destination, relative);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    copyEntry(source, target);
  }
}

/** @param {string} file */
function isSymlink(file) {
  try {
    return fs.lstatSync(file).isSymbolicLink();
  } catch {
    return false;
  }
}

/**
 * @param {string} repoRoot
 * @param {string} pluginRel
 * @param {string} sha
 * @param {string} destination
 */
function snapshotCommit(repoRoot, pluginRel, sha, destination) {
  const archive = spawnSync(
    "git",
    ["archive", "--format=tar", sha, "--", pluginRel],
    { cwd: repoRoot, maxBuffer: 1 << 30 },
  );
  if (archive.status !== 0)
    throw new Error(
      `The base commit has no ${pluginRel}/ directory to evaluate: ${String(archive.stderr).trim()}`,
    );
  fs.mkdirSync(destination, { recursive: true });
  const extract = spawnSync("tar", ["-x", "-f", "-", "-C", destination], {
    input: archive.stdout,
  });
  if (extract.status !== 0)
    throw new Error(
      `Could not unpack the base commit: ${String(extract.stderr).trim()}`,
    );
}

/** @param {string} value */
function shellQuote(value) {
  return `'${value.replace(/'/g, "'\\''")}'`;
}

/** @param {string} value */
function firstLine(value) {
  return value.split("\n")[0].trim();
}

/**
 * Finds the Git binary behind the macOS launcher at /usr/bin/git, or null when
 * the Git on PATH is not that launcher.
 *
 * @param {NodeJS.ProcessEnv} env
 * @returns {string | null}
 */
function gitBehindLauncher(env) {
  const which = spawnSync("/usr/bin/which", ["git"], { env, encoding: "utf8" });
  if (which.status !== 0 || firstLine(which.stdout) !== "/usr/bin/git")
    return null;
  const xcrun = spawnSync("/usr/bin/xcrun", ["--find", "git"], {
    env,
    encoding: "utf8",
  });
  const realGit = xcrun.status === 0 ? firstLine(xcrun.stdout) : "";
  return realGit && realGit !== "/usr/bin/git" ? realGit : null;
}

/**
 * On macOS, /usr/bin/git and the other developer tools there are launchers
 * that need a cache directory the eval sandbox denies, so sandboxed shell
 * commands cannot run Git at all. When that launcher is the Git on PATH, write
 * a wrapper for each program in the real toolchain directory (Git also starts
 * helpers such as git-upload-pack from PATH) and return the wrapper directory
 * so the caller can put it first on PATH.
 *
 * @param {string} directory
 * @param {NodeJS.Platform} platform
 * @param {NodeJS.ProcessEnv} env
 * @param {(env: NodeJS.ProcessEnv) => string | null} [findGit]
 * @returns {string | null}
 */
function toolchainWrapperDir(
  directory,
  platform,
  env,
  findGit = gitBehindLauncher,
) {
  if (platform !== "darwin") return null;
  const realGit = findGit(env);
  if (!realGit) return null;
  const toolchain = path.dirname(realGit);
  fs.mkdirSync(directory, { recursive: true });
  for (const name of fs.readdirSync(toolchain)) {
    const tool = path.join(toolchain, name);
    try {
      fs.accessSync(tool, fs.constants.X_OK);
      if (!fs.statSync(tool).isFile()) continue;
    } catch {
      continue;
    }
    fs.writeFileSync(
      path.join(directory, name),
      `#!/bin/sh\nexec ${shellQuote(tool)} "$@"\n`,
      { mode: 0o755 },
    );
  }
  return directory;
}

/**
 * @param {string} pluginPath
 * @param {string} outputDir
 * @param {Options} options
 * @param {Suite} suite
 * @param {number | null} costCeiling
 * @returns {string[]}
 */
function runnerArguments(pluginPath, outputDir, options, suite, costCeiling) {
  const args = [
    "plugin",
    "eval",
    pluginPath,
    "--tag",
    options.suite,
    "--runs",
    String(options.runs),
    // One arm per version: the comparison here is base against candidate, not
    // plugin against no plugin.
    "--ablation",
    "none",
    // A failing check is a result to report, not a failed command.
    "--threshold",
    "0",
    "--trust-plugin",
    "--no-publish",
    "--output-dir",
    outputDir,
  ];
  if (options.caseGlob) args.push("--case", options.caseGlob);
  if (options.model) args.push("--model", options.model);
  if (options.judgeModel) args.push("--judge-model", options.judgeModel);
  if (costCeiling !== null) args.push("--max-cost-usd", String(costCeiling));
  if (options.concurrency > 1)
    args.push("--concurrency", String(options.concurrency));
  if (suite.scaffold) args.push("--scaffold");
  if (options.keepTemp) args.push("--keep-temp");
  // --allow-tools takes a list, so it goes last.
  if (suite.allowTools.length) args.push("--allow-tools", ...suite.allowTools);
  return args;
}

/**
 * @param {string} arm
 * @param {string[]} args
 * @param {string} outputDir
 * @param {NodeJS.ProcessEnv} env
 * @returns {{ result: any, problem: string | null }}
 */
function runArm(arm, args, outputDir, env) {
  const command = env.SKILL_EVAL_CLAUDE_BIN || "claude";
  const file = path.join(outputDir, "aggregate-result.json");
  // A result left by an earlier run into the same directory is not this run's.
  fs.rmSync(file, { force: true });
  // The runner's progress goes to stderr so stdout carries only the report.
  const result = spawnSync(command, args, {
    env,
    stdio: ["ignore", process.stderr, process.stderr],
  });
  if (result.error)
    throw new Error(`Could not start ${command}: ${result.error.message}`);
  if (!fs.existsSync(file))
    throw new Error(
      `claude plugin eval wrote no result for the ${arm} version (exit ${result.status}). Its output above says why.`,
    );
  const parsed = JSON.parse(fs.readFileSync(file, "utf8"));
  // With a zero threshold the runner only fails when something went wrong. An
  // early stop is already part of the result, so it is not repeated here.
  const problem =
    result.status !== 0 && !parsed.partial
      ? `\`claude plugin eval\` exited ${result.status} for the ${arm} version: a case failed to load or a run ended on an error. Its output has the details, and the figures below cover only what ran.`
      : null;
  return { result: parsed, problem };
}

/** @param {number[]} values */
function mean(values) {
  return values.length
    ? values.reduce((sum, value) => sum + value, 0) / values.length
    : null;
}

/**
 * Tallies every check of one version from a `claude plugin eval` result.
 * A run that ended on an API error has no grader results, and a run whose
 * judge graders were skipped at the cost ceiling is not comparable, so neither
 * counts toward a check.
 *
 * @param {string} arm
 * @param {any} result
 * @returns {ArmSummary}
 */
function summarizeArm(arm, result) {
  /** @type {Map<string, Map<string, Tally>>} */
  const cases = new Map();
  /** @type {number[]} */
  const costs = [];
  /** @type {number[]} */
  const seconds = [];
  /** @type {RunError[]} */
  const errors = [];
  let runCount = 0;
  for (const entry of Array.isArray(result.cases) ? result.cases : []) {
    /** @type {Map<string, Tally>} */
    const checks = new Map();
    const runs = (entry.arms && entry.arms.with) || [];
    runs.forEach((/** @type {any} */ run, /** @type {number} */ index) => {
      runCount += 1;
      if (typeof run.costUsd === "number")
        costs.push(run.costUsd + (run.judgeCostUsd || 0));
      if (typeof run.durationSeconds === "number")
        seconds.push(run.durationSeconds);
      if (run.error)
        errors.push({
          arm,
          caseName: entry.name,
          run: index + 1,
          error: String(run.error),
        });
      const graders = Array.isArray(run.graders) ? run.graders : [];
      if (!graders.length || run.skippedPaidGraders) return;
      for (const grader of graders) {
        const tally = checks.get(grader.name) || { passes: 0, runs: 0 };
        tally.runs += 1;
        if (grader.passed) tally.passes += 1;
        checks.set(grader.name, tally);
      }
    });
    cases.set(entry.name, checks);
  }
  return {
    cases,
    costPerRun: mean(costs),
    secondsPerRun: mean(seconds),
    runCount,
    errors,
    partialReason: result.partial
      ? String(result.partialReason || "stopped early")
      : null,
  };
}

/** @param {Tally} tally */
function isUnstable(tally) {
  return tally.passes > 0 && tally.passes < tally.runs;
}

/**
 * @param {any} baseResult
 * @param {any} candidateResult
 * @returns {Comparison}
 */
function compareResults(baseResult, candidateResult) {
  const base = summarizeArm("base", baseResult);
  const candidate = summarizeArm("candidate", candidateResult);
  /** @type {CheckRow[]} */
  const rows = [];
  const totals = {
    base: { passes: 0, runs: 0 },
    candidate: { passes: 0, runs: 0 },
  };
  const caseNames = new Set([...candidate.cases.keys(), ...base.cases.keys()]);
  for (const caseName of caseNames) {
    const baseChecks = base.cases.get(caseName) || new Map();
    const candidateChecks = candidate.cases.get(caseName) || new Map();
    const checkNames = new Set([
      ...candidateChecks.keys(),
      ...baseChecks.keys(),
    ]);
    for (const check of checkNames) {
      const before = baseChecks.get(check) || null;
      const after = candidateChecks.get(check) || null;
      /** @type {CheckStatus} */
      let status = "not-compared";
      if (
        before &&
        after &&
        before.runs >= MIN_RUNS_FOR_VERDICT &&
        after.runs >= MIN_RUNS_FOR_VERDICT
      ) {
        const change = after.passes / after.runs - before.passes / before.runs;
        status =
          change > CHANGE_THRESHOLD
            ? "improved"
            : change < -CHANGE_THRESHOLD
              ? "regressed"
              : "unchanged";
        totals.base.passes += before.passes;
        totals.base.runs += before.runs;
        totals.candidate.passes += after.passes;
        totals.candidate.runs += after.runs;
      }
      rows.push({
        caseName,
        check,
        base: before,
        candidate: after,
        status,
        unstable:
          (before !== null && isUnstable(before)) ||
          (after !== null && isUnstable(after)),
      });
    }
  }
  const improved = rows.filter((row) => row.status === "improved").length;
  const regressed = rows.filter((row) => row.status === "regressed").length;
  const partial = base.partialReason || candidate.partialReason;
  /** @type {Verdict} */
  let verdict = "no-difference";
  /** @type {string | null} */
  let incompleteReason = null;
  if (partial) {
    verdict = "incomplete";
    incompleteReason = `a run stopped early (${partial})`;
  } else if (!totals.base.runs) {
    verdict = "incomplete";
    incompleteReason = `no check has ${MIN_RUNS_FOR_VERDICT} graded runs on both versions`;
  } else if (improved && regressed) verdict = "mixed";
  else if (improved) verdict = "better";
  else if (regressed) verdict = "worse";
  return { verdict, incompleteReason, rows, totals, base, candidate };
}

/** @param {Tally | null} tally */
function formatTally(tally) {
  return tally ? `${tally.passes}/${tally.runs}` : "not run";
}

/** @param {Tally} tally */
function formatShare(tally) {
  if (!tally.runs) return "none";
  const percent = Math.round((tally.passes / tally.runs) * 100);
  return `${tally.passes} of ${tally.runs} (${percent}%)`;
}

/** @param {number | null} value */
function formatCost(value) {
  return value === null ? "unknown" : `$${value.toFixed(2)}`;
}

/** @param {number | null} value */
function formatSeconds(value) {
  return value === null ? "unknown" : `${Math.round(value)} s`;
}

/**
 * @param {number | null} before
 * @param {number | null} after
 */
function formatRelativeChange(before, after) {
  if (before === null || after === null || before === 0) return "";
  const percent = Math.round(((after - before) / before) * 100);
  return `${percent > 0 ? "+" : ""}${percent}%`;
}

/**
 * @param {number} count
 * @param {string} noun
 */
function countOf(count, noun) {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

/**
 * @param {Comparison} comparison
 * @returns {string}
 */
function verdictSentence(comparison) {
  const improved = comparison.rows.filter(
    (row) => row.status === "improved",
  ).length;
  const regressed = comparison.rows.filter(
    (row) => row.status === "regressed",
  ).length;
  switch (comparison.verdict) {
    case "better":
      return `**Verdict: better.** ${countOf(improved, "check")} improved and none got worse.`;
    case "worse":
      return `**Verdict: worse.** ${countOf(regressed, "check")} got worse and none improved.`;
    case "mixed":
      return `**Verdict: mixed.** ${countOf(improved, "check")} improved and ${countOf(regressed, "check")} got worse.`;
    case "incomplete":
      return `**Verdict: incomplete.** There is no comparison because ${comparison.incompleteReason}.`;
    default:
      return "**Verdict: no detectable difference.** No check moved by more than half its runs.";
  }
}

/**
 * @param {string[]} header
 * @param {string[][]} rows
 */
function markdownTable(header, rows) {
  return [
    `| ${header.join(" | ")} |`,
    `| ${header.map(() => "---").join(" | ")} |`,
    ...rows.map((row) => `| ${row.join(" | ")} |`),
  ].join("\n");
}

/** @param {string[] | undefined} problems */
function renderProblems(problems) {
  return (problems || []).flatMap((problem) => [`Warning: ${problem}`, ""]);
}

/** @param {RunError[]} errors */
function renderErrors(errors) {
  if (!errors.length) return [];
  return [
    "## Run errors",
    "",
    ...errors.map(
      (error) =>
        `- ${error.arm}, \`${error.caseName}\`, run ${error.run}: ${error.error}`,
    ),
    "",
  ];
}

/**
 * @param {string} suite
 * @param {Comparison} comparison
 * @param {{ base: string, candidate: string, runs: number, reports: string[], problems?: string[] }} details
 * @returns {string}
 */
function renderComparison(suite, comparison, details) {
  const { base, candidate, totals, rows } = comparison;
  const changed = rows.filter(
    (row) => row.status === "improved" || row.status === "regressed",
  );
  const unstable = rows.filter(
    (row) => row.unstable && row.status === "unchanged",
  );
  const notCompared = rows.filter((row) => row.status === "not-compared");
  const pointChange =
    totals.base.runs && totals.candidate.runs
      ? Math.round(
          (totals.candidate.passes / totals.candidate.runs -
            totals.base.passes / totals.base.runs) *
            100,
        )
      : null;
  const lines = [
    `# Skill eval: ${suite}`,
    "",
    verdictSentence(comparison),
    "",
    ...renderProblems(details.problems),
    `Base is ${details.base}. Candidate is ${details.candidate}. Each ran ${countOf(candidate.cases.size, "case")} ${details.runs} time${details.runs === 1 ? "" : "s"}.`,
    "",
    markdownTable(
      ["", "Base", "Candidate", "Change"],
      [
        [
          "Checks passed",
          formatShare(totals.base),
          formatShare(totals.candidate),
          pointChange === null
            ? ""
            : `${pointChange > 0 ? "+" : ""}${pointChange} points`,
        ],
        [
          "Cost per run",
          formatCost(base.costPerRun),
          formatCost(candidate.costPerRun),
          formatRelativeChange(base.costPerRun, candidate.costPerRun),
        ],
        [
          "Time per run",
          formatSeconds(base.secondsPerRun),
          formatSeconds(candidate.secondsPerRun),
          formatRelativeChange(base.secondsPerRun, candidate.secondsPerRun),
        ],
      ],
    ),
    "",
  ];
  if (changed.length)
    lines.push(
      "## Checks that changed",
      "",
      markdownTable(
        ["Case", "Check", "Base", "Candidate", "Result"],
        changed.map((row) => [
          `\`${row.caseName}\``,
          `\`${row.check}\``,
          formatTally(row.base),
          formatTally(row.candidate),
          row.status === "improved" ? "improved" : "got worse",
        ]),
      ),
      "",
    );
  if (unstable.length)
    lines.push(
      "## Unstable checks",
      "",
      "These passed in some runs and failed in others on the same version, and did not move enough to count as changed.",
      "",
      markdownTable(
        ["Case", "Check", "Base", "Candidate"],
        unstable.map((row) => [
          `\`${row.caseName}\``,
          `\`${row.check}\``,
          formatTally(row.base),
          formatTally(row.candidate),
        ]),
      ),
      "",
    );
  if (notCompared.length)
    lines.push(
      "## Not compared",
      "",
      `These checks have fewer than ${MIN_RUNS_FOR_VERDICT} graded runs on one of the versions.`,
      "",
      markdownTable(
        ["Case", "Check", "Base", "Candidate"],
        notCompared.map((row) => [
          `\`${row.caseName}\``,
          `\`${row.check}\``,
          formatTally(row.base),
          formatTally(row.candidate),
        ]),
      ),
      "",
    );
  lines.push(...renderErrors([...base.errors, ...candidate.errors]));
  lines.push(
    "A check counts as changed when its pass rate moves by more than half its runs. Smaller moves are within run-to-run noise at this sample size.",
    "",
    `Full reports: ${details.reports.map((report) => `\`${report}\``).join(" and ")}`,
  );
  return `${lines.join("\n")}\n`;
}

/**
 * @param {string} suite
 * @param {ArmSummary} summary
 * @param {{ candidate: string, runs: number, reports: string[], problems?: string[] }} details
 * @returns {string}
 */
function renderCandidate(suite, summary, details) {
  /** @type {string[][]} */
  const rows = [];
  const total = { passes: 0, runs: 0 };
  for (const [caseName, checks] of summary.cases)
    for (const [check, tally] of checks) {
      total.passes += tally.passes;
      total.runs += tally.runs;
      rows.push([`\`${caseName}\``, `\`${check}\``, formatTally(tally)]);
    }
  const lines = [
    `# Skill eval: ${suite}`,
    "",
    `Ran ${details.candidate} alone, ${countOf(summary.cases.size, "case")} ${details.runs} time${details.runs === 1 ? "" : "s"}. There is no verdict without a base version.`,
    "",
    ...renderProblems(details.problems),
    ...(summary.partialReason
      ? [`The run stopped early (${summary.partialReason}).`, ""]
      : []),
    `Checks passed: ${formatShare(total)}. Cost per run: ${formatCost(summary.costPerRun)}. Time per run: ${formatSeconds(summary.secondsPerRun)}.`,
    "",
    markdownTable(["Case", "Check", "Passed"], rows),
    "",
    ...renderErrors(summary.errors),
    `Full report: \`${details.reports[0]}\``,
  ];
  return `${lines.join("\n")}\n`;
}

/**
 * @param {string[]} argv
 * @param {Dependencies} [dependencies]
 * @returns {number} Exit code: 0 for a finished report, 2 when a run stopped
 *   early or the runner reported a problem.
 */
function main(argv, dependencies = {}) {
  const print = dependencies.print || ((text) => process.stdout.write(text));
  const options = parseOptions(argv);
  if (options.help) {
    print(`${USAGE}\n`);
    return 0;
  }
  const env = dependencies.env || process.env;
  const pluginDir = dependencies.pluginDir || PLUGIN_DIR;
  const suite = loadSuite(pluginDir, options.suite);
  const repoRoot = git(["rev-parse", "--show-toplevel"], pluginDir).trim();
  // "." when the plugin is the repository root; Git rejects an empty path.
  const pluginRel =
    path.relative(fs.realpathSync(repoRoot), fs.realpathSync(pluginDir)) || ".";
  const stamp = (dependencies.now ? dependencies.now() : new Date())
    .toISOString()
    .replace(/[:.]/g, "-");
  const out = path.resolve(
    options.out ||
      path.join(repoRoot, ".context", "skill-evals", options.suite, stamp),
  );
  fs.mkdirSync(out, { recursive: true });
  const wrapper = toolchainWrapperDir(
    path.join(out, "bin"),
    dependencies.platform || process.platform,
    env,
  );
  const runEnv = wrapper
    ? { ...env, PATH: `${wrapper}${path.delimiter}${env.PATH || ""}` }
    : env;
  const head = git(["rev-parse", "--short", "HEAD"], repoRoot).trim();
  const dirty = git(
    ["status", "--porcelain", "--", pluginRel],
    repoRoot,
  ).trim();
  const candidateLabel = `the working tree at ${head}${dirty ? " with uncommitted changes" : ""}`;
  const arms = options.candidateOnly ? 1 : 2;
  const costCeiling =
    options.maxCostUsd === null ? null : options.maxCostUsd / arms;

  const snapshots = fs.mkdtempSync(path.join(os.tmpdir(), "skill-eval-"));
  try {
    const candidateRoot = path.join(snapshots, "candidate");
    snapshotWorkingTree(repoRoot, pluginRel, candidateRoot);
    const candidateOut = path.join(out, "candidate");
    /** @param {string} root @param {string} outputDir */
    const argumentsFor = (root, outputDir) =>
      runnerArguments(
        path.join(root, pluginRel),
        outputDir,
        options,
        suite,
        costCeiling,
      );

    if (options.candidateOnly) {
      const only = runArm(
        "candidate",
        argumentsFor(candidateRoot, candidateOut),
        candidateOut,
        runEnv,
      );
      const summary = summarizeArm("candidate", only.result);
      const report = renderCandidate(options.suite, summary, {
        candidate: candidateLabel,
        runs: options.runs,
        reports: [path.join(candidateOut, "report.html")],
        problems: only.problem ? [only.problem] : [],
      });
      fs.writeFileSync(path.join(out, "comparison.md"), report);
      print(report);
      return summary.partialReason || only.problem ? 2 : 0;
    }

    const base = resolveBase(repoRoot, options.base);
    const baseRoot = path.join(snapshots, "base");
    snapshotCommit(repoRoot, pluginRel, base.sha, baseRoot);
    // Both versions run the candidate's cases; only the plugin differs.
    const baseEvals = path.join(baseRoot, pluginRel, EVAL_DIR);
    fs.rmSync(baseEvals, { recursive: true, force: true });
    copyEntry(path.join(candidateRoot, pluginRel, EVAL_DIR), baseEvals);
    const baseOut = path.join(out, "base");
    const baseRun = runArm(
      "base",
      argumentsFor(baseRoot, baseOut),
      baseOut,
      runEnv,
    );
    const candidateRun = runArm(
      "candidate",
      argumentsFor(candidateRoot, candidateOut),
      candidateOut,
      runEnv,
    );
    const problems = [baseRun.problem, candidateRun.problem].flatMap(
      (problem) => (problem ? [problem] : []),
    );
    const comparison = compareResults(baseRun.result, candidateRun.result);
    const report = renderComparison(options.suite, comparison, {
      base: `${base.label} (${base.sha.slice(0, 8)})`,
      candidate: candidateLabel,
      runs: options.runs,
      reports: [
        path.join(baseOut, "report.html"),
        path.join(candidateOut, "report.html"),
      ],
      problems,
    });
    fs.writeFileSync(path.join(out, "comparison.md"), report);
    fs.writeFileSync(
      path.join(out, "comparison.json"),
      `${JSON.stringify(
        {
          suite: options.suite,
          base: { ref: base.label, sha: base.sha },
          candidate: candidateLabel,
          runs: options.runs,
          verdict: comparison.verdict,
          incompleteReason: comparison.incompleteReason,
          problems,
          totals: comparison.totals,
          checks: comparison.rows,
        },
        null,
        2,
      )}\n`,
    );
    print(report);
    return comparison.verdict === "incomplete" || problems.length ? 2 : 0;
  } finally {
    if (options.keepTemp)
      process.stderr.write(`Kept plugin snapshots in ${snapshots}\n`);
    else fs.rmSync(snapshots, { recursive: true, force: true });
  }
}

if (require.main === module) {
  try {
    process.exitCode = main(process.argv.slice(2));
  } catch (error) {
    process.stderr.write(
      `skill-eval-compare: ${error instanceof Error ? error.message : String(error)}\n`,
    );
    process.exitCode = 1;
  }
}

module.exports = {
  compareResults,
  loadSuite,
  main,
  parseOptions,
  renderCandidate,
  renderComparison,
  runnerArguments,
  summarizeArm,
  toolchainWrapperDir,
};
