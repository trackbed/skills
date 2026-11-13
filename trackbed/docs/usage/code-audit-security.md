# code:audit-security

Use it to get an evidence-backed picture of a whole repository's security posture before you start fixing anything. It inventories the attack surface across code, identity, data, integrations, dependencies, CI/CD, infrastructure, secrets, and agent or LLM tooling, maps the trust boundaries, and ranks what it finds. It inspects files statically: it runs no project code, probes no live service, reads no secret values, and applies no fix. To harden code as you write it, use `trackbed:code:harden-security`; for a dependency-only audit, use `trackbed:deps:audit`.

## Before you run it

- Run it only in a repository you trust. Audit an untrusted repository from an isolated session that has not loaded that repository's instructions.

## Options

| Option | Effect |
| --- | --- |
| `--output <repo-relative-path>` | Write the report to this Markdown file inside the repository. Its folder must already exist. An existing file is replaced only when it is an earlier audit report and you confirm, and you are asked before a file that Git does not ignore is written. |
| `--visual` | Also write an interactive page of the same report beside it, at the `--output` path with `.html` in place of `.md`. Needs `--output` with a path ending in `.md`. See [Visual Reports](../visual-reports.md). |

## Examples

```text
# Audit the repository and read the report in the conversation
/trackbed:code:audit-security

# Write the report to a file in the repository
/trackbed:code:audit-security --output security-audit.md

# Write the report and an interactive page beside it
/trackbed:code:audit-security --output security-audit.md --visual
```

## What you get

- A `Security Posture Audit`: a summary, the scope and its limits, a coverage table with a status for every surface, the attack surface inventory, trust boundaries and data flows, ranked findings with details, coverage gaps, candidates it ruled out, and where to take each finding next.
- Each finding carries a severity, a confidence, whether it is `VERIFIED` or `SUSPECTED`, its location, an owner, a remediation route, and the check that would show it fixed.
- Without `--output` the report is the reply and nothing is written. With it, the report file is the only file written, plus the page with `--visual`.
- No secret values in the report. It is a review of the repository's state, not a penetration test or a compliance assessment.
