import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";
import { buildSite } from "../lib/build-site.mjs";
import {
  AGENTS_PAGE,
  CATALOG_PATH,
  GUIDE_PAGES,
  GUIDES_DIR,
  PLUGIN_MANIFEST_PATH,
  README_PAGES,
  README_SECTIONS_OFF_SITE,
  REGISTRY_PATH,
  SKILLS_PAGE,
} from "../lib/config.mjs";

const CREATE = "trackbed/skills/pr:create/SKILL.md";
const COMMIT = "trackbed/skills/git:commit-message/SKILL.md";
const REVIEWER = "trackbed/agents/code-reviewer.md";

const SKILL_ROWS = [
  "Who can start a skill.",
  "",
  "### Pull Requests",
  "",
  "| Skill | Invocation | Arguments | Description |",
  "| --- | --- | --- | --- |",
  "| `/trackbed:pr:create` | User, Auto | `[--draft]` | Publish a PR. |",
  "",
  "### Background Skills",
  "",
  "| Skill | Invocation | Arguments | Description |",
  "| --- | --- | --- | --- |",
  "| `trackbed:git:commit-message` | Background | — | Write commit messages. |",
].join("\n");

const [firstPage] = README_PAGES;
const [firstGuide] = GUIDE_PAGES;

function sectionBody({ heading, slug }) {
  if (slug === AGENTS_PAGE) return "`trackbed:code-reviewer` reviews code.";
  if (heading === firstPage.heading) {
    return `Run \`/trackbed:pr:create --draft\`. See [gates](${GUIDES_DIR}/${firstGuide.file}#gates) and [contributing](CONTRIBUTING.md).`;
  }
  return `Text for ${heading}.`;
}

function readmeText({
  intro = "A plugin for testing:",
  skillRows = SKILL_ROWS,
} = {}) {
  return [
    "# trackbed",
    "",
    intro,
    "",
    "- one thing",
    "",
    ...README_PAGES.flatMap((page) => [
      `## ${page.heading}`,
      "",
      page.slug === SKILLS_PAGE ? skillRows : sectionBody(page),
      "",
    ]),
    `## ${README_SECTIONS_OFF_SITE[0]}`,
    "",
    "Stays on GitHub.",
    "",
  ].join("\n");
}

/**
 * A small repository with the shape the site reads: every README section and
 * guide that config.mjs places, two skills, and one agent. Its content is
 * fixed here, so these tests do not move when the real documentation does.
 */
function fixtureRepo(t, overrides = {}) {
  const root = mkdtempSync(path.join(tmpdir(), "trackbed-site-fixture-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));

  const files = {
    [PLUGIN_MANIFEST_PATH]: JSON.stringify({
      name: "trackbed",
      version: "1.2.3",
      description: "Fallback tagline",
    }),
    "CONTRIBUTING.md": "# Contributing\n",
    "README.md": readmeText(),
    ...Object.fromEntries(
      GUIDE_PAGES.map(({ file }) => [
        `${GUIDES_DIR}/${file}`,
        `# Guide ${file}\n\nText.\n`,
      ]),
    ),
    [`${GUIDES_DIR}/${firstGuide.file}`]: [
      "# Review Workflows",
      "",
      "Start from the [README](../../README.md#pull-requests), then run `/trackbed:pr:create` with `trackbed:code-reviewer`.",
      "",
      "## Gates",
      "",
    ].join("\n"),
    [CATALOG_PATH]: JSON.stringify({
      skills: [
        {
          name: "trackbed:git:commit-message",
          invocation: "Background",
          path: COMMIT,
        },
        { name: "trackbed:pr:create", invocation: "User, Auto", path: CREATE },
      ],
      agents: [{ name: "trackbed:code-reviewer", path: REVIEWER }],
      hooks: [],
    }),
    [REGISTRY_PATH]: JSON.stringify({
      readme_skill_sync: {
        summaries: {
          "trackbed:git:commit-message": "Write commit messages.",
          "trackbed:pr:create": "Publish a PR; `--draft` opens a draft.",
        },
      },
      readme_agent_sync: {
        summaries: { "trackbed:code-reviewer": "Reviews recent code." },
      },
    }),
    [CREATE]: [
      "---",
      "name: pr:create",
      'description: "Publish a PR with <ISSUE-ID> and *care*. Use when delegated by trackbed:git:commit-message, not by trackbed:pr:create itself or `trackbed:git:commit-message`."',
      'argument-hint: "[--draft] [--base <branch>]"',
      "user-invocable: true",
      "---",
      "",
      "Hand the diff to trackbed:code-reviewer first.",
      "",
    ].join("\n"),
    "trackbed/skills/pr:create/references/notes.md":
      "Mentions trackbed:unknown:skill, which is not a component.\n",
    [COMMIT]: [
      "---",
      "name: git:commit-message",
      "description: Write commit messages.",
      "user-invocable: false",
      "trackbed-platforms: [claude-code]",
      "---",
      "",
      "Used by trackbed:pr:create.",
      "",
    ].join("\n"),
    [REVIEWER]: [
      "---",
      "name: code-reviewer",
      "description: Reviews code.",
      "model: inherit",
      "disallowedTools: Write, Edit, NotebookEdit",
      "---",
      "",
    ].join("\n"),
    ...overrides,
  };

  for (const [repoPath, content] of Object.entries(files)) {
    if (content === undefined) continue;
    const file = path.join(root, repoPath);
    mkdirSync(path.dirname(file), { recursive: true });
    writeFileSync(file, content);
  }
  return root;
}

function pageBodies(site) {
  return new Map(site.pages.map((page) => [page.slug, page.body]));
}

test("renders a skill page from its frontmatter, summary, and mentions", (t) => {
  const site = buildSite(fixtureRepo(t));
  const page = site.pages.find(
    (candidate) => candidate.slug === "skills/pr-create",
  );

  assert.deepEqual(page.frontmatter, {
    title: "trackbed:pr:create",
    description: "Publish a PR; --draft opens a draft.",
    editUrl: `https://github.com/trackbed/skills/edit/main/${CREATE}`,
  });
  assert.equal(
    page.body,
    [
      "Publish a PR; `--draft` opens a draft.",
      "",
      "```text wrap",
      "/trackbed:pr:create [--draft] [--base <branch>]",
      "```",
      "",
      "- **Invocation:** [User, Auto](/skills/)",
      "- **Hosts:** Claude Code, Codex (`$trackbed:pr:create` in Codex)",
      "- **Category:** [Pull Requests](/skills/#pull-requests)",
      `- **Source:** [\`${CREATE}\`](https://github.com/trackbed/skills/blob/main/${CREATE})`,
      "",
      "## Description",
      "",
      "Publish a PR with &lt;ISSUE-ID> and \\*care\\*. Use when delegated by [`trackbed:git:commit-message`](/skills/git-commit-message/), not by `trackbed:pr:create` itself or `trackbed:git:commit-message`.",
      "",
      "## Guides",
      "",
      `- [${firstPage.heading}](/${firstPage.slug}/)`,
      `- [Review Workflows](/${firstGuide.slug}/)`,
      "",
      "## Related",
      "",
      "- **Refers to:** [`trackbed:git:commit-message`](/skills/git-commit-message/)",
      "- **Referred to by:** [`trackbed:git:commit-message`](/skills/git-commit-message/)",
      "- **Agents:** [`trackbed:code-reviewer`](/agents/code-reviewer/)",
    ].join("\n"),
  );
});

test("leaves out what a background, single-host skill does not have", (t) => {
  const body = pageBodies(buildSite(fixtureRepo(t))).get(
    "skills/git-commit-message",
  );

  assert.equal(
    body,
    [
      "Write commit messages.",
      "",
      "- **Invocation:** [Background](/skills/)",
      "- **Hosts:** Claude Code",
      "- **Category:** [Background Skills](/skills/#background-skills)",
      `- **Source:** [\`${COMMIT}\`](https://github.com/trackbed/skills/blob/main/${COMMIT})`,
      "",
      "## Description",
      "",
      "Write commit messages.",
      "",
      "## Related",
      "",
      "- **Refers to:** [`trackbed:pr:create`](/skills/pr-create/)",
      "- **Referred to by:** [`trackbed:pr:create`](/skills/pr-create/)",
    ].join("\n"),
  );
});

test("renders an agent page with the skills and guides that use it", (t) => {
  const body = pageBodies(buildSite(fixtureRepo(t))).get(
    "agents/code-reviewer",
  );

  assert.equal(
    body,
    [
      "Reviews recent code.",
      "",
      "- **Changes code:** No, it reports findings",
      "- **Model:** `inherit`",
      `- **Source:** [\`${REVIEWER}\`](https://github.com/trackbed/skills/blob/main/${REVIEWER})`,
      "",
      "## Description",
      "",
      "Reviews code.",
      "",
      "## Used by",
      "",
      "- [`trackbed:pr:create`](/skills/pr-create/)",
      "",
      "## Guides",
      "",
      `- [Review Workflows](/${firstGuide.slug}/)`,
    ].join("\n"),
  );
});

test("routes links and code spans in README sections and guides", (t) => {
  const bodies = pageBodies(buildSite(fixtureRepo(t)));

  assert.equal(
    bodies.get(firstPage.slug),
    `Run [\`/trackbed:pr:create --draft\`](/skills/pr-create/). See [gates](/${firstGuide.slug}/#gates) and [contributing](https://github.com/trackbed/skills/blob/main/CONTRIBUTING.md).`,
  );
  assert.equal(
    bodies.get(firstGuide.slug),
    "Start from the [README](/skills/#pull-requests), then run [`/trackbed:pr:create`](/skills/pr-create/) with [`trackbed:code-reviewer`](/agents/code-reviewer/).\n\n## Gates",
  );
  assert.match(
    bodies.get(SKILLS_PAGE),
    /^Who can start a skill\.\n\n## Pull Requests\n/,
  );
});

test("builds the landing page and sidebar from the README and the catalog", (t) => {
  const site = buildSite(fixtureRepo(t));
  const home = site.pages.find((page) => page.slug === "index");
  const slugs = new Set(site.pages.map((page) => page.slug));
  const skills = site.sidebar.find((group) => group.label === "Skills");

  assert.equal(site.version, "1.2.3");
  assert.equal(home.frontmatter.hero.tagline, "A plugin for testing");
  assert.match(
    home.body,
    /^- one thing\n\nThis site documents trackbed v1\.2\.3\./,
  );
  for (const action of home.frontmatter.hero.actions) {
    const slug = action.link.replace(/^\/|\/$/g, "");
    assert.ok(
      action.link.startsWith("https://") || slugs.has(slug),
      `the home page links to ${action.link}`,
    );
  }
  assert.deepEqual(skills.items, [
    { label: "Overview", slug: "skills" },
    {
      label: "Pull Requests",
      collapsed: true,
      items: [{ label: "pr:create", slug: "skills/pr-create" }],
    },
    {
      label: "Background Skills",
      collapsed: true,
      items: [
        { label: "git:commit-message", slug: "skills/git-commit-message" },
      ],
    },
  ]);
});

test("links to the sources at the commit being documented", (t) => {
  const site = buildSite(fixtureRepo(t), { sourceRef: "abc123" });
  const page = site.pages.find(
    (candidate) => candidate.slug === "skills/pr-create",
  );
  const bodies = pageBodies(site);

  assert.match(
    page.body,
    new RegExp(
      `\\(https://github\\.com/trackbed/skills/blob/abc123/${CREATE}\\)`,
    ),
  );
  assert.match(
    bodies.get(firstPage.slug),
    /\(https:\/\/github\.com\/trackbed\/skills\/blob\/abc123\/CONTRIBUTING\.md\)/,
  );
  assert.match(bodies.get("index"), /\/blob\/abc123\/trackbed\/CHANGELOG\.md/);
  // Editing happens on the default branch, whatever commit the site shows.
  assert.equal(
    page.frontmatter.editUrl,
    `https://github.com/trackbed/skills/edit/main/${CREATE}`,
  );
});

test("keeps README text as text in the hero, which Starlight renders as HTML", (t) => {
  const site = buildSite(
    fixtureRepo(t, {
      "README.md": readmeText({ intro: "Run `trackbed:<name>` & go:" }),
    }),
  );
  const home = site.pages.find((page) => page.slug === "index");

  assert.equal(
    home.frontmatter.hero.tagline,
    "Run trackbed:&lt;name&gt; &amp; go",
  );
  assert.equal(home.frontmatter.description, "Run trackbed:<name> & go");
});

test("reads an agent as read-only only when both write tools are disallowed", (t) => {
  const agent = (disallowedTools) =>
    pageBodies(
      buildSite(
        fixtureRepo(t, {
          [REVIEWER]: `---\nname: code-reviewer\ndescription: Reviews code.\ndisallowedTools: ${disallowedTools}\n---\n`,
        }),
      ),
    ).get("agents/code-reviewer");

  assert.match(agent("[Write, Edit]"), /\*\*Changes code:\*\* No/);
  // "NotebookEdit" contains "Edit" but does not disallow it.
  assert.match(agent("Write, NotebookEdit"), /\*\*Changes code:\*\* Yes/);
});

test("fails the sync when a source stops fitting the site", (t) => {
  const withFile = (repoPath, content) => () =>
    buildSite(fixtureRepo(t, { [repoPath]: content }));

  assert.throws(
    withFile(`${GUIDES_DIR}/new-guide.md`, "# New\n"),
    /new-guide\.md is not placed/,
  );
  assert.throws(
    withFile("CONTRIBUTING.md", undefined),
    /README\.md: link target does not exist: CONTRIBUTING\.md/,
  );
  assert.throws(
    withFile(
      REGISTRY_PATH,
      JSON.stringify({ readme_skill_sync: { summaries: {} } }),
    ),
    /no README summary for trackbed:git:commit-message/,
  );
  // A skill the README's tables do not list has no category to sit under.
  assert.throws(
    withFile(
      "README.md",
      readmeText({ skillRows: SKILL_ROWS.split("### Background Skills")[0] }),
    ),
    /README\.md: no table in the Skills section has a row for trackbed:git:commit-message/,
  );
  // The definition would stay behind in another section's page.
  assert.throws(
    withFile("README.md", `${readmeText()}\n[ship]: CONTRIBUTING.md\n`),
    /reference-style link or footnote \(\[ship\]: CONTRIBUTING\.md\)/,
  );
  // Errors from the Markdown rewrite name the file they are about.
  assert.throws(
    withFile(
      `${GUIDES_DIR}/${firstGuide.file}`,
      "Review Workflows\n================\n",
    ),
    new RegExp(`${GUIDES_DIR}/${firstGuide.file}: Only "#" headings`),
  );
});
