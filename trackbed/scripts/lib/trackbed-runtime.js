// @ts-check
"use strict";

const fs = require("fs");
const path = require("path");

/**
 * Host vocabulary matches the `trackbed-platforms` skill frontmatter values.
 */
const PLATFORM_CODEX = "codex";
const PLATFORM_CLAUDE_CODE = "claude-code";
// A Claude Code plugin root carries `.claude-plugin/`; the converted Codex
// plugin carries `.codex-plugin/` instead.
const PLUGIN_MANIFESTS = [
  path.join(".claude-plugin", "plugin.json"),
  path.join(".codex-plugin", "plugin.json"),
];

// Conductor prepends a `<system_instruction>` block to the user's own text.
const CONDUCTOR_INSTRUCTION_CLOSE = "</system_instruction>";
// Codex delivers repository instructions and environment details as user
// messages; they can mention skill commands the user never typed.
const CODEX_INJECTED_CONTEXT_PREFIXES = [
  "# AGENTS.md instructions for",
  "<environment_context>",
];
const CODEX_ROLLOUT_FILE_PATTERN = /^rollout-.+\.jsonl$/;

/**
 * @typedef {{ text: string, recordedAt: string }} CodexPrompt
 * @typedef {Object} CodexRollout
 * @property {boolean} skipFile Subagent threads replay the parent's prompts.
 * @property {string} sessionId
 * @property {(record: unknown) => CodexPrompt[]} prompts
 */

/**
 * Resolves the host that produced a hook payload. Codex markers are checked
 * before `CLAUDECODE` because a Codex process started from a Claude Code shell
 * inherits `CLAUDECODE=1`.
 * @param {unknown} input
 * @param {NodeJS.ProcessEnv} env
 * @returns {string}
 */
function detectPlatform(input, env) {
  const payload = asRecord(input);
  if (isNonEmptyString(payload.platform)) return payload.platform;
  const override = trackbedSetting(env, "TRACKBED_AGENT_PLATFORM");
  if (override) return override;
  if (
    isNonEmptyString(payload.turn_id) ||
    (typeof payload.transcript_path === "string" &&
      CODEX_ROLLOUT_FILE_PATTERN.test(path.basename(payload.transcript_path)))
  ) {
    return PLATFORM_CODEX;
  }
  if (env.CLAUDECODE === "1") return PLATFORM_CLAUDE_CODE;
  return "";
}

/**
 * Returns the manifest version of the plugin copy at `pluginRoot`. An empty
 * string means no host manifest there was readable; reports show it as
 * `unknown`, like records written before versions were stamped.
 * @param {string} pluginRoot
 * @returns {string}
 */
function readPluginVersion(pluginRoot) {
  for (const manifest of PLUGIN_MANIFESTS) {
    let parsed;
    try {
      parsed = JSON.parse(
        fs.readFileSync(path.join(pluginRoot, manifest), "utf8"),
      );
    } catch {
      continue;
    }
    const version = asRecord(parsed).version;
    if (isNonEmptyString(version)) return version;
  }
  return "";
}

/**
 * @param {string} text
 * @returns {string} The text after the last Conductor instruction block.
 */
function stripConductorInstructions(text) {
  const end = text.lastIndexOf(CONDUCTOR_INSTRUCTION_CLOSE);
  return end === -1
    ? text
    : text.slice(end + CONDUCTOR_INSTRUCTION_CLOSE.length);
}

/**
 * Classifies a Codex rollout by its first line. Forked threads carry a second
 * `session_meta` for the parent history, so later records never reclassify.
 * @param {unknown} firstRecord
 * @returns {CodexRollout | null}
 */
function openCodexRollout(firstRecord) {
  const record = asRecord(firstRecord);
  if (record.type !== "session_meta" || !isRecord(record.payload)) return null;
  const payload = asRecord(record.payload);
  const source = payload.source;
  return {
    skipFile:
      payload.thread_source === "subagent" ||
      (isRecord(source) && "subagent" in source),
    sessionId: isNonEmptyString(payload.id)
      ? payload.id
      : stringValue(payload.session_id),
    prompts: codexUserPrompts,
  };
}

/**
 * Only `response_item` user messages count; `event_msg` and `compacted`
 * records repeat the same text.
 * @param {unknown} input
 * @returns {CodexPrompt[]}
 */
function codexUserPrompts(input) {
  const record = asRecord(input);
  const payload = asRecord(record.payload);
  if (
    record.type !== "response_item" ||
    payload.type !== "message" ||
    payload.role !== "user" ||
    !Array.isArray(payload.content)
  ) {
    return [];
  }
  const text = payload.content
    .map(asRecord)
    .filter((block) => block.type === "input_text")
    .map((block) => stringValue(block.text))
    .join("\n");
  const start = text.trimStart();
  if (
    CODEX_INJECTED_CONTEXT_PREFIXES.some((prefix) => start.startsWith(prefix))
  ) {
    return [];
  }
  return [
    {
      text: stripConductorInstructions(text),
      recordedAt: stringValue(record.timestamp),
    },
  ];
}

/** @param {unknown} value @returns {value is string} */
function isNonEmptyString(value) {
  return typeof value === "string" && value !== "";
}

/** @param {unknown} value */
function stringValue(value) {
  return typeof value === "string" ? value : "";
}

/** @param {unknown} value @returns {value is Record<string, unknown>} */
function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** @param {unknown} value @returns {Record<string, unknown>} */
function asRecord(value) {
  return isRecord(value) ? value : {};
}

/**
 * Read the installed skill folders and return a resolver for that snapshot.
 * Exact names take precedence, and ambiguous aliases have no owner.
 * @param {string} skillsRoot
 * @returns {(typedName: string) => {dir: string, name: string} | null}
 */
function readSkillFolderResolver(skillsRoot) {
  const folders = new Set();
  /** @type {Map<string, string | null>} */
  const aliases = new Map();
  for (const entry of fs.readdirSync(skillsRoot, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.name.startsWith(".")) continue;
    folders.add(entry.name);
    const alias = entry.name.replaceAll(":", "-");
    aliases.set(alias, aliases.has(alias) ? null : entry.name);
  }
  return (typedName) => {
    const name = folders.has(typedName) ? typedName : aliases.get(typedName);
    return name ? { dir: path.join(skillsRoot, name), name } : null;
  };
}

/**
 * Resolve a TRACKBED_ setting with the same precedence as trackbed_setting.
 * @param {NodeJS.ProcessEnv} env
 * @param {`TRACKBED_${string}`} name
 * @param {string} [defaultValue]
 */
function trackbedSetting(env, name, defaultValue = "") {
  return (
    env[name] || env[`KRAMME_${name.slice("TRACKBED_".length)}`] || defaultValue
  );
}

/**
 * Resolve state files using the same directory precedence as trackbed-paths.sh.
 * @param {string} file
 * @param {NodeJS.ProcessEnv} [env]
 * @returns {string | null}
 */
function trackbedStatePath(file, env = process.env) {
  const base =
    env.XDG_STATE_HOME || (env.HOME && path.join(env.HOME, ".local", "state"));
  if (!base) return null;

  const current = path.join(base, "trackbed", file);
  const previous = path.join(base, "kramme-cc-workflow", file);
  if (isFile(current)) return current;
  return isFile(previous) ? previous : current;
}

/** @param {string} file */
function isFile(file) {
  try {
    return fs.statSync(file).isFile();
  } catch {
    return false;
  }
}

module.exports = {
  PLATFORM_CLAUDE_CODE,
  PLATFORM_CODEX,
  asRecord,
  detectPlatform,
  openCodexRollout,
  readPluginVersion,
  readSkillFolderResolver,
  stringValue,
  stripConductorInstructions,
  trackbedSetting,
  trackbedStatePath,
};
