# pr:review-queue

Use it to see which Pull Requests are waiting on your review and where each one stands: how long it has waited, whether it looks ready for review, your part, CI, and the linked issue. It reads live GitHub state and reports; it never reviews, comments, re-runs jobs, or merges. It covers the repository you run it in unless you pass `--all-repos`. Only requests made to you personally are listed, not requests to a team you belong to.

In Conductor it also shows which Pull Requests already have a review workspace and where that review stands, and offers to start `trackbed:pr:github-review` in a new workspace for each of the others. It starts only the ones you confirm. Elsewhere, review one of the Pull Requests with `trackbed:pr:github-review`.

## Before you run it

- `gh` is installed and authenticated, and `jq` is installed.
- Run it inside a clone of a GitHub repository, or pass `--repo` or `--all-repos`.
- The Conductor part needs a local Conductor workspace whose agent has Conductor's workspace tools. Without them the report is the same, minus the `Workspace` column and the offer.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[OWNER/NAME#N ...]` | Pull Requests to look up again by number, such as `acme/web#412`. On a recheck, pass every Pull Request from the previous report. |

## Options

| Option | Effect |
| --- | --- |
| `--repo OWNER/NAME` | Search this repository instead of the one you run it in. |
| `--all-repos` | Search every repository your GitHub login can read, grouped by repository. Cannot be combined with `--repo`. |
| `--since ISO-8601` | Also include Pull Requests you reviewed that changed since this time, and ones that requested you and closed since then. On a recheck, pass the snapshot time of the previous report. |

## Examples

```text
# Show the open Pull Requests in this repository that request your review
/trackbed:pr:review-queue

# Show the queue for another repository
/trackbed:pr:review-queue --repo acme/web

# Show the queue across every repository you can read
/trackbed:pr:review-queue --all-repos

# Recheck since the last report, including two Pull Requests it listed
/trackbed:pr:review-queue --since 2026-11-12T09:30:00Z acme/web#412 acme/api#87
```

## What you get

- A report in the conversation. No file is written and nothing changes on GitHub.
- An opening sentence with the snapshot time in UTC, how many Pull Requests wait on you, and how many of those look ready for review. On a recheck, it also says what changed since the last report.
- A table per repository that always has these columns:

  | Column | Shows |
  | --- | --- |
  | PR | The number and title, linked to the Pull Request |
  | Author | Who opened it |
  | Linear issue | The linked issue, or "none found" |
  | CI | Green, running, failing, cancelled, or none |
  | Waiting | How long it has waited on you |
  | Ready? | "Yes", "Probably", or "No", with the reasons |
  | Your part | Not reviewed, a pending review you never submitted, your open threads, or a re-request |
  | Workspace | In Conductor only: the review workspace and where its review stands, or "none" |

- Finished items in a separate "No longer waiting on you" table.
- Notes where the table needs them, such as a failing check that looks like a flake, and a suggested order for working through the queue.
- In Conductor, an offer to start reviews for the Pull Requests that have no workspace, look ready, and have no pending review of yours. After you answer yes and name which, each one gets its own new workspace that runs `trackbed:pr:github-review` on it. Those reviews only report: they post nothing to GitHub without asking you in their own workspace.

The [review guide](../review.md#your-review-queue) explains how the waiting time, the readiness estimate, your part, and CI are read.
