# siw:spec-audit

Use it before you break a spec into issues, to find out whether someone could implement it correctly without guessing. It audits the spec for coherence, completeness, clarity, scope, actionability, testability, documented rationale, and technical design, has a cold reader restate it, and checks what it says about existing code against the repository. It writes a report and edits the spec only when you apply fixes. For findings that need a decision, continue with `trackbed:siw:resolve-audit`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[spec-file-path(s)]` | Spec files or a folder to audit. |
| `siw` | Audit the specs found under `siw/`. This also happens when you pass nothing. |
| `[audit-report-path]` | With `--apply`, an existing spec audit report whose findings to fix without auditing again. |

## Options

| Option | Effect |
| --- | --- |
| `--product` | Also judge whether the spec proposes the right product for the right users. Its `PROD-NNN` findings are never fixed automatically. |
| `--auto` | Skip the prompts: replace an earlier report and, in an SIW workflow, create issues for Critical and Major findings. With `--apply`, fix without asking. |
| `--apply` | After the audit, fix the findings that can be corrected safely from the spec itself and mark them in the report. No issues are created. With a report path, skip the audit and fix that report. |
| `--dry-run` | With `--apply` and a report path, show the proposed fixes without changing files. |
| `--threshold 60-100` | With `--apply`, the fix confidence a finding needs before it is fixed. The default is 80. |
| `--allow-dirty` | With `--apply`, a report path, and `--auto`, edit spec files that have uncommitted changes. Without it, that run stops. |
| `--model opus\|sonnet\|haiku` | Run the audit agents on this model. The default is `opus`. Claude Code only. |
| `--inline` | Reply with the report in the conversation and write no file. It creates no issues and cannot be combined with `--apply` or `--visual`. |
| `--visual` | Also write `AUDIT_SPEC_REPORT.html`, an interactive page of the same report. See [Visual Reports](../visual-reports.md). |
| `--team` | Run the auditors as a team that checks each other's findings and also checks the spec for new code patterns introduced without a reason. Needs Agent Teams in Claude Code or `multi_agent` in Codex. |

## Examples

```text
# Audit the specs under siw/ and write the report
/trackbed:siw:spec-audit

# Audit, then fix the mechanical findings in the spec
/trackbed:siw:spec-audit --apply

# Also judge whether the spec proposes the right product
/trackbed:siw:spec-audit docs/spec.md --product

# Preview the fixes for an existing report without changing files
/trackbed:siw:spec-audit --apply siw/AUDIT_SPEC_REPORT.md --dry-run
```

## What you get

- `siw/AUDIT_SPEC_REPORT.md`, or `AUDIT_SPEC_REPORT.md` in the project root when there is no `siw/` folder: a score per dimension, an overall assessment, and `SPEC-NNN` findings rated Critical, Major, or Minor. Finding IDs stay the same across runs.
- If a report already exists, a choice to replace it, append to it, or abort.
- Unless a flag decides it, a choice to apply the safe fixes, create local SIW issues, or keep the report only. Issues are offered only in an initialized SIW workflow.
- When fixes are applied, the edits in the spec files and `[Auto-fixed]` on each fixed finding in the report.
- A closing summary with the scores, the finding counts, and the next steps.

The [SIW guide](../siw.md#specification-audit) explains the passes and how to resolve what remains.
