import { COMPONENT_NAME } from "./components.mjs";
import {
  CATALOG_PATH,
  HOME_PAGE,
  README_PATH,
  REPO_URL,
  SKILLS_PAGE,
} from "./config.mjs";
import { nodeText, parseMarkdown } from "./markdown.mjs";
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

export function skillPage(skill, related) {
  const {
    category,
    guides,
    refersTo,
    referredBy,
    agents,
    componentsByName,
    sourceUrl,
  } = related;
  const hosts = skill.hosts.map((host) => HOST_LABELS[host] ?? host).join(", ");
  const usage = [`/${skill.name}`, skill.argumentHint]
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
    skill.userInvocable ? `\`\`\`text wrap\n${usage}\n\`\`\`` : null,
    bulletList(facts),
    section(
      "Description",
      renderDescription(skill.description, skill, componentsByName),
    ),
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
    section(
      "Description",
      renderDescription(agent.description, agent, componentsByName),
    ),
    section("Used by", bulletList([...usedBy].sort(byName).map(codeLink))),
    section("Guides", guideList(guides)),
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

/**
 * The landing page is the README's introduction: its first paragraph becomes
 * the hero tagline and the rest follows as the page body.
 */
export function homePage({
  title,
  intro,
  renderIntro,
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

  return {
    slug: HOME_PAGE,
    frontmatter: {
      title,
      description: tagline,
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
      renderIntro(rest).trim(),
      `This site documents trackbed ${version}. See the [changelog](${sourceUrl("trackbed/CHANGELOG.md")}) for what changed, or the [component catalog](${sourceUrl(CATALOG_PATH)}) for a machine-readable index.`,
    ].join("\n\n"),
  };
}
