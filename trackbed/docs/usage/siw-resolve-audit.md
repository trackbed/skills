# siw:resolve-audit

Use it after `trackbed:siw:spec-audit` when findings need a decision rather than a mechanical fix. It goes through the audit report one finding at a time: it checks whether the finding holds, summarizes it, offers two or three options with a recommendation, and turns the option you pick into a local SIW issue. It creates planning issues under `siw/` and annotates the report; it implements nothing. For fixes that need no decision, use `trackbed:siw:spec-audit` with `--apply`.

## Before you run it

- An audit report exists. Run `trackbed:siw:spec-audit` first.
- The SIW workflow is initialized, so `siw/OPEN_ISSUES_OVERVIEW.md` exists. No issue is created without it.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[audit-report-path]` | The report to resolve. Without it, `siw/AUDIT_SPEC_REPORT.md` is used, then `AUDIT_SPEC_REPORT.md` in the project root. |
| `[finding-id(s)]` | Resolve only these findings, such as `SPEC-003 PROD-001`. Without any, every open finding is handled, most severe first. Naming a contested finding reopens it. |

## Options

| Option | Effect |
| --- | --- |
| `--auto` | Pick the strongest option for each finding and create its issue without asking. A finding it can disprove is marked contested without asking. Critical findings it doubts, and findings that hinge on a fact no file records, are left for you and listed in the summary. |

## Examples

```text
# Go through every open finding in the audit report
/trackbed:siw:resolve-audit

# Resolve two findings from a specific report
/trackbed:siw:resolve-audit siw/AUDIT_SPEC_REPORT.md SPEC-003 PROD-001

# Let the agent choose the resolution for each finding
/trackbed:siw:resolve-audit --auto
```

## What you get

- For each finding you resolve, `siw/issues/ISSUE-G-<NNN>-resolve-<finding-id>-<slug>.md`, a row in `siw/OPEN_ISSUES_OVERVIEW.md`, and a line in `siw/LOG.md`. The issue's priority follows the audit severity: Critical to High, Major to Medium, Minor to Low.
- The audit report annotated: `Existing issue: G-<NNN>` on resolved findings, and `**Status:** [Contested]` with the evidence on findings you agreed were wrong. A contested finding gets no issue.
- A final summary: findings that wait on your decision first, then the issues created and the findings that were contested or skipped.

Findings that the audit already fixed with `--apply`, or that already have an issue, are skipped, so you can run it again safely. Next, move the issue set to Linear with `trackbed:siw:transfer-to-linear`. The [SIW guide](../siw.md#specification-audit) describes how findings are checked.
