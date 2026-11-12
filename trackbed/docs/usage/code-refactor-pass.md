# code:refactor-pass

Use it once a feature or fix works, to simplify the recent changes before you merge. It edits files: it removes dead code, straightens logic, and cleans up AI-generated slop such as obvious comments and needless defensive checks, without changing behavior, and it commits each simplification on its own once the project's checks pass. With `--rewrite` it instead scraps a working but hacky implementation and writes it again properly. To scan a whole codebase without changing it, use `trackbed:code:refactor-opportunities`.

## Before you run it

- The project's build, lint, and tests pass on the unchanged code. The pass stops when they fail or cannot run.
- For `--rewrite`, the conversation already holds a working implementation written in this session.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[scope ...]` | One or more files or directories to clean up. Without any, the scope is everything the current branch changed against its base branch, including uncommitted and untracked files. |

## Options

| Option | Effect |
| --- | --- |
| `--rewrite` | Scrap the working implementation from this conversation and write it again from what was learned, after saving the earlier version on a throwaway branch or in a labeled stash. Cannot be combined with a scope. |

## Examples

```text
# Simplify everything the current branch changed
/trackbed:code:refactor-pass

# Simplify only these paths
/trackbed:code:refactor-pass src/billing/export.ts src/billing/format

# Redo the hacky solution from this conversation properly
/trackbed:code:refactor-pass --rewrite
```

## What you get

- One commit per simplification, each made only after `trackbed:verify:run` passes with the tests unchanged. A change that fails a test, or leaves the code no clearer, is reverted.
- Before the first one, a checkpoint commit that holds any uncommitted changes in the scope exactly as they were.
- A `SIMPLICITY CHECK` line for each simplification, and a `NOTICED BUT NOT TOUCHING` line for anything outside the scope that it left alone. Review reports and plan files, such as `REVIEW_OVERVIEW.md` and `PR_PLAN_*.md`, are never touched.
- When nothing is worth changing, a message that the code is already clean, and no commits.
- With `--rewrite`, the command that restores the earlier version, and a new implementation that passes the same checks with the tests unchanged. If it fails them or is no clearer, the earlier version is restored.
