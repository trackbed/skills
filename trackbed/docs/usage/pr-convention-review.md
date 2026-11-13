# pr:convention-review

Use it to check whether your branch and uncommitted work depart from how the codebase already does things. It compares the changes with the repository's documented rules and with the practice in comparable files, and it also flags code that is more defensive or more layered than comparable code. Every finding cites the rule or the example files it is measured against. It never edits source. To judge complexity against what the task needs instead, use `trackbed:pr:overengineering-review`.

## Options

| Option | Effect |
| --- | --- |
| `--subagent-model <model>` | Run the review agents on this model: a model class, a model ID, or `inherit`. See [Reviewer Models](../review.md#reviewer-models). |
| `--base <branch>` | Compare against `<branch>` instead of the detected base branch. |
| `--threshold 0-100` | Drop findings whose confidence score is below this number. The default is 80. |
| `--baseline <path>` | Save the practice found in comparable files to this file, and reuse it on later runs while those files are unchanged. The file's folder must exist and be ignored by Git. `trackbed:pr:review-convergence` sets it so its later review rounds reuse the result. |
| `--inline` | Reply with the report in the conversation and write no file. Cannot be combined with `--visual`. |
| `--visual` | Also write `CONVENTION_REVIEW_OVERVIEW.html`, an interactive page of the same report. See [Visual Reports](../visual-reports.md). |
| `--no-diff-comments` | In a Conductor workspace, do not post the findings as comments on the diff. |

## Examples

```text
# Review everything that changed on the current branch
/trackbed:pr:convention-review

# Compare against develop and also report lower-confidence findings
/trackbed:pr:convention-review --base develop --threshold 60

# Reply in the conversation instead of writing a file
/trackbed:pr:convention-review --inline
```

## What you get

- `CONVENTION_REVIEW_OVERVIEW.md` in the project root. Findings are grouped as critical, important, and suggestions, each with its location, confidence, the rule or example files it departs from, and a minimal fix.
- The same report lists areas where the codebase itself has no single convention, older drift it noticed but left alone, findings it filtered out, and what the change gets right.
- A closing summary with the counts. In a Conductor workspace, findings that have a file and line are also posted as comments on the diff: critical and important ones always, and suggestions when fewer than 10 such findings exist.
- When a report from an earlier run exists, findings you already addressed are not raised again, and the others are carried forward while they still apply.

The report is a working file, so do not commit it. Next, fix the findings with `/trackbed:pr:resolve-review`. The [review guide](../review.md#repository-standards-and-review-policy) explains how to steer the review with your repository's own standards.
