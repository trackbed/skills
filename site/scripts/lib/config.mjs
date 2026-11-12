/**
 * Where every page on the site comes from. Nothing on the site is written by
 * hand: pages are README sections, docs guides, or generated from component
 * sources. A README section or a guide that is in neither of its two lists
 * fails the sync, so new material is placed on purpose.
 */

export const REPO_URL = "https://github.com/trackbed/skills";
export const DEFAULT_BRANCH = "main";

export const README_PATH = "README.md";
export const PLUGIN_MANIFEST_PATH = "trackbed/.claude-plugin/plugin.json";
export const CATALOG_PATH = "trackbed/docs/component-catalog.json";
export const REGISTRY_PATH = "trackbed/scripts/synced-contracts.yaml";
export const GUIDES_DIR = "trackbed/docs";

export const HOME_PAGE = "index";
export const SKILLS_PAGE = "skills";
export const AGENTS_PAGE = "agents";

/** README `##` sections that become pages, keyed by heading text. */
export const README_PAGES = [
  { heading: "Quick Start", slug: "start/quick-start" },
  { heading: "Requirements", slug: "start/requirements" },
  { heading: "Installation & Updating", slug: "start/installation" },
  { heading: "Configuration", slug: "start/configuration" },
  { heading: "Workflows", slug: "workflows" },
  { heading: "Skills", slug: SKILLS_PAGE },
  { heading: "Agents", slug: AGENTS_PAGE },
  { heading: "Hooks", slug: "reference/hooks" },
  {
    heading: "Renamed and Removed Commands",
    slug: "reference/renamed-and-removed-commands",
  },
  { heading: "Attribution", slug: "reference/attribution" },
];

/** README `##` sections that stay on GitHub; links to them point there. */
export const README_SECTIONS_OFF_SITE = [
  "Table of Contents",
  "Documentation",
  "Related Plugins",
  "Releases",
  "Contributing",
  "Development",
  "Plugin Structure",
  "Adding Components",
  "Local Repository Maintenance",
  "License",
];

/** Guides under `trackbed/docs/` that become pages. */
export const GUIDE_PAGES = [
  { file: "review.md", slug: "guides/review" },
  { file: "shipping.md", slug: "guides/shipping" },
  { file: "siw.md", slug: "guides/siw" },
  { file: "visual-reports.md", slug: "guides/visual-reports" },
  { file: "hooks.md", slug: "guides/hooks" },
  { file: "mcp-servers.md", slug: "guides/mcp-servers" },
];

/** Maintainer docs under `trackbed/docs/` that stay on GitHub. */
export const GUIDES_OFF_SITE = [
  "agent-autonomy.md",
  "agent-portability.md",
  "architecture.md",
  "code-map.md",
  "development.md",
  "skill-expansion-roadmap.md",
];

/**
 * Sidebar groups of README and guide pages. The Skills and Agents groups are
 * generated from the component catalog and sit between these two.
 */
export const SIDEBAR_BEFORE_COMPONENTS = [
  {
    label: "Start Here",
    pages: [
      "start/quick-start",
      "start/requirements",
      "start/installation",
      "start/configuration",
    ],
  },
  {
    label: "Guides",
    pages: [
      "workflows",
      "guides/review",
      "guides/shipping",
      "guides/siw",
      "guides/visual-reports",
      "guides/hooks",
      "guides/mcp-servers",
    ],
  },
];

export const SIDEBAR_AFTER_COMPONENTS = [
  {
    label: "Reference",
    pages: [
      "reference/hooks",
      "reference/renamed-and-removed-commands",
      "reference/attribution",
    ],
  },
];

/** Pages whose mentions of a skill or agent are listed on that component's page. */
export function listsComponentMentions(slug) {
  return (
    slug === "workflows" ||
    slug.startsWith("start/") ||
    slug.startsWith("guides/")
  );
}
