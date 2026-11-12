# pr:walkthrough

Use it to give a reviewer a visual tour of a change. By default it builds a guided page for the current branch or its open Pull Request, with four interactive diagrams: system overview, data flow, code dependencies, and user actions. With `--report` it builds a before/after report of a branch, commit, Pull Request, or range instead. It only writes local HTML, so nothing is committed, pushed, or published, and it is for orientation: for actionable review findings, use `trackbed:pr:code-review`.

## Before you run it

- Run it inside a Git repository.
- `gh` is installed and authenticated when you pass a Pull Request number to `--report`. The guided walkthrough uses `gh` to find the branch's open Pull Request when it is available.
- `python3` is available for the guided walkthrough.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[branch\|commit\|PR#\|range]` | What `--report` covers: a branch name (your working tree against that branch), a commit hash (that commit), `HEAD` (uncommitted changes only), a Pull Request number such as `#42`, or a range such as `abc123..def456`. Only valid with `--report`. Without it, the report compares against the detected base branch. |

## Options

| Option | Effect |
| --- | --- |
| `--report` | Build the before/after report instead of the guided walkthrough. |
| `--base <ref>` | Compare against `<ref>` instead of the detected base branch. With `--report`, it cannot be combined with a branch, commit, Pull Request, or range argument. |
| `--output <path>` | Write the page to `<path>` instead of the default location. |

## Examples

```text
# Build the guided walkthrough for the current branch or its open Pull Request
/trackbed:pr:walkthrough

# Build the guided walkthrough against the develop branch
/trackbed:pr:walkthrough --base develop

# Build a before/after report of Pull Request 42
/trackbed:pr:walkthrough --report #42

# Report on the working tree against main and choose where the file goes
/trackbed:pr:walkthrough --report main --output ~/reports/checkout-change.html
```

## What you get

- The guided walkthrough at `.context/pr-walkthrough/index.html`: one page that opens straight from disk, with a guided tour, search, and zoom in each of the four views. Its diagram data is in `.context/pr-walkthrough/graph.json`, and images it uses are saved in an `assets/` folder beside the page.
- With `--report`, a page in `~/.trackbed/diagrams/` named `diff-review-<name>.html`, opened in your browser. It can hold a summary, key figures, architecture and flow diagrams, before/after comparisons, a file map, test coverage, review notes, and a decision log; sections with nothing to show are left out.
- A reply with the file path. For the guided walkthrough it also names the base, the head, and the Pull Request when one was found, and says whether the page passed its checks.
