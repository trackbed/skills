# Posting Guards

Read this before the first GitHub write in Step 8. These guards make every reply true when it is posted, visible to reviewers, and posted once. They never push, commit, submit, or discard anything; when a guard fails, the skill holds the affected writes and tells the user what to do.

## 1. Pending review

GitHub files a new reply into the poster's own pending (unsubmitted) review, where only that person can see it. Before the first write of the run, including a resolve-only run, check for one:

```bash
if [ -z "$SELF" ]; then
  echo "Could not identify the authenticated GitHub user; nothing was posted." >&2
  exit 1
fi
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

A reply that says a change was made is true only once the change is in a commit on the PR's remote head. Skip this section when every item's `Changed paths` is `none`. Otherwise, in Step 8 before asking for confirmation, read the head GitHub reports and fetch it:

```bash
PR_HEAD_OID=$(gh pr view "$PR_NUMBER" --repo "$OWNER/$REPO" --json headRefOid --jq '.headRefOid // empty')
[ -n "$PR_HEAD_OID" ] || {
  echo "Could not read the PR head; nothing was posted." >&2
  exit 1
}
git fetch origin "refs/pull/$PR_NUMBER/head" \
  || echo "Could not fetch the PR head from origin; items whose fix needs it stay held." >&2
```

A failed fetch does not stop the run: when the head commit is missing locally, the script exits 2 and the item is held. For every item whose `Changed paths` is not `none`, run `"$FIX_CHECK" "$(git rev-parse --show-toplevel)" "$PR_HEAD_OID"` followed by each changed path, relative to the repository root, as its own single-quoted argument:

- Exit 0: the fix is on the PR head; the item may be posted and resolved.
- Any other exit status: set `Post status: held — fix not on PR head`. Do not post its reply or resolve its thread. Record what the user must do: for `uncommitted` paths, commit and push them; for `not-on-head` paths, push the commits that change them, listed by `git log --oneline "$PR_HEAD_OID..HEAD" -- <paths>`, or, when that lists nothing, pull the PR head because the checkout is behind it; otherwise report the script's error.

The same check covers an answered-unresolved thread whose earlier reply cited a change: resolve it only after its paths pass.

## 3. Re-check each item just before writing it

The plan is a snapshot; GitHub is the source of truth. Immediately before posting or resolving each item, re-read it and compare against the item's drafting snapshot (`Thread state` and `Latest comment at drafting`), never against the thread's shape alone: under `--all`, a thread can already be resolved, or already end in an earlier reply from `SELF`, when it is drafted.

- **Inline thread with a GraphQL thread ID** — fetch the thread with `node(id: $THREAD_ID) { ... on PullRequestReviewThread { isResolved comments(last: 100) { nodes { author { login } createdAt body } } } }`.
  - If it is now resolved and its `Thread state` was not `resolved` at drafting, set `Post status: skipped — resolved since drafting` and move on; an item this run already posted keeps `posted`. A thread that was already resolved at drafting, kept by `--all`, still gets its reply.
  - If the item has a reply to post (`Reply target` is not `none`) and a comment from `SELF` was created after `Latest comment at drafting`, the reply was posted after drafting. Set `Post status: posted` without posting again, then continue to the resolve step for it. A `SELF` comment from before drafting never counts, so an `--all` reply to an already-answered thread is still posted.
- **REST-only inline thread** (`Thread ID: unavailable`) — the GraphQL query above needs a thread ID, so re-read the thread over REST instead: the root comment and every reply to it.

  ```bash
  gh api --paginate --slurp "repos/$OWNER/$REPO/pulls/$PR_NUMBER/comments" \
    | jq --argjson root "$ROOT_COMMENT_ID" '[.[][] | select(.id == $root or .in_reply_to_id == $root) | {login: .user.login, created_at}]'
  ```

  REST reports no resolution state, so skip the resolved check; Step 8 already required explicit confirmation for this post. If a `SELF` comment in the result was created after `Latest comment at drafting`, set `Post status: posted` without posting again. If the root comment is missing from the result, treat it as a failed re-read. REST-only threads are never resolved.

- **Review-summary or general comment** — re-fetch every page of the PR's issue comments with `gh api --paginate "repos/$OWNER/$REPO/issues/$PR_NUMBER/comments"`. If a `SELF` comment created after both the item's latest non-author comment and its `Latest comment at drafting` links that comment's URL or matches the draft body, set `Post status: posted` without posting again.

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
