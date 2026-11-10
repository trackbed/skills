import assert from "node:assert/strict";
import { test } from "node:test";
import { analyzeReadme } from "../lib/readme.mjs";
import { createLinkResolver, githubUrl } from "../lib/routes.mjs";

const README = [
  "# trackbed",
  "",
  "Intro paragraph.",
  "",
  "## Quick Start",
  "",
  "### Updating",
  "",
  "## Skills",
  "",
  "### Pull Requests",
  "",
  "### Updating",
  "",
  "## Contributing",
  "",
  "### PR Title Format",
  "",
].join("\n");

const readme = analyzeReadme(README, {
  pages: [
    { heading: "Quick Start", slug: "start/quick-start" },
    { heading: "Skills", slug: "skills" },
  ],
  offSite: ["Contributing"],
});

const files = new Map([
  ["README.md", "file"],
  ["trackbed/docs", "directory"],
  ["trackbed/docs/review.md", "file"],
  ["trackbed/docs/development.md", "file"],
  ["trackbed/skills/pr:create/SKILL.md", "file"],
  ["trackbed/docs/flow.png", "file"],
]);
const resolveLink = createLinkResolver({
  pathKind: (repoPath) => files.get(repoPath) ?? null,
  filePages: new Map([["trackbed/docs/review.md", "guides/review"]]),
  readmeAnchors: readme.anchors,
});
const fromReadme = (url, currentPage = "start/quick-start") =>
  resolveLink(url, { sourceFile: "README.md", currentPage });
const fromGuide = (url) =>
  resolveLink(url, {
    sourceFile: "trackbed/docs/review.md",
    currentPage: "guides/review",
  });

test("places README headings on their pages", () => {
  assert.deepEqual(readme.anchors.get("trackbed"), {
    page: "index",
    anchor: null,
  });
  assert.deepEqual(readme.anchors.get("skills"), {
    page: "skills",
    anchor: null,
  });
  assert.deepEqual(readme.anchors.get("pull-requests"), {
    page: "skills",
    anchor: "pull-requests",
  });
  // GitHub numbers the second "Updating" across the README; its page holds only one.
  assert.deepEqual(readme.anchors.get("updating-1"), {
    page: "skills",
    anchor: "updating",
  });
  assert.deepEqual(readme.anchors.get("pr-title-format"), {
    page: null,
    anchor: null,
  });
  assert.equal(readme.intro.trim(), "Intro paragraph.");
  assert.equal(readme.sectionText(readme.sections[0]).trim(), "### Updating");
});

test("fails on a README section nobody has placed", () => {
  assert.throws(
    () =>
      analyzeReadme(README, { pages: [], offSite: ["Skills", "Contributing"] }),
    /README section "Quick Start" is not placed/,
  );
  assert.throws(
    () =>
      analyzeReadme(README, {
        pages: [{ heading: "Hooks", slug: "reference/hooks" }],
        offSite: ["Quick Start", "Skills", "Contributing"],
      }),
    /README has no "## Hooks" section/,
  );
});

test("routes README anchors to the page that holds the heading", () => {
  assert.equal(fromReadme("#skills"), "/skills/");
  assert.equal(fromReadme("#pull-requests"), "/skills/#pull-requests");
  assert.equal(fromReadme("#updating"), "#updating");
  assert.equal(
    fromReadme("#updating", "skills"),
    "/start/quick-start/#updating",
  );
  assert.equal(fromReadme("#updating-1"), "/skills/#updating");
  assert.equal(
    fromReadme("#pr-title-format"),
    "https://github.com/trackbed/skills/blob/main/README.md#pr-title-format",
  );
  assert.equal(fromGuide("../../README.md"), "/");
  assert.equal(fromGuide("../../README.md#skills"), "/skills/");
});

test("routes files to their page when they have one and to GitHub otherwise", () => {
  assert.equal(
    fromReadme("trackbed/docs/review.md#gates"),
    "/guides/review/#gates",
  );
  assert.equal(fromGuide("#gates"), "#gates");
  assert.equal(
    fromGuide("development.md#running-the-tests"),
    "https://github.com/trackbed/skills/blob/main/trackbed/docs/development.md#running-the-tests",
  );
  assert.equal(
    fromGuide("../skills/pr:create/SKILL.md"),
    "https://github.com/trackbed/skills/blob/main/trackbed/skills/pr:create/SKILL.md",
  );
  assert.equal(
    fromReadme("trackbed/docs/"),
    "https://github.com/trackbed/skills/tree/main/trackbed/docs",
  );
  assert.equal(
    fromReadme("https://example.com/a.md"),
    "https://example.com/a.md",
  );
  assert.equal(
    fromReadme("mailto:someone@example.com"),
    "mailto:someone@example.com",
  );
});

test("reads a leading slash as the repository root, as GitHub does", () => {
  assert.equal(fromGuide("/trackbed/docs/review.md#gates"), "#gates");
  assert.equal(fromGuide("/README.md#skills"), "/skills/");
  assert.throws(() => fromGuide("/review.md"), /link target does not exist/);
});

test("points images at the file's bytes, not at its GitHub page", () => {
  const image = (url) =>
    resolveLink(url, {
      sourceFile: "trackbed/docs/review.md",
      currentPage: "guides/review",
      image: true,
    });

  assert.equal(
    image("flow.png"),
    "https://github.com/trackbed/skills/raw/main/trackbed/docs/flow.png",
  );
  assert.equal(image("https://example.com/a.png"), "https://example.com/a.png");
  assert.throws(() => image("missing.png"), /link target does not exist/);
});

test("decodes percent-escapes in a linked path", () => {
  assert.equal(
    fromGuide("../skills/pr%3Acreate/SKILL.md"),
    "https://github.com/trackbed/skills/blob/main/trackbed/skills/pr:create/SKILL.md",
  );
  assert.throws(
    () => fromGuide("100%.md"),
    /malformed percent-escape: 100%\.md/,
  );
});

test("points GitHub links at the given source ref", () => {
  const pinned = createLinkResolver({
    pathKind: (repoPath) => files.get(repoPath) ?? null,
    filePages: new Map(),
    readmeAnchors: readme.anchors,
    sourceRef: "v1.2.0",
  });
  const from = (url, image = false) =>
    pinned(url, { sourceFile: "README.md", currentPage: "skills", image });

  assert.equal(
    from("trackbed/docs/review.md#gates"),
    "https://github.com/trackbed/skills/blob/v1.2.0/trackbed/docs/review.md#gates",
  );
  assert.equal(
    from("#pr-title-format"),
    "https://github.com/trackbed/skills/blob/v1.2.0/README.md#pr-title-format",
  );
  assert.equal(
    from("trackbed/docs/flow.png", true),
    "https://github.com/trackbed/skills/raw/v1.2.0/trackbed/docs/flow.png",
  );
});

test("fails on links whose target is gone", () => {
  assert.throws(
    () => fromReadme("old-name/docs/review.md"),
    /link target does not exist/,
  );
  assert.throws(
    () => fromGuide("../../../outside.md"),
    /link target does not exist/,
  );
  assert.throws(() => fromReadme("#no-such-heading"), /README has no heading/);
});

test("escapes characters that would end a Markdown link early", () => {
  assert.equal(
    githubUrl("docs/a (draft).md"),
    "https://github.com/trackbed/skills/blob/main/docs/a%20%28draft%29.md",
  );
});
