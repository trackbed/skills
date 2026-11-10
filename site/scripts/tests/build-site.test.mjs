import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { buildSite } from "../lib/build-site.mjs";
import { CATALOG_PATH, PLUGIN_MANIFEST_PATH } from "../lib/config.mjs";
import { isAbsoluteUrl, parseMarkdown, walk } from "../lib/markdown.mjs";
import { writeSite } from "../lib/write-site.mjs";

const repoRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../..",
);
const readJson = (repoPath) =>
  JSON.parse(readFileSync(path.join(repoRoot, repoPath), "utf8"));

// These run against the repository itself: they fail when a README section, a
// guide, or a component stops fitting the site, which is what CI is for.
const site = buildSite(repoRoot);
const pagesBySlug = new Map(site.pages.map((page) => [page.slug, page]));

function sidebarSlugs(items) {
  return items.flatMap((item) =>
    item.items ? sidebarSlugs(item.items) : [item.slug],
  );
}

test("gives every shipped skill and agent a page", () => {
  const catalog = readJson(CATALOG_PATH);
  const titles = new Set(site.pages.map((page) => page.frontmatter.title));

  for (const component of [...catalog.skills, ...catalog.agents]) {
    assert.ok(titles.has(component.name), `no page for ${component.name}`);
  }
  assert.equal(site.pages.length, pagesBySlug.size, "two pages share a slug");
  assert.equal(site.version, readJson(PLUGIN_MANIFEST_PATH).version);
});

test("puts every page except the home page in the sidebar, once", () => {
  const slugs = sidebarSlugs(site.sidebar);

  assert.deepEqual(
    [...slugs].sort(),
    [...pagesBySlug.keys()].filter((slug) => slug !== "index").sort(),
  );
});

test("leaves no repository-relative link in any page", () => {
  for (const page of site.pages) {
    walk(parseMarkdown(page.body), (node) => {
      if (!["link", "image", "definition"].includes(node.type)) return;
      const onSite = node.url.startsWith("/") || node.url.startsWith("#");
      assert.ok(
        onSite || isAbsoluteUrl(node.url),
        `${page.slug} links to ${node.url}`,
      );
    });
  }
});

test("writes one Markdown file per page and the generated site data", (t) => {
  const out = mkdtempSync(path.join(tmpdir(), "trackbed-site-"));
  t.after(() => rmSync(out, { recursive: true, force: true }));
  const contentDir = path.join(out, "docs");
  const generatedDir = path.join(out, "generated");

  writeSite(site, { contentDir, generatedDir });
  // A second run replaces the output instead of adding to it.
  writeSite(
    { ...site, pages: site.pages.slice(0, 1) },
    { contentDir, generatedDir },
  );

  assert.match(
    readFileSync(path.join(contentDir, "index.md"), "utf8"),
    /^---\ntitle: /,
  );
  assert.equal(
    existsSync(path.join(contentDir, `${site.pages[1].slug}.md`)),
    false,
  );
  assert.deepEqual(
    Object.keys(
      JSON.parse(readFileSync(path.join(generatedDir, "site.json"), "utf8")),
    ),
    ["sidebar"],
  );
});
