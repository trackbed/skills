# deps:audit

Use it to find outdated packages, known vulnerabilities, and dependencies that have fallen far behind, and to get an upgrade plan ordered by urgency and risk. It is experimental. By default it only reports: it updates packages only when you pick that choice after the audit. To carry out a major framework or library upgrade, use `trackbed:code:migrate`.

## Before you run it

- The project uses a supported package manager: npm, yarn, pnpm, pip, pipenv, poetry, cargo, Go modules, or .NET.
- Some checks need an extra tool, such as `pip-audit`, `cargo-outdated`, `cargo-audit`, or `govulncheck`. When one is missing, that check is skipped and you get the install command.
- The working tree is clean, if you want the skill to apply updates.

## Options

| Option | Effect |
| --- | --- |
| `--auto` | Audit every detected ecosystem, write `DEPENDENCY_AUDIT.md`, and stop without asking anything. Nothing is updated. |
| `--visual` | Also write `DEPENDENCY_AUDIT.html`, an interactive page of the same report. See [Visual Reports](../visual-reports.md). The choices that write no Markdown report are not offered. |

## Examples

```text
# Audit, then choose how to see the results and whether to apply anything
/trackbed:deps:audit

# Audit every ecosystem and write DEPENDENCY_AUDIT.md, with no questions and no updates
/trackbed:deps:audit --auto

# Do the same and add an interactive page of the report
/trackbed:deps:audit --auto --visual
```

## What you get

- A summary in the conversation: vulnerabilities by severity, outdated packages by major, minor, and patch updates, and an upgrade plan in four phases, from urgent security fixes to major upgrades.
- Without `--auto`, a question about what to do next: show the summary only, write the report, write it and apply the low-risk patch and minor updates, write it and get the `trackbed:siw:init` command that plans the major upgrades as [SIW](../siw.md) issues, or build a visual page with `trackbed:visual:explain`.
- `DEPENDENCY_AUDIT.md` in the project root when you pass `--auto` or pick a choice that writes the report. An existing report is overwritten.
- If you choose to apply updates, the updated packages in your working tree, followed by a `trackbed:verify:run` run. If a check fails, the skill stops and leaves the changes for you to inspect or revert.

When several ecosystems are detected and you did not pass `--auto`, the skill first asks which ones to audit.
