# workflow:cleanup-artifacts

Use it to delete the working files that trackbed skills leave behind: review, audit, and QA reports, generated plans, evidence under `.context/`, SIW tracking files such as `siw/LOG.md` and `siw/issues/`, and diagram pages under `~/.trackbed/diagrams/`. It deletes files, so it first lists what it found and asks what to remove. SIW specifications are kept unless you choose to delete them too.

## Before you run it

- Install `trash` so deleted files can be restored from the system Trash. Without it, files are deleted permanently after a second confirmation and directories are skipped.

## Options

| Option | Effect |
| --- | --- |
| `--auto` | Delete this project's disposable files without asking, keeping SIW specifications and the shared diagram pages. It needs `trash` and stops when a tracked artifact has uncommitted changes. Set by `trackbed:linear:issue-to-pr --ship` when it delegates; you rarely need it. |
| `--siw` | Retire the local `siw/` workspace instead. Only files under `siw/` are offered, including the discovery brief and strengthening plan that a plain run leaves alone. It runs only when you ask for it yourself, always asks first, and cannot be combined with `--auto`. See the [SIW guide](../siw.md#cleanup). |

## Examples

```text
# List the artifacts found and choose what to delete
/trackbed:workflow:cleanup-artifacts

# Delete this project's disposable artifacts without a prompt
/trackbed:workflow:cleanup-artifacts --auto

# Retire the SIW workspace after its issues were moved to Linear
/trackbed:workflow:cleanup-artifacts --siw
```

## What you get

- A list of the files found, with a warning for tracked files that have uncommitted changes, and a choice: delete the artifacts, delete the artifacts and the SIW specifications, or cancel.
- The chosen files and directories deleted. Only files the run found are touched.
- A report of what was deleted and whether it went to the Trash or is gone for good, what could not be deleted, and what was skipped.
- `No artifact files found.` when there is nothing to delete.
- With `--siw`, the `siw/` directory itself removed once it is empty.
