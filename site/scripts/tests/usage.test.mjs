import assert from "node:assert/strict";
import { test } from "node:test";
import { readUsage, usagePath } from "../lib/usage.mjs";

const skill = {
  name: "trackbed:pr:create",
  shortName: "pr:create",
  slug: "skills/pr-create",
  argumentHint: "[--draft] [--base <branch>] [--depth <balanced|full>]",
};

function guide(changes = {}) {
  const parts = {
    title: "# pr:create",
    lead: "Opens a Pull Request.",
    before: null,
    options: [
      "## Options",
      "",
      "| Option | Effect |",
      "| --- | --- |",
      "| `--draft` | Open a draft. |",
      "| `--base <branch>` | Target `<branch>`. |",
      "| `--depth <balanced\\|full>` | Review depth. |",
    ].join("\n"),
    examples: [
      "## Examples",
      "",
      "```text",
      "# Open a draft against develop",
      "/trackbed:pr:create --draft --base develop",
      "",
      "/trackbed:pr:create",
      "```",
    ].join("\n"),
    result: "## What you get\n\n- An open Pull Request.",
    ...changes,
  };
  return `${Object.values(parts).filter(Boolean).join("\n\n")}\n`;
}

test("names a skill's usage guide after its page", () => {
  assert.equal(usagePath(skill), "trackbed/docs/usage/pr-create.md");
  assert.equal(usagePath({ slug: "skills/qa" }), "trackbed/docs/usage/qa.md");
});

test("splits a usage guide into its lead and its sections", () => {
  const usage = readUsage(
    guide({ before: "## Before you run it\n\n- `gh` is authenticated." }),
    skill,
  );

  assert.equal(usage.lead, "Opens a Pull Request.");
  assert.match(usage.sections, /^## Before you run it\n\n- `gh`/);
  assert.match(usage.sections, /## What you get\n\n- An open Pull Request\.$/);
  assert.equal(readUsage(guide({ lead: null }), skill).lead, "");
});

test("accepts a skill without flags only without an Options table", () => {
  const plain = { ...skill, argumentHint: "<url>" };

  assert.doesNotThrow(() =>
    readUsage(
      guide({
        options: null,
        examples:
          "## Examples\n\n```text\n/trackbed:pr:create https://example.com\n```",
      }),
      plain,
    ),
  );
  assert.throws(
    () => readUsage(guide(), plain),
    /documents --base, --depth, --draft, which the skill's argument-hint does not list/,
  );
});

test("rejects a guide that does not match its skill", () => {
  const failure = (changes, pattern) =>
    assert.throws(() => readUsage(guide(changes), skill), pattern);

  failure(
    { title: "# pr:rebase" },
    /the title is "pr:rebase" but the skill is "pr:create"/,
  );
  failure({ title: "Opens things." }, /the first line must be "# pr:create"/);
  failure({ result: null }, /"## What you get" is missing/);
  failure({ result: "## What you get" }, /"## What you get" is empty/);
  failure({ before: "## Notes\n\nText." }, /"Notes" is not a usage section/);
  failure(
    { before: "### Options\n\nText." },
    /"Options" is not a usage section/,
  );
  // "Before you run it" comes first.
  failure(
    { result: "## What you get\n\n- A PR.\n\n## Before you run it\n\n- gh." },
    /sections must appear once each, in this order/,
  );
  failure(
    {
      options:
        "## Options\n\n| Option | Effect |\n| --- | --- |\n| `--draft` | Open a draft. |",
    },
    /no row for --base, --depth, which the skill's argument-hint lists/,
  );
  // A flag named in an Effect cell is not documented by it.
  failure(
    {
      options:
        "## Options\n\n| Option | Effect |\n| --- | --- |\n| `--draft` | Like `--base` and `--depth`. |",
    },
    /no row for --base, --depth/,
  );
  failure(
    { examples: "## Examples\n\nRun it." },
    /"## Examples" needs a code block with a command/,
  );
  failure(
    { examples: "## Examples\n\n```text\n/trackbed:pr:rebase\n```" },
    /every example must start with \/trackbed:pr:create; found: \/trackbed:pr:rebase/,
  );
  failure(
    { examples: "## Examples\n\n```text\n/trackbed:pr:create-more\n```" },
    /every example must start with \/trackbed:pr:create/,
  );
  failure(
    { examples: "## Examples\n\n```text\n/trackbed:pr:create --force\n```" },
    /an example uses --force, which the skill's argument-hint does not list/,
  );
});
