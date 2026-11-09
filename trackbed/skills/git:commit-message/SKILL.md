---
name: git:commit-message
description: Create commit messages for branch commits. Use when committing code changes, writing commit messages, or drafting a message for a pasted diff or change summary. Follows the repository's commit-subject convention (plain English when none is found), with a pre-commit checklist, a names-only secret scan, a stray-file check, and AI-attribution rules. Not for PR titles or merge commits.
user-invocable: false
disable-model-invocation: false
---

# Commit Messages

Follow these conventions when creating commits. These cover branch commits only — PR titles and merge commits use Conventional Commits and are out of scope here.

## Drafting only

When the user only wants a message drafted for a diff or change summary pasted into the conversation, nothing is being committed. Skip the Prerequisites branch check and the checklist items that inspect the repository: verification, the secret scan, the stray-file check, and the working-state check. Still apply the format, the commit convention, the body guidelines, and the AI-attribution rules, and point out a diff that spans two concerns. Resolve the convention from the current repository only when the pasted change belongs to it; otherwise use plain English unless the user names a convention. Never paste a credential you notice in the pasted diff back into the message or your reply; tell the user which file holds it instead.

## Prerequisites

Before committing, ensure you're working on a feature branch rather than a repository workbench or production branch. A workbench may be `main`, `development`, or another name; do not infer its role from the name alone.

```bash
CURRENT_BRANCH=$(git branch --show-current)
CONFIGURED_BASE=$(git config --local --get trackbed.baseBranch || true)
CONDUCTOR_BASE=${CONDUCTOR_DEFAULT_BRANCH:-}
REMOTE_DEFAULT=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2> /dev/null || true)
REMOTE_DEFAULT=${REMOTE_DEFAULT#origin/}
```

If `CURRENT_BRANCH` is empty, or equals `main`, `master`, `CONFIGURED_BASE`, `CONDUCTOR_BASE`, or `REMOTE_DEFAULT`, ask the user to create a feature branch first. Also honor any additional protected branches named in repository instructions. Empty optional values do not match a named current branch. This keeps a `main` workbench protected while also guarding a configured `development` workbench.

## Format

Read `${CLAUDE_PLUGIN_ROOT}/shared/git/references/commit-conventions.md` and resolve the branch-commit convention before writing a subject. Run its signal block with `{history-ref}` set to `refs/remotes/origin/<name>`, using the first non-empty of `CONFIGURED_BASE`, `CONDUCTOR_BASE`, and `REMOTE_DEFAULT` as `<name>`, or `auto` when none is set. Apply the reference's safe-substitution rule. Resolve once per repository per session and reuse the decision for later commits, unless the user explicitly requests a different format.

Plain English is the default when no repository convention is found:

```
Add user authentication endpoint

Implement login and logout functionality with JWT tokens.
Sessions expire after 24 hours of inactivity.
```

## Repository conventions first

Plain English stays the default narrative format. Never impose Conventional Commits on a repository that does not use them; follow a repository that does. Explicit branch-commit instructions outrank squash-merged PR-title history, as the shared reference specifies. Keep each subject descriptive of the step it introduces, with any required ticket or caller work label composed under the resolved convention.

## Pre-commit checklist

Before running `git commit`, confirm all seven:

- [ ] **One logical change, independently reviewable.** If the diff spans two concerns, split it now — not "in a follow-up".
- [ ] **Verified the change.** Tests, typecheck, or lint ran against the staged state; failures were resolved or are deliberately called out in the body.
- [ ] **Subject follows the resolved convention:** imperative mood, about 72 characters or fewer when the convention's prefix allows, no trailing period, and never a placeholder such as `WIP`, `temp`, `fixup`, or `misc`.
- [ ] **Body explains the _why_** when non-obvious — motivation, previous behavior, constraint that forced the shape. Omit the body if the subject is self-explanatory.
- [ ] **Repository left in a working state.** This commit should not break the target workbench branch if it were the tip.
- [ ] **No credentials staged.** Run the names-only secret scan below and settle every path it lists.
- [ ] **No stray files staged.** Review the staged file list for build output, dependency directories, local env and private key files, and personal editor and OS settings.

Two things need explicit user approval before `git commit`: passing `--no-verify` to get past failing hooks (fix the hook failure first) and amending a commit that has already been pushed to a shared branch.

### Secret scan

```bash
git diff --cached -i -G 'password|secret|api_key|token' --name-only
```

This case-insensitive check names files whose staged changes match; it never prints matching lines or values. Settle each listed path before committing: unstage or remove the credential, or confirm a false positive by reviewing the file locally without echoing credentials into terminal or agent logs. Never print, quote, or repeat a matched value in the terminal, the commit message, or your reply. A nonzero exit is a failed check, not a clean scan. Extend the pattern with project-specific markers (`PRIVATE_KEY`, vendor prefixes) when the project has them.

### Stray-file check

List the staged paths with `git diff --cached --name-only` and unstage anything that should not be versioned:

- Build output, such as `dist/`, `build/`, `out/`, `coverage/`, or compiled binaries.
- Dependency directories, such as `node_modules/`, `.venv/`, or `vendor/`.
- Local env files, such as `.env` or `.env.local`, and private key files, such as `*.pem` or `id_rsa`. Committed templates such as `.env.example` are fine.
- Personal editor and OS settings, such as `.idea/`, personal `.vscode/` files, swap files, or `.DS_Store`.

A generated file is allowed only when the project already versions it, which means the path or a peer of the same kind is tracked on the base branch. Otherwise unstage it.

## Body Guidelines

- Keep the body short; omit it entirely if it doesn't add value beyond the subject line
- Describe the outcome and its motivation; implementation detail belongs in the diff.
- Phrase the subject as a present-tense command.
- State the constraint or user need that made the change necessary.
- Mention the old behavior only when the contrast helps a reviewer understand the change.

## AI-Generated Changes

Never include AI attribution markers in commits. Do not add:

- `Co-Authored-By: Claude <noreply@anthropic.com>`
- Phrases like "Generated by AI", "Written with Claude", or similar markers

Commit messages should focus solely on what changed and why, regardless of how the code was produced.

## Output markers

Use these uppercase markers when reasoning about commit decisions. One marker per line, no decoration:

- **STACK DETECTED** — the repo's commit conventions and any CI hooks observed. `STACK DETECTED: plain-English branch commits, tier 2 (AGENTS.md requires plain English), ticket source: none, husky pre-commit runs eslint + tsc`.
- **UNVERIFIED** — claims about the change you couldn't confirm. `UNVERIFIED: haven't run the full test suite after the amend — only typecheck was run`.
- **NOTICED BUT NOT TOUCHING** — adjacent issues observed while staging. `NOTICED BUT NOT TOUCHING: unrelated lint warning in an adjacent file — not part of this commit`.
- **CHANGES MADE / THINGS I DIDN'T TOUCH / POTENTIAL CONCERNS** — end-of-turn summary when a commit (or commit series) is complete.
- **CONFUSION** — contradictory signals in the staged diff. `CONFUSION: commit subject says "fix", but the diff adds a new endpoint`.
- **MISSING REQUIREMENT** — a decision is needed before the commit can be written. `MISSING REQUIREMENT: subject claims a bug fix, but the failing test that motivates it isn't committed yet`.
- **PLAN** — announced sequence when splitting the staging area across multiple commits. `PLAN: commit 1 extracts the validator, commit 2 wires it into the handler, commit 3 adds the test`.
