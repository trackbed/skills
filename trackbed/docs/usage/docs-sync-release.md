# docs:sync-release

Use it around a release to find documentation that no longer matches the code. It compares a change range you name, or your current checkout, with the installation, usage, architecture, testing, and public interface docs those changes affect, and returns a drift report with evidence. It edits nothing unless you pass `--apply`, and it never stages, commits, pushes, or touches changelogs, versions, tags, or Pull Requests. To review one document for quality, use `trackbed:docs:review`.

## Before you run it

- Name a scope: a range, `--base`, or `--current`. With none, the skill asks instead of guessing.
- The revisions you name exist in your local repository. The skill does not fetch.

## Arguments

| Argument         | Meaning                                                   |
| ---------------- | --------------------------------------------------------- |
| `<base>...<ref>` | Compare the merge base of the two revisions with `<ref>`. |

## Options

| Option | Effect |
| --- | --- |
| `--base <rev>` | Compare this base revision with `--ref`. An alternative to the `<base>...<ref>` form. |
| `--ref <rev>` | The revision to compare the base with. Without it, the comparison ends at `HEAD` and the printed scope says so. |
| `--current` | Inspect the current checkout: the commits since your branch left the [base branch](../shipping.md#base-branch), plus staged, unstaged, and untracked changes. |
| `--apply` | After the report, list the exact edits and apply them to local documentation, then check them again. With a named range, this works only when `<ref>` is the commit you have checked out. |

## Examples

```text
# Report documentation drift between a release tag and the current commit
/trackbed:docs:sync-release v1.0.0...HEAD

# Report drift for the current checkout, including uncommitted changes
/trackbed:docs:sync-release --current

# Name the base and the ref separately
/trackbed:docs:sync-release --base v1.0.0 --ref release/1.1

# Report, then apply the corrections to the docs
/trackbed:docs:sync-release --current --apply
```

## What you get

- The resolved scope, then a `DOCUMENTATION SYNC REPORT` in the conversation. It lists the changes it found as evidence and gives each affected document a status: `CURRENT`, `DRIFT`, `MISSING`, `GENERATED`, `UNVERIFIED`, or `OUT OF SCOPE`, with the exact correction it proposes. No report file is written.
- With `--apply`, a `PLAN:` naming every file it will change, then the smallest edits that fix the drift, left unstaged in your working tree. Generated docs are updated by running their generator, never by hand. The skill asks before it edits a document that already had uncommitted changes.
- After applying, a `DOCUMENTATION SYNC COMPLETE` summary: what changed, what was verified, and what is still unverified.
