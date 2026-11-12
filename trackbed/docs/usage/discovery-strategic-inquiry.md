# discovery:strategic-inquiry

Use it to surface blind spots. It reads what the project says about itself, compares that with the code, its history, and what is missing, and produces a ranked list of strategic questions, each with a brief on how to investigate it. It writes one report file and changes nothing else: it does not fix, file, or implement anything. It is not a defect or quality audit; for those, use `trackbed:code:refactor-opportunities` with `--ranked`, `trackbed:pr:code-review`, or `trackbed:product:review`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[focus]` | A product area (`onboarding`), a path (`src/auth`), or a theme (`pricing`). Without it, the whole repository and product are in scope. |

## Options

| Option | Effect |
| --- | --- |
| `--max-questions N` | Limit the report to `N` ranked questions. The default is 10 and the most is 15. |
| `--output <path>` | Write the report to this path instead of `STRATEGIC_INQUIRY.md` in the repository root. A path outside the working tree needs your confirmation. |
| `--inline` | Reply with the report in the conversation and write no file. Cannot be combined with `--visual`. |
| `--visual` | Also write `STRATEGIC_INQUIRY.html`, an interactive page of the same report. With `--output`, the page takes that path with `.html` in place of `.md`. See [Visual Reports](../visual-reports.md). |

## Examples

```text
# Question the whole repository and product
/trackbed:discovery:strategic-inquiry

# Focus on one area and keep the list short
/trackbed:discovery:strategic-inquiry onboarding --max-questions 5

# Focus on a path and get the interactive page as well
/trackbed:discovery:strategic-inquiry src/auth --visual
```

## What you get

- `STRATEGIC_INQUIRY.md` in the repository root. It replaces an earlier report at the same path.
- Ranked questions numbered from `SQ-001`. Each has why it matters, the evidence that prompted it, the uncomfortable answer, how to investigate it with a rough effort, what would settle it, where the answer lives (`repo`, `production`, `users/market`, or `team decision`), and a prompt you can paste to run the investigation.
- A registry of the assumptions the product rests on, and the candidate questions that were dropped, each with a reason.
- A closing summary: the report path, the top three questions, the cheapest high-leverage investigation to start with, the mix of answer locations, and any audit-type items set aside with the review skill they belong to.

The report asks questions and does not answer them. It is a working file, not meant to be committed. Pursue one question in depth with `trackbed:discovery:interview`, and record a settled decision with `trackbed:docs:adr`.
