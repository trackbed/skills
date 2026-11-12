# linear:breakdown-findings

Use it after a review, audit, scan, or QA run to turn the findings into Linear issues that each fit one Pull Request. It checks the findings against the repository, groups them into themes, orders them by dependency, and hands each theme to `trackbed:linear:issue-define`, which creates the issue only after you approve its full draft. It writes to Linear and never edits repository files. For local `PR_PLAN_*.md` files instead, use `trackbed:code:breakdown-findings`.

## Before you run it

- The Linear MCP server is connected, except for `--dry-run`. See [MCP servers](../mcp-servers.md#linear).
- The findings carry evidence. A bare list of ideas is rejected.
- Before it writes to Linear, the run may ask you to save pasted findings to a file, so that a resume can repeat them exactly.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[source ...]` | Report files, or pasted findings, but not both. Without any, the known reports in the repository root are used, such as `REVIEW_OVERVIEW.md` and `QA_REPORT.md`, plus any you select from other worktrees. If there are none, a review in the current conversation is used. |
| `--` | Ends the options. Required when pasted findings start with a hyphen. |

## Options

| Option | Effect |
| --- | --- |
| `--auto` | Continue with the proposed grouping without asking you to confirm it. You still approve every issue and the dependency links. |
| `--ask` | Ask every relevant interview question for each issue, instead of only clarifying what is missing. |
| `--dry-run` | Show the planned issues, then stop. Nothing is created in Linear. Cannot be combined with `--resume`. |
| `--resume <partial-report-path>` | Continue a stopped run from the partial report you saved to this file. Repeat the original sources and the same `--ask`, team, project, and label options. |
| `--team <team>` | Create the issues in this Linear team. Without it, the only team is used, or you are asked. |
| `--project <project>` | Add the issues to this existing project. A missing project is not created. |
| `--label <label>` | Label every issue with this existing label. Repeat the flag for more labels. |

## Examples

```text
# Break down the review and audit reports found in the repository root
/trackbed:linear:breakdown-findings

# Preview the planned issues for one report without writing to Linear
/trackbed:linear:breakdown-findings --dry-run REVIEW_OVERVIEW.md

# Create issues in one team and project, with the full set of questions per issue
/trackbed:linear:breakdown-findings --ask --team ENG --project "Checkout" QA_REPORT.md

# Continue a stopped run from the partial report you saved
/trackbed:linear:breakdown-findings --resume partial-report.txt --team ENG -- QA_REPORT.md
```

## What you get

- The proposed grouping first: each theme with its size, impact, and dependencies, and the findings left out with the reason.
- One Linear issue per theme you approve. When you pick an existing issue as a match, the theme is recorded against it and no copy is created.
- After one more approval, blocked-by relations between the issues, where the Linear tools support them.
- A closing report: each theme with its issue, which issues can run in parallel, and the first ones that are ready to start.
- If the run stops partway, a `PARTIAL LINEAR FINDINGS BATCH` block and the exact command to resume. Save the block to a file yourself; the skill writes no files.
