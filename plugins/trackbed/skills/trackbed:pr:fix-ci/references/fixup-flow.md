# Fixup Commit Flow (Step 8b)

**Goal:** Amend existing branch commits instead of adding new commits, keeping history clean during iteration.

For stacks, capture and prepare a fresh frozen snapshot under `stack-rewrite-safety.md` before this phase's fetches or history edits, after the existing cross-worktree confirmation. Never reuse a snapshot from an earlier published iteration.

Before any fetch or rewrite in this phase, capture the single-branch publication precondition below when `IN_STACK=false`. Keep these values unchanged through the push, including after later fetches; never refresh the lease to make a rejected push succeed. A lookup failure, absent remote branch, or ambiguous response stops before rewriting.

```bash
if [ "$IN_STACK" = false ]; then
  REWRITE_BRANCH=$(git branch --show-current) || exit 1
  [ -n "$REWRITE_BRANCH" ] || exit 1
  REWRITE_REMOTE_REF="refs/heads/$REWRITE_BRANCH"
  REWRITE_REMOTE=$(git remote get-url --push origin) || exit 1
  REWRITE_OBSERVATION=$(git ls-remote --exit-code --refs "$REWRITE_REMOTE" "$REWRITE_REMOTE_REF") || exit 1
  read -r REWRITE_REMOTE_OID REWRITE_OBSERVED_REF <<< "$REWRITE_OBSERVATION"
  [[ "$REWRITE_REMOTE_OID" =~ ^([0-9a-f]{40}|[0-9a-f]{64})$ ]] || exit 1
  [ "$REWRITE_OBSERVED_REF" = "$REWRITE_REMOTE_REF" ] || exit 1
  git fetch --no-tags -- "$REWRITE_REMOTE" "$REWRITE_REMOTE_OID" || exit 1
  git merge-base --is-ancestor "$REWRITE_REMOTE_OID" HEAD || exit 1
fi
```

## Step 8b.1: Determine Base Branch (from PR)

Use the PR's base branch from Step 1 so fixups stay scoped to the actual target branch.

```bash
BASE=$(env GH_PROMPT_DISABLED=1 gh pr view --json baseRefName --jq .baseRefName) || {
  echo "Could not resolve the current Pull Request target; stop before rewriting commits." >&2
  exit 1
}
```

If the PR base branch is empty, stop rather than substituting the repository default. A Pull Request targeting `development` must not be rewritten against production `main`, and a Pull Request targeting `main` must retain that target.

```bash
if [ -z "$BASE" ]; then
  echo "Pull Request target branch is missing; stop before rewriting commits." >&2
  exit 1
fi
BASE_REF="origin/$BASE"
```

Before using `BASE_REF`, ensure the remote ref exists and is up to date:

```bash
git fetch origin "$BASE"
git show-ref --verify --quiet "refs/remotes/origin/$BASE"
```

If the ref is missing, re-run base detection or `git fetch origin` and try again.

Derive the branch fork point from the resolved base ref. This keeps fixup autosquash scoped to branch commits even when the base branch has advanced:

```bash
FIXUP_BASE=$(git merge-base HEAD "$BASE_REF")
```

## Step 8b.2: Map Changed Files to Commits

For each changed file (from `git diff --name-only`, `git diff --cached --name-only`, and untracked files from `git ls-files --others --exclude-standard`), find which branch commit last touched it:

```bash
git log "$BASE_REF..HEAD" -n 1 --format=%H -- "<file_path>"
```

Combine and de-dupe those file lists before mapping. Group files by their target commit SHA. Files with no matching commit are "orphans" (files not touched by any branch commit, including files last modified on the base branch).

## Step 8b.3: Create Fixup Commits

For each target commit (from the mapping):

```bash
git add -A -- <matched_files...>
git commit --fixup=<commit_sha>
```

## Step 8b.4: Handle Orphan Files

If any files were not touched by branch commits (orphans), create a regular commit for them:

```bash
git add -A -- <orphan_files...>
git commit -m "<descriptive message of what was fixed>"
```

## Step 8b.5: Autosquash Rebase

```bash
GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash "$FIXUP_BASE"
```

**If rebase fails (conflicts):**

1. Abort the rebase:
   ```bash
   git rebase --abort
   ```
2. Log a warning:
   > "Autosquash rebase failed due to conflicts. Falling back to regular commit mode for this iteration. The fixup commits remain on the branch and can be manually squashed later."
3. Fall back to regular commit (Step 8 default behavior) for any remaining uncommitted changes
4. Continue to push step

## Step 8b.6: Push with Force

After successful rebase (or fallback), confirm one of these is true before pushing:

- The branch is not shared.
- The user explicitly confirmed collaborators are coordinated for a history rewrite.

If neither is true, stop here. Keep the rebased result local, tell the user not to push it yet, and recommend either coordinating first or switching back to the default mode for visible iteration commits.

If one of those conditions is true, choose exactly one push path:

```bash
if [ "$IN_STACK" = true ]; then
  gh stack rebase --upstack --no-trunk
  python3 "${CODEX_HOME:-$HOME/.codex}/plugins/cache/trackbed/trackbed/1.1.1/scripts/git-rewrite/stack-publication.py" publish --state "$STACK_PUBLICATION_STATE" || exit 1
else
  [ "$(git branch --show-current)" = "$REWRITE_BRANCH" ] || exit 1
  git -c push.followTags=false push --no-follow-tags \
    --force-with-lease="${REWRITE_REMOTE_REF}:$REWRITE_REMOTE_OID" \
    -- "$REWRITE_REMOTE" "HEAD:$REWRITE_REMOTE_REF" || exit 1
fi
```

**Note:** `--force-with-lease` is required because the rebase rewrites history. The captured exact OID rejects an intervening remote push even after a fetch; keep collaborator coordination as a separate gate.

`IN_STACK` was resolved in the parent skill before the loop. A stack rewrite orphans the branches above it, so the stack path restacks locally first and pushes only after that succeeds. Never force-push the rewritten parent branch before the stack-wide atomic push.
