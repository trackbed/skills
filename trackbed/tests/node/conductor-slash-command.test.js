"use strict";

const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  findSkill,
  parseLeadingCommand,
  respond,
} = require("../../hooks/lib/conductor-slash-command.js");

const SCRIPT = path.resolve(
  __dirname,
  "../../hooks/lib/conductor-slash-command.js",
);
const REPO_ROOT = path.resolve(__dirname, "../..");
const CONDUCTOR_BLOCK =
  "<system_instruction>\nYou are working inside Conductor.\n</system_instruction>\n\n";
const CLAUDE_ENV = { CLAUDECODE: "1" };

/**
 * Builds a minimal Claude Code plugin root with the given skills.
 * @param {import("node:test").TestContext} t
 * @param {Record<string, string>} skills Folder name to frontmatter body.
 * @param {{ manifest?: string }} [options]
 */
function pluginRoot(t, skills, { manifest = ".claude-plugin" } = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "conductor-command-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(path.join(root, manifest));
  fs.writeFileSync(path.join(root, manifest, "plugin.json"), "{}");
  for (const [folder, frontmatter] of Object.entries(skills)) {
    fs.mkdirSync(path.join(root, "skills", folder), { recursive: true });
    fs.writeFileSync(
      path.join(root, "skills", folder, "SKILL.md"),
      `---\nname: ${folder}\n${frontmatter}---\n# Body\n`,
    );
  }
  return root;
}

const USER_ONLY = "disable-model-invocation: true\nuser-invocable: true\n";

/** @param {string} prompt @param {Record<string, unknown>} [extra] */
function payload(prompt, extra = {}) {
  return { hook_event_name: "UserPromptSubmit", prompt, ...extra };
}

/** @param {Record<string, unknown>} output */
function contextOf(output) {
  const specific = /** @type {Record<string, unknown>} */ (
    output.hookSpecificOutput
  );
  assert.equal(specific.hookEventName, "UserPromptSubmit");
  return String(specific.additionalContext);
}

test("parses a command typed after Conductor's instruction blocks", () => {
  assert.deepEqual(
    parseLeadingCommand(
      `${CONDUCTOR_BLOCK}<system_instruction>\nAttached files\n</system_instruction>\n\n  /trackbed:pr:github-review 8704 --stack\nfocus on tests`,
    ),
    {
      typed: "/trackbed:pr:github-review",
      name: "pr:github-review",
      args: "8704 --stack\nfocus on tests",
    },
  );
});

test("ignores prompts Claude Code expands or that carry no leading command", () => {
  for (const prompt of [
    "/trackbed:pr:create",
    `Please run ${CONDUCTOR_BLOCK}/trackbed:pr:create`,
    `${CONDUCTOR_BLOCK}Run /trackbed:pr:create later`,
    `${CONDUCTOR_BLOCK}/trackbed:pr:create/extra`,
    `${CONDUCTOR_BLOCK}/other:pr:create`,
    "<system_instruction>never closed /trackbed:pr:create",
  ]) {
    assert.equal(parseLeadingCommand(prompt), null, prompt);
  }
});

test("resolves the frontmatter name and the hyphenated id to one skill", (t) => {
  const root = pluginRoot(t, {
    "pr:github-review": USER_ONLY,
    "pr:github-review-reply": USER_ONLY,
    qa: USER_ONLY,
  });
  for (const name of ["pr:github-review", "pr-github-review"]) {
    assert.deepEqual(findSkill(root, name), {
      dir: path.join(root, "skills", "pr:github-review"),
      name: "pr:github-review",
    });
  }
  assert.equal(findSkill(root, "qa")?.name, "qa");
  assert.equal(findSkill(root, "pr:missing"), null);
});

test("skips skills the user cannot invoke in Claude Code", (t) => {
  const root = pluginRoot(t, {
    "domain:background":
      "disable-model-invocation: false\nuser-invocable: false\n",
    "domain:codex-only": `${USER_ONLY}trackbed-platforms: [codex]\n`,
    "domain:both": `${USER_ONLY}trackbed-platforms: [claude-code, codex]\n`,
  });
  assert.equal(findSkill(root, "domain:background"), null);
  assert.equal(findSkill(root, "domain:codex-only"), null);
  assert.equal(findSkill(root, "domain:both")?.name, "domain:both");
});

test("tells the model to run the typed skill with its root and arguments", (t) => {
  const root = pluginRoot(t, { "pr:github-review": USER_ONLY });
  const context = contextOf(
    respond(payload(`${CONDUCTOR_BLOCK}/trackbed:pr-github-review 8704`), {
      pluginRoot: root,
      env: CLAUDE_ENV,
    }),
  );
  const skillDir = path.join(root, "skills", "pr:github-review");
  assert.match(
    context,
    /starts with the slash command `\/trackbed:pr-github-review`/,
  );
  assert.match(context, /skill `trackbed:pr:github-review`/);
  assert.ok(context.includes(`Read \`${path.join(skillDir, "SKILL.md")}\``));
  assert.ok(context.includes(`Base directory for this skill: ${skillDir}`));
  assert.ok(context.includes(`\`\${CLAUDE_PLUGIN_ROOT}\` means \`${root}\``));
  assert.ok(context.includes("<arguments>\n8704\n</arguments>"));
  assert.match(context, /Do not call the Skill tool for this skill/);
});

test("says when the command has no arguments", (t) => {
  const root = pluginRoot(t, { qa: USER_ONLY });
  const context = contextOf(
    respond(payload(`${CONDUCTOR_BLOCK}/trackbed:qa`), {
      pluginRoot: root,
      env: CLAUDE_ENV,
    }),
  );
  assert.match(context, /`\$ARGUMENTS` is empty/);
  assert.doesNotMatch(context, /<arguments>/);
});

test("stays silent outside a Claude Code plugin or on other events", (t) => {
  const prompt = `${CONDUCTOR_BLOCK}/trackbed:qa`;
  const claudeRoot = pluginRoot(t, { qa: USER_ONLY });
  const codexRoot = pluginRoot(
    t,
    { qa: USER_ONLY },
    { manifest: ".codex-plugin" },
  );

  assert.deepEqual(
    respond(payload(prompt), { pluginRoot: codexRoot, env: CLAUDE_ENV }),
    {},
  );
  assert.deepEqual(
    respond(payload(prompt, { turn_id: "turn-1" }), {
      pluginRoot: claudeRoot,
      env: CLAUDE_ENV,
    }),
    {},
  );
  assert.deepEqual(
    respond(
      { hook_event_name: "PreToolUse", prompt },
      { pluginRoot: claudeRoot, env: CLAUDE_ENV },
    ),
    {},
  );
  assert.deepEqual(
    respond({ prompt: 42 }, { pluginRoot: claudeRoot, env: CLAUDE_ENV }),
    {},
  );
});

test("resolves every shipped user-invocable skill by both spellings", () => {
  const skillsRoot = path.join(REPO_ROOT, "skills");
  for (const folder of fs.readdirSync(skillsRoot)) {
    const source = fs.readFileSync(
      path.join(skillsRoot, folder, "SKILL.md"),
      "utf8",
    );
    const userInvocable = !/^user-invocable:\s*false\s*$/m.test(source);
    const claudeCode = !/^trackbed-platforms:\s*\[codex\]\s*$/m.test(source);
    const expected = userInvocable && claudeCode ? folder : undefined;
    assert.equal(findSkill(REPO_ROOT, folder)?.name, expected, folder);
    assert.equal(
      findSkill(REPO_ROOT, folder.replaceAll(":", "-"))?.name,
      expected,
      folder,
    );
  }
});

test("the script prints an empty object for unreadable input", () => {
  const result = spawnSync(process.execPath, [SCRIPT], {
    encoding: "utf8",
    input: "not json",
  });
  assert.equal(result.status, 0);
  assert.equal(result.stdout.trim(), "{}");
});
