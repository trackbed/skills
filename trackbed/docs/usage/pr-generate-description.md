# pr:generate-description

Use it to write a Pull Request title and description from the branch diff, the commit log, and the linked Linear issue. With `--check`, it instead reports whether an open Pull Request's description still matches the diff. When the current branch already has an open Pull Request, it updates that title and body on GitHub; otherwise it prints them for you to copy. It never creates a Pull Request; use `trackbed:pr:create` for that.

## Before you run it

- To update a Pull Request or run `--check`, `gh` is installed and authenticated.
- `--check` needs a Pull Request for the current branch.

## Options

| Option | Effect |
| --- | --- |
| `--manual` | Ask clarifying questions before writing, print the result for copy-paste without updating a Pull Request, and offer to save it to a file. |
| `--no-update` | Print the title and body and never change an existing Pull Request. With `--check`, report only, without the offer to update. Skills that delegate to this one pass it. |
| `--check` | Compare the open Pull Request's title and body with the diff and report where they disagree, instead of writing a description. After important or critical drift, it asks once before it regenerates and updates the Pull Request. |
| `--strict` | With `--check`, also report suggestion-level drift, such as a claim that cannot be tied to the diff. |
| `--base <ref>` | Compare against `<ref>` instead of the detected base branch. |
| `--base-commit <oid>` | Pin the comparison to this full commit ID, together with `--base`. Set by `trackbed:pr:create` when it delegates; you rarely need it. |
| `--linear-issue <ISSUE-ID>` | Use this Linear issue as context instead of the ID read from the branch name. |
| `--independent-review-line <line>` | Put this one-line record of an independent review in the body unchanged. Works only with `--no-update`. Set by `trackbed:pr:create` when it delegates; you rarely need it. |

## Examples

```text
# Write a title and description, and update the open Pull Request if there is one
/trackbed:pr:generate-description

# Answer clarifying questions first and get the text to copy
/trackbed:pr:generate-description --manual

# Check whether the open Pull Request's description still matches the diff
/trackbed:pr:generate-description --check

# Check strictly and only report, without the offer to update
/trackbed:pr:generate-description --check --strict --no-update
```

## What you get

- A Conventional Commits title and a description that follows your repository's Pull Request template when it has one.
- With an open Pull Request, its title and body updated on GitHub. With `--manual`, `--no-update`, or no Pull Request, the text in the conversation to copy.
- A `MISSING REQUIREMENT:` line when context it will not invent is missing, such as the reason for a database migration. Unless the only gap is a missing Linear issue ID, it then prints the text instead of updating the Pull Request.
- With `--manual`, when you accept the offer, the description saved to `.trackbed/pr-description/PR_DESCRIPTION.md`. It adds `.trackbed/` to Git's local exclude file.
- With `--check`, a `PR Description Check` report in the conversation: a verdict from Accurate to Inaccurate, and for each finding what the body says, what the diff shows, and a fix. No file is written.
