---
name: pr:stack
description: Create and manage GitHub stacked PRs with gh-stack v0.3.0 or newer. Build an ordered chain of dependent branches, submit chained draft PRs, make mid-stack edits safely, merge or sync stacks, and adopt existing branch chains. Use when a change should land as a sequence of small dependent PRs instead of one large PR. Requires stacked PRs to be enabled for the repository; degrades to a manual chain otherwise.
argument-hint: "[init [--base <trunk>] <branches...> | submit | sync | merge <pr-number> | adopt [--base <trunk>] <branches...> | status]"
disable-model-invocation: true
user-invocable: true
---

<!-- Adapted from github/gh-stack skills/gh-stack/SKILL.md at commit a1b4a3d4d0bcde9ec3a78ab99b2d63af121857a9 under the MIT License. Full notice: references/github-gh-stack-LICENSE. -->

# GitHub Stacked PRs

Manage a **stack**: an ordered chain of branches where each branch builds on the one below it and each maps to one PR whose base is the branch below. Reviewers see only the diff for that layer; GitHub tracks the chain server-side, evaluates CI and branch protection against the stack base, and lands cascading merges bottom-up.

```
<resolved trunk>
 └── auth-layer     → PR #1 (base: <resolved trunk>)
  └── api-endpoints → PR #2 (base: auth-layer)
   └── frontend     → PR #3 (base: api-endpoints)
```

Read `references/cli-agent-rules.md` before running any `gh stack` command — every invocation must be non-interactive (branch names as arguments, `submit --auto`, `view --json`, never `modify`).

Also read `${CLAUDE_PLUGIN_ROOT}/shared/git/references/stack-operations.md` before any `gh stack` command. It holds the gh-stack exit codes, the rules for other worktrees, and the **Sync outcomes** and **Merge outcomes** checks. Before every `gh stack rebase` and `gh stack sync` in this skill, run its other-workspace preflight with `${CLAUDE_PLUGIN_ROOT}/scripts/list-stack-worktrees.sh`. It also governs conflicts, paused rebases, and `--accept-base-change`.

## When to use

- New work that naturally lands as an ordered sequence of small, dependently-reviewable PRs (foundation → API → UI).
- An existing local branch chain (e.g. built from a `trackbed:code:breakdown-findings --split` Stack plan) that should become a linked GitHub stack.
- Maintaining an existing stack: syncing after merges, restacking after edits, checking status.

## When NOT to use

- A single independent change — use `trackbed:pr:create`; a one-PR stack is ceremony without benefit.
- Deciding _how_ to split a large existing branch — run `trackbed:code:breakdown-findings --split` first; its Stack strategy hands the slice plan back to this skill.
- Unrelated parallel work — stacks are strictly linear (one parent, one child per branch). Parallel workstreams get separate branches or separate stacks.
- Cross-fork contributions — stacks cannot span forks.

## Step 0: Parse operands safely

Treat every user-supplied branch, PR number, and PR URL as data:

- Parse argument tokens directly into `STACK_BRANCHES` or `STACK_ITEMS` arrays. Never build a command string, use `eval`/`sh -c`, or re-split a joined string.
- For `init` or local `adopt`, accept at most one `--base <trunk>` before collecting branch operands. Reject a missing value or a use of `--base` with another action. Validate it with `git check-ref-format --branch`, store it as `BASE_BRANCH_OVERRIDE`, and pass it to the shared base resolver; it is a trunk choice, not a stack layer.
- Before passing a branch to `init`, `add`, or `checkout`, require `git check-ref-format --branch "$branch"` to succeed. For branch `checkout`, also reject integer-like names (including a leading `+`); use a validated nonnumeric branch or `up`/`down` navigation.
- Before passing an item to `link`, accept only a valid branch, a positive integer PR number, or a current-repository PR URL matching `https://github.com/<owner>/<repo>/pull/<positive-integer>`. For remote `checkout`, use the resolved positive `STACK_NUMBER`; PR numbers and PR URLs both enter gh-stack's stack-first lookup.
- For `link`, preserve supplied PR numbers and URLs. A leading bare number can select an existing stack or push an identically named local branch, so reject both collisions. Explicit PR URLs bypass numeric target selection. Use a validated nonnumeric branch first only when the user supplied that branch; never replace a selected PR with its head branch.
- Invoke commands with quoted array expansion: `gh stack init --base "$BASE_BRANCH" "${STACK_BRANCHES[@]}"` after validating the trunk, and the guarded `gh stack link "${STACK_ITEMS[@]}"` procedure in Adopt.

If an operand fails validation, stop and name it. Do not “repair” or normalize user input.

## Step 1: Availability and membership

### Conductor workspaces

Synced Conductor workspace boundary contract (keep aligned across git-mutating workflow skills): when `CONDUCTOR_WORKSPACE_PATH` is set: stay on the current branch absent explicit approval; use another Conductor workspace—not raw worktrees or throwaway branches—for isolation. Never remove, reset, or re-point a Conductor workspace path; archive workspaces through Conductor. Conductor changes defaults, not permissions or safety gates.

When `CONDUCTOR_WORKSPACE_PATH` is set, capture and validate the entry branch as `{workspace-branch}` before any stack checkout. Stack operations may check out sibling stack branches as gh stack requires; finish by returning to `{workspace-branch}` and say so in the report.

- **Extension missing or older than v0.3.0 (`STACK_CLI_SUPPORTED=0`):** the membership resolver still checks GitHub. If GitHub reports an existing remote stack, do not create a duplicate manual chain. Otherwise offer to install the extension (`gh extension install github/gh-stack`) or upgrade it (`gh extension upgrade stack`); if declined, fall back to ordered branches each rooted on the previous, PRs opened with `gh pr create --base <parent-branch>`, and a note in each PR body naming its position in the chain.
- **Feature not enabled (exit code 9 from `submit`/`link`/`checkout`):** stacked PRs must be enabled for the repository. Stop without retrying, tell the user so, and offer the same manual-chain fallback — once the repository is enabled, re-run Step 1 and follow its route.

One-time non-interactive setup (safe to re-run):

```bash
git config rerere.enabled true
git config remote.pushDefault origin # only when multiple remotes exist
```

Resolve both local CLI state and server-side GitHub state, then pick the workflow below:

```bash
STACK_RESOLVED=$("${CLAUDE_PLUGIN_ROOT}/scripts/resolve-stack-membership.sh") || {
  echo "Stack membership could not be determined; stop before creating, adopting, or rewriting a stack." >&2
  exit 1
}
eval "$STACK_RESOLVED"
```

| State | Route |
| --- | --- |
| `STACK_MEMBERSHIP=local` and the user wants status | **Status report** |
| `STACK_MEMBERSHIP=local` | **Maintain** — mid-stack edits, sync, submit new layers |
| `STACK_MEMBERSHIP=remote` | Do not create or adopt a duplicate. For native maintenance, follow `${CLAUDE_PLUGIN_ROOT}/shared/git/references/stack-checkout.md` to import by `STACK_NUMBER`, restore the entry branch, and revalidate membership before retrying; otherwise report/manage the existing server-side stack. |
| `STACK_MEMBERSHIP=none`, user wants a new stack | **Create** |
| `STACK_MEMBERSHIP=none`, ordered branches already exist | **Adopt** |

The resolver treats “not tracked locally” as either a `gh stack view` exit 2 or a zero exit with empty output or the known “is not part of a stack” notice — gh-stack can report an untracked branch through either channel — then queries the branch PR's GraphQL `stack` field. A zero exit only proves local membership when stdout has the documented stack JSON shape and includes the current branch. Authentication, API, parsing, and unexpected CLI failures stop the workflow; they are never interpreted as “not stacked.”

The minimum supported extension version is v0.3.0. Older versions push stack branches one at a time by default, can replay already-merged commits when rebasing after a merge, and do not follow a base branch that GitHub retargets. An older or unparseable version does not block the resolver: it warns, reads membership with `gh stack view --json` only, and returns `STACK_CLI_SUPPORTED=0`, so unstacked branches and other skills keep working. Never run another `gh stack` command under that value. When that version tracks the branch locally, the resolver stops with the exact `gh extension upgrade stack` command instead, because every route for a local stack runs stack commands.

## Create a new stack

1. Plan layers by dependency order **before** creating branches: foundational changes (schema, models, shared utilities) in lower branches; consumers (API, UI, integration tests) above. Each branch is one reviewable concern. Keep a stack to roughly four or five PRs; anything deeper needs explicit coordination (named chain positions, one reviewer, an agreed merge cadence).
2. Resolve the new stack's trunk with `${CLAUDE_PLUGIN_ROOT}/scripts/resolve-base.sh --strict --workbench --format json` from the user's repository, passing `--base "$BASE_BRANCH_OVERRIDE"` when supplied. `--workbench` skips any Pull Request target on the entry branch because this is a new stack. Parse its `base_branch` JSON field as `BASE_BRANCH`, validate it with `git check-ref-format --branch`, then initialize with explicit branch names and that branch (never bare — that prompts):

   ```bash
   RESOLVE_ARGS=(--strict --workbench --format json)
   [ -n "${BASE_BRANCH_OVERRIDE:-}" ] && RESOLVE_ARGS+=(--base "$BASE_BRANCH_OVERRIDE")
   RESOLVED_JSON=$("${CLAUDE_PLUGIN_ROOT}/scripts/resolve-base.sh" "${RESOLVE_ARGS[@]}") || exit 1
   BASE_BRANCH=$(printf '%s' "$RESOLVED_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["base_branch"])') || exit 1
   git check-ref-format --branch "$BASE_BRANCH" > /dev/null || exit 1
   gh stack init --base "$BASE_BRANCH" first-layer
   ```

   This preserves a `main` workbench in repositories that release from tags and selects a configured `development` workbench when production `main` is the remote default. If the repository's workbench cannot be determined, stop for an explicit base rather than guessing from branch names. Carry the same `BASE_BRANCH` into a manual-chain fallback for the bottom Pull Request.

3. Work bottom-up. On each branch, stage deliberately with plain `git add <files>` / `git commit`, then create the next layer:

   ```bash
   gh stack add next-layer
   ```

   Uncommitted changes carry over to the new branch (standard git behavior) — commit or stash before `add` for a clean cut. `add` must run from the topmost branch (`gh stack top` first if elsewhere).

4. When you realize a change belongs to a **lower** layer, do not commit it where you are: `gh stack down` (or `gh stack checkout <branch>`), commit it there, `gh stack rebase --upstack`, then `gh stack top` and continue. Changes committed at the wrong layer end up in the wrong PR's diff.

## Submit: push and open the chained PRs

```bash
gh stack submit --auto        # push all branches, create chained PRs as drafts
gh stack submit --auto --open # same, but ready for review
```

`--auto` titles each PR from its commits (single commit → commit subject; multiple → humanized branch name) and cannot set custom titles or bodies. Immediately after submitting, bring every PR up to the repository's standards:

- List the PRs: `gh stack view --json | jq -r '.branches[] | select(.pr) | "\(.pr.number) \(.name)"'`
- For each, read its URL with `gh pr view <number> --json url`, require a valid HTTPS hostname, and retain that hostname as `PR_HOST`; stop if it cannot be determined. Repository placeholders do not select the API host. Then write the title and body to temporary files with the runtime's file writer, then run `gh api --method PATCH "repos/{owner}/{repo}/pulls/<number>" --hostname "$PR_HOST" -f title="$(cat <title-file>)" -F body=@<body-file> --silent`. Do not invoke `trackbed:pr:generate-description` from inside this skill: every model-initiated call to that child must use output-only `--no-update`, while this workflow has no separate validated payload and publication phase. If generated assistance is needed, stop this workflow, check out the intended PR branch, and ask the user to invoke `/trackbed:pr:generate-description` directly.
- Name the chain position in each body ("PR 2 of 3 in this stack") — the Stack Map UI shows it, but reviewer notifications don't.

Re-running `submit --auto` is safe: it pushes changed branches, creates PRs only for branches without one, and repairs base branches.

## Maintain an existing stack

**Respond to review feedback on a lower layer:**

```bash
gh stack checkout <validated-nonnumeric-branch> # or: gh stack down / bottom
# edit, git add <files>, git commit
gh stack rebase --upstack                 # rebase everything above onto the new commits
env -u GH_STACK_NO_ATOMIC gh stack push                             # all branches, --force-with-lease --atomic
```

**Routine sync (trunk moved, PRs merged, stack changed on GitHub):**

First read `${CLAUDE_PLUGIN_ROOT}/shared/git/references/stack-rewrite-safety.md` and run its complete preflight. Stop before syncing if any open branch diverged; allow behind-only branches. Use its resolved `STACK_REMOTE` for sync and any recovery rebase. Run the sync through the shared reference's **Sync outcomes** block, which runs `env -u GH_STACK_NO_ATOMIC gh stack sync --remote "$STACK_REMOTE"` (fetch, cascade-rebase, push, and sync PR state) and checks its outcome in the same Bash call; add `--prune` to delete local branches for merged PRs. Report the stack as synced only when the block prints `STACK_SYNCED=true`.

Sync handles squash-merged parents automatically. The shared preflight stops divergent active branches with the integrate-first message; gh-stack alone does not reconcile that divergence. Clearing `GH_STACK_NO_ATOMIC` makes Git ref updates all-or-nothing; PR/API updates remain separate.

**Conflicts (exit code 3) are command-specific.** Resolve them in the worktree gh-stack names, under the shared reference's **Conflicts** rules:

- After `env -u GH_STACK_NO_ATOMIC gh stack sync`, all branches were restored before the command returned. Repeat the shared preflight and the other-workspace preflight, then start a fresh `gh stack rebase --remote "$STACK_REMOTE"`, resolve markers file by file, `git add` each, then run `gh stack rebase --continue`.
- After `gh stack rebase`, a rebase session remains active. Resolve markers file by file, `git add` each, then run `gh stack rebase --continue` directly — do not start a second rebase.

Repeat per conflict round. `gh stack rebase --abort` restores all branches if the resolution stops being mechanical; then escalate to the user. Continue or abort only a rebase this session started.

**After any history rewrite on a stack branch** (`trackbed:git:fixup`, `trackbed:git:recreate-commits`, fix-ci consolidation): the branches above are orphaned until you restack. Never push a single stack branch with plain `git push --force-with-lease`; `env -u GH_STACK_NO_ATOMIC gh stack push` updates every branch atomically:

```bash
gh stack rebase --upstack --no-trunk
env -u GH_STACK_NO_ATOMIC gh stack push
```

**Restructure (reorder / drop / rename branches):** never `gh stack modify` (TUI-only). Rebuilding the stack records a new order but does not move commits, so fix Git history first, then tear down and rebuild. PRs and branches survive, except that a renamed branch gets a new PR; tell the user to close the old one.

1. Read `${CLAUDE_PLUGIN_ROOT}/shared/git/references/stack-rewrite-safety.md` and run its complete preflight with `STACK_STOP_ON_BEHIND=1` before every Restructure, because the rebuild force-pushes every moved layer and would drop commits that exist only on the remote. If it stops on a behind branch, run **Routine sync** above; on a diverged branch, integrate it; then start over. Run `gh stack view --json`. If any branch reports `needsRebase: true`, restack first and start over, because a stale layer's old parent tip is not where that layer starts: run `gh stack rebase --remote "$STACK_REMOTE"`, handling conflicts as in **Conflicts** above. Validate the trunk and record it as `<recorded-trunk>`. For every branch, record its tip SHA and its old parent's tip SHA before moving anything; for the bottom branch, the old parent tip is `git merge-base <recorded-trunk> <branch>`.
2. Keep the recorded branch names until step 4. From the lowest changed position up the new order, rebase every layer onto its new parent, including a layer whose parent kept its name but was itself moved. Use the recorded old parent tip so only that layer's own commits move:

   ```bash
   git rebase --onto <new-parent> <recorded-old-parent-tip> <branch>
   ```

   The new bottom layer's parent is the recorded trunk. A dropped branch leaves the stack; its commits stay out of every remaining layer. Stop on a conflict or any other Git error, such as a branch checked out in another worktree, and escalate instead of resolving content the user did not ask to change or touching another worktree.

3. Confirm each layer holds only its own commits. A rebase changes commit SHAs, so compare patches with `git range-diff <recorded-old-parent-tip>..<recorded-tip> <new-parent>..<branch>`. Stop on any unpaired commit: a line marked `<` (dropped) or `>` (added).

   On any stop in steps 2–3, nothing has been unstacked or pushed yet. Run `git rebase --abort` if a rebase is active, restore each layer you already moved to its recorded tip (`git reset --keep <recorded-tip>` on the checked-out branch, `git branch -f <branch> <recorded-tip>` for the others), and report the recorded trunk and tips to the user.

4. Rebuild from the recorded trunk, bottom to top. Rename branches only after `gh stack unstack`, then pass the new names to `init`:

   ```bash
   gh stack unstack
   # rename branches with plain git as needed
   gh stack init --base <recorded-trunk> <branches bottom-to-top>
   gh stack submit --auto
   ```

## Adopt an existing chain

- **Local ordered branches** (e.g. built from a `trackbed:code:breakdown-findings --split` Stack plan): validate every member with `git check-ref-format --branch`, store them in `STACK_BRANCHES`, resolve `BASE_BRANCH` through the Create step's `${CLAUDE_PLUGIN_ROOT}/scripts/resolve-base.sh` JSON procedure (including `BASE_BRANCH_OVERRIDE` when supplied), then run `gh stack init --base "$BASE_BRANCH" "${STACK_BRANCHES[@]}"` (bottom to top — existing branches are adopted), followed by `gh stack submit --auto`. Stop if the resolved trunk is unclear or conflicts with the chain's known parent. gh-stack shares local tracking across a clone's worktrees, so a worktree chain needs `init`, not `link`.
- **PRs already on GitHub without a local chain, or branches managed by other tools** (jj, Sapling, git-town): validate each branch/PR operand from Step 0 and store them in `STACK_ITEMS` bottom to top. Read `references/link-target.md` and run its guarded link procedure with the original array. Bare PR leaders require collision checks; explicit URLs pass through unchanged. Branch-led input uses the supplied branch. It pushes branch operands, creates missing PRs, repairs bases, and links the stack — no local tracking required.

## Status report

Summarize `gh stack view --json` for the user: trunk, branch order bottom-to-top with PR number/state per branch, which branches need a rebase (`needsRebase`), and which are merged or queued. Recommend the next action (`sync` when the trunk moved or something merged; `rebase` when `needsRebase`; `submit --auto` when branches lack PRs).

## Merging

Select the **highest PR the user intends to land**: use the top PR to land the entire stack, or a lower PR to land only that PR and every unmerged PR below it. Validate the target as a positive integer under Step 0. Choose one merge method allowed by the repository (`merge`, `squash`, or `rebase`); if the user did not specify one and more than one is allowed, ask rather than guessing.

Read `references/merge-target.md` and run its target resolution before merging. It resolves the selected PR's stack number, uses that number for a whole-stack merge, and allows a partial PR target only after proving that no stack has the same number. If the PR is in no stack or its stack number cannot be determined, report that and stop. On a partial-target collision, stop and ask the user how to proceed; never substitute the whole stack or a PR URL.

Run the merge headlessly with the resolved `MERGE_TARGET`, confirmation flag, and validated method. Run the merge-target resolution, this block, and the shared **Merge outcomes** check in one Bash call with the maximum Bash timeout, so the variables they share stay set and a slow merge is not cut off:

```bash
MERGE_ARGS=(--yes)
case "$MERGE_METHOD" in
  merge) MERGE_ARGS+=(--merge) ;;
  squash) MERGE_ARGS+=(--squash) ;;
  rebase) MERGE_ARGS+=(--rebase) ;;
  *)
    echo "Unsupported stack merge method: $MERGE_METHOD" >&2
    exit 1
    ;;
esac
echo "MERGE_STARTED=true"
MERGE_OUTPUT=$(gh stack merge "$MERGE_TARGET" "${MERGE_ARGS[@]}" 2>&1)
MERGE_STATUS=$?
printf '%s\nMERGE_STATUS=%s\n' "$MERGE_OUTPUT" "$MERGE_STATUS"
```

`gh stack merge` atomically lands every eligible PR through the target; if any cannot merge, none do. A repository merge queue controls its own method, so gh-stack ignores the supplied method there, and the PRs are only queued. GitHub re-targets and rebases PRs above a partial merge.

Whatever `MERGE_STATUS` is, follow the shared reference's **Merge outcomes** section next: report merged and queued PRs separately, and handle the printed `MERGE_STATUS` of 3 or 4 as it says. Only when every PR through the target shows as merged, repeat the routine-sync preflight and run **Routine sync** with `--prune`.

## Verification

Before reporting done:

- [ ] `gh stack view --json` shows the expected branch order, and no branch has `needsRebase: true`.
- [ ] Every PR's base is the branch below it (bottom PR's base is the trunk); this is the only check that also covers the manual-chain fallback.
