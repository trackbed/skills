# pr:gut-check

Use it for a quick first read of your branch before a deeper review or before you open a Pull Request. It answers one question: does anything here look strange, unusual, or unnecessary? There is no rubric, no severity, and no report file, and it changes nothing. For a systematic review, use `trackbed:pr:code-review`.

## Options

| Option | Effect |
| --- | --- |
| `--base <branch>` | Compare against `<branch>` instead of the detected base branch. |
| `--intent <text>` | What the branch is meant to do, so a change that contradicts it stands out. Useful before a Pull Request exists. It must come last: everything after it is read as the intent. `trackbed:pr:review-convergence` sets it when it delegates. |

## Examples

```text
# React to everything that changed on the current branch
/trackbed:pr:gut-check

# Compare against the develop branch
/trackbed:pr:gut-check --base develop

# Say what the branch is for, before a Pull Request exists
/trackbed:pr:gut-check --intent Add CSV export to the reports page
```

## What you get

- A reply in the conversation and no file. It covers committed, staged, unstaged, and untracked changes, and the branch's commit history.
- One short item per oddity, most surprising first: what it is, the file and line or the commit, why it looks strange, and what would make it look ordinary.
- A plain "nothing stood out" when that is the answer. It does not report style, naming, or missing tests.
- A closing sentence that names the base, the number of changed files, and any file it did not read in full.

For a deeper pass, use `trackbed:pr:code-review`, `trackbed:pr:overengineering-review`, or `trackbed:pr:convention-review`.
