# pr:shape-up

Use it when the current branch has an open Pull Request that you want ready to merge. It takes no arguments: it reads the Pull Request and does only what is needed, which can be a rebase onto the target branch, fixes for failing CI until the checks are green, and fixes and replies for comments from AI reviewers such as CodeRabbit or Copilot. It can force-push the rebased branch with a lease, push fix commits, and post replies on GitHub, but it never replies to a person. For review comments from people, use `trackbed:pr:github-review-reply`.

## Before you run it

- The current branch has an open Pull Request.
- Your checkout matches the Pull Request head. Push your local commits, or update the checkout, first.
- `gh` is installed and authenticated, and `python3` is available.

## Examples

```text
# Get the current branch's open Pull Request ready to merge
/trackbed:pr:shape-up

# Run it again later to handle comments an AI reviewer posted after the last run
/trackbed:pr:shape-up
```

## What you get

- Only the work the Pull Request needs, in at most three rounds: a rebase, in the first round only, fixes pushed as `[FIX PIPELINE]` commits, and replies to AI reviewers, with the threads those replies settle resolved.
- A closing report that says `PR shape: in shape` or `needs attention`, followed by the state of the rebase, CI, and AI review comments and the number of rounds.
- A "Left for you" list when something remains: blockers, threads it left open and why, and the number of open threads from people.
- A Pull Request that is already in shape gets the report and nothing else.

The CI pass checks all review feedback on the Pull Request, so it may also fix a valid request from a person. The [shipping guide](../shipping.md#shaping-up-an-open-pull-request) describes each pass.
