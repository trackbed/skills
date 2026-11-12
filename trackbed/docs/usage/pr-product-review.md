# pr:product-review

Use it to review what your changes mean for users: product value, flows, and copy, plus usability, visual consistency, and accessibility when UI files changed. Specialist agents each cover one category, and their findings are filtered down to the ones your changes caused, including uncommitted work. It does not edit code. For code-quality findings, use `trackbed:pr:code-review`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[app-url\|auto]` | The URL of the running app, or `auto` to detect your local dev server. The reviewers then also inspect the app in a browser. This needs a browser MCP server such as [Claude in Chrome](../mcp-servers.md#claude-in-chrome); without one the review reads the code only. |

## Options

| Option | Effect |
| --- | --- |
| `--subagent-model <model>` | Run the review agents on this model: a model class, a model ID, or `inherit`. See [Reviewer Models](../review.md#reviewer-models). |
| `--categories a11y,ux,product,visual` | Run only the listed categories, or `all`. Without it, the product reviewer always runs, UX and visual run when UI files changed, and accessibility runs only when the project shows accessibility requirements. |
| `--threshold 0-100` | Report only findings with at least this confidence. The defaults are 90 for accessibility and 70 for the other categories. |
| `--base <branch>` | Compare against `<branch>` instead of the detected base branch. |
| `--parallel` | Launch the reviewers at the same time instead of one after another. |
| `--team` | Run the reviewers as a team that checks each other's findings. In Claude Code this needs Agent Teams enabled. |
| `--inline` | Reply with the report in the conversation and write no file. Cannot be combined with `--visual`. |
| `--visual` | Also write `PRODUCT_REVIEW_OVERVIEW.html`, an interactive page of the same report. See [Visual Reports](../visual-reports.md). |
| `--no-diff-comments` | In a Conductor workspace, do not post the findings as comments on the diff. |

## Examples

```text
# Review the product and UI changes on the current branch
/trackbed:pr:product-review

# Also inspect the running app in a browser, detecting the dev server
/trackbed:pr:product-review auto

# Run only the accessibility and UX reviewers, against the develop branch
/trackbed:pr:product-review --categories a11y,ux --base develop

# Reply in the conversation and report only high-confidence findings
/trackbed:pr:product-review --inline --threshold 85
```

## What you get

- `PRODUCT_REVIEW_OVERVIEW.md` in the project root: findings numbered from `PROD-001` and grouped as critical, important, and suggestions, each with its file, confidence, user impact, and a recommended fix. It also lists what is done well and, when the product reviewer ran, open questions for the product owner. With `--inline` the same report arrives as a reply and no file is written.
- In a Conductor workspace, findings that point at a file and line are also posted as comments on the diff: critical and important ones always, and suggestions when fewer than 10 such findings exist.
- The report is a working file. Do not commit it; `trackbed:workflow:cleanup-artifacts` removes it.

Next, fix the findings with `trackbed:pr:resolve-review`.
