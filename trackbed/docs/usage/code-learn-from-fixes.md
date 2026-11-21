# code:learn-from-fixes

Use it for a retrospective on recent bug fixes. It reads the fixes merged in a window, by default the last week, works out what in the design allowed each one, and answers one question: if the project were started over from scratch, which architecture decisions or feature adjustments would have made these bugs impossible? For each decision it says what it would cost and whether the project can still adopt it. It is read-only: it changes no code and writes no file. To check whether one fix has siblings elsewhere, use `trackbed:debug:find-sibling-bugs`.

## Before you run it

- The run uses the locally cached default branch and reports its tip and date. In a repository with no remotes, it uses local `HEAD`.
- A fix enters the window when it lands on that branch. The run uses commit wording and Pull Request metadata to identify repairs and confirms them from the changes that reached the branch. Fixes folded into feature commits can be missed.
- If more than 40 integrations match the window and path, the run asks whether to narrow the scope or screen them in batches. It asks before reading patches.

## Options

| Option | Effect |
| --- | --- |
| `--since <duration\|date\|ref>` | Where the window starts. Use a duration such as `2 weeks ago`, a calendar date in `YYYY-MM-DD` form, or a tag or commit on the default branch's first-parent history. A tag or commit starts the window immediately after that integration. The default is `1 week ago`. The window ends at the cached tip. |
| `--path <dir>` | Include only defects whose repairs touch the repository-relative directory. Other changes in the same integration can provide context. |

Use positive whole numbers for durations in hours, days, weeks, months, or years.

## Examples

```text
# Learn from the last week of bug fixes
/trackbed:code:learn-from-fixes

# Look back a month
/trackbed:code:learn-from-fixes --since 1 month ago

# Cover everything fixed since the last release
/trackbed:code:learn-from-fixes --since v2.3.0

# Keep to one part of the codebase
/trackbed:code:learn-from-fixes --since 2 weeks ago --path services/billing
```

## What you get

- A `Bug-Fix Retrospective` in the conversation and no file. It opens with a verdict: the one or two decisions that would have removed the most fixes.
- Bug classes: fixes grouped by the property of the design that allowed them, not by file or symptom. A class with one fix is marked `single fix`.
- Each class links to a decision, names the best option of the other kind, and shows how each fix fares under the decision. A class is rated `Obviates` when the decision prevents every fix in it, or `Reduces` when a fix survives.
- Each decision gets one entry ranked by the number of distinct fixes it prevents across its classes. A sample of one or two fixes reports decisions without ranks. The entry names the kind of change, its cost, what the project's records say, and its status today. Statuses are `Fixed in the window`, `Adopt now`, `Adopt for new code`, `Rewrite only`, `Already decided`, and `Previously declined`.
- The fixes with no design lesson, and what was read, set aside, or left unread or partly read.

The report ends with next steps: `trackbed:docs:adr` to record a decision, `trackbed:code:encode-constraint` to make the repository reject a class, or `trackbed:code:refactor-opportunities` to prepare a change. It starts none of them.
