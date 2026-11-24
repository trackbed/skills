#!/usr/bin/env node
// Decision: trackbed/docs/decisions/2026-09-08-review-execution-evidence.md
/* Local execution evidence, not a trusted host attestation. No shell evaluation. */
"use strict";
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { execFileSync } = require("node:child_process");

/**
 * @typedef {{aspects: string[], noCleanup?: boolean, emphasizedDimensions?: string[],
 * applicability?: Record<string, {applicable: boolean, reason: string}>, context?: string, resume?: unknown}} Plan
 * @typedef {{kind: string, agent: string, status: string, agentId?: string, started?: number,
 * finished?: number, outputHash?: string, interrupted?: {agentId?: string, started?: number, reason: string}[]}} Job
 * @typedef {{head: string, baseOid: string, index: string, files: string}} Scope
 * @typedef {{version: number, runId: string, created: string, evidence: string, root: string,
 * base: string, scope: Scope, planHash: string, coverage: Record<string, {active: boolean, reason: string, reviewers: string[]}>,
 * sequence: number, jobs: Record<string, Job>, reportHash?: string}} Ledger
 */
/** @type {Record<string, string[]>} */
const REVIEWERS = {
  code: ["code-reviewer"],
  errors: ["silent-failure-hunter"],
  slop: ["deslop-reviewer"],
  tests: ["pr-test-analyzer"],
  comments: ["comment-analyzer"],
  types: ["type-design-analyzer"],
  architecture: ["architecture-strategist"],
  removal: ["cleanup-reviewer"],
  lean: ["cleanup-reviewer"],
  refactor: ["cleanup-reviewer"],
  simplify: ["cleanup-reviewer"],
  performance: ["performance-oracle"],
  security: ["security-reviewer"],
};
const CONDITIONAL = [
  "tests",
  "comments",
  "types",
  "architecture",
  "removal",
  "performance",
  "security",
];
const ADVISORY_CLEANUP = ["lean", "refactor", "simplify"];
const STAGES = [
  "integrity",
  "relevance",
  "slop-meta",
  "previous-context",
  "aggregation",
  "final-check",
];
// Agent stages that have nothing to process when no finding reaches them. A skip launches no agent, needs explicit
// `Skipped:` evidence, and must be stated in the sealed report so a consumer can see the stage did not run.
/** @type {Record<string, string>} */
const SKIPPABLE = {
  relevance: "Relevance validation: skipped (no findings)",
  "slop-meta": "Slop meta-review: skipped (no findings)",
};
// This review's untracked root report is its output, not its scope. So are the untracked root and siw/ visual pages in
// the plugin's protected-report list, which collect-review-diff.sh drops from the reviewed scope by default.
// Other untracked reports stay in that scope, so they stay in the snapshot too.
const OWN_REPORT = "REVIEW_OVERVIEW.md";
const REVIEW_ARTIFACT_PATTERNS = path.join(
  __dirname,
  "..",
  "..",
  "..",
  "scripts",
  "review-artifact-patterns.sh",
);
const COMPLETE = ["succeeded", "skipped"];
/** @param {import("node:crypto").BinaryLike} value */
const hash = (value) => crypto.createHash("sha256").update(value).digest("hex");
/** @param {unknown} value */
const jsonHash = (value) => hash(JSON.stringify(value));
/** @param {unknown} condition @param {string} message @returns {asserts condition} */
function requireValue(condition, message) {
  if (!condition) throw new Error(message);
}
/** @param {string} root @param {...string} args */
function git(root, ...args) {
  return execFileSync("git", ["-C", root, ...args], {
    maxBuffer: 64 * 1024 * 1024,
  });
}
/** @param {string} root @param {string} base */
function snapshot(root, base) {
  const head = git(root, "rev-parse", "HEAD").toString().trim();
  const baseOid = git(root, "rev-parse", "--verify", `${base}^{commit}`)
    .toString()
    .trim();
  const tracked = git(root, "ls-files", "-z")
    .toString()
    .split("\0")
    .filter(Boolean);
  const untracked = execFileSync(
    "bash",
    [REVIEW_ARTIFACT_PATTERNS, "--without-visual-pages"],
    {
      input: git(root, "ls-files", "--others", "--exclude-standard", "-z"),
      maxBuffer: 64 * 1024 * 1024,
    },
  )
    .toString()
    .split("\0")
    .filter((name) => name && name !== OWN_REPORT);
  const files = [...new Set([...tracked, ...untracked])].sort().map((name) => {
    const file = path.join(root, name);
    let state;
    try {
      const stat = fs.lstatSync(file);
      if (stat.isSymbolicLink()) state = `link:${fs.readlinkSync(file)}`;
      else if (stat.isFile())
        state = `${stat.mode & 0o111}:${hash(fs.readFileSync(file))}`;
      else if (stat.isDirectory()) {
        // Gitlinks need their own HEAD and dirty-state evidence.
        state = `gitlink:${git(file, "rev-parse", "HEAD")}:${git(file, "status", "--porcelain")}`;
        requireValue(
          !git(file, "status", "--porcelain").toString().trim(),
          `Dirty submodule: ${name}`,
        );
      } else throw new Error(`Unsupported review path: ${name}`);
    } catch (error) {
      if (
        !(error instanceof Error && "code" in error && error.code === "ENOENT")
      )
        throw error;
      state = "absent";
    }
    return [name, state];
  });
  requireValue(
    head === git(root, "rev-parse", "HEAD").toString().trim(),
    "HEAD changed during capture",
  );
  return {
    head,
    baseOid,
    index: hash(git(root, "ls-files", "--stage", "-z")),
    files: jsonHash(files),
  };
}
/** @param {Plan} plan */
function jobsFor(plan) {
  requireValue(
    Array.isArray(plan.aspects) && plan.aspects.length > 0,
    "Plan needs normalized aspects",
  );
  requireValue(
    plan.aspects.every((a) => a === "all" || Object.hasOwn(REVIEWERS, a)),
    "Unknown aspect",
  );
  requireValue(
    !Object.hasOwn(plan, "noCleanup") || typeof plan.noCleanup === "boolean",
    "Plan noCleanup must be a boolean",
  );
  const emphasized = Object.hasOwn(plan, "emphasizedDimensions")
    ? plan.emphasizedDimensions
    : [];
  requireValue(
    Array.isArray(emphasized) &&
      emphasized.every(
        (dimension) =>
          typeof dimension === "string" && Object.hasOwn(REVIEWERS, dimension),
      ),
    "Plan emphasizedDimensions must be an array of recognized dimensions (not all)",
  );
  if (plan.noCleanup) {
    requireValue(
      !plan.aspects.some((dimension) => ADVISORY_CLEANUP.includes(dimension)),
      "--no-cleanup conflicts with explicitly requested cleanup aspects",
    );
    requireValue(
      !emphasized.some((dimension) => ADVISORY_CLEANUP.includes(dimension)),
      "--no-cleanup conflicts with emphasized cleanup dimensions",
    );
  }
  const all = plan.aspects.includes("all");
  requireValue(
    all || emphasized.every((dimension) => plan.aspects.includes(dimension)),
    "Emphasized dimension excluded by explicit aspect filter",
  );
  /** @type {Record<string, {kind: string, agent: string}>} */
  const jobs = {};
  /** @type {Ledger["coverage"]} */
  const coverage = {};
  for (const [dimension, reviewers] of Object.entries(REVIEWERS)) {
    const selected = all || plan.aspects.includes(dimension);
    let active = selected;
    let reason = selected
      ? "required by selected scope"
      : "excluded by explicit aspect filter";
    if (selected && plan.noCleanup && ADVISORY_CLEANUP.includes(dimension)) {
      active = false;
      reason = "excluded by --no-cleanup";
    }
    if (selected && CONDITIONAL.includes(dimension)) {
      const decision = plan.applicability?.[dimension];
      requireValue(
        typeof decision?.applicable === "boolean" &&
          typeof decision.reason === "string" &&
          decision.reason.trim(),
        `Missing applicability evidence: ${dimension}`,
      );
      active = decision.applicable;
      reason = decision.reason;
    }
    coverage[dimension] = { active, reason, reviewers };
    if (active)
      for (const reviewer of reviewers)
        jobs[reviewer] = { kind: "reviewer", agent: `trackbed:${reviewer}` };
  }
  requireValue(Object.keys(jobs).length > 0, "No applicable reviewers");
  for (const stage of STAGES)
    jobs[stage] = {
      kind: "stage",
      agent:
        stage === "relevance"
          ? "trackbed:pr-relevance-validator"
          : stage === "slop-meta"
            ? "trackbed:deslop-reviewer"
            : "orchestrator",
    };
  return { jobs, coverage };
}
/** @param {string} id @param {Record<string, Job>} jobs */
function dependencies(id, jobs) {
  if (!STAGES.includes(id)) return [];
  const index = STAGES.indexOf(id);
  return index === 0
    ? Object.keys(jobs).filter((key) => !STAGES.includes(key))
    : [STAGES[index - 1]];
}
/** @param {string} file */
function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}
/** @param {string} directory @param {Ledger} ledger */
function saveLedger(directory, ledger) {
  const file = path.join(directory, "ledger.json");
  const temp = `${file}.pending`;
  try {
    writePending(file, `${JSON.stringify(ledger, null, 2)}\n`);
    fs.renameSync(temp, file);
  } catch (error) {
    fs.rmSync(temp, { force: true });
    throw error;
  }
}
/** @param {string} directory @param {string} root */
function load(directory, root) {
  /** @type {Ledger} */
  const ledger = readJson(path.join(directory, "ledger.json"));
  requireValue(
    ledger.root === root,
    "Evidence belongs to a different repository",
  );
  const planFile = path.join(directory, "plan.json");
  const pendingPlan = `${planFile}.pending`;
  const plan = readJson(fs.existsSync(pendingPlan) ? pendingPlan : planFile);
  requireValue(
    ledger.version === 1 && ledger.planHash === jsonHash(plan),
    "Plan changed or unsupported ledger",
  );
  const derived = jobsFor(plan);
  requireValue(
    JSON.stringify(ledger.coverage) === JSON.stringify(derived.coverage),
    "Coverage changed",
  );
  requireValue(
    JSON.stringify(Object.keys(ledger.jobs)) ===
      JSON.stringify(Object.keys(derived.jobs)),
    "Job inventory changed",
  );
  for (const [id, job] of Object.entries(derived.jobs)) {
    requireValue(
      job.agent === ledger.jobs[id].agent && job.kind === ledger.jobs[id].kind,
      `Job changed: ${id}`,
    );
  }
  if (fs.existsSync(pendingPlan)) fs.renameSync(pendingPlan, planFile);
  recoverOutputs(directory, ledger);
  return { plan, ledger };
}
class StaleScopeError extends Error {}
/** @param {Ledger} ledger */
function fresh(ledger) {
  if (jsonHash(snapshot(ledger.root, ledger.base)) !== jsonHash(ledger.scope))
    throw new StaleScopeError("Review scope is stale; start a fresh full run");
}
/** @param {string} directory @param {Ledger} ledger @param {string} [root] */
function validate(directory, ledger, root = repositoryRoot()) {
  requireValue(
    ledger.root === root,
    "Evidence belongs to a different repository",
  );
  fresh(ledger);
  const ids = new Set();
  const abandoned = interruptedIds(ledger);
  requireValue(
    ledger.jobs.relevance?.status !== "skipped" ||
      ledger.jobs["slop-meta"]?.status === "skipped",
    "A skipped relevance stage leaves nothing for slop meta-review; skip it too",
  );
  for (const [id, job] of Object.entries(ledger.jobs)) {
    requireValue(
      job.status === "succeeded" ||
        (job.status === "skipped" && Object.hasOwn(SKIPPABLE, id)),
      `Incomplete job: ${id} (${job.status})`,
    );
    requireValue(
      Number.isInteger(job.started) &&
        Number.isInteger(job.finished) &&
        typeof job.started === "number" &&
        typeof job.finished === "number" &&
        job.started < job.finished,
      `Invalid execution order: ${id}`,
    );
    if (job.agent !== "orchestrator" && job.status !== "skipped") {
      requireValue(
        typeof job.agentId === "string" &&
          job.agentId.trim() &&
          !ids.has(job.agentId) &&
          !abandoned.has(job.agentId),
        `Missing or reused agent ID: ${id}`,
      );
      ids.add(job.agentId);
    }
    for (const dependency of dependencies(id, ledger.jobs)) {
      requireValue(
        (ledger.jobs[dependency].finished ?? Infinity) < job.started,
        `Stage started too early: ${id}`,
      );
    }
    const output = fs.readFileSync(path.join(directory, `${id}.txt`));
    requireValue(
      output.toString().trim() && hash(output) === job.outputHash,
      `Missing or changed output: ${id}`,
    );
  }
}
/** @param {Ledger} ledger @param {string} id */
function requireDependencies(ledger, id) {
  for (const dependency of dependencies(id, ledger.jobs))
    requireValue(
      COMPLETE.includes(ledger.jobs[dependency].status) ||
        (id === "integrity" && ledger.jobs[dependency].status === "failed"),
      `Incomplete dependency: ${dependency}`,
    );
  if (id === "integrity")
    requireValue(
      Object.values(ledger.jobs).some(
        (item) => item.kind === "reviewer" && item.status === "succeeded",
      ),
      "All primary reviewers failed",
    );
}
/** @param {Ledger} ledger */
function interruptedIds(ledger) {
  return new Set(
    Object.values(ledger.jobs).flatMap((job) =>
      (job.interrupted ?? []).map((entry) => entry.agentId).filter(Boolean),
    ),
  );
}
// An interrupted job returns to pending; its abandoned invocation ID stays as evidence and can never be reused.
/** @param {Ledger} ledger @param {string} id @param {string} reason */
function applyRequeue(ledger, id, reason) {
  const job = ledger.jobs[id];
  requireValue(Object.hasOwn(ledger.jobs, id), `Unknown job: ${id}`);
  requireValue(
    job.status === "running",
    "Only a running job can be requeued; failed jobs need a fresh run",
  );
  requireValue(reason?.trim(), "requeue needs --reason");
  job.interrupted = [
    ...(job.interrupted ?? []),
    { agentId: job.agentId, started: job.started, reason },
  ];
  delete job.agentId;
  delete job.started;
  job.status = "pending";
}
/** @param {Ledger} ledger @param {string} id @param {string | undefined} agentId */
function applyStart(ledger, id, agentId) {
  const job = ledger.jobs[id];
  requireValue(Object.hasOwn(ledger.jobs, id), `Unknown job: ${id}`);
  requireValue(
    job.status === "pending",
    "Job already started; requeue an interrupted job, or retain failed evidence and start a fresh run for retries",
  );
  requireDependencies(ledger, id);
  if (job.agent !== "orchestrator") {
    requireValue(agentId?.trim(), "Actual host agent ID required");
    requireValue(
      !Object.values(ledger.jobs).some((other) => other.agentId === agentId) &&
        !interruptedIds(ledger).has(agentId),
      "Use a distinct invocation ID per delegated job",
    );
    job.agentId = agentId;
  }
  job.status = "running";
  job.started = ++ledger.sequence;
}
/** @param {Ledger} ledger @param {string} id @param {string} status @param {Buffer} output */
function applyFinish(ledger, id, status, output) {
  const job = ledger.jobs[id];
  requireValue(Object.hasOwn(ledger.jobs, id), `Unknown job: ${id}`);
  requireValue(
    (job.status === "running" && ["succeeded", "failed"].includes(status)) ||
      (job.status === "pending" && ["failed", "skipped"].includes(status)),
    "finish needs running job, --status succeeded|failed and --output (or a pending job with --status failed|skipped)",
  );
  requireValue(
    output.toString().trim(),
    "Empty output is not evidence; save an explicit zero-findings result",
  );
  if (status === "skipped") {
    requireValue(
      Object.hasOwn(SKIPPABLE, id),
      `Only ${Object.keys(SKIPPABLE).join(" and ")} may be skipped`,
    );
    requireValue(
      output.toString().trimStart().startsWith("Skipped:"),
      "Skipped output must start with `Skipped:` and say why nothing reached the stage",
    );
    requireDependencies(ledger, id);
  }
  if (job.status === "pending") job.started = ++ledger.sequence;
  job.status = status;
  job.outputHash = hash(output);
  job.finished = ++ledger.sequence;
}
/** @param {string} file @returns {{job: string, status: string, output: string, agentId?: string, data: Buffer}[]} */
function readManifest(file) {
  const manifest = readJson(file);
  requireValue(
    Array.isArray(manifest) && manifest.length > 0,
    "Manifest must be a non-empty JSON array",
  );
  return manifest.map(
    (
      /** @type {{job: string, status: string, output: string, agentId?: string}} */ entry,
      /** @type {number} */ index,
    ) => {
      requireValue(
        entry &&
          typeof entry === "object" &&
          typeof entry.job === "string" &&
          typeof entry.status === "string" &&
          typeof entry.output === "string" &&
          (entry.agentId === undefined || typeof entry.agentId === "string") &&
          Object.keys(entry).every((key) =>
            ["job", "status", "output", "agentId"].includes(key),
          ),
        `Manifest entry ${index} needs job, status, output, and optional agentId`,
      );
      return { ...entry, data: fs.readFileSync(entry.output) };
    },
  );
}
/** @param {string} file @param {string | Buffer} data */
function writePending(file, data) {
  const pending = `${file}.pending`;
  fs.rmSync(pending, { force: true });
  const fd = fs.openSync(pending, "wx", 0o600);
  try {
    fs.writeFileSync(fd, data);
  } finally {
    fs.closeSync(fd);
  }
}

/** @param {string} directory @param {Ledger} ledger */
function recoverOutputs(directory, ledger) {
  for (const [id, job] of Object.entries(ledger.jobs)) {
    const output = path.join(directory, `${id}.txt`);
    const pending = `${output}.pending`;
    if (!fs.existsSync(pending)) continue;
    if (job.outputHash === undefined) {
      fs.unlinkSync(pending);
      continue;
    }
    requireValue(
      hash(fs.readFileSync(pending)) === job.outputHash,
      `Changed pending output: ${id}`,
    );
    fs.renameSync(pending, output);
  }
}

/** @param {string} directory @param {Ledger} ledger @param {{job: string, data: Buffer}[]} steps */
function commitOutputs(directory, ledger, steps) {
  const outputs = steps.map((step) => path.join(directory, `${step.job}.txt`));
  try {
    for (const [index, step] of steps.entries()) {
      writePending(outputs[index], step.data);
    }
    saveLedger(directory, ledger);
  } catch (error) {
    for (const output of outputs)
      fs.rmSync(`${output}.pending`, { force: true });
    throw error;
  }
  recoverOutputs(directory, ledger);
}

/** @typedef {Record<string, string>} Options */
/** @typedef {{directory: string, requestedDirectory: string, root: string, options: Options, plan: Plan, ledger: Ledger}} Transaction */
/** @param {string} directory @param {Options} options @param {string} root */
function init(directory, options, root) {
  requireValue(
    options.plan && options.base && !options.base.startsWith("-"),
    "init needs --plan and --base",
  );
  const plan = readJson(options.plan);
  const { jobs, coverage } = jobsFor(plan);
  requireValue(
    typeof plan.context === "string" && plan.context.trim(),
    "Plan needs scope, PR metadata and previous-review context evidence",
  );
  const scope = snapshot(root, options.base);
  requireValue(
    fs
      .readdirSync(directory)
      .every((name) =>
        ["plan.json.pending", "ledger.json.pending"].includes(name),
      ),
    "Run directory must be empty",
  );
  /** @type {Ledger} */
  const ledger = {
    version: 1,
    runId: crypto.randomUUID(),
    created: new Date().toISOString(),
    evidence: "self-attested",
    root,
    base: options.base,
    scope,
    planHash: jsonHash(plan),
    coverage,
    sequence: 0,
    jobs: Object.fromEntries(
      Object.entries(jobs).map(([id, job]) => [
        id,
        { ...job, status: "pending" },
      ]),
    ),
  };
  const planFile = path.join(directory, "plan.json");
  writePending(planFile, `${JSON.stringify(plan, null, 2)}\n`);
  saveLedger(directory, ledger);
  fs.renameSync(`${planFile}.pending`, planFile);
  console.log(JSON.stringify(ledger));
}

/** @param {Transaction} transaction */
function status({ plan, ledger }) {
  let scopeFresh = true;
  try {
    fresh(ledger);
  } catch (error) {
    if (!(error instanceof StaleScopeError)) throw error;
    scopeFresh = false;
  }
  console.log(
    JSON.stringify({
      runId: ledger.runId,
      root: ledger.root,
      base: ledger.base,
      created: ledger.created ?? null,
      sealed: Boolean(ledger.reportHash),
      scopeFresh,
      aspects: plan.aspects,
      noCleanup: plan.noCleanup ?? false,
      emphasizedDimensions: plan.emphasizedDimensions ?? [],
      resume: plan.resume ?? null,
      jobs: Object.fromEntries(
        Object.entries(ledger.jobs).map(([id, job]) => [
          id,
          {
            status: job.status,
            ...(job.agentId ? { agentId: job.agentId } : {}),
            interrupted: job.interrupted?.length ?? 0,
          },
        ]),
      ),
    }),
  );
}

/** @param {Transaction} transaction */
function requeue({ directory, ledger, options }) {
  applyRequeue(ledger, options.job, options.reason);
  saveLedger(directory, ledger);
}

/** @param {Transaction} transaction */
function start({ directory, ledger, options }) {
  applyStart(ledger, options.job, options["agent-id"]);
  saveLedger(directory, ledger);
}

/** @param {Transaction} transaction */
function finish({ directory, ledger, options }) {
  requireValue(
    options.job && options.status && options.output,
    "finish needs --job, --status succeeded|failed|skipped and --output",
  );
  const data = fs.readFileSync(options.output);
  applyFinish(ledger, options.job, options.status, data);
  commitOutputs(directory, ledger, [{ job: options.job, data }]);
}

/** @param {Job} job @param {{status: string, agentId?: string}} step */
function shouldRecordStart(job, step) {
  return (
    job.status === "pending" &&
    step.status !== "skipped" &&
    (step.status !== "failed" ||
      Boolean(step.agentId) ||
      job.agent === "orchestrator")
  );
}

/** @param {Transaction} transaction */
function record({ directory, ledger, options }) {
  requireValue(options.manifest, "record needs --manifest <file.json>");
  const steps = readManifest(options.manifest);
  for (const step of steps) {
    requireValue(
      Object.hasOwn(ledger.jobs, step.job),
      `Unknown job: ${step.job}`,
    );
    if (shouldRecordStart(ledger.jobs[step.job], step)) {
      applyStart(ledger, step.job, step.agentId);
    }
    applyFinish(ledger, step.job, step.status, step.data);
  }
  commitOutputs(directory, ledger, steps);
}

/** @param {Transaction} transaction */
function reportHash({ directory, requestedDirectory, root, ledger, options }) {
  validate(directory, ledger, root);
  requireValue(
    options.report,
    "Report file required (save exact inline content to a temporary file)",
  );
  const report = fs.readFileSync(options.report);
  const reportText = report.toString();
  for (const heading of [
    "Relevance Filter",
    "Previous Review Context",
    "Auto-resolution Readiness",
    "Coverage Status",
    "Critical Issues",
    "Important Issues",
    "Suggestions",
    "Slop Warnings",
    "Filtered (Pre-existing/Out-of-scope)",
    "Filtered (Previously Addressed)",
    "Strengths",
    "Approval Standard",
    "Recommended Action",
  ]) {
    requireValue(
      reportText
        .split("\n")
        .some(
          (line) =>
            line === `## ${heading}` || line.startsWith(`## ${heading} (`),
        ),
      `Missing report section: ${heading}`,
    );
  }
  for (const prefix of ["Review status:", "Review execution:", "Review run:"])
    requireValue(
      reportText.split("\n").filter((line) => line.startsWith(prefix))
        .length === 1,
      `Ambiguous report field: ${prefix}`,
    );
  requireValue(
    reportText.split("\n").includes(`Review execution: ${requestedDirectory}`),
    "Report must name this execution directory",
  );
  requireValue(
    reportText.split("\n").includes(`Review run: ${ledger.runId}`),
    "Report run ID missing",
  );
  requireValue(
    reportText.split("\n").includes("Review status: COMPLETE"),
    "Report status must be COMPLETE",
  );
  for (const [id, line] of Object.entries(SKIPPABLE))
    if (ledger.jobs[id]?.status === "skipped")
      requireValue(
        reportText.split("\n").some((text) => text.trim() === line),
        `Report must state: ${line}`,
      );
  return hash(report);
}

/** @param {Ledger} ledger */
function printComplete(ledger) {
  console.log(
    JSON.stringify({
      status: "COMPLETE",
      runId: ledger.runId,
      evidence: ledger.evidence,
      scope: ledger.scope,
      coverage: ledger.coverage,
      jobs: ledger.jobs,
    }),
  );
}

/** @param {Transaction} transaction */
function seal(transaction) {
  const { directory, ledger } = transaction;
  const report = reportHash(transaction);
  requireValue(!ledger.reportHash, "Run already sealed");
  ledger.reportHash = report;
  saveLedger(directory, ledger);
  printComplete(ledger);
}

/** @param {Transaction} transaction */
function check(transaction) {
  const { ledger, options, plan } = transaction;
  requireValue(
    ledger.reportHash === reportHash(transaction),
    "Missing seal or changed report",
  );
  if (options.aspects)
    requireValue(
      JSON.stringify(plan.aspects) ===
        JSON.stringify(options.aspects.split(",")),
      "Review aspect scope does not match consumer requirement",
    );
  printComplete(ledger);
}

const COMMANDS = {
  init: { options: ["plan", "base"], run: init },
  status: { options: [], run: status },
  requeue: { options: ["job", "reason"], run: requeue, mutation: true },
  start: { options: ["job", "agent-id"], run: start, mutation: true },
  finish: { options: ["job", "output", "status"], run: finish, mutation: true },
  record: { options: ["manifest"], run: record, mutation: true },
  seal: { options: ["report"], run: seal },
  check: { options: ["report", "aspects"], run: check },
};

function repositoryRoot() {
  return git(process.cwd(), "rev-parse", "--show-toplevel").toString().trim();
}

/** Resolve aliases before checking the location of a new run. @param {string} directory */
function resolveDirectory(directory) {
  let ancestor = directory;
  while (!fs.existsSync(ancestor)) ancestor = path.dirname(ancestor);
  return path.join(
    fs.realpathSync.native(ancestor),
    path.relative(ancestor, directory),
  );
}

/** @param {string} directory @param {() => void} action */
function withWriterLock(directory, action) {
  const fd = fs.openSync(
    directory,
    fs.constants.O_RDONLY | fs.constants.O_DIRECTORY,
  );
  try {
    // Python locks the inherited open file description. Node retains its
    // descriptor throughout the transaction, so process exit releases the lock.
    execFileSync(
      "python3",
      ["-I", "-c", "import fcntl; fcntl.flock(3, fcntl.LOCK_EX)"],
      {
        stdio: ["ignore", "ignore", "pipe", fd],
      },
    );
    action();
  } finally {
    fs.closeSync(fd);
  }
}

/** @param {string[]} argv */
function main(argv) {
  const [command, directoryArg, ...rest] = argv;
  requireValue(
    Object.hasOwn(COMMANDS, command) && directoryArg,
    "Usage: review-execution.js init|start|finish|record|requeue|status|seal|check RUN_DIR [--key value]",
  );
  const name = /** @type {keyof typeof COMMANDS} */ (command);
  requireValue(rest.length % 2 === 0, "Options require values");
  /** @type {Record<string, string>} */
  const options = {};
  /** @type {string[]} */
  const allowed = COMMANDS[name].options;
  for (let i = 0; i < rest.length; i += 2) {
    const key = rest[i].replace(/^--/, "");
    requireValue(
      rest[i].startsWith("--") &&
        allowed.includes(key) &&
        !Object.hasOwn(options, key),
      `Invalid option: ${rest[i]}`,
    );
    options[key] = rest[i + 1];
  }
  const requestedDirectory = path.resolve(directoryArg);
  const directory = resolveDirectory(requestedDirectory);
  const root = repositoryRoot();
  const relative = path.relative(fs.realpathSync.native(root), directory);
  requireValue(
    relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative),
    "Keep execution artifacts outside the working tree (use mktemp -d)",
  );
  if (name === "init")
    fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
  withWriterLock(directory, () => {
    if (name === "init") {
      COMMANDS.init.run(directory, options, root);
      return;
    }
    const handler = COMMANDS[name];
    const { plan, ledger } = load(directory, root);
    if ("mutation" in handler) {
      requireValue(
        !ledger.reportHash,
        "Sealed run cannot change; start a fresh run",
      );
      fresh(ledger);
    }
    handler.run({ directory, requestedDirectory, root, options, plan, ledger });
  });
}
if (require.main === module) {
  try {
    main(process.argv.slice(2));
  } catch (error) {
    console.error(
      `INCOMPLETE: ${error instanceof Error ? error.message : String(error)}`,
    );
    process.exitCode = 1;
  }
}
module.exports = { main, jobsFor, snapshot, validate };
