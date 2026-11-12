# product:describe-behavior

Use it to document how an existing product, app, CLI, or workflow behaves for its users, feature by feature. It reads the source and tests, writes behavior documents in which every claim names its evidence, checks the claims against the running product, and records the mismatches. It writes only inside the corpus folder: it does not change code or tests, and it does not commit or file issues unless you ask for that separately. For a spec of a feature that is not built yet, use `trackbed:docs:feature-spec`; for a one-off review of a live product, use `trackbed:product:review`.

## Before you run it

- In a Git repository, the product source has no staged, unstaged, or untracked changes. Otherwise the run stops before it collects evidence. The corpus folder itself does not count.
- For a new corpus, the output folder does not exist yet or is empty. If it already holds a corpus, pass `--resume`.
- To have claims checked against the product, it is already running, or you confirm the exact command that starts it. Without that, the runtime checks are recorded as `BLOCKED`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[product or surface]` | The product or user-facing surface to describe. The skill asks when it cannot tell which surface, role, or configuration you mean. |

## Options

| Option | Effect |
| --- | --- |
| `--source <path>` | Read this source repository as evidence. The default is the current repository. |
| `--output <path>` | Write the corpus here instead of `docs/product-behavior/`. A path outside the current repository needs your confirmation. |
| `--resume` | Continue an existing corpus instead of creating one. The folder's index must identify it as a product behavior corpus. |

## Examples

```text
# Start a corpus for one surface in docs/product-behavior/
/trackbed:product:describe-behavior the checkout flow in the web app

# Describe a CLI whose source is in another repository, in a folder you choose
/trackbed:product:describe-behavior the admin CLI --source ../admin-cli --output docs/admin-cli-behavior

# Continue the corpus you started earlier
/trackbed:product:describe-behavior --resume
```

## What you get

- A corpus, by default under `docs/product-behavior/`: `README.md` with the scope and a coverage table, `glossary.md`, one document per feature under `behaviors/`, a matching checklist under `verification/`, and `triage.md` for unresolved mismatches.
- Every claim has a stable ID such as `AUTH-SIGNIN-01` and an evidence label: `SOURCE`, `TEST`, `OBSERVED`, or `UNKNOWN`. Each check ends as `PASS`, `FAIL`, `BLOCKED`, or `NOT_RUN`.
- A closing report with the corpus location and source revision, counts by coverage and verification status, the open `UNKNOWN`, `FAIL`, and `BLOCKED` claims, and the triage entries by classification and severity.

A mismatch goes to triage and is not treated as a confirmed bug. The skill asks before any check that would delete data, send notifications, or write to shared data.
