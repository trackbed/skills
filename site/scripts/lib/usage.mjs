import { USAGE_DIR } from "./config.mjs";
import { nodeText, parseMarkdown, walk } from "./markdown.mjs";

/** The `##` sections a usage guide may hold, in the order it must hold them. */
export const USAGE_SECTIONS = [
  "Before you run it",
  "Arguments",
  "Options",
  "Examples",
  "What you get",
];
const REQUIRED_SECTIONS = ["Examples", "What you get"];

const FLAG = /--[a-z][a-z0-9-]*/g;

export function usagePath(skill) {
  return `${USAGE_DIR}/${skill.slug.replace(/^skills\//, "")}.md`;
}

function flagsIn(text) {
  return new Set(text.match(FLAG) ?? []);
}

function listFlags(flags) {
  return [...flags].sort().join(", ");
}

/** The flags a table documents: the ones written in its first column. */
function documentedFlags(nodes) {
  const flags = new Set();
  for (const node of nodes) {
    walk(node, (candidate) => {
      if (candidate.type !== "table") return;
      for (const row of candidate.children.slice(1)) {
        for (const flag of flagsIn(nodeText(row.children[0]))) flags.add(flag);
      }
    });
  }
  return flags;
}

function codeBlocks(nodes) {
  const blocks = [];
  for (const node of nodes) {
    walk(node, (candidate) => {
      if (candidate.type === "code") blocks.push(candidate);
    });
  }
  return blocks;
}

/**
 * Check a skill's usage guide against the skill and split it into the part
 * above its first `##` heading and the sections below.
 *
 * The guide is written by hand, so the checks tie it to the skill's own
 * `argument-hint`: the Options table documents exactly the flags the skill
 * accepts, and every example is a command for this skill that uses only those
 * flags. A flag added to or removed from the skill fails here until the guide
 * says so too.
 *
 * Returns `{ lead, sections }` as source text; errors do not name the file.
 */
export function readUsage(text, skill) {
  const tree = parseMarkdown(text);
  const blocks = tree.children;

  const title = blocks[0];
  if (title?.type !== "heading" || title.depth !== 1) {
    throw new Error(`the first line must be "# ${skill.shortName}"`);
  }
  if (nodeText(title) !== skill.shortName) {
    throw new Error(
      `the title is "${nodeText(title)}" but the skill is "${skill.shortName}"`,
    );
  }

  const found = [];
  for (const node of blocks.slice(1)) {
    if (node.type !== "heading") {
      found.at(-1)?.nodes.push(node);
      continue;
    }
    const heading = nodeText(node);
    if (node.depth !== 2 || !USAGE_SECTIONS.includes(heading)) {
      throw new Error(
        `"${heading}" is not a usage section; use "## " with one of: ${USAGE_SECTIONS.join(", ")}`,
      );
    }
    found.push({
      title: heading,
      start: node.position.start.offset,
      nodes: [],
    });
  }

  const titles = found.map((section) => section.title);
  const expected = USAGE_SECTIONS.filter((name) => titles.includes(name));
  if (titles.join("|") !== expected.join("|")) {
    throw new Error(
      `sections must appear once each, in this order: ${USAGE_SECTIONS.join(", ")}`,
    );
  }
  for (const name of REQUIRED_SECTIONS) {
    if (!titles.includes(name)) throw new Error(`"## ${name}" is missing`);
  }
  for (const section of found) {
    if (section.nodes.length === 0) {
      throw new Error(`"## ${section.title}" is empty`);
    }
  }

  const accepted = flagsIn(skill.argumentHint ?? "");
  const options = found.find((section) => section.title === "Options");
  const documented = documentedFlags(options?.nodes ?? []);
  const undocumented = accepted.difference(documented);
  if (undocumented.size > 0) {
    throw new Error(
      `the Options table has no row for ${listFlags(undocumented)}, which the skill's argument-hint lists`,
    );
  }
  const unknown = documented.difference(accepted);
  if (unknown.size > 0) {
    throw new Error(
      `the Options table documents ${listFlags(unknown)}, which the skill's argument-hint does not list`,
    );
  }

  const examples = found.find((section) => section.title === "Examples");
  const commands = codeBlocks(examples.nodes)
    .flatMap((block) => block.value.split("\n"))
    .map((line) => line.trim())
    .filter((line) => line !== "" && !line.startsWith("#"));
  if (commands.length === 0) {
    throw new Error(`"## Examples" needs a code block with a command`);
  }
  const command = `/${skill.name}`;
  for (const line of commands) {
    if (line !== command && !line.startsWith(`${command} `)) {
      throw new Error(
        `every example must start with ${command}; found: ${line}`,
      );
    }
    const stray = flagsIn(line).difference(accepted);
    if (stray.size > 0) {
      throw new Error(
        `an example uses ${listFlags(stray)}, which the skill's argument-hint does not list: ${line}`,
      );
    }
  }

  const leadEnd = found[0].start;
  return {
    lead: text.slice(title.position.end.offset, leadEnd).trim(),
    sections: text.slice(leadEnd).trim(),
  };
}
