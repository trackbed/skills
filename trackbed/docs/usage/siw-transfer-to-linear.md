# siw:transfer-to-linear

Use it when the spec and issue set in `siw/` are approved and Linear should take over. It shows a migration plan and, after you approve it, creates one Linear project with the specs and the log as Linear Documents, milestones from the phases, and one issue per SIW issue. The migration is one-way, not a sync: it writes to Linear, adds a `Linear Transfer` section to each migrated issue file, and deletes nothing. To create the issue set first, use `trackbed:siw:generate-phases`.

## Before you run it

- The Linear MCP server is connected and can create projects, milestones, and issues. See [MCP servers](../mcp-servers.md#linear). `--dry-run` also works without it and marks the Linear details as `UNVERIFIED`.
- The SIW directory holds a spec file or `OPEN_ISSUES_OVERVIEW.md`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[siw-dir]` | The SIW directory. The default is `siw`. A value that is not an existing directory and contains no path separator is read as a project name. |

## Options

| Option | Effect |
| --- | --- |
| `--project <name-or-id>` | Use the existing Linear project that matches this ID, slug, or exact name. If none matches, a project with this name is created. |
| `--team <team>` | The Linear team that owns the migrated work: a name, key, or UUID. Without it, the only team is used, or you are asked. |
| `--dry-run` | Print the migration plan and stop. Nothing is written to Linear. |
| `--skip-done` | Leave out issues whose SIW status is `DONE`. By default every issue is migrated. |
| `--skip-existing` | Also skip a source issue when an existing Linear issue in the target team and project has exactly the same title. Issues that already carry a `Linear Transfer` section are skipped on every run. |
| `--retry` | Same as `--skip-existing`. Use it to resume a migration that stopped partway. |

## Examples

```text
# Review the migration plan without writing to Linear
/trackbed:siw:transfer-to-linear --dry-run

# Migrate siw/ into a named project owned by one team
/trackbed:siw:transfer-to-linear --project "Notification System" --team ENG

# Resume a migration that stopped partway
/trackbed:siw:transfer-to-linear siw --project "Notification System" --team ENG --retry
```

## What you get

- The migration plan first: what will be created, reused, or skipped, issues with duplicate content, references that would stay local, and files that cannot be migrated. You settle open decisions and confirm the Linear workspace before anything is written.
- In Linear: the project, Documents for the main spec, the supporting specs, selected specs from `siw/contracts/`, and `LOG.md`, milestones for the phases, and the issues. Dependencies are kept as text and, where the Linear tools support it, as native relations.
- In each migrated issue file, a `## Linear Transfer` section naming the Linear issue, so a later run skips it.
- A verified result with the project URL and counts. After a failure, it lists what is still local only and prints the command to resume.

Only after a clean migration does it suggest retiring the local files with `trackbed:workflow:cleanup-artifacts` and `--siw`. Then implement with `trackbed:linear:issue-implement` or `trackbed:linear:issue-to-pr`. The [SIW guide](../siw.md#transfer-to-linear) covers the migration in full.
