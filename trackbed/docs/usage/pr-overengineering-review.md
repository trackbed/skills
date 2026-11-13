# pr:overengineering-review

Use it to ask whether your branch, including uncommitted work, does more than the task needs: needless complexity, speculative generality, or handling for edge cases that are very unlikely. One agent looks for candidates, and a second pass tries to justify each one; only candidates with no justification are confirmed. It does not edit code. It measures against what the task requires; to measure against how the codebase already does things, use `trackbed:pr:convention-review`.

## Before you run it

- It needs to know the task: an open Pull Request's title and body, meaningful commit messages, or `--requirements`. With none of these, it stops and asks for `--requirements`.
- A report from an earlier run, `OVERENGINEERING_REVIEW_OVERVIEW.md`, is not committed or staged.

## Options

| Option | Effect |
| --- | --- |
| `--subagent-model <model>` | Run the review agents on this model: a model class, a model ID, or `inherit`. See [Reviewer Models](../review.md#reviewer-models). |
| `--base <branch>` | Compare against `<branch>` instead of the detected base branch. |
| `--inline` | Reply with the report in the conversation and write no file. Cannot be combined with `--visual`. |
| `--visual` | Also write `OVERENGINEERING_REVIEW_OVERVIEW.html`, an interactive page of the same report. See [Visual Reports](../visual-reports.md). |
| `--no-diff-comments` | In a Conductor workspace, do not post the findings as comments on the diff. |
| `--requirements <text>` | What the change must accomplish. It outranks the Pull Request text and commit messages as the statement of the task. It must come last: everything after it is read as the requirements. `trackbed:pr:review-convergence` sets it when it delegates. |

## Examples

```text
# Review the current branch against its Pull Request and commit messages
/trackbed:pr:overengineering-review

# State the task yourself for a branch without a Pull Request
/trackbed:pr:overengineering-review --requirements Add retry with backoff to the upload client

# Compare against develop and reply in the conversation
/trackbed:pr:overengineering-review --base develop --inline
```

## What you get

- `OVERENGINEERING_REVIEW_OVERVIEW.md` in the project root, with three groups: Confirmed Overdoing, Judgment Calls that can be argued either way, and Justified candidates with the reason the complexity stays.
- For each confirmed finding and judgment call: an ID such as `OE-001`, its location, what the complexity guards against, why that is unlikely or unneeded, and a simpler alternative.
- In a Conductor workspace, open findings that have a file and line are also posted as comments on the diff.
- On a later run, earlier findings keep their IDs and their resolution status.

The report is a working file, so do not commit it. Next, run `/trackbed:pr:resolve-review`; judgment calls come up there as accept-or-simplify decisions.
