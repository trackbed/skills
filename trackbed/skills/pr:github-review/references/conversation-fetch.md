# Fetching and mapping an ongoing review conversation

How to pull the existing comments on a PR and classify them from the **reviewer's seat** (you are reviewing someone else's PR, not authoring it). All operations in this reference are reads. `gh` and `jq` were confirmed in Preflight.

Set the repository and actor context from values already resolved earlier:

```bash
OWNER="${PR_NWO%%/*}"
REPO="${PR_NWO#*/}"
# SELF (your login) and AUTHOR (the PR author's login) are already set.
```

## 1. Fetch the data

Use the shared review-thread location reference resolved in Step 7 for the required anchor fields, submission filter, and code reads.

**Inline review comments (REST)** — retain the shared anchor fields, stable IDs, node IDs, `in_reply_to_id`, `user.login`, `user.type`, and `html_url`:

```bash
gh api --paginate "repos/$OWNER/$REPO/pulls/$PR_NUMBER/comments"
```

**Review threads (GraphQL)** — thread IDs, resolution state, and per-comment authors. Match to REST comments by node ID (`REST.node_id` == `GraphQL.id`):

```bash
gh api graphql -f owner="$OWNER" -f name="$REPO" -F number="$PR_NUMBER" -f query='
query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          isOutdated
          path
          diffSide
          startDiffSide
          line
          startLine
          originalLine
          originalStartLine
          subjectType
          comments(first: 100) {
            nodes { id url body createdAt state author { login __typename } }
          }
        }
      }
    }
  }
}'
```

Repeat with the returned `endCursor` while `hasNextPage` is true.

**General PR comments (REST)** — top-level discussion not anchored to a line:

```bash
gh api --paginate "repos/$OWNER/$REPO/issues/$PR_NUMBER/comments"
```

**Prior reviews (REST)** — summary-level review verdicts, including your own standing decision:

```bash
gh api --paginate "repos/$OWNER/$REPO/pulls/$PR_NUMBER/reviews"
```

**GraphQL fallback.** If GraphQL fails but REST succeeds, resolution state is unknown. Continue REST-only: group inline comments by `in_reply_to_id` (root comments have none), mark each thread `Resolution: unknown`, and never assume a thread is resolved. If `--all-threads` was not set, say plainly that the unresolved-only filter cannot be applied without GraphQL and include all threads.

## 2. Group into threads

Apply the shared submission filter before grouping: exclude `PENDING` comments and reviews, including your own pending review IDs in REST-only fallback. Pending-only threads never enter the map; latest-author and open-thread counts use submitted comments only.

1. Join REST inline comments to GraphQL threads by node ID. The first comment in a GraphQL thread is the root; for REST-only fallback, a root has no `in_reply_to_id` and replies point to it.
2. Treat each general PR comment as its own single-comment item.
3. For each thread, record: root author, latest submitted comment author, latest comment timestamp, the full shared anchor, resolution state, and the thread URL. Your last review excludes `PENDING`; preserve its actual submitted state, including `DISMISSED` when applicable.

## 3. Filter

- Unless `--include-bots`, drop comments whose GraphQL `__typename` is `Bot` or REST `user.type` is `Bot`.
- Unless `--all-threads`, drop threads that are resolved. Keep unresolved threads and any thread whose latest comment is **not** from you.
- Never drop a thread you started (`root author == SELF`) that has replies — those are the ones most likely to need your response.

## 4. Classify each thread from the reviewer's seat

Assign exactly one state by applying these rules in order and stopping at the first match:

1. `resolved` — the thread is resolved. It is present only with `--all-threads`; surface it for context with no action.
2. `author-responded` — the unresolved thread was started by `SELF`, and its latest submitted comment is from `AUTHOR` (often "done" / "fixed" / a question). Apply the shared locating rules to inspect the anchored code and current implementation, not finding overlap: if the code now resolves the concern the fix landed, otherwise it is still open.
3. `awaiting-you` — the remaining unresolved thread was started by you or explicitly directed at you, and its latest comment is from another reviewer rather than `SELF` or `AUTHOR`. You owe a response.
4. `your-open` — the unresolved thread was started by `SELF`, and no one else has replied. It is still outstanding; surface it but do not redraft it.
5. `peer-comment` — another reviewer raised an unresolved concern that is not directed at you. Surface it and use it to suppress duplicate fresh findings; reply only when you genuinely want to add something.
6. `new-from-others` — any remaining unresolved general comment or thread from the author or reviewers. Surface it for awareness and dedupe fresh findings against it.

For every anchored thread, follow the shared locating rules and record a live verification — `addressed`, `still-open`, or `cant-tell` (missing evidence or genuinely ambiguous). Preserve the historical anchor and verified current location separately, including full ranges and file subjects. Cross-reference fresh findings by path + root cause and the applicable range or relocated location; record the matching finding's location (`path:line`, or `—`). Together these let the report draft informed replies and suppress findings already raised.
