import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
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
  QUICK_START_PAGE,
  README_PAGES,
  README_PATH,
  README_SECTIONS_OFF_SITE,
  SIDEBAR_AFTER_COMPONENTS,
  SIDEBAR_BEFORE_COMPONENTS,
  SKILLS_PAGE,
  USAGE_DIR,
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
import { readUsage, usagePath } from "./usage.mjs";

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

/**
 * Every skill a person can start has a usage guide, and every usage guide
 * belongs to such a skill, so a renamed or removed skill cannot leave one
 * behind.
 */
function checkUsageGuides(repoRoot, skills) {
  const expected = new Map(
    skills
      .filter((skill) => skill.userInvocable)
      .map((skill) => [path.posix.basename(usagePath(skill)), skill]),
  );
  const directory = path.join(repoRoot, USAGE_DIR);
  const found = new Set(
    existsSync(directory)
      ? readdirSync(directory).filter((name) => name.endsWith(".md"))
      : [],
  );
  for (const [name, skill] of expected) {
    if (!found.has(name)) {
      throw new Error(
        `${skill.name} has no usage guide: add ${USAGE_DIR}/${name} (see site/README.md)`,
      );
    }
  }
  for (const name of found) {
    if (!expected.has(name)) {
      throw new Error(
        `${USAGE_DIR}/${name} matches no user-invocable skill: rename or delete it`,
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

  const readmeSection = (heading) =>
    readme.sectionText(
      readme.sections.find((section) => section.title === heading),
    );
  const quickStart = README_PAGES.find(
    (page) => page.slug === QUICK_START_PAGE,
  );

  pages.push(
    homePage({
      title: manifest.name,
      intro: readme.intro,
      renderIntro: (text) =>
        render(text, { sourceFile: README_PATH, slug: HOME_PAGE }).text,
      quickStart: {
        heading: quickStart.heading,
        body: render(readmeSection(quickStart.heading), {
          sourceFile: README_PATH,
          slug: HOME_PAGE,
        }).text.trim(),
      },
      version: `v${manifest.version}`,
      fallbackTagline: manifest.description,
      sourceUrl,
    }),
  );

  for (const { heading, slug, dropTableColumns } of README_PAGES) {
    const sourceText = readmeSection(heading);
    const { text } = render(sourceText, {
      sourceFile: README_PATH,
      slug,
      headingShift: -1,
      dropTableColumns,
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

  checkUsageGuides(repoRoot, skills);
  const usageOf = (skill) => {
    if (!skill.userInvocable) return null;
    const sourceFile = usagePath(skill);
    let usage;
    try {
      usage = readUsage(read(sourceFile), skill);
    } catch (error) {
      throw new Error(`${sourceFile}: ${error.message}`, { cause: error });
    }
    const part = (text) =>
      text && render(text, { sourceFile, slug: skill.slug }).text.trim();
    return { lead: part(usage.lead), sections: part(usage.sections) };
  };

  for (const skill of skills) {
    pages.push(
      skillPage(skill, {
        usage: usageOf(skill),
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
