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
/** One hand-written usage guide per user-invocable skill, named by its page. */
export const USAGE_DIR = "trackbed/docs/usage";

export const HOME_PAGE = "index";
export const HOME_TAB_TITLE =
  "trackbed: agent workflows for Claude Code and Codex";
export const QUICK_START_PAGE = "start/quick-start";
export const SKILLS_PAGE = "skills";
export const AGENTS_PAGE = "agents";

/**
 * README `##` sections that become pages, keyed by heading text.
 * `dropTableColumns` leaves a column of the section's tables off the page.
 */
export const README_PAGES = [
  { heading: "Quick Start", slug: QUICK_START_PAGE },
  { heading: "Requirements", slug: "start/requirements" },
  { heading: "Installation & Updating", slug: "start/installation" },
  { heading: "Configuration", slug: "start/configuration" },
  { heading: "Workflows", slug: "workflows" },
  // Each skill's own page shows its arguments, and four columns do not fit.
  { heading: "Skills", slug: SKILLS_PAGE, dropTableColumns: ["Arguments"] },
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
  { file: "troubleshooting.md", slug: "guides/troubleshooting" },
  { file: "concepts.md", slug: "start/concepts" },
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
      QUICK_START_PAGE,
      "start/concepts",
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
      "guides/mcp-servers",
      "guides/troubleshooting",
    ],
  },
];

export const SIDEBAR_AFTER_COMPONENTS = [
  {
    label: "Reference",
    pages: [
      "reference/hooks",
      // The detail behind the hook table above, so the two sit together.
      "guides/hooks",
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
