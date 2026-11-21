# Let the Review Queue Read Conductor Workspaces and Start Reviews

- Status: PROPOSED
- Date: 2026-11-21
- Deciders: repository maintainer (behavior requested in the implementation request; design choices made during it)
- Extends: [2026-11-19-local-conductor-orchestration.md](2026-11-19-local-conductor-orchestration.md)

## Context

`trackbed:pr:review-queue` reports which Pull Requests wait on the user's review. It read only GitHub. A user who reviews in Conductor could not tell from the report which Pull Requests already had a review workspace or how far that review had come, and created one workspace per Pull Request by hand to run `trackbed:pr:github-review`.

The 2026-11-19 record lets `trackbed:linear:next`, git-mutating skills, and a Wayfinder map owner start local Conductor workspaces after the user approves. It covers no skill that only reads Conductor, and it names no other launcher.

Two existing rules bear on a launch from this skill:

- `AGENTS.md` keeps side-effecting skills model-disabled by default. `trackbed:pr:review-queue` is model-invocable, so that the model can answer "what is waiting on my review?" without a typed command.
- `trackbed:pr:github-review` is user-only, and its `--draft-review` flag authorizes a GitHub write.

Checked against Conductor 0.98.0 on 2026-11-21:

- A workspace record carries a `name`, a `branch`, and an `appUrl`, and no Pull Request reference.
- `ListSessions` with `filter.query` returns every chat whose messages contain the text, with up to three excerpts each. That includes the chat that runs the search and chats that only mention the Pull Request. A search can stop early and return a cursor to continue from.
- `ListRepositories` returns each repository's `remoteUrl`.

## Decision

1. **Reading.** When `ListWorkspaces` and `ListSessions` are in the tool set, the review queue matches each Pull Request that waits on the user to a local workspace and reports where that workspace's newest chat stands.
   - A workspace matches by the Pull Request's head branch, as in a workspace Conductor opened from the Pull Request, or by an `OWNER/NAME#N` reference in its name, as in a workspace this skill started.
   - One call lists the chats of all matched workspaces. The run reads at most the last five messages of one chat per Pull Request.
   - One search per repository looks for the review command followed by a Pull Request URL of that repository, to find reviews started in a workspace the two rules above miss. A chat counts only when the match is the user's own message and its workspace is not archived, so a report that suggests the command does not count.
   - Tool presence alone enables this. No environment variable is read, because there is only a local route.
2. **Starting.** When `CreateWorkspace` is also present, the report ends with one offer to start `trackbed:pr:github-review` in a new local workspace per Pull Request. A Pull Request is offered only when it has no workspace or review chat, is estimated ready or probably ready, and has no unsubmitted pending review. The run starts only the Pull Requests the user confirms in that run. Each gets three new UUIDs that one retry reuses, the run stops at the first one that is not created, and it reads each created workspace's state once.
3. **First message.** The snapshot script prints each Pull Request's first message for Claude Code and for Codex as `reviewCommand`. The model copies it unchanged and adds no flag. It never adds `--draft-review`, so every launched review is report-only and asks in its own workspace before any GitHub write.
4. **Invocation.** `trackbed:pr:review-queue` stays model-invocable. Creating the confirmed workspaces is its only write. It never messages, cancels, or archives a chat or a workspace, including the ones it created. The user's yes to the offer is the request to run the user-only `trackbed:pr:github-review` in each new workspace.

## Consequences

- In Conductor the report gains a `Workspace` column. Hosts without the tools, including older Conductor versions, see no change.
- The lookup costs one `ListWorkspaces` call per repository, one `ListSessions` call for the matched workspaces, and about two more for the search, because a search can stop early and must be continued. In a dry run on 11 waiting Pull Requests, the branch match found both workspaces Conductor had opened from a Pull Request.
- Matching is a heuristic. A review started with a Pull Request number, in a workspace on another branch, is missed, and the queue then offers a second review. An archived review workspace counts as none.
- A run the model started can end with the offer. Nothing is created until the user answers yes.
- Tests pin the gate wording and the script's commands, but cannot prove that the model copies a message unchanged. As with `trackbed:linear:next`, the Conductor transcript records each first message.
- Each launched review runs several review agents on the user's Mac. The offer says so before the user answers.

## Alternatives Considered

### Make the review queue user-only

Rejected. The model could then no longer answer a question about the queue on its own, and the launch already waits for an explicit yes that names the Pull Requests.

### Only print the review commands

Rejected. The report already closed by offering the command, which left the user to create every workspace by hand.

### Start the reviews as chats in the queue's own workspace

Rejected. The request was for one workspace per Pull Request. That keeps each review's report, drafts, and resume state in its own workspace, and gives a later queue run a workspace to find.

### Search the chats for each Pull Request's URL

Rejected after a dry run. Every such search returned the same earlier queue reports, about 25 KB of excerpts each, because a queue report links every Pull Request it lists. It also cost two calls per Pull Request. Searching once per repository for the review command returned three chats in the same repository.

### Build the first message in a separate helper

Rejected. `trackbed:linear:next` uses a helper because its messages carry flags that grant authorization. Here the message varies only in the Pull Request URL, so the snapshot script that already prints the URL prints the message too.

### Set a status or a section on the workspaces the queue starts

Deferred, as the 2026-11-19 record deferred workspace statuses. The workspace name carries the Pull Request reference, which is enough for the next run to find it.
