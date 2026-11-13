# code:outside-view

Use it to find quality problems your structured audits do not look for, especially in code written mostly by AI. Several raters explore the code before reading any of the project's instructions and rate it with no rubric; the run then groups their complaints, compares them with the latest ranked weakness audit, and tracks the score across runs. It writes one report and changes no code. For findings ranked by evidence, use `trackbed:code:refactor-opportunities` with `--ranked`.

## Options

| Option | Effect |
| --- | --- |
| `--subagent-model <model>` | Run the in-repo raters on this model: a model class, a model ID, or `inherit`. See [Reviewer Models](../review.md#reviewer-models). |
| `--raters N` | How many in-repo raters to launch, from 3 to 6. The default is 4. |
| `--output <path>` | Write the report to this path instead of `OUTSIDE_VIEW_REPORT.md` in the project root. A path outside the working tree needs your confirmation. With `--visual`, the page goes beside it under the same name. |
| `--visual` | Also write `OUTSIDE_VIEW_REPORT.html`, an interactive page of the same report. See [Visual Reports](../visual-reports.md). |
| `--compare <report-path>` | Compare the complaints with this report instead of `CODEBASE_WEAKNESS_REPORT.md` in the project root. |
| `--cross-model` | Allow one extra rater from a different model family, which sends source files to that provider. It runs only when the host can run that model fully isolated; otherwise the run continues without it and says why. |

## Examples

```text
# Rate the codebase with the default four raters
/trackbed:code:outside-view

# Use six raters and also write the interactive page
/trackbed:code:outside-view --raters 6 --visual

# Compare with a weakness audit stored somewhere else
/trackbed:code:outside-view --compare docs/audits/CODEBASE_WEAKNESS_REPORT.md
```

## What you get

- `OUTSIDE_VIEW_REPORT.md` in the project root, replacing the earlier report but keeping its run history. It holds each rater's score from 1 to 10, the complaints grouped into clusters marked `consensus`, `split`, or `single-voice`, the strengths, and what each rater looked at.
- A comparison with the weakness audit: each cluster is marked as covered by it, filtered out of it, or a blind spot. A blind spot that returns in two or more runs in a row comes with a suggestion for where to encode it, such as a lint rule or an audit signal.
- A reply with the report path, the mean score and its trend, the top three clusters, the number of blind spots, and anything that ran in a reduced way.

If fewer than three raters return a usable answer, the run stops and leaves the earlier report untouched. For the comparison, run `trackbed:code:refactor-opportunities` with `--ranked` first; without a weakness audit the run skips it.
