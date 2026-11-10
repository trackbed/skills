import GithubSlugger from "github-slugger";
import { HOME_PAGE, SKILLS_PAGE } from "./config.mjs";
import { listHeadings, nodeText, parseMarkdown, walk } from "./markdown.mjs";

/** Markdown whose two halves can land in different sections of the README. */
const SPLIT_UNSAFE = new Set([
  "definition",
  "linkReference",
  "imageReference",
  "footnoteDefinition",
  "footnoteReference",
]);

/**
 * Split the README into its `##` sections and work out where each of its
 * GitHub anchors lands on the site.
 *
 * `anchors` maps a GitHub anchor to `{ page, anchor }`; `page` is null for a
 * section that stays on GitHub. A heading's anchor on its page can differ from
 * its GitHub anchor, because GitHub numbers repeated headings across the whole
 * README while a page only numbers the ones it holds.
 */
export function analyzeReadme(text, { pages, offSite }) {
  const tree = parseMarkdown(text);
  walk(tree, (node) => {
    if (SPLIT_UNSAFE.has(node.type)) {
      const source = text.slice(
        node.position.start.offset,
        node.position.end.offset,
      );
      throw new Error(
        `README.md uses a reference-style link or footnote (${source}). Its sections become separate pages, which would lose the definition; write the link inline`,
      );
    }
  });
  const headings = listHeadings(text, tree);
  const pageByHeading = new Map(pages.map((page) => [page.heading, page.slug]));

  const anchors = new Map();
  const sections = [];
  let section = null;
  let pageSlugger = new GithubSlugger();

  for (const heading of headings) {
    if (heading.depth === 1) {
      anchors.set(heading.slug, { page: HOME_PAGE, anchor: null });
      continue;
    }
    if (heading.depth === 2) {
      if (section) section.end = heading.start;
      const page = pageByHeading.get(heading.title) ?? null;
      if (page === null && !offSite.includes(heading.title)) {
        throw new Error(
          `README section "${heading.title}" is not placed: add it to README_PAGES or README_SECTIONS_OFF_SITE in site/scripts/lib/config.mjs`,
        );
      }
      section = {
        title: heading.title,
        page,
        headingStart: heading.start,
        start: heading.end,
        end: text.length,
      };
      sections.push(section);
      pageSlugger = new GithubSlugger();
      anchors.set(heading.slug, { page, anchor: null });
      continue;
    }
    const page = section ? section.page : HOME_PAGE;
    anchors.set(heading.slug, {
      page,
      anchor: page === null ? null : pageSlugger.slug(heading.title),
    });
  }

  for (const page of pages) {
    if (!sections.some((candidate) => candidate.title === page.heading)) {
      throw new Error(
        `README has no "## ${page.heading}" section for the ${page.slug} page`,
      );
    }
  }

  const firstHeadingTwo = sections[0]?.headingStart ?? text.length;
  const titleHeading = headings.find((heading) => heading.depth === 1);
  return {
    tree,
    anchors,
    sections,
    intro: text.slice(titleHeading ? titleHeading.end : 0, firstHeadingTwo),
    sectionText: (candidate) => text.slice(candidate.start, candidate.end),
  };
}

/**
 * Read skill categories from the tables of the README's Skills section: a
 * skill belongs to the nearest heading above the table row that lists it.
 */
export function readSkillCategories(text, readme, skillNames) {
  const section = readme.sections.find(
    (candidate) => candidate.page === SKILLS_PAGE,
  );
  const headings = listHeadings(text, readme.tree).filter(
    (heading) => heading.start >= section.start && heading.end <= section.end,
  );
  const categories = [];

  walk(readme.tree, (node) => {
    if (node.type !== "table") return;
    const offset = node.position.start.offset;
    if (offset < section.start || offset >= section.end) return;
    const heading = headings.findLast((candidate) => candidate.start < offset);
    if (!heading) return;

    for (const row of node.children.slice(1)) {
      const name = nodeText(row.children[0]).replace(/^[/$]/, "");
      if (!skillNames.has(name)) continue;
      let category = categories.find(
        (candidate) => candidate.slug === heading.slug,
      );
      if (!category) {
        category = { title: heading.title, slug: heading.slug, skills: [] };
        categories.push(category);
      }
      category.skills.push(name);
    }
  });

  return categories;
}
