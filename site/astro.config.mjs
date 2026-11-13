// @ts-check
import { readFileSync } from "node:fs";
import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";
import starlightLinksValidator from "starlight-links-validator";
import { REPO_URL } from "./scripts/lib/config.mjs";
import { hostCommandLanguage } from "./src/host-command-language.mjs";

/** @returns {{ sidebar: import("@astrojs/starlight/types").StarlightUserConfig["sidebar"] }} */
function readGeneratedSite() {
  try {
    return JSON.parse(
      readFileSync(
        new URL("./src/generated/site.json", import.meta.url),
        "utf8",
      ),
    );
  } catch (error) {
    throw new Error(
      "src/generated/site.json is missing: run `npm run sync` (the `dev` and `build` scripts do it for you)",
      { cause: error },
    );
  }
}

// Vercel sets this to the project's production domain on every build.
const productionHost = process.env.VERCEL_PROJECT_PRODUCTION_URL;

/** Link previews need an absolute image URL, so only a deployed build has one. */
function socialImage(host) {
  if (!host) return [];
  const image = `https://${host}/og.png`;
  return [
    { tag: "meta", attrs: { property: "og:image", content: image } },
    { tag: "meta", attrs: { property: "og:image:width", content: "1200" } },
    { tag: "meta", attrs: { property: "og:image:height", content: "630" } },
    { tag: "meta", attrs: { name: "twitter:image", content: image } },
  ];
}

export default defineConfig({
  site: productionHost ? `https://${productionHost}` : undefined,
  // Typographic replacement would turn the `--flag` in a skill description into an en dash.
  markdown: { smartypants: false },
  integrations: [
    starlight({
      title: "trackbed",
      description:
        "Documentation for trackbed, a cross-host agent workflow plugin for Claude Code and Codex.",
      social: [{ icon: "github", label: "GitHub", href: REPO_URL }],
      head: socialImage(productionHost),
      customCss: ["./src/styles/custom.css"],
      expressiveCode: {
        // A long command wraps instead of scrolling its comment out of view.
        defaultProps: { wrap: true, preserveIndent: true },
        shiki: { langs: [hostCommandLanguage] },
      },
      sidebar: readGeneratedSite().sidebar,
      plugins: [starlightLinksValidator()],
    }),
  ],
});
