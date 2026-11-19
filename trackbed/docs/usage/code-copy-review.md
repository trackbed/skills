# code:copy-review

Use it to find UI text that repeats what the interface already says: a label that restates its icon, helper text that echoes the label, a placeholder that mirrors it. On the base branch it audits the whole codebase; on any other branch it reviews only the text your changes introduce, including uncommitted ones. It writes a report and edits code only when you add `--apply`. It judges whether text is needed, not grammar, tone, or brand voice; for a wider UX review, use `trackbed:pr:product-review`.

## Before you run it

- **`--apply` edits files in your working tree** and commits nothing. Commit or stash your own work first if you want the two kept apart.
- **For screenshots, start your development server before `--apply --visual`.** The skill uses a local server it can tie to this checkout, or the one you pass with `--url`, and never starts one. Without it the fixes still happen, and the walkthrough shows each change as text.

## Arguments

| Argument | Meaning |
| --- | --- |
| `<scope-path>` | Audit the UI files under this path, whichever branch you are on. Cannot be combined with `--pr`, `--base`, or `--all`. |
| `<finding-ids>` | With `--revert`: the IDs of the changes to undo, such as `COPY-003`, or the prompt copied from a walkthrough page. |

## Options

| Option | Effect |
| --- | --- |
| `--pr` | Review the branch diff and local changes instead of choosing the mode from the current branch. |
| `--base <branch>` | Compare against `<branch>` instead of the detected base branch. Cannot be combined with `--all` or a scope path. |
| `--threshold 0-100` | Report only findings with at least this confidence. The default is 75. |
| `--inline` | Reply with the report in the conversation and write no file. Cannot be combined with `--visual` or `--apply`. |
| `--visual` | Also write `COPY_REVIEW_OVERVIEW.html`, an interactive page of the same report. See [Visual Reports](../visual-reports.md). With `--apply`, the page is a before and after walkthrough of the changes. |
| `--apply` | Fix the Critical and Important findings in the working tree after the review, without committing. Only you can turn it on: the agent never adds it on its own. Cannot be combined with `--inline`. |
| `--url <url>` | Take the walkthrough's screenshots from this running app instead of detecting one, for example an app served from a container. Needs `--apply` and `--visual`. |
| `--revert <finding-ids>` | Undo changes from the apply run recorded in the current report, using its saved source edits. Takes no other option. |
| `--all` | Audit the whole codebase, whichever branch you are on. Cannot be combined with `--pr` or `--base`. |

## Examples

```text
# Audit the codebase on the base branch, or review your changes on any other branch
/trackbed:code:copy-review

# Review only the changes on this branch, compared with develop
/trackbed:code:copy-review --pr --base develop

# Audit one directory and keep only high-confidence findings
/trackbed:code:copy-review src/components --threshold 85

# Audit the whole codebase and reply in the conversation
/trackbed:code:copy-review --all --inline

# Review this branch, fix what it finds, and get a before and after walkthrough
/trackbed:code:copy-review --apply --visual

# The same, with screenshots from an app the skill cannot find by itself
/trackbed:code:copy-review --apply --visual --url http://localhost:3000

# Undo one of those changes
/trackbed:code:copy-review --revert COPY-003
```

## What you get

- A line that names the mode it chose, before it scans.
- `COPY_REVIEW_OVERVIEW.md` in the project root: findings as Critical, Important, and Suggestions, the findings it filtered out as pre-existing, out of scope, or addressed in an earlier report, and the copy that works well. A codebase audit replaces any earlier report, groups findings by category, and summarizes the patterns.
- With `--apply`, uncommitted edits for the Critical and Important findings, and in the report what changed: each finding's status, its text before and after, and the files edited.
  - It removes or shortens exactly the text a finding names. Suggestions stay untouched unless you ask for them.
  - If the run stops during verification or screenshot capture, you can still use `--revert` with the applied finding IDs in the report.
  - A button, link, or field that loses its only visible text keeps its name for screen readers. Tests and stories that found a control by the removed words are updated. A translation key is deleted only if one finding removes all of its uses, so each finding can be reverted independently.
  - Text shared with screens outside the review, or text that may be there for onboarding, legal, or accessibility reasons, is deferred with the decision it needs.
- With `--apply --visual`, `COPY_REVIEW_OVERVIEW.html` as a before and after walkthrough: each change shows the screen before and after the edit, side by side, taken from your running app and cropped to the part that changed.
  - A screen is skipped, with the reason on the page, when it needs a sign-in you have not given, would show personal data or credentials, or cannot be reached in the running app.
  - Mark each change Keep or Revert, then copy the prompt and paste it to the agent: it runs `--revert` on the changes you marked.
  - The copied prompt identifies its apply run. A prompt from an older walkthrough is refused once the Markdown report has been replaced.
  - The screenshots are saved under `.trackbed/copy-review/`, which Git ignores locally.
- A closing summary with the counts per severity and the number of findings filtered out.
- When no UI files are in scope, a short reply and no file.

The report, the page, and the screenshots are working files: do not commit them. `trackbed:workflow:cleanup-artifacts` removes them. Next, fix the findings with `trackbed:pr:resolve-review`, or rerun with `--apply` to fix them here.
