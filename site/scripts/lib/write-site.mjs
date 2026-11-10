import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { stringify } from "yaml";

/**
 * Replace the generated content: one Markdown file per page in `contentDir`,
 * and the sidebar in `generatedDir`.
 */
export function writeSite(site, { contentDir, generatedDir }) {
  for (const directory of [contentDir, generatedDir]) {
    rmSync(directory, { recursive: true, force: true });
    mkdirSync(directory, { recursive: true });
  }
  for (const page of site.pages) {
    const file = path.join(contentDir, `${page.slug}.md`);
    mkdirSync(path.dirname(file), { recursive: true });
    writeFileSync(
      file,
      `---\n${stringify(page.frontmatter, { lineWidth: 0 })}---\n\n${page.body}\n`,
    );
  }
  writeFileSync(
    path.join(generatedDir, "site.json"),
    `${JSON.stringify({ sidebar: site.sidebar }, null, 2)}\n`,
  );
}
