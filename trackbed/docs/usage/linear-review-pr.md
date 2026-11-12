# linear:review-pr

Use it to check whether an existing Pull Request implements its Linear issue completely and stays within the issue's scope. It lists the issue's requirements, traces each one to the diff, the code, and the tests, and then checks every change in the Pull Request against the issue. It is read-only: it does not edit code, update the issue, or post to GitHub, and it never runs code from the Pull Request. For a full review of someone else's Pull Request, use `trackbed:pr:github-review`, which runs this check for linked issues.

## Before you run it

- `git`, `gh`, and `jq` are installed, and `gh` is authenticated.
- The Linear MCP server is connected. See [MCP servers](../mcp-servers.md#linear).
- You are in a clone of the repository the Pull Request belongs to.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[PR-number\|PR-url]` | The Pull Request to audit: a number such as `482` or `#482`, or its GitHub URL. Without it, the Pull Request of the current branch is used. |
| `[ISSUE-ID]` | The Linear issue, such as `ENG-217`. Without it, the ID is read from the Pull Request's title, description, or branch name. If several are found, you are asked which one applies. |

## Examples

```text
# Audit the current branch's Pull Request against the issue it names
/trackbed:linear:review-pr

# Audit a specific Pull Request
/trackbed:linear:review-pr 482

# Name both the Pull Request and the issue
/trackbed:linear:review-pr https://github.com/acme/app/pull/482 ENG-217
```

## What you get

- A report in the conversation. No file is written.
- A verdict with its rationale: `PASS`, `PASS_WITH_CONCERNS`, `FAIL`, or `BLOCKED`. `BLOCKED` means no sound verdict was possible, for example because the issue has no checkable requirements or a document it depends on could not be read.
- A table of every requirement with its status, from `VERIFIED` to `MISSING` or `CONTRADICTED`, and the code and test evidence behind it.
- Findings by severity, changes the issue does not ask for, requirements that could not be verified, and recommended next actions.
- Test evidence from trusted CI results only. Tests are not run locally, and the report names the gap when no trusted result exists.

After fixes are pushed, run it again with the same Pull Request and issue. The [review guide](../review.md#linked-linear-issues) describes how `trackbed:pr:github-review` uses this check.
