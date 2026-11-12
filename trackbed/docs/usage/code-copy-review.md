# code:copy-review

Use it to find UI text that repeats what the interface already says: a label that restates its icon, helper text that echoes the label, a placeholder that mirrors it. On the base branch it audits the whole codebase; on any other branch it reviews only the text your changes introduce, including uncommitted ones. It writes a report and does not edit code. It judges whether text is needed, not grammar, tone, or brand voice; for a wider UX review, use `trackbed:pr:product-review`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `<scope-path>` | Audit the UI files under this path, whichever branch you are on. Cannot be combined with `--pr`, `--base`, or `--all`. |

## Options

| Option | Effect |
| --- | --- |
| `--pr` | Review the branch diff and local changes instead of choosing the mode from the current branch. |
| `--base <branch>` | Compare against `<branch>` instead of the detected base branch. Cannot be combined with `--all` or a scope path. |
| `--threshold 0-100` | Report only findings with at least this confidence. The default is 75. |
| `--inline` | Reply with the report in the conversation and write no file. Cannot be combined with `--visual`. |
| `--visual` | Also write `COPY_REVIEW_OVERVIEW.html`, an interactive page of the same report. See [Visual Reports](../visual-reports.md). |
| `--all` | Audit the whole codebase, whichever branch you are on. Cannot be combined with `--pr` or `--base`. |

## Examples

```text
# Audit the codebase on the base branch, or review your changes on any other branch
/trackbed:code:copy-review

# Review only the changes on this branch, compared with develop
/trackbed:code:copy-review --pr --base develop

# Audit one directory and keep only high-confidence findings
/trackbed:code:copy-review src/components --threshold 85

# Audit the whole codebase and reply in the conversation
/trackbed:code:copy-review --all --inline
```

## What you get

- A line that names the mode it chose, before it scans.
- `COPY_REVIEW_OVERVIEW.md` in the project root: findings as Critical, Important, and Suggestions, the findings it filtered out as pre-existing, out of scope, or addressed in an earlier report, and the copy that works well. A codebase audit replaces any earlier report, groups findings by category, and summarizes the patterns.
- A closing summary with the counts per severity and the number of findings filtered out.
- When no UI files are in scope, a short reply and no file.

The report is a working file: do not commit it. `trackbed:workflow:cleanup-artifacts` removes it. Next, fix the findings with `trackbed:pr:resolve-review`.
