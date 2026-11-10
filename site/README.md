# Documentation site

The trackbed documentation site, built with [Astro Starlight](https://starlight.astro.build/) and hosted on Vercel.

The site renders sources that already exist in this repository. No page content is written here: to change what a page says, change its source. The root [README](../README.md) stays the canonical entry point, and each skill's `SKILL.md` stays its contract.

## Where pages come from

| Pages | Source |
| --- | --- |
| Home, Start Here, Workflows, the Skills and Agents overviews, Reference | `##` sections of the root `README.md` |
| Guides | The user-facing guides under `trackbed/docs/` |
| One page per skill and agent | `trackbed/docs/component-catalog.json` for the list, each component's frontmatter, and the README summaries in `trackbed/scripts/synced-contracts.yaml` |

`npm run sync` writes the pages to `src/content/docs/` and the sidebar to `src/generated/site.json`. Both are git-ignored and rebuilt on every run. On the way it:

- rewrites repository links to site pages, or to GitHub for files the site does not carry;
- links every `` `trackbed:<name>` `` code span to that skill's or agent's page;
- lists, on each component page, the guides and skills that mention it.

A link whose target no longer exists fails the sync, and the build validates every internal link and anchor. A skill missing from the README's skill tables, and a reference-style link or footnote in the README, fail it too: the README is split into pages, which would separate such a link from its definition.

Links to files on GitHub point at the commit Vercel is building, so they keep working on the live site after `main` moves on. Local and CI builds link to `main`, and "Edit page" links always do.

## Placing new material

[scripts/lib/config.mjs](scripts/lib/config.mjs) lists which README sections and guides become pages and which stay on GitHub. A new README `##` section or a new `trackbed/docs/*.md` file fails the sync until it is added to one of the two lists, so nothing lands on the site or is left off it by accident. New skills and agents need nothing: they appear once the component catalog lists them.

## Commands

Run these from `site/`. They need the Node.js version in `package.json`.

```bash
npm ci
npm test         # content sync and link routing tests
npm run dev      # sync, then serve with live reload
npm run build    # sync, build to dist/, and validate links
```

The sync runs when `npm run dev` starts, so restart it to pick up a change to the README, a guide, or a component.

## Deploying on Vercel

The site is deployed when a release Pull Request merges. The [Create Release Tag](../.github/workflows/release-tag.yml) workflow tags the release and then calls [Deploy Docs Site](../.github/workflows/deploy-docs-site.yml), which triggers a Vercel Deploy Hook, and Vercel builds `main` and publishes it. Nothing else deploys: [vercel.json](vercel.json) turns off Vercel's automatic Git deployments, so pushes and Pull Requests build nothing there. The [Docs Site](../.github/workflows/site.yml) workflow builds the site on every Pull Request instead.

One-time setup:

1. Import `trackbed/skills` as a new Vercel project.
2. Set **Root Directory** to `site`. Leave "Include files outside the root directory in the Build Step" on, because the build reads the repository's README, guides, and components.
3. Keep access to System Environment Variables enabled under **Environment Variables**. The sitemap and the commit-pinned links read `VERCEL_PROJECT_PRODUCTION_URL` and `VERCEL_GIT_COMMIT_SHA`.
4. Under **Settings**, **Git**, **Deploy Hooks**, create a hook for the `main` branch and save its URL as the repository secret `VERCEL_DEPLOY_HOOK_URL`. Treat the URL as a password: anyone who has it can deploy the project.

To deploy outside a release, for the first deployment or for a fix to the site itself, run the Deploy Docs Site workflow from the Actions tab or with `gh workflow run deploy-docs-site.yml`.

Two things to know:

- **Without the secret, nothing deploys.** The workflow warns and succeeds, so a fork or a repository that has not set up Vercel still gets a green release.
- **The hook builds `main` as it is when it fires.** That is the release commit unless another Pull Request merges in the minute between the release merge and the hook.
