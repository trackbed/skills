import assert from "node:assert/strict";
import { test } from "node:test";
import { listHeadings, transformMarkdown } from "../lib/markdown.mjs";

const keepLinks = { resolveLink: (url) => url };

test("rewrites link, image, and definition destinations and nothing else", () => {
  const source = [
    'See [the guide](docs/guide.md#top "Guide") and ![shot](img/a.png).',
    "",
    "[![badge](img/b.png)](docs/guide.md)",
    "",
    "[ref]: docs/ref.md",
    "",
    "```md",
    "[not a link](docs/guide.md)",
    "```",
  ].join("\n");

  const images = [];
  const { text } = transformMarkdown(source, {
    resolveLink: (url, { image }) => {
      if (image) images.push(url);
      return `/site/${url}`;
    },
  });

  assert.deepEqual(images, ["img/a.png", "img/b.png"]);

  assert.equal(
    text,
    [
      'See [the guide](/site/docs/guide.md#top "Guide") and ![shot](/site/img/a.png).',
      "",
      "[![badge](/site/img/b.png)](/site/docs/guide.md)",
      "",
      "[ref]: /site/docs/ref.md",
      "",
      "```md",
      "[not a link](docs/guide.md)",
      "```",
    ].join("\n"),
  );
});

test("links inline code to a component page, except in links and headings", () => {
  const source = [
    "## Uses `trackbed:pr:create`",
    "",
    "Run `/trackbed:pr:create --draft`, not [`trackbed:pr:create`](elsewhere.md).",
    "",
    "| Skill | Arguments |",
    "| --- | --- |",
    "| `/trackbed:pr:create` | `[a\\|b]` |",
  ].join("\n");

  const { text } = transformMarkdown(source, {
    ...keepLinks,
    linkForCode: (value) =>
      value.includes("trackbed:pr:create") ? "/skills/pr-create/" : null,
  });

  assert.equal(
    text,
    [
      "## Uses `trackbed:pr:create`",
      "",
      "Run [`/trackbed:pr:create --draft`](/skills/pr-create/), not [`trackbed:pr:create`](elsewhere.md).",
      "",
      "| Skill | Arguments |",
      "| --- | --- |",
      "| [`/trackbed:pr:create`](/skills/pr-create/) | `[a\\|b]` |",
    ].join("\n"),
  );
});

test("shifts headings and leaves fenced comment lines alone", () => {
  const source = [
    "### Install",
    "",
    "```bash",
    "# a comment",
    "```",
    "",
    "#### Codex",
  ].join("\n");

  const { text } = transformMarkdown(source, {
    ...keepLinks,
    headingShift: -1,
  });

  assert.equal(
    text,
    ["## Install", "", "```bash", "# a comment", "```", "", "### Codex"].join(
      "\n",
    ),
  );
});

test("takes the page title from the single top-level heading", () => {
  const { text, title } = transformMarkdown(
    "# Review `Workflows`\n\nBody.\n\n## Next\n",
    {
      ...keepLinks,
      dropTitle: true,
    },
  );

  assert.equal(title, "Review Workflows");
  assert.equal(text, "\nBody.\n\n## Next\n");
  assert.throws(
    () =>
      transformMarkdown("# One\n\n# Two\n", { ...keepLinks, dropTitle: true }),
    /More than one "#" heading/,
  );
});

test("turns GitHub alerts into asides and still rewrites the links inside", () => {
  const source = [
    "> [!IMPORTANT]",
    "> Read the [credits](#attribution)",
    "> before you fork.",
    "",
    "> An ordinary quote.",
  ].join("\n");

  const { text } = transformMarkdown(source, {
    resolveLink: (url) =>
      url === "#attribution" ? "/reference/attribution/" : url,
  });

  assert.equal(
    text,
    [
      ":::note[Important]",
      "Read the [credits](/reference/attribution/)",
      "before you fork.",
      ":::",
      "",
      "> An ordinary quote.",
    ].join("\n"),
  );
});

test("fails instead of rewriting a destination it cannot locate exactly", () => {
  const rewrite = (source) =>
    transformMarkdown(source, { resolveLink: (url) => `/site/${url}` });

  // The scan for "](" would land inside the title.
  assert.throws(
    () => rewrite('![shot](img/a.png "see ](x")'),
    /Cannot rewrite the link to img\/a\.png/,
  );
  // An escaped ">" inside an angle-bracket destination.
  assert.throws(
    () => rewrite("[doc](<a\\>b.md>)"),
    /Cannot rewrite the link to a>b\.md/,
  );
  // Ordinary escapes and angle brackets are located exactly.
  assert.equal(
    rewrite("[doc](<a b.md>) [x](a\\_b.md)").text,
    "[doc](/site/a b.md) [x](/site/a_b.md)",
  );
});

test("names the text when two rewrites collide", () => {
  assert.throws(
    () =>
      transformMarkdown("# See [the guide](guide.md)\n", {
        resolveLink: (url) => `/site/${url}`,
        dropTitle: true,
      }),
    /Two rewrites overlap at "guide\.md"/,
  );
});

test("refuses relative links it cannot rewrite safely", () => {
  assert.throws(
    () => transformMarkdown('<a href="docs/guide.md">guide</a>\n', keepLinks),
    /raw HTML/,
  );
  assert.throws(
    () => transformMarkdown("Title\n=====\n", keepLinks),
    /Only "#" headings/,
  );
});

test("numbers repeated headings the way GitHub does", () => {
  const headings = listHeadings(
    "# A\n\n## Updating\n\n## B & C\n\n### Updating\n",
  );

  assert.deepEqual(
    headings.map((heading) => heading.slug),
    ["a", "updating", "b--c", "updating-1"],
  );
});
