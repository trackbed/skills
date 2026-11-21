# Contributing

This repository ships the `trackbed` Claude Code plugin from `trackbed/`. The root [README.md](README.md) is the canonical entry point for public documentation, and the guides under [trackbed/docs/](trackbed/docs/) hold the deep usage reference it links; plugin source and tests live under [trackbed/](trackbed/).

## Start Here

Before changing files, read the narrowest docs that match the work:

- [AGENTS.md](AGENTS.md) for component conventions.
- [docs/architecture.md](trackbed/docs/architecture.md) for subsystem boundaries.
- [docs/code-map.md](trackbed/docs/code-map.md) for source-to-test mapping.
- [docs/decisions/README.md](trackbed/docs/decisions/README.md) for settled repository decisions.

Check the working tree before editing and preserve unrelated local changes:

```bash
git status --short
```

## Local Setup

Check the portable baseline toolchain without changing the host:

```bash
bash trackbed/scripts/bootstrap-dev.sh --check
```

To install missing dependencies, choose the explicit install mode:

```bash
bash trackbed/scripts/bootstrap-dev.sh --install
```

On macOS, installation uses Homebrew for Make, Bats, `jq`, Node.js 20+, and Python 3.11+. On Debian 12+ and Ubuntu 22.04+, install Node.js 20+ with npm first; Python 3.11+ must also be available before setup mutates the host. The bootstrap then uses `apt-get` for `make`, `bats`, `jq`, `zsh`, `python3`, and `python3-venv`. Both paths create a repository-local `.venv` from the pinned `requirements-dev.txt` and install Node packages with `npm ci`. The Makefile automatically prefers ShellCheck, Ruff, and mypy from `.venv`.

The equivalent npm aliases are `npm run bootstrap:check` and `npm run bootstrap:install` once Node.js 20+, npm, and Python 3.11+ are available. The check mode is the default and never invokes a package manager. Neither mode installs or modifies Git hooks. Skill changes also require SkillSpector for `pr-verify`; install it separately before running the changed-skill security gate.

### Converter changes

For a focused converter change, run `make -C trackbed test-convert`.

The repository-root `package.json` versions the npm installer entrypoint. `trackbed/package.json` versions the plugin package and is managed by the plugin release flow. These versions are intentionally independent; do not synchronize them. See the [release guide](trackbed/RELEASE.md) for the complete versioning and release contract.

## Change Guidelines

- Keep changes scoped to the subsystem being modified.
- Add or update README entries for new skills, agents, hooks, commands, and user-facing workflows. Follow the [README decision](trackbed/docs/decisions/2026-10-28-readme-entry-point.md) for generated summaries, prose length, and where tests should check behavior wording. Use “Pull Request” or “PR” consistently.
- Keep shipped skills self-contained within the installed plugin. A skill may use its own directory, plugin-level `trackbed/shared/` references and assets, and `trackbed/scripts/` helpers, but never repository-level docs. Put a file that two or more skills need in one of those plugin-level locations instead of copying it, and name its `${CLAUDE_PLUGIN_ROOT}/...` path in each consuming `SKILL.md`.
- Keep skills current with new models. When Anthropic or OpenAI release a new model or prompting guide, review the skills it affects against it; `/trackbed:skill:review` checks current-model fit. Declare the guide in each changed skill's `references/sources.yaml` so the monthly `/trackbed:skill:audit-sources` run flags its later revisions.
- Keep `SKILL.md` focused on orchestration. Move references, templates, and helpers to `references/`, `assets/`, and `scripts/` and load them at the step that needs them. The [frontmatter guide](trackbed/skills/skill:create/references/frontmatter-guide.md) covers routing descriptions, menu visibility, quoted argument hints, and platform selection.
- Use plain-English commit messages on branches. Pull Request titles must use Conventional Commits format.

### External Sources and Rights

Record each external source in the skill's `references/sources.yaml`. For plugin-level scripts that no single skill owns, place `sources.yaml` beside the scripts. The [manifest schema](trackbed/scripts/schemas/skill-contracts.json) lists the fields every entry requires.

- Use `usage: inspiration` for ideas, facts, or methods expressed in your own words. When permission to reproduce a source is absent or unclear, link to it and write an original summary.
- Use `usage: copied` for retained prose, code, templates, or substantial assets. Verify a compatible upstream license even for public, attributed material. Record the license, exact `upstream_path`, and immutable commit, revision, release, or version. Ship the complete required notice. Its `notice` path is relative to the skill directory for skills and to the manifest directory for shared scripts. Where the file format permits a header, include the source, license, upstream path, and immutable revision there. See the [copied-source example](trackbed/scripts/dev-server/sources.yaml).
- Keep source-audit downloads transient. Commit provenance notes, review dates, hashes, and revision metadata. Exclude fetched audit bodies and `references/sources-snapshot/` directories from commits.

## Verification

Run `npm run format` (or `make -C trackbed format` from the repository root) to format changed files. It uses the same file selection and configuration as `npm run format:check`, which checks without writing. Both include committed changes against `origin/main` (override with `FORMAT_BASE`), working-tree changes, and untracked files; deleted files are skipped.

Choose the smallest meaningful focused check first. Use the smoke target for representative cross-language feedback, then broaden to the complete PR or release gate when the change warrants it.

```bash
# Closest focused test for a documentation change (use the code map for other changes)
make -C trackbed test-bats-file BATS_TEST_FILE=tests/repository-instructions.bats

# Representative cross-language feedback
make -C trackbed test-smoke

# Complete default suite
make -C trackbed test

# Shell, Python, and JavaScript linting
make -C trackbed lint

# Normal Pull Request gate
make -C trackbed pr-verify

# Release-candidate gate
make -C trackbed verify
```

Focused targets are listed in [docs/development.md](trackbed/docs/development.md#running-the-tests). Use [docs/code-map.md](trackbed/docs/code-map.md) to map files to likely tests.

When addressing size warnings from `python3 trackbed/scripts/lint-skill-contracts.py`, start with the first entry in the relevant README prose, skill length, or description queue. Split long README passages or move detail to a guide. Move skill reference material out of the body and preserve behavior, routing terms, safety constraints, and context readers cannot infer. The [contract registry](trackbed/scripts/synced-contracts.yaml) defines the warning thresholds and hard limits.

### Documentation site

The site under [site/](site/README.md) renders the README, the user-facing guides, and the component sources; it holds no page content of its own. It has its own `package.json` and needs the Node.js version named there. The Docs Site CI job tests and builds it on every Pull Request; `make -C trackbed pr-verify` does not. Run the same checks yourself after changing `site/`, and after moving, renaming, or deleting a file or heading that the README or a guide links to:

```bash
npm --prefix site ci
npm --prefix site test
npm --prefix site run build
```

The build checks links and headings. Register each new README `##` section or top-level `trackbed/docs/*.md` guide in [site/scripts/lib/config.mjs](site/scripts/lib/config.mjs). The site discovers [usage guides](site/README.md#usage-guides) separately for shipped user-invocable skills. Add or update the matching guide when a skill or its flags change.

### Optional pre-commit check

Run the fast contributor gate directly before committing:

```bash
npm run check:pre-commit
```

It checks formatting for maintained Python, JavaScript, shell, Markdown, JSON, and YAML files changed from the base branch, then runs lint, the cross-language smoke suite, and the installed-resource boundary check.

To opt in to the repository-managed hook, install `pre-commit` first (`brew install pre-commit` on macOS or `sudo apt-get install -y pre-commit` on Debian/Ubuntu), then run:

```bash
npm run hooks:install
```

The local hook delegates to `npm run check:pre-commit`. Remove it at any time with `npm run hooks:uninstall`. No hook is installed by the bootstrap script or other repository commands.

### Claude Code skill-edit check

Claude Code sessions in this repository load a project hook from `.claude/settings.json`. After an agent writes or edits a file under `trackbed/skills/`, the hook runs `trackbed/scripts/check-skill-edit.sh`:

- `node trackbed/scripts/check-installed-resources.js` on every such edit.
- `python3 trackbed/scripts/lint-skill-contracts.py --skill <path>` when the file is a skill's `SKILL.md`. This mode checks only that file's frontmatter and line budget; the full linter still runs in `make -C trackbed lint`.

A clean edit adds at most about two seconds and prints nothing. A failure goes back to the agent with the checker's message. To turn the hook off on your machine, add `{"env": {"TRACKBED_SKILL_EDIT_CHECK": "0"}}` to `.claude/settings.local.json`, or export `TRACKBED_SKILL_EDIT_CHECK=0` before starting Claude Code.
