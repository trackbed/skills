import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import {
  COMPONENT_NAME,
  findComponentNames,
  loadComponents,
} from "./components.mjs";
import {
  AGENTS_PAGE,
  DEFAULT_BRANCH,
  GUIDE_PAGES,
  GUIDES_DIR,
  GUIDES_OFF_SITE,
  HOME_PAGE,
  listsComponentMentions,
  PLUGIN_MANIFEST_PATH,
  README_PAGES,
  README_PATH,
  README_SECTIONS_OFF_SITE,
  SIDEBAR_AFTER_COMPONENTS,
  SIDEBAR_BEFORE_COMPONENTS,
  SKILLS_PAGE,
} from "./config.mjs";
import { transformMarkdown } from "./markdown.mjs";
import { agentPage, homePage, skillPage } from "./pages.mjs";
import { analyzeReadme, readSkillCategories } from "./readme.mjs";
import {
  createLinkResolver,
  githubEditUrl,
  githubUrl,
  pageUrl,
} from "./routes.mjs";

/** An inline code span that starts with a component name: `/trackbed:pr:create --draft`. */
const CODE_SPAN_COMPONENT = new RegExp(`^[/$]?(${COMPONENT_NAME})(?=\\s|$)`);

function checkGuidesPlaced(repoRoot) {
  const placed = new Set([
    ...GUIDE_PAGES.map((guide) => guide.file),
    ...GUIDES_OFF_SITE,
  ]);
  const guides = readdirSync(path.join(repoRoot, GUIDES_DIR)).filter((name) =>
    name.endsWith(".md"),
  );
  for (const name of guides) {
    if (!placed.has(name)) {
      throw new Error(
        `${GUIDES_DIR}/${name} is not placed: add it to GUIDE_PAGES or GUIDES_OFF_SITE in site/scripts/lib/config.mjs`,
      );
    }
  }
}

function sidebarGroup(group) {
  return { label: group.label, items: group.pages.map((slug) => ({ slug })) };
}

function componentLink(component) {
  return { label: component.shortName, slug: component.slug };
}

/**
 * Read the repository and return everything the site needs: the pages to
 * write, the sidebar, and the plugin version the pages document.
 *
 * `sourceRef` is the branch, tag, or commit that links to files on GitHub
 * point at. Edit links always point at the default branch.
 */
export function buildSite(repoRoot, { sourceRef = DEFAULT_BRANCH } = {}) {
  const sourceUrl = (repoPath) => githubUrl(repoPath, { ref: sourceRef });
  const read = (repoPath) =>
    readFileSync(path.join(repoRoot, repoPath), "utf8");
  const pathKind = (repoPath) => {
    const stats = statSync(path.join(repoRoot, repoPath), {
      throwIfNoEntry: false,
    });
    if (!stats) return null;
    return stats.isDirectory() ? "directory" : "file";
  };

  checkGuidesPlaced(repoRoot);
  const manifest = JSON.parse(read(PLUGIN_MANIFEST_PATH));
  const readmeText = read(README_PATH);
  const readme = analyzeReadme(readmeText, {
    pages: README_PAGES,
    offSite: README_SECTIONS_OFF_SITE,
  });
  const { skills, agents } = loadComponents(repoRoot);
  const componentsByName = new Map(
    [...skills, ...agents].map((component) => [component.name, component]),
  );

  const resolveLink = createLinkResolver({
    pathKind,
    filePages: new Map(
      GUIDE_PAGES.map((guide) => [`${GUIDES_DIR}/${guide.file}`, guide.slug]),
    ),
    readmeAnchors: readme.anchors,
    sourceRef,
  });
  const render = (text, { sourceFile, slug, ...options }) => {
    try {
      return transformMarkdown(text, {
        resolveLink: (url, { image }) =>
          resolveLink(url, { sourceFile, currentPage: slug, image }),
        linkForCode: (value) => {
          const name = CODE_SPAN_COMPONENT.exec(value)?.[1];
          const component = name && componentsByName.get(name);
          return component && component.slug !== slug
            ? pageUrl(component.slug)
            : null;
        },
        ...options,
      });
    } catch (error) {
      // Every failure here is about what a source file says, so name the file.
      throw new Error(`${sourceFile}: ${error.message}`, { cause: error });
    }
  };

  const pages = [];
  /** Guide and README pages, with the component names each one mentions. */
  const mentioningPages = [];
  const addProsePage = (page, sourceText) => {
    pages.push(page);
    if (listsComponentMentions(page.slug)) {
      mentioningPages.push({
        slug: page.slug,
        title: page.frontmatter.title,
        mentions: findComponentNames(sourceText),
      });
    }
  };

  pages.push(
    homePage({
      title: manifest.name,
      intro: readme.intro,
      renderIntro: (text) =>
        render(text, { sourceFile: README_PATH, slug: HOME_PAGE }).text,
      version: `v${manifest.version}`,
      fallbackTagline: manifest.description,
      sourceUrl,
    }),
  );

  for (const { heading, slug } of README_PAGES) {
    const sourceText = readme.sectionText(
      readme.sections.find((section) => section.title === heading),
    );
    const { text } = render(sourceText, {
      sourceFile: README_PATH,
      slug,
      headingShift: -1,
    });
    addProsePage(
      {
        slug,
        frontmatter: { title: heading, editUrl: githubEditUrl(README_PATH) },
        body: text.trim(),
      },
      sourceText,
    );
  }

  for (const { file, slug } of GUIDE_PAGES) {
    const sourceFile = `${GUIDES_DIR}/${file}`;
    const sourceText = read(sourceFile);
    const { text, title } = render(sourceText, {
      sourceFile,
      slug,
      dropTitle: true,
    });
    if (title === null) {
      throw new Error(`${sourceFile} needs a "#" heading for its page title`);
    }
    addProsePage(
      {
        slug,
        frontmatter: { title, editUrl: githubEditUrl(sourceFile) },
        body: text.trim(),
      },
      sourceText,
    );
  }

  const guidesMentioning = (component) =>
    mentioningPages.filter((page) => page.mentions.has(component.name));
  const skillsMentioning = (component) =>
    skills.filter(
      (skill) => skill !== component && skill.mentions.has(component.name),
    );

  const categories = readSkillCategories(
    readmeText,
    readme,
    new Set(skills.map((skill) => skill.name)),
  );
  const categoryOf = new Map();
  for (const category of categories) {
    const anchor = readme.anchors.get(category.slug).anchor;
    for (const name of category.skills) {
      categoryOf.set(name, { title: category.title, anchor });
    }
  }

  for (const skill of skills) {
    pages.push(
      skillPage(skill, {
        category: categoryOf.get(skill.name) ?? null,
        guides: guidesMentioning(skill),
        refersTo: skills.filter(
          (other) => other !== skill && skill.mentions.has(other.name),
        ),
        referredBy: skillsMentioning(skill),
        agents: agents.filter((agent) => skill.mentions.has(agent.name)),
        componentsByName,
        sourceUrl,
      }),
    );
  }
  for (const agent of agents) {
    pages.push(
      agentPage(agent, {
        guides: guidesMentioning(agent),
        usedBy: skillsMentioning(agent),
        componentsByName,
        sourceUrl,
      }),
    );
  }

  const uncategorized = skills.filter((skill) => !categoryOf.has(skill.name));
  if (uncategorized.length > 0) {
    throw new Error(
      `${README_PATH}: no table in the Skills section has a row for ${uncategorized.map((skill) => skill.name).join(", ")}`,
    );
  }

  const sidebar = [
    ...SIDEBAR_BEFORE_COMPONENTS.map(sidebarGroup),
    {
      label: "Skills",
      items: [
        { label: "Overview", slug: SKILLS_PAGE },
        ...categories.map((category) => ({
          label: category.title,
          collapsed: true,
          items: category.skills.map((name) =>
            componentLink(componentsByName.get(name)),
          ),
        })),
      ],
    },
    {
      label: "Agents",
      collapsed: true,
      items: [
        { label: "Overview", slug: AGENTS_PAGE },
        ...agents.map(componentLink),
      ],
    },
    ...SIDEBAR_AFTER_COMPONENTS.map(sidebarGroup),
  ];

  return { pages, sidebar, version: manifest.version };
}
