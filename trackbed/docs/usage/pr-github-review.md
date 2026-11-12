# pr:github-review

Use it when someone asked you to review their Pull Request on GitHub. It fetches the Pull Request into a temporary worktree, runs the code review and, when UI files changed, the UI review, checks linked Linear issues, reads the existing conversation, and writes a report with a recommended verdict and draft comments. It writes nothing to GitHub unless you ask. For your own branch, use `trackbed:pr:code-review`; to answer reviewers on your own Pull Request, use `trackbed:pr:github-review-reply`.

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
- An offer to create one unsubmitted pending review that holds the draft inline comments GitHub can attach to a changed line. Only you can see it until you submit it. Its payload is kept under `.context/github-review-drafts/`, which must be ignored by Git.
- A submitted review only after you send a separate message such as `Post the prepared review to PR 482 as request changes`. It never replies to or resolves threads; it hands you the prepared text.
- Your checked-out branch left as it is. The temporary worktree is removed unless you pass `--keep-worktree`.

The [review guide](../review.md#reviewing-someone-elses-pull-request) covers re-reviews, the clarity check, and what the skill writes to GitHub.
