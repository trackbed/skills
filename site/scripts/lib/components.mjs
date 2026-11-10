import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { parse as parseYaml } from "yaml";
import { CATALOG_PATH, REGISTRY_PATH } from "./config.mjs";
import { splitFrontmatter } from "./markdown.mjs";

/** A qualified skill or agent name, such as `trackbed:pr:create`. */
export const COMPONENT_NAME = "trackbed:[a-z0-9]+(?:[:-][a-z0-9]+)*";
const ALL_HOSTS = ["claude-code", "codex"];
const WRITE_TOOLS = ["Write", "Edit"];

/** Qualified component names (`trackbed:pr:create`) that appear in `text`. */
export function findComponentNames(text) {
  return new Set(text.match(new RegExp(COMPONENT_NAME, "g")) ?? []);
}

function readMarkdownTree(directory) {
  return readdirSync(directory, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(".md"))
    .map((entry) =>
      readFileSync(path.join(entry.parentPath, entry.name), "utf8"),
    )
    .join("\n");
}

function requireSummary(summaries, name) {
  const summary = summaries[name];
  if (typeof summary !== "string" || summary === "") {
    throw new Error(`${REGISTRY_PATH} has no README summary for ${name}`);
  }
  return summary;
}

function shortName(name) {
  return name.replace(/^trackbed:/, "");
}

/**
 * Load every shipped skill and agent. The component catalog says which
 * components exist, each component's own file supplies its frontmatter, and
 * the README summaries come from the registry the README rows are synced from.
 */
export function loadComponents(repoRoot) {
  const read = (repoPath) =>
    readFileSync(path.join(repoRoot, repoPath), "utf8");
  const catalog = JSON.parse(read(CATALOG_PATH));
  const registry = parseYaml(read(REGISTRY_PATH));

  const skills = catalog.skills.map((entry) => {
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

  const agents = catalog.agents.map((entry) => {
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
