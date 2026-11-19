# Publishing `--auto` Fixes

Read this in Step 8 when `AUTO=true` and Step 5 recorded `Changed paths` for any item. The user's `--auto` request covers committing and pushing the fixes, so their replies can post in the same run. Publishing adds one new commit on top of the PR head and pushes it to the PR branch. It never force-pushes, rewrites history, or commits a file outside the fixes. When publishing does not run or fails, the fixes stay where they are, and the fix-on-head guard holds their replies as usual.

## When to publish

Publish only when all of these hold:

- `PUBLISH_FIXES=true`: Step 5 found no local changes before it started. Otherwise a fix commit could sweep in the user's own edits to the same files.
- `PR_CROSS_REPO=false`. A Pull Request from a fork has its branch in another repository, so do not push it; tell the user to push the fixes themselves.
- Step 5 ended without stopping, so every fix passed its validation.

When any condition fails, skip the rest of this file and report which one failed in the Step 11 output.

## Commit and push

Write the commit message to `.context/github-review-replies/commit-message.txt`: a plain-English summary of the fixes, written in the repository's commit style. Then run the script. Pass the union of the `Changed paths` Step 5 recorded, each relative to the repository root and as its own single-quoted argument:

```bash
"$PUBLISH_SCRIPT" "$(git rev-parse --show-toplevel)" "$PR_HEAD" "$PR_FETCH_REMOTE" "$PR_HEAD_BRANCH" \
  .context/github-review-replies/commit-message.txt 'src/a.ts' 'src/b.ts'
```

The script checks that the checkout is on the PR branch at exactly `PR_HEAD` with nothing already staged. It stages only the given paths and refuses to commit when a tracked file outside them has changed, or when a new file outside them appeared that is not one of this skill's own artifacts (`GITHUB_REVIEW_REPLY_PLAN.md`, `GITHUB_REVIEW_REPLY_PLAN.html`, or `.context/`). The tree was clean before Step 5, so such a file came from the fixes, such as a new test left out of `Changed paths`, and committing without it would push an incomplete fix. Then it commits and pushes without force, so a push to the branch since the run started gets the new commit rejected rather than overwritten.

- **Exit 0**: it printed the pushed commit ID. Record it as `PUSHED_COMMIT`, then wait until GitHub reports it as the PR head:

  ```bash
  for attempt in 1 2 3 4 5 6; do
    [ "$(gh pr view "$PR_NUMBER" --repo "$OWNER/$REPO" --json headRefOid --jq '.headRefOid')" = "$PUSHED_COMMIT" ] && break
    sleep 5
  done
  ```

  If GitHub never reports it, continue: the fix-on-head guard holds the affected replies, and re-running later posts them.

- **Exit 1**: the commit exists locally but was not pushed. Report the printed commit ID and the script's reason, and tell the user to push it.
- **Exit 2**: nothing was committed. Report the script's reason. The fixes stay uncommitted in the working tree.
