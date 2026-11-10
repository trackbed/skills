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

The site is at <https://trackbed-docs.vercel.app>, served by the `trackbed-docs` Vercel project. The project holds settings that are not in this repository. To recreate it, apply all of them:

1. **Root Directory** is `site`, with "Include files outside the root directory in the Build Step" left on, because the build reads the repository's README, guides, and components.
2. Access to System Environment Variables is on. The sitemap and the commit-pinned links read `VERCEL_PROJECT_PRODUCTION_URL` and `VERCEL_GIT_COMMIT_SHA`.
3. A Deploy Hook for the `main` branch exists, and its URL is the repository secret `VERCEL_DEPLOY_HOOK_URL`. Treat the URL as a password: anyone who has it can deploy the project. The hook's ID together with the project ID is enough to rebuild the URL, so keep both out of logs.
4. Preview deployments are disabled, and Vercel's Pull Request comments, commit statuses, and GitHub deployment events are off.

The fourth setting protects other Pull Requests. `vercel.json` only stops deployments for commits that contain it, so a branch cut before the site existed would otherwise get a failing preview build and a red Vercel status.

```bash
vercel project update trackbed-docs --root-directory site --framework astro --node-version 24.x
vercel project update trackbed-docs --no-git-pr-comments --no-git-commit-status --no-github-deployment-events
vercel git connect https://github.com/trackbed/skills --project trackbed-docs
vercel deploy-hooks create release-workflow --git-branch main --project trackbed-docs
```

The CLI has no flag for disabling preview deployments; set `previewDeploymentsDisabled` to `true` with `PATCH /v9/projects/trackbed-docs` on the Vercel REST API. Connecting the repository needs the Vercel GitHub app installed on the organization, which only an organization owner can do.

To deploy outside a release, for the first deployment or for a fix to the site itself, run the Deploy Docs Site workflow from the Actions tab or with `gh workflow run deploy-docs-site.yml`.

Two things to know:

- **Without the secret, nothing deploys.** The workflow warns and succeeds, so a fork or a repository that has not set up Vercel still gets a green release.
- **The hook builds `main` as it is when it fires.** That is the release commit unless another Pull Request merges in the minute between the release merge and the hook.
- **A failed build is not reported on GitHub.** With commit statuses off, the workflow only confirms that Vercel accepted the request. Vercel emails the failure, and the project's deployment list shows it.
