// @ts-check

import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { parse as parseYaml } from "yaml";
import { CATALOG_PATH, REGISTRY_PATH } from "./config.mjs";
import { splitFrontmatter } from "./markdown.mjs";

/**
 * @typedef {object} Component
 * @property {string} name
 * @property {string} shortName
 * @property {string} slug
 * @property {string} path
 * @property {string} description
 * @property {string} summary
 */

/** @typedef {"User" | "User, Auto" | "Background" | "Hidden"} Invocation */

/**
 * @typedef {Component & {
 *   invocation: Invocation,
 *   argumentHint: string | null,
 *   userInvocable: boolean,
 *   hosts: string[],
 *   mentions: Set<string>
 * }} Skill
 */

/** @typedef {Component & {model: string | null, readOnly: boolean}} Agent */

/**
 * @typedef {Pick<Component, "name" | "path">} CatalogEntry
 * @typedef {{skills: (CatalogEntry & {invocation: Invocation})[], agents: CatalogEntry[]}} Catalog
 */

/** @typedef {{summaries: Record<string, string>}} SummaryRegistry */

/** A qualified skill or agent name, such as `trackbed:pr:create`. */
export const COMPONENT_NAME = "trackbed:[a-z0-9]+(?:[:-][a-z0-9]+)*";
const ALL_HOSTS = ["claude-code", "codex"];
const WRITE_TOOLS = ["Write", "Edit"];

/**
 * Qualified component names (`trackbed:pr:create`) that appear in `text`.
 * @param {string} text
 */
export function findComponentNames(text) {
  return new Set(text.match(new RegExp(COMPONENT_NAME, "g")) ?? []);
}

/** @param {string} directory */
function readMarkdownTree(directory) {
  return readdirSync(directory, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(".md"))
    .map((entry) =>
      readFileSync(path.join(entry.parentPath, entry.name), "utf8"),
    )
    .join("\n");
}

/**
 * @param {Record<string, string>} summaries
 * @param {string} name
 */
function requireSummary(summaries, name) {
  const summary = summaries[name];
  if (typeof summary !== "string" || summary === "") {
    throw new Error(`${REGISTRY_PATH} has no README summary for ${name}`);
  }
  return summary;
}

/** @param {string} name */
function shortName(name) {
  return name.replace(/^trackbed:/, "");
}

/**
 * Load every shipped skill and agent. The component catalog says which
 * components exist, each component's own file supplies its frontmatter, and
 * the README summaries come from the registry the README rows are synced from.
 *
 * @param {string} repoRoot
 * @returns {{skills: Skill[], agents: Agent[]}}
 */
export function loadComponents(repoRoot) {
  /** @param {string} repoPath */
  const read = (repoPath) =>
    readFileSync(path.join(repoRoot, repoPath), "utf8");
  /** @type {Catalog} */
  const catalog = JSON.parse(read(CATALOG_PATH));
  /** @type {{readme_skill_sync: SummaryRegistry, readme_agent_sync: SummaryRegistry}} */
  const registry = parseYaml(read(REGISTRY_PATH));

  /** @type {Skill[]} */
  const skills = catalog.skills.map((entry) => {
    /** @type {{data: {
     *   description: string,
     *   "argument-hint"?: string,
     *   "user-invocable"?: boolean,
     *   "trackbed-platforms"?: string[]
     * }}} */
    const { data } = splitFrontmatter(read(entry.path));
    const short = shortName(entry.name);
    return {
      name: entry.name,
      shortName: short,
      slug: `skills/${short.replaceAll(":", "-")}`,
      path: entry.path,
      invocation: entry.invocation,
      description: data.description,
      argumentHint: data["argument-hint"] ?? null,
      userInvocable: data["user-invocable"] !== false,
      hosts: data["trackbed-platforms"] ?? ALL_HOSTS,
      summary: requireSummary(registry.readme_skill_sync.summaries, entry.name),
      mentions: findComponentNames(
        readMarkdownTree(path.join(repoRoot, path.dirname(entry.path))),
      ),
    };
  });

  /** @type {Agent[]} */
  const agents = catalog.agents.map((entry) => {
    /** @type {{data: {
     *   description: string,
     *   disallowedTools?: string | string[],
     *   model?: string
     * }}} */
    const { data } = splitFrontmatter(read(entry.path));
    const disallowed = new Set(
      [data.disallowedTools ?? []]
        .flat()
        .flatMap((entry) => String(entry).split(","))
        .map((tool) => tool.trim()),
    );
    return {
      name: entry.name,
      shortName: shortName(entry.name),
      slug: `agents/${shortName(entry.name)}`,
      path: entry.path,
      description: data.description,
      model: data.model ?? null,
      readOnly: WRITE_TOOLS.every((tool) => disallowed.has(tool)),
      summary: requireSummary(registry.readme_agent_sync.summaries, entry.name),
    };
  });

  const slugs = new Set();
  for (const component of [...skills, ...agents]) {
    if (slugs.has(component.slug)) {
      throw new Error(`Two components share the page ${component.slug}`);
    }
    slugs.add(component.slug);
  }

  return { skills, agents };
}
