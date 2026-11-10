#!/usr/bin/env node
/**
 * Write the site's content from the repository's own sources: README sections,
 * the user-facing guides under trackbed/docs/, and one page per skill and
 * agent. The output directories are git-ignored and rebuilt on every run.
 */
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildSite } from "./lib/build-site.mjs";
import { writeSite } from "./lib/write-site.mjs";

const siteRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);

const site = buildSite(path.resolve(siteRoot, ".."), {
  // On Vercel, link to the sources as they are in the commit being built, so
  // a page's links keep working after `main` moves on.
  sourceRef: process.env.VERCEL_GIT_COMMIT_SHA || undefined,
});
writeSite(site, {
  contentDir: path.join(siteRoot, "src/content/docs"),
  generatedDir: path.join(siteRoot, "src/generated"),
});
console.log(`Synced ${site.pages.length} pages for trackbed v${site.version}.`);
