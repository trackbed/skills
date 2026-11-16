"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const test = require("node:test");
const YAML = require("yaml");

const workflow = YAML.parse(
  fs.readFileSync(
    path.resolve(__dirname, "../../../.github/workflows/tests.yml"),
    "utf8",
  ),
);
/** @type {{needs: string[], if: string, steps: {run: string}[]}} */
const aggregate = workflow.jobs["hooks-required"];
const required = [
  "hooks",
  "walkthrough-browser-smoke",
  "lint",
  "python38-compatibility",
];

/** @param {Record<string, string>} results */
function runAggregate(results) {
  const script = aggregate.steps
    .map((step) => step.run)
    .join("\n")
    .replace(/\$\{\{ needs\.([\w-]+)\.result \}\}/g, (_, job) => results[job]);
  assert.ok(
    !script.includes("${{"),
    "all workflow expressions must be resolved",
  );
  return spawnSync("bash", ["-e", "-c", script], { encoding: "utf8" });
}

test("required CI aggregate accepts successful jobs", () => {
  assert.deepEqual([...aggregate.needs].sort(), [...required].sort());
  assert.equal(aggregate.if, "${{ always() }}");
  const result = runAggregate(
    Object.fromEntries(required.map((job) => [job, "success"])),
  );
  assert.equal(result.status, 0, result.stderr);
});

for (const job of required) {
  for (const status of ["failure", "cancelled", "skipped"]) {
    test(`required CI aggregate rejects ${job} ${status}`, () => {
      const results = Object.fromEntries(
        required.map((name) => [name, "success"]),
      );
      results[job] = status;
      const result = runAggregate(results);
      assert.equal(result.status, 1, result.stdout + result.stderr);
    });
  }
}

test("CI reuses local browser and compatibility entry points", () => {
  assert.ok(
    workflow.jobs["walkthrough-browser-smoke"].steps.some(
      (/** @type {{run?: string}} */ step) =>
        step.run === "make -C trackbed test-walkthrough-browser",
    ),
  );
  assert.ok(
    workflow.jobs["python38-compatibility"].steps.some(
      (/** @type {{run?: string}} */ step) =>
        step.run ===
        "make -C trackbed test-python38-compatibility PYTHON38=python3",
    ),
  );
});
