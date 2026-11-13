import { COMPONENT_NAME } from "./components.mjs";
import {
  CATALOG_PATH,
  HOME_PAGE,
  HOME_TAB_TITLE,
  README_PATH,
  REPO_URL,
  SKILLS_PAGE,
} from "./config.mjs";
import { HOST_COMMAND_LANGUAGE, nodeText, parseMarkdown } from "./markdown.mjs";
import { githubEditUrl, pageUrl } from "./routes.mjs";

const HOST_LABELS = { "claude-code": "Claude Code", codex: "Codex" };

function codeLink(component) {
  return `[\`${component.name}\`](${pageUrl(component.slug)})`;
}

/** `sourceUrl(repoPath)` is the file on GitHub at the commit the site documents. */
function sourceLink(repoPath, sourceUrl) {
  return `[\`${repoPath}\`](${sourceUrl(repoPath)})`;
}

/** Starlight inserts the hero tagline as HTML, and the README's words are text. */
function escapeHtml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function byName(a, b) {
  return a.name.localeCompare(b.name);
}

/**
 * Frontmatter descriptions are plain text, not Markdown. Keep their code
 * spans, stop `*` and `<` from being read as markup, and show every component
 * name as code, linked when it is another component with a page.
 */
function renderDescription(description, self, componentsByName) {
  return description
    .split(/(`[^`]*`)/)
    .map((part) => {
      if (part.startsWith("`")) return part;
      return part
        .replaceAll("<", "&lt;")
        .replaceAll("*", "\\*")
        .replace(new RegExp(COMPONENT_NAME, "g"), (name) => {
          const component = componentsByName.get(name);
          return component && component !== self
            ? codeLink(component)
            : `\`${name}\``;
        });
    })
    .join("");
}

function plainText(markdown) {
  return markdown.replaceAll("`", "");
}

function bulletList(items) {
  return items.map((item) => `- ${item}`).join("\n");
}

function section(heading, body) {
  return body ? `## ${heading}\n\n${body}` : null;
}

function guideList(guides) {
  return bulletList(
    guides.map((guide) => `[${guide.title}](${pageUrl(guide.slug)})`),
  );
}

function inlineLinks(label, components) {
  if (components.length === 0) return null;
  return `**${label}:** ${[...components].sort(byName).map(codeLink).join(", ")}`;
}

/**
 * An invisible element whose attribute the search index reads as page text.
 * Search matches a word from its start, and a component name is one word
 * (`trackbed:pr:code-review`), so the names people type without the prefix
 * would otherwise find nothing: `pr:code-review` and `code-review`. It closes
 * the page so that it stays out of the excerpts of other matches.
 */
function searchNames(component) {
  const short = component.shortName;
  const names = new Set([short, short.slice(short.lastIndexOf(":") + 1)]);
  return `<span data-pagefind-index-attrs="data-names" data-names="${[...names].join(" ")}"></span>`;
}

/** The frontmatter description, set apart as what the host reads. */
function hostDescription(component, reads, componentsByName) {
  const description = renderDescription(
    component.description,
    component,
    componentsByName,
  );
  return section("Host description", `${reads}\n\n> ${description}`);
}

const HOST_READS = {
  User: "The host shows this text in its command menu. It never starts this skill on its own.",
  Background:
    "The host reads this text to decide when to apply the skill. You cannot start it yourself.",
};
const HOST_READS_AUTO =
  "The host shows this text in its command menu, and reads it to decide when to start the skill without being asked.";

export function skillPage(skill, related) {
  const {
    category,
    guides,
    refersTo,
    referredBy,
    agents,
    componentsByName,
    sourceUrl,
    usage,
  } = related;
  const hosts = skill.hosts.map((host) => HOST_LABELS[host] ?? host).join(", ");
  const command = [`/${skill.name}`, skill.argumentHint]
    .filter(Boolean)
    .join(" ");
  const codex =
    skill.userInvocable && skill.hosts.includes("codex")
      ? ` (\`$${skill.name}\` in Codex)`
      : "";

  const facts = [
    `**Invocation:** [${skill.invocation}](${pageUrl(SKILLS_PAGE)})`,
    `**Hosts:** ${hosts}${codex}`,
    category
      ? `**Category:** [${category.title}](${pageUrl(SKILLS_PAGE, category.anchor)})`
      : null,
    `**Source:** ${sourceLink(skill.path, sourceUrl)}`,
  ].filter(Boolean);

  const body = [
    skill.summary,
    usage?.lead,
    skill.userInvocable
      ? `\`\`\`${HOST_COMMAND_LANGUAGE}\n${command}\n\`\`\``
      : null,
    bulletList(facts),
    usage?.sections,
    section("Guides", guideList(guides)),
    section(
      "Related",
      bulletList(
        [
          inlineLinks("Refers to", refersTo),
          inlineLinks("Referred to by", referredBy),
          inlineLinks("Agents", agents),
        ].filter(Boolean),
      ),
    ),
    hostDescription(
      skill,
      HOST_READS[skill.invocation] ?? HOST_READS_AUTO,
      componentsByName,
    ),
    searchNames(skill),
  ];

  return {
    slug: skill.slug,
    frontmatter: {
      title: skill.name,
      description: plainText(skill.summary),
      editUrl: githubEditUrl(skill.path),
    },
    body: body.filter(Boolean).join("\n\n"),
  };
}

export function agentPage(
  agent,
  { guides, usedBy, componentsByName, sourceUrl },
) {
  const facts = [
    `**Changes code:** ${agent.readOnly ? "No, it reports findings" : "Yes"}`,
    agent.model ? `**Model:** \`${agent.model}\`` : null,
    `**Source:** ${sourceLink(agent.path, sourceUrl)}`,
  ].filter(Boolean);

  const body = [
    agent.summary,
    bulletList(facts),
    section("Used by", bulletList([...usedBy].sort(byName).map(codeLink))),
    section("Guides", guideList(guides)),
    hostDescription(
      agent,
      "The host reads this text to decide when to launch the agent.",
      componentsByName,
    ),
    searchNames(agent),
  ];

  return {
    slug: agent.slug,
    frontmatter: {
      title: agent.name,
      description: plainText(agent.summary),
      editUrl: githubEditUrl(agent.path),
    },
    body: body.filter(Boolean).join("\n\n"),
  };
}

/** Where the README introduction's closing notices (`> [!NOTE]`) begin. */
function noticesStart(text) {
  const blocks = parseMarkdown(text).children;
  const index = blocks.findIndex(
    (node) => node.type === "blockquote" && /^\[!/.test(nodeText(node)),
  );
  if (index === -1) return text.length;
  // A comment that switches the formatter off belongs with the notice below it.
  const before = blocks[index - 1];
  const first = before?.type === "html" ? before : blocks[index];
  return first.position.start.offset;
}

/**
 * The landing page is the README's introduction with the Quick Start inside
 * it: the first paragraph becomes the hero tagline, what the plugin does comes
 * next, then how to install it, and the introduction's notices close the page.
 */
export function homePage({
  title,
  intro,
  renderIntro,
  quickStart,
  version,
  fallbackTagline,
  sourceUrl,
}) {
  const first = parseMarkdown(intro).children[0];
  let tagline = fallbackTagline;
  let rest = intro;
  if (first?.type === "paragraph") {
    tagline = nodeText(first).replace(/\s*:$/, "");
    rest = intro.slice(first.position.end.offset);
  }
  const split = noticesStart(rest);

  return {
    slug: HOME_PAGE,
    frontmatter: {
      title,
      description: tagline,
      // Starlight would title the tab "trackbed | trackbed".
      head: [{ tag: "title", content: HOME_TAB_TITLE }],
      template: "splash",
      editUrl: githubEditUrl(README_PATH),
      hero: {
        tagline: escapeHtml(tagline),
        actions: [
          {
            text: "Quick Start",
            link: pageUrl("start/quick-start"),
            icon: "right-arrow",
          },
          {
            text: "Browse skills",
            link: pageUrl(SKILLS_PAGE),
            variant: "minimal",
          },
          {
            text: "GitHub",
            link: REPO_URL,
            icon: "external",
            variant: "minimal",
          },
        ],
      },
    },
    body: [
      renderIntro(rest.slice(0, split)).trim(),
      `## ${quickStart.heading}\n\n${quickStart.body}`,
      renderIntro(rest.slice(split)).trim(),
      `This site documents trackbed ${version}. See the [changelog](${sourceUrl("trackbed/CHANGELOG.md")}) for what changed, or the [component catalog](${sourceUrl(CATALOG_PATH)}) for a machine-readable index.`,
    ]
      .filter(Boolean)
      .join("\n\n"),
  };
}
