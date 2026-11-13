# pr:adversarial-review

Use it when you want a second opinion on your branch from a different model provider than the one you are working in: Codex when you run Claude Code, Claude when you run Codex. It runs one read-only review of the committed branch, checks every finding against the code, and reports the result in the conversation. It changes nothing in the repository or on GitHub. For the regular review by specialized agents, use `trackbed:pr:code-review`.

## Before you run it

- The working tree is clean, with no uncommitted or untracked files, and the branch has at least one commit ahead of its base.
- The other provider's CLI is installed and signed in. In a Conductor cloud workspace, the review runs as a session of the other provider in that workspace instead.
- Running it sends the tracked files at `HEAD`, the committed diff, and any requirements you pass to that provider.

## Options

| Option | Effect |
| --- | --- |
| `--provider claude\|codex` | The provider that reviews. The default is the one you are not using; naming the one you are using stops the run. |
| `--model <id>` | The model the reviewing provider uses. Without it, that provider's configured default applies. |
| `--base <branch>` | Compare against `<branch>` instead of the detected base branch. |
| `--requirements <authoritative requirements>` | What the change must do, passed to the reviewer to check the change against. It must come last: everything after it is read as the requirements. `trackbed:pr:review-convergence` sets it when it delegates. |

## Examples

```text
# Get a review from the other provider with its default model
/trackbed:pr:adversarial-review

# From Claude Code, review against the develop branch with Codex
/trackbed:pr:adversarial-review --provider codex --base develop

# Tell the reviewer what the change must do
/trackbed:pr:adversarial-review --requirements Exports include archived projects and finish within 30 seconds
```

## What you get

- A reply in the conversation and no file. It starts with `Adversarial review: passed` or `blocked`, then names both providers, the model, the reviewed commit, where the review ran, and what the reviewer covered.
- A count of blocking, advisory, and rejected findings, then every finding the reviewer returned: its claim, the severity the reviewer gave it, the severity after checking it against the code, the evidence, and a recommendation. Rejected findings stay in the list with the reason.
- `passed` means the review finished and every finding was checked, even when it found real problems. `blocked` means the review could not run or its result could not be trusted, for example a missing CLI, a timeout, or a tree that changed during the review.
