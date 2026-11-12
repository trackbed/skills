# pr:code-review

Use it before you open a Pull Request, or after a round of fixes, to get findings on the changes in your branch. Specialized review agents cover the aspects that apply, and their findings are filtered down to the ones your changes caused. It does not edit code unless you pass `--loop`. For UX, visual, and accessibility review, use `trackbed:pr:product-review`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[aspects]` | Review only these aspects: `comments`, `tests`, `errors`, `types`, `architecture`, `code`, `slop`, `security`, `performance`, `removal`, `lean`, `refactor`, `simplify`, or `all`. Without any, every aspect that applies to the changed files runs. |
| `[parallel]` | Deprecated spelling of `--parallel`. |

## Options

| Option | Effect |
| --- | --- |
| `--base <branch>` | Compare against `<branch>` instead of the detected base branch. |
| `--emphasize <dim>...` | Give these aspects more weight: a matching suggestion can be raised to Important. Takes the same aspect names, except `all`. |
| `--no-cleanup` | Skip the advisory cleanup aspects `lean`, `refactor`, and `simplify`. Useful for a second pass over a small fix. |
| `--previous-review <path>` | Read an earlier review from this file instead of the `REVIEW_OVERVIEW.md` in the repository. |
| `--inline` | Reply with the findings in the conversation and write no file. Cannot be combined with `--visual`. |
| `--visual` | Also write `REVIEW_OVERVIEW.html`, an interactive page of the same findings. See [Visual Reports](../visual-reports.md). |
| `--loop` | After the review, apply fixes and review again until the findings are resolved. This edits files. |
| `--team` | Run the reviewers as a team that checks each other's findings. In Claude Code this needs Agent Teams enabled. |
| `--parallel` | Launch the reviewers at the same time instead of one after another. |
| `--subagent-model <model>` | Run the review agents on this model: a model class, a model ID, or `inherit`. See [Reviewer Models](../review.md#reviewer-models). |
| `--no-diff-comments` | In a Conductor workspace, do not post the findings as comments on the diff. |

## Examples

```text
# Review everything that changed on the current branch
/trackbed:pr:code-review

# Review only security and tests, against the develop branch
/trackbed:pr:code-review security tests --base develop

# Review, fix what was found, and review again until it is clean
/trackbed:pr:code-review --loop

# Re-check a small fix without the cleanup aspects, and reply in the conversation
/trackbed:pr:code-review --no-cleanup --inline
```

## What you get

- `REVIEW_OVERVIEW.md` in the repository root: Critical issues, Important issues, and Suggestions, each finding with an ID, a location, a confidence score, and its evidence, followed by a recommended action. With `--inline` the same content arrives as a reply and no file is written.
- A closing line with the number of review agents that ran.
- With `--loop`, the fixes in your working tree.

Next, fix the findings with `/trackbed:pr:resolve-review`. The [review guide](../review.md#code-review) explains how findings are ordered and how to steer a review with your repository's own standards.
