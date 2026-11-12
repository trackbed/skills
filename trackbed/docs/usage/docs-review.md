# docs:review

Use it to get a review of one Markdown document outside a tracked SIW workflow: requirements, an implementation plan, a strategy draft, a README or guide, a proposal, or a decision draft. It works out what kind of document it is, has a fresh reader restate it, applies the review lenses that fit, and returns a verdict with findings ordered by severity. It never edits the document and does not read source code. For documents under `siw/`, use `trackbed:siw:spec-audit`.

## Before you run it

- The document is a Markdown file (`.md`, `.markdown`, `.mdown`, or `.mkd`). Convert other formats with `trackbed:docs:to-markdown` first.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[markdown-path]` | The document to review. One document per run; without a path the skill asks for one. |

## Options

| Option | Effect |
| --- | --- |
| `--trade-offs` | Also look for trade-offs the document accepts as unavoidable that a known design pattern could remove. Applies to implementation plans, proposals, and decision drafts. The results are advisory and appear in their own `False Compromises` section. |
| `--inline` | Reply with the report in the conversation and write no file. This is the default. |
| `--file` | Write the report to `DOC_REVIEW.md` in the current directory or repository root, replacing an earlier one, and reply with a short summary. |
| `--output <path>` | Write the report to `<path>` instead of `DOC_REVIEW.md`. The path cannot be the reviewed document. |
| `--visual` | Also write `DOC_REVIEW.html`, an interactive page of the same report. Needs `--file` or `--output <path>`; with `--output`, the page takes that path with `.html` in place of `.md`. See [Visual Reports](../visual-reports.md). |

## Examples

```text
# Review a proposal and get the report as a reply
/trackbed:docs:review docs/proposal.md

# Write the report to DOC_REVIEW.md with an interactive page beside it
/trackbed:docs:review README.md --file --visual

# Write the report to a file you name
/trackbed:docs:review docs/strategy.md --output STRATEGY_REVIEW.md

# Also check a proposal for trade-offs it could avoid
/trackbed:docs:review docs/proposal.md --trade-offs
```

## What you get

- A report that opens with a verdict: whether you can use the document as it stands, the problems that matter most, and what you still have to decide. A sound document gets `No findings.`
- Findings `DOC-001`, `DOC-002`, and so on, rated Critical, Major, Minor, or Nit. Each has its location, the lens that found it, the problem, why it matters, and a concrete fix.
- A `Comprehension Read` section with a first reader's restatement of the document, to compare with what you meant, and a `Coverage` section with the document type, the lenses reviewed, and any open unknowns.
- With `--file` or `--output <path>`, the report file and a reply with its path, the verdict, and finding counts by severity. `DOC_REVIEW.md` is a working file, not something to commit; `trackbed:workflow:cleanup-artifacts` removes it.
