# pr:review-queue

Use it to see which Pull Requests are waiting on your review and where each one stands: your part, CI, merge state, and the linked issue. It reads live GitHub state and reports; it never reviews, comments, re-runs jobs, or merges. Only requests made to you personally are listed, not requests to a team you belong to. To review one of the Pull Requests, use `trackbed:pr:github-review`.

## Before you run it

- `gh` is installed and authenticated, and `jq` is installed.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[OWNER/NAME#N ...]` | Pull Requests to look up again by number, such as `acme/web#412`. On a recheck, pass every Pull Request from the previous report. |

## Options

| Option | Effect |
| --- | --- |
| `--repo OWNER/NAME` | Limit the searches to one repository. Without it, the queue spans every repository your GitHub login can read. |
| `--since ISO-8601` | Also include Pull Requests you reviewed that changed since this time, and ones that requested you and closed since then. On a recheck, pass the snapshot time of the previous report. |

## Examples

```text
# Show every open Pull Request that requests your review
/trackbed:pr:review-queue

# Limit the queue to one repository
/trackbed:pr:review-queue --repo acme/web

# Recheck since the last report, including two Pull Requests it listed
/trackbed:pr:review-queue --since 2026-11-12T09:30:00Z acme/web#412 acme/api#87
```

## What you get

- A report in the conversation. No file is written and nothing changes on GitHub.
- An opening sentence with the snapshot time in UTC and how many Pull Requests wait on you. On a recheck, it also says what changed since the last report.
- A table per repository with each Pull Request and its issue, your part, CI, and merge state. Finished items go in a separate "No longer waiting on you" table.
- Notes where the table needs them, such as a failing check that looks like a flake, and a suggested order for working through the queue.

The [review guide](../review.md#your-review-queue) explains how your part and CI are read.
