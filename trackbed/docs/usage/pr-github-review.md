# pr:github-review

Review someone else's Pull Request and get a local report with a recommended verdict and draft comments. You choose whether to create a private draft on GitHub and whether to submit it. For your own branch, use `trackbed:pr:code-review`. To answer reviewers on your own Pull Request, use `trackbed:pr:github-review-reply`.

When the review produces inline comments, checking that the author can act on them adds about 30–50 minutes. Add `--no-clarity-check` to skip that step.

## Before you run it

- `gh` and `jq` are installed, and `gh` is authenticated.
- You run it from a clone of the Pull Request's repository.
- Linear access is needed only when the Pull Request links Linear issues. Without it, the report says what was not covered.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[pr-number\|pr-url]` | The Pull Request to review. Without it, the current branch's Pull Request is used when it requests your review; otherwise you choose from the Pull Requests waiting for your review. |

## Options

| Option | Effect |
| --- | --- |
| `--subagent-model <model>` | Run the review agents on this model: a model class, a model ID, or `inherit`. See [Reviewer Models](../review.md#reviewer-models). |
| `--stack` | Review the whole stack the Pull Request belongs to: measure each layer, check what crosses layers, and plan the per-layer reviews. Combines only with `--inline` and `--visual`. |
| `--draft-review` | Create the pending review with the draft inline comments without asking first. It stays unsubmitted. |
| `--no-clarity-check` | Skip the check in which fresh readers test each draft comment for clarity. That check takes about 30–50 minutes. |
| `--base <ref>` | Compare against `<ref>` instead of the Pull Request's target branch. Use it when the detected base is wrong. |
| `--categories a11y,ux,product,visual` | Limit the UI review to these categories, given as a comma-separated list. |
| `--code-only` | Skip the UI review even when UI files changed. |
| `--sequential` | Launch the reviewers one after another instead of at the same time. |
| `--fresh` | Ignore the existing review conversation and review the whole Pull Request as a first pass. |
| `--full` | Review the whole diff even when you reviewed this Pull Request before. Without it, a re-review covers only what changed since your last review. |
| `--include-bots` | Include comments from bots and apps when reading the conversation. By default only people's comments count. |
| `--all-threads` | Also include resolved threads and hidden comments in the conversation. |
| `--inline` | Reply with the report in the conversation and write no file. Cannot be combined with `--visual`. |
| `--visual` | Also write `GITHUB_PR_REVIEW_OVERVIEW.html`, or `GITHUB_STACK_REVIEW_OVERVIEW.html` with `--stack`, an interactive page of the same report. See [Visual Reports](../visual-reports.md). |
| `--keep-worktree` | Keep the temporary worktree on disk and report its path. |

## Examples

```text
# Review a Pull Request by number
/trackbed:pr:github-review 482

# Review it and create the pending review with the inline comments
/trackbed:pr:github-review 482 --draft-review

# Map the whole stack before reviewing its layers
/trackbed:pr:github-review 482 --stack

# A shorter pass: code only, no clarity check, report in the conversation
/trackbed:pr:github-review 482 --code-only --no-clarity-check --inline
```

## What you get

- `GITHUB_PR_REVIEW_OVERVIEW.md` in the project root: a recommended verdict, findings by severity, the state of the open conversation, coverage of linked Linear issues, draft comments, and a prepared review body. With `--stack`, `GITHUB_STACK_REVIEW_OVERVIEW.md` instead, and no GitHub write at all.
- An offer to create one private pending review with the eligible inline comments. Before accepting, you can ask for changes, such as “Drop the comment about naming and show me the revised draft.” The skill updates the local report and asks again. Only you can see the pending review until you submit it. Its payload is kept under `.context/github-review-drafts/`, which must be ignored by Git.
- A submitted review only after you send a separate message such as `Post the prepared review to PR 482 as request changes`. It never replies to or resolves threads; it hands you the prepared text.
- Your checked-out branch left as it is. The temporary worktree is removed unless you pass `--keep-worktree`.

**To resume an interrupted single-PR review**, run the command again from the same clone with the same review options. For PR 482 with default settings, use `/trackbed:pr:github-review 482`. Leave off `--draft-review` to keep the result local. If a GitHub write had an uncertain outcome, inspect the PR first.

A matching run reuses saved work within 24 hours of its start and refreshes the GitHub conversation when in scope. If review inputs changed or resume was off, the review starts over. See [Resuming Interrupted Reviews and Audits](../review.md#resuming-interrupted-reviews-and-audits).

The [review guide](../review.md#reviewing-someone-elses-pull-request) covers re-reviews, the clarity check, and what the skill writes to GitHub.
