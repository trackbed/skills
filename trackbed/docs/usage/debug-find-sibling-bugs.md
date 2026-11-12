# debug:find-sibling-bugs

Use it after your branch contains a bug fix, to check whether the same flaw exists elsewhere. It works out what the branch fixed and why the old code failed, then searches the rest of the repository for places where the same cause can still produce the problem. It is read-only: it changes no code and writes no file. To diagnose a bug that is not fixed yet, use `trackbed:debug:investigate`.

## Before you run it

- The current branch differs from its base, and the difference fixes a defect. Uncommitted and untracked changes count.
- If the branch does not fix a bug, the run stops and says so.

## Options

| Option | Effect |
| --- | --- |
| `--base <branch>` | Compare against `<branch>` instead of the detected base branch. |
| `--intent <text>` | State the problem the branch fixes. Everything after the flag is read as that statement, so put it last. Useful when the branch has no Pull Request or its commits do not explain the problem. |

## Examples

```text
# Search for siblings of the bug the current branch fixes
/trackbed:debug:find-sibling-bugs

# Compare against develop instead of the detected base branch
/trackbed:debug:find-sibling-bugs --base develop

# Say what the branch fixes when the commits do not
/trackbed:debug:find-sibling-bugs --intent Saving a profile twice creates duplicate rows
```

## What you get

- A report in the conversation. For each fix on the branch it states the problem, the pattern that caused it, and the rule the fix now enforces.
- Each sibling marked Confirmed or Probable, with its file and line, the likely impact, the evidence, and the smallest check that would confirm it.
- What was searched: the areas, the kinds of search, how many candidates were examined and cleared, and any limits.
- `No validated sibling bugs found.` when no candidate holds up. That describes the search, not the whole repository.

When the same fix is needed in three or more places, the report suggests `trackbed:code:refactor-opportunities`. When a type, lint rule, or test could reject the pattern, it suggests `trackbed:code:encode-constraint`.
