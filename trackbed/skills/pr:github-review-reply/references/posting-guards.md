# Posting Guards

Read this before the first GitHub write in Step 8. These guards make every reply true when it is posted, visible to reviewers, and posted once. They never push, commit, submit, or discard anything; when a guard fails, the skill holds the affected writes and tells the user what to do.

## 1. Pending review

GitHub files a new reply into the poster's own pending (unsubmitted) review, where only that person can see it. Before the first write of the run, including a resolve-only run, check for one:

```bash
if ! PENDING_REVIEWS_JSON=$(gh api --paginate --slurp "repos/$OWNER/$REPO/pulls/$PR_NUMBER/reviews"); then
  echo "Could not check for a pending review; nothing was posted." >&2
  exit 1
fi
if ! PENDING_REVIEW_IDS=$(printf '%s' "$PENDING_REVIEWS_JSON" \
  | jq -r --arg self "$SELF" '.[][] | select(.user.login == $self and .state == "PENDING") | .id'); then
  echo "GitHub returned an invalid review list; nothing was posted." >&2
  exit 1
fi
if [ -n "$PENDING_REVIEW_IDS" ]; then
  echo "You have a pending review on this PR (review ID(s): $PENDING_REVIEW_IDS). Replies posted now would go into it and stay hidden. Submit or discard it in GitHub, then re-run." >&2
  exit 1
fi
```

A failed or invalid lookup stops the run the same way: no write happens without a clean check. Never submit, discard, or edit the pending review for the user.

## 2. Fix on the PR head

A reply that says a change was made is true only once the change is in a commit on the PR's remote head. Fetch the head GitHub reports right before writing:

```bash
PR_HEAD_OID=$(gh pr view "$PR_NUMBER" --repo "$OWNER/$REPO" --json headRefOid --jq '.headRefOid // empty')
[ -n "$PR_HEAD_OID" ] || {
  echo "Could not read the PR head; nothing was posted." >&2
  exit 1
}
git fetch origin "refs/pull/$PR_NUMBER/head"
[ "$(git rev-parse FETCH_HEAD)" = "$PR_HEAD_OID" ] || {
  echo "The PR head moved while fetching; re-run." >&2
  exit 1
}
```

For every item whose `Changed paths` is not `none`, run `"$FIX_CHECK" "$(git rev-parse --show-toplevel)" "$PR_HEAD_OID" <changed paths>`, with paths relative to the repository root, with `FIX_CHECK` set in Step 8:

- Exit 0: the fix is on the PR head; the item may be posted and resolved.
- Exit 1 or 2: set `Post status: held — fix not on PR head`. Do not post its reply or resolve its thread. Record what the user must do: for `uncommitted` paths, commit and push them; for `not-on-head` paths, push the commits that change them, listed by `git log --oneline "$PR_HEAD_OID..HEAD" -- <paths>`; for exit 2, report the error.

The same check covers an answered-unresolved thread whose earlier reply cited a change: resolve it only after its paths pass.

## 3. Re-check each item just before writing it

The plan is a snapshot; GitHub is the source of truth. Immediately before posting or resolving each item, re-read it:

- **Inline thread** — fetch the thread with `node(id: $THREAD_ID) { ... on PullRequestReviewThread { isResolved comments(last: 100) { nodes { author { login } createdAt body } } } }`.
  - If it is now resolved, set `Post status: skipped — resolved since drafting` and move on.
  - If a comment from `SELF` already follows the latest comment from anyone else, the reply was posted earlier. Set `Post status: posted` without posting again, then continue to the resolve step for it.
- **Review-summary or general comment** — re-fetch the PR's issue comments. If a `SELF` comment created after the item's latest non-author comment links that comment's URL or matches the draft body, set `Post status: posted` without posting again.

If the re-read fails, stop posting and report the item, like any other failed write.

## 4. Posting order and rate limits

Post one item at a time, in plan order, and never in parallel. Finish the re-check, the post, and the plan update for one item before starting the next.

If GitHub answers a write with a rate limit (HTTP 429, or HTTP 403 whose message mentions a rate limit), stop at once. Do not retry or wait it out. Report each item not yet written, with its plan heading, and tell the user that re-running later is safe because the re-check skips anything already posted.

## 5. Copilot resolution reason

When resolving a thread, check whether its first comment came from Copilot code review:

```bash
gh api graphql -f threadId="$THREAD_ID" -f query='
query($threadId: ID!) {
  node(id: $threadId) {
    ... on PullRequestReviewThread { comments(first: 1) { nodes { isCopilotCodeReview } } }
  }
}' --jq '.data.node.comments.nodes[0].isCopilotCodeReview'
```

When it prints `true`, add `resolutionReason: ADDRESSED` to the `resolveReviewThread` input. If this query fails, or GitHub rejects the `resolutionReason` argument, resolve the thread without a reason; the reason is optional and never blocks a resolve.
