#!/usr/bin/env node
// @ts-check
"use strict";

// Conductor puts a `<system_instruction>` block in front of the first message
// of a chat. That message then no longer starts with `/`, so Claude Code never
// expands a `/trackbed:<skill>` command typed at its start, and the model
// cannot start a `disable-model-invocation: true` skill through the Skill
// tool. This hook tells the model which skill the user typed and how to run
// it, as the slash command would have.

const fs = require("fs");
const path = require("path");

const {
  PLATFORM_CODEX,
  asRecord,
  detectPlatform,
  readSkillFolderResolver,
  stripConductorInstructions,
} = require("../../scripts/lib/trackbed-runtime.js");

const CONDUCTOR_INSTRUCTION_OPEN = "<system_instruction>";
// Claude Code accepts both the frontmatter name (`pr:github-review`) and its
// hyphenated id (`pr-github-review`) after the plugin name.
const COMMAND_PATTERN = /^\/trackbed:([a-z0-9][a-z0-9:-]*)(?=\s|$)/;
const FRONTMATTER_PATTERN = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/;

/**
 * @typedef {Object} Skill
 * @property {string} dir Absolute path to the skill directory.
 * @property {string} name Frontmatter name, such as `pr:github-review`.
 */

/**
 * Returns the hook's JSON response for one `UserPromptSubmit` payload.
 * @param {unknown} input
 * @param {{ pluginRoot: string, env: NodeJS.ProcessEnv }} options
 * @returns {Record<string, unknown>}
 */
function respond(input, { pluginRoot, env }) {
  const payload = asRecord(input);
  const prompt = payload.prompt;
  if (typeof prompt !== "string") return {};
  if (
    typeof payload.hook_event_name === "string" &&
    payload.hook_event_name !== "UserPromptSubmit"
  ) {
    return {};
  }
  // The converted Codex plugin ships this hook too, but its skills live in
  // prefixed folders and Codex reads `$trackbed:` mentions anywhere.
  if (detectPlatform(input, env) === PLATFORM_CODEX) return {};
  if (!fs.existsSync(path.join(pluginRoot, ".claude-plugin", "plugin.json"))) {
    return {};
  }

  const command = parseLeadingCommand(prompt);
  if (!command) return {};
  const skill = findSkill(pluginRoot, command.name);
  if (!skill) return {};

  return {
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext: renderContext({
        typed: command.typed,
        args: command.args,
        skill,
        pluginRoot,
      }),
    },
  };
}

/**
 * Finds a `/trackbed:` command at the start of the user's own text, after
 * Conductor's instruction blocks. Text without those blocks is left to Claude
 * Code, which expands a leading slash command itself.
 * @param {string} prompt
 * @returns {{ typed: string, name: string, args: string } | null}
 */
function parseLeadingCommand(prompt) {
  if (!prompt.trimStart().startsWith(CONDUCTOR_INSTRUCTION_OPEN)) return null;
  const userText = stripConductorInstructions(prompt);
  if (userText === prompt) return null;
  const text = userText.trimStart();
  const match = COMMAND_PATTERN.exec(text);
  if (!match) return null;
  return {
    typed: match[0],
    name: match[1],
    args: text.slice(match[0].length).trim(),
  };
}

/**
 * Resolves a typed name to a user-invocable Claude Code skill.
 * @param {string} pluginRoot
 * @param {string} name
 * @returns {Skill | null}
 */
function findSkill(pluginRoot, name) {
  const skillsRoot = path.join(pluginRoot, "skills");
  let skill;
  let source;
  try {
    skill = readSkillFolderResolver(skillsRoot)(name);
    if (!skill) return null;
    source = fs.readFileSync(path.join(skill.dir, "SKILL.md"), "utf8");
  } catch {
    return null;
  }
  const frontmatter = FRONTMATTER_PATTERN.exec(source);
  if (!frontmatter) return null;
  const fields = frontmatter[1];
  if (/^user-invocable:\s*false\s*$/m.test(fields)) return null;
  const platforms = /^trackbed-platforms:\s*\[([^\]]*)\]\s*$/m.exec(fields);
  if (
    platforms &&
    !platforms[1]
      .split(",")
      .map((value) => value.trim())
      .includes("claude-code")
  ) {
    return null;
  }
  return skill;
}

/**
 * @param {{ typed: string, args: string, skill: Skill, pluginRoot: string }} options
 * @returns {string}
 */
function renderContext({ typed, args, skill, pluginRoot }) {
  const skillFile = path.join(skill.dir, "SKILL.md");
  const argumentLine = args
    ? `- \`$ARGUMENTS\` means the text between these markers:\n<arguments>\n${args}\n</arguments>`
    : "- `$ARGUMENTS` is empty: the user gave no arguments.";
  return [
    `The user's message starts with the slash command \`${typed}\`. Conductor put its <system_instruction> block in front of the message, so Claude Code did not expand the command. The user typed it, so treat this message as the expanded command for the skill \`trackbed:${skill.name}\`:`,
    "",
    `1. Read \`${skillFile}\` and follow its instructions after the YAML frontmatter, exactly as if they had been expanded into this message.`,
    `2. Base directory for this skill: ${skill.dir}`,
    "3. Substitute these values wherever the skill uses them:",
    `- \`\${CLAUDE_PLUGIN_ROOT}\` means \`${pluginRoot}\`.`,
    argumentLine,
    "",
    "Do not call the Skill tool for this skill. This message is already the user's invocation, and the Skill tool may refuse a skill that only the user can start.",
  ].join("\n");
}

function main() {
  let input;
  try {
    input = JSON.parse(fs.readFileSync(0, "utf8"));
  } catch {
    process.stdout.write("{}\n");
    return;
  }
  const pluginRoot = path.resolve(__dirname, "..", "..");
  const output = respond(input, { pluginRoot, env: process.env });
  process.stdout.write(`${JSON.stringify(output)}\n`);
}

if (require.main === module) {
  main();
}

module.exports = { findSkill, parseLeadingCommand, respond };
