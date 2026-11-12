# code:refactor-opportunities

Use it to find what is worth refactoring in the whole codebase, the current Pull Request, a path, or a feature. It scans for problems such as dead code, duplication, complexity, tight coupling, and implicit state machines, then writes a prioritized report without changing any code. With `--for` it reports only the refactors that would make a planned change easier, and with `--ranked` it ranks the codebase's biggest weaknesses instead. To apply a narrow cleanup, use `trackbed:code:refactor-pass`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `full` | Scan all source directories. This is the default. |
| `pr` | Scan what the current branch changed against its base branch, including uncommitted and untracked files. Only problems the changes caused are reported. |
| `path <file-or-folder>` | Scan only this file, folder, or glob. |
| `feature <name>` | Find the feature's code, tests, routes, schemas, and docs, then scan those. |

## Options

| Option | Effect |
| --- | --- |
| `--subagent-model <model>` | Run the scan agents, and the `--ranked` reviewers, on this model: a model class, a model ID, or `inherit`. See [Reviewer Models](../review.md#reviewer-models). |
| `--for <spec-file \| description>` | Report only the refactors that would make a change you are about to build easier. Name the change as a spec, plan, or issue file or a quoted description; it cannot be combined with `pr` or `--ranked`. |
| `--ranked` | Rank the biggest maintainability, readability, and correctness weaknesses into `CODEBASE_WEAKNESS_REPORT.md` instead. It launches nine research reviewers and a challenge reviewer, does not accept `pr`, and runs only when you ask for it yourself. |
| `--solo` | With `--ranked`, do the audit in the main conversation and launch no reviewers. This costs less and covers less. |
| `--output <path>` | With `--ranked`, write the report to this path instead of `CODEBASE_WEAKNESS_REPORT.md` in the project root. |
| `--max-findings N` | With `--ranked`, cap the ranked findings in the report. The default is 20. |
| `--base <ref>` | With `pr`, compare against `<ref>` instead of the detected base branch. With `--ranked`, read change history from this commit; the scanned files stay the same. |
| `--visual` | Also write `REFACTOR_OPPORTUNITIES_OVERVIEW.html`, an interactive page of the same report; with `--ranked`, `CODEBASE_WEAKNESS_REPORT.html`. See [Visual Reports](../visual-reports.md). |

## Examples

```text
# Scan the whole codebase
/trackbed:code:refactor-opportunities

# Scan only what the current branch changed
/trackbed:code:refactor-opportunities pr

# Find the refactors that would make a planned change easier
/trackbed:code:refactor-opportunities --for docs/specs/csv-invoice-export.md

# Rank the ten biggest weaknesses under one folder
/trackbed:code:refactor-opportunities path src/billing --ranked --max-findings 10
```

## What you get

- `REFACTOR_OPPORTUNITIES_OVERVIEW.md` in the project root, replacing any earlier one. It lists findings `RO-001`, `RO-002`, and so on by severity, each with its location and a suggested fix, groups them into themes, and recommends an order. A theme whose fix would edit more than 500 lines is marked as an automation candidate.
- With `--ranked`, `CODEBASE_WEAKNESS_REPORT.md` instead, with findings `WA-001`, `WA-002`, and so on in rank order.
- A summary with the findings by severity, the top three themes, and the refactor to start with, plus an `Agents launched: N` line.

The run then asks which single item you want to take forward. It offers `trackbed:code:refactor-pass` for a narrow fix, and `trackbed:code:breakdown-findings` or `trackbed:linear:breakdown-findings` to schedule the item.
