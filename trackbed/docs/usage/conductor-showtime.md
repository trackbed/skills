# conductor:showtime

Use it in Conductor when a repository has several workspaces on their way to a merged Pull Request and you want all of them moved one step. One run is one pass: it places every workspace on a stage, sends a workspace's own chat the command it needs, merges the Pull Requests that pass the merge gate, archives merged workspaces, and sorts the sidebar into five sections. It never edits code itself. It asks before merging and archiving unless you pass `--auto`.

It can send `trackbed:pr:create` or `trackbed:pr:shape-up` to idle chats in any workspace of the repository. It can also merge your open Pull Requests in the repository at `origin`, including one whose workspace is gone. Conductor applies its **Delete branch on archive** setting, and GitHub applies the repository's branch cleanup setting when a PR merges.

## Before you run it

- Run it in a local Conductor workspace of the repository, in a chat whose agent has Conductor's workspace tools. Elsewhere it stops at once.
- `gh` is installed and authenticated, and Git 2.37+ and Python 3.10+ are available.
- The repository's required checks are what the merge gate trusts. A Pull Request with no checks at all never merges.
- Showtime treats committed work on a clean checkout as finished: such a workspace with no Pull Request gets `trackbed:pr:create` once its chat has been idle for ten minutes. A workspace with an uncommitted change gets no command. Run with `--dry-run` first to see what a pass would send.

## Options

| Option | Effect |
| --- | --- |
| `--auto` | Merge and archive without asking. Also answer a chat that stopped on a decision request with its recommended first option. A Pull Request that matches a hold rule stays open and is reported. |
| `--dry-run` | Read everything and report what the pass would do. Nothing is sent, merged, archived, or moved. |
| `--idle-minutes <n>` | How long a chat must have been idle before it gets a command. Default 10. |

## Examples

```text
# Take one pass: send what is needed, then ask before merging and archiving
/trackbed:conductor:showtime

# See what a pass would do, without changing anything
/trackbed:conductor:showtime --dry-run

# Merge and archive without asking, and answer decision requests with the recommended option
/trackbed:conductor:showtime --auto

# Send commands to chats that have been idle for at least half an hour
/trackbed:conductor:showtime --idle-minutes 30
```

In Claude Code, `/loop /trackbed:conductor:showtime --auto` repeats the pass until nothing can move without you.

## What you get

- A report that leads with what waits on you: questions from chats, held Pull Requests with the reason, and workspaces that need a look. Then what changed since the last pass, and one table row per workspace with its stage, its Pull Request, and its next move.
- Commands sent to idle chats, at most two for the same problem. A chat that stopped on a question gets no command.
- Without `--auto`, approve only the Pull Request commits and archive candidates shown in the preview. New candidates and changed commits need another preview.
- Showtime rechecks the merge gate immediately before making a synchronous, head-pinned merge. It skips a PR the recheck refuses and rebuilds the board once when the train ends. PRs whose base requires a merge queue need to be merged through GitHub.
- Workspaces moved into the sections "Working", "Needs me", "Needs a nudge", "Merge-ready", and "Merged". A workspace you placed in a section of your own, or pinned, stays where it is.

Under `--auto`, three kinds of Pull Request are held and never merged: one whose risk signals are high or could not be computed, one marked as a breaking change, and one with a changes request or an unanswered comment from a person. The [shipping guide](../shipping.md#driving-conductor-workspaces-to-merge) describes the stages, the merge gate, and the hold rules.
