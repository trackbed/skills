# Drive a Repository's Conductor Workspaces to Merge With Showtime

- Status: PROPOSED
- Date: 2026-11-22
- Deciders: repository maintainer (skill requested in the implementation request; the seven choices marked "maintainer's choice" below were recorded by the maintainer in a decision document on 2026-11-22)
- Extends: [2026-11-19-local-conductor-orchestration.md](2026-11-19-local-conductor-orchestration.md)
- Applies: [2026-07-29-skill-catalog-shape.md](2026-07-29-skill-catalog-shape.md) (one more single-skill domain)

## Context

A day of parallel work leaves many Conductor workspaces at different points on the way to a merged Pull Request, and the maintainer moves each one by hand. On 2026-11-21 this repository had seven live workspaces, seven open Pull Requests, and six chats running at once. The Pull Requests merged in hand-run batches after waits of up to eight hours.

Checked against Conductor 0.98.0 on 2026-11-22:

- A message sent with `SendSessionMessage` arrives as a plain user message. `/trackbed:pr-shape-up` started the skill in a Claude Code chat, and `$trackbed:pr:shape-up` started it in a Codex chat.
- `ListSessionMessages` marks a message that another chat sent with that chat's `senderSessionId`.
- `CreateWorkspace` makes a new branch from a base branch. It cannot open a workspace on an existing Pull Request's branch.

Existing rules that bear on such a skill:

- The 2026-11-19 record lets a run message, cancel, or archive only what that run started.
- The shared decision request format says: "Never pick an option for the user, including the recommended one."
- The [unattended default](2026-10-31-unattended-default-for-shipping-skills.md) record limits unattended mode to the request being answered, and says that a request reaching a skill through another agent is not a direct request.
- The [risk triage](2026-09-28-pr-risk-triage.md) record says a tier is not an approval, and lists auto-approval as not decided.

Two repository facts shaped the merge rules. No approving review is required here, so nothing but checks stands between a diff and `main`. A push to `main` runs only the semantic scan, so nothing tests two green Pull Requests in combination after they merge.

## Decision

1. **Skill and domain.** `trackbed:conductor:showtime` is user-only. `conductor` is a new domain for skills whose subject is the Conductor host's workspaces and chats. It holds one skill; the owner is the repository maintainer, and the case for the domain is reviewed on 2026-12-22.
2. **One pass.** A run reads the repository's workspaces and chats, the user's open Pull Requests, and each checkout. A bundled helper places every workspace on one stage and names its next move. The model never merges, sends, or archives on its own reading.
3. **Reach.** Showtime acts on every workspace of the repository, including the ones the user or another skill started. This replaces "only what the run started" for this skill, and only for four actions: sending a message, archiving a merged workspace, creating a sidebar section, and moving a workspace between sections. It never cancels a chat or creates a workspace, and it leaves its own workspace out.
4. **Fixed commands.** The helper prints each message. A chat gets `trackbed:pr:create --showtime` when its checkout has committed work and no Pull Request, and `trackbed:pr:shape-up` when its Pull Request has a conflict, a failing required check, stale checks, or an open thread from an AI reviewer. Creation has a narrow exception to the unattended default: the receiving skill verifies the Conductor relay and the sender's direct user request before applying its existing auto-mode gates to a clean checkout. Refresh the chat before sending. Count at most two accepted commands for the same problem. A repeated plan uses the same message ID.
5. **Merge gate.** A Pull Request merges only when it is the user's own, targets the default branch, and is not a draft; its required checks are green on the head commit; it has no unresolved review thread, no conflict, no missing required review, and no other branch-protection block; its chat is idle and its checkout holds nothing unpublished; and its checks are not stale.
6. **Stale checks (maintainer's choice).** The helper inspects commits on the default branch's first-parent history after the Pull Request head's commit date. For a merge commit it uses the diff against its first parent, which includes topic changes newly introduced by that merge. A hit on a changed file, CI configuration, a lockfile, or shared build tooling requires a rebase and new checks. GitHub reads and Git fetches both use the repository at `origin`.
7. **Hold rules (maintainer's choice).** A Pull Request that passes the gate still does not merge unattended when its deterministic risk floor is high or cannot be computed, when its title or description marks a breaking change, or when a person's latest review requests changes or a person's comment is unanswered. An author review with no text, such as the carrier of a reply to a bot's thread, answers no one. The risk floor is used as a hold, never as an approval.
8. **Merging.** The helper's `merge` command rechecks one PR cleared by a board no older than fifteen minutes. It pins the cleared head and uses GitHub's synchronous merge endpoint, which requires branch rules to pass and reports completion before the next PR can proceed. A branch requiring a merge queue is handled through GitHub. Between merges the board is not rebuilt: each `merge` rechecks its PR against a freshly fetched default branch, a refused PR is skipped and the train goes on, and the board is rebuilt once when the train ends.
9. **Two modes.** By default showtime sends commands on its own and asks once before merging and archiving. Approval covers the displayed PR numbers and head SHAs and the displayed archive workspace IDs and head SHAs. Refreshes may remove candidates. `--auto` merges and archives without asking and never merges a held Pull Request.
10. **Authority of `--auto` (maintainer's choice).** `--auto` counts only when it is in the user's own message that starts the run. Under `/loop`, the repeated message is that request again, so every pass keeps the authority, for any workspace on the board at that pass, until the loop ends.
11. **Decision requests (maintainer's choice).** Under `--auto`, a chat that stopped on a decision request in the shared format gets a reply that picks the first option of every decision, when that option alone is marked recommended. The helper writes the reply. This sets aside "never pick an option for the user" for showtime `--auto` only; the rule still binds every workflow that asks. A chat that waits on a dialog or a permission prompt is never answered.
12. **Pull Requests without a workspace (maintainer's choice).** An open Pull Request with no live workspace can pass the gate and merge, with the chat check skipped. Nothing can be sent for it.
13. **No new work (maintainer's choice).** Showtime starts no workspace. `trackbed:linear:next` stays the only way work starts.
14. **Archiving.** Require a merged PR that matches the workspace's head repository, branch, and SHA. Verify its checkout is still clean and its chats are idle immediately before archiving. Conductor applies its **Delete branch on archive** setting.
15. **Sidebar (maintainer's choice).** Each pass moves workspaces into five sections named for the stage groups, creating them on first use. It moves a workspace only when it is in no section or already in one of the five.

## Consequences

- One command moves a whole repository's workspaces forward, and under `/loop --auto` Pull Requests can merge with nobody watching. The gate and the hold rules are then the only review a diff gets.
- A chat in any workspace of the repository can receive a command it did not ask for. The ten-minute idle rule and the check of the chat's last message keep one from landing on a question or between two turns.
- An agent's own recommendation can be accepted with nobody reading it. Requests in any other format, including the prose a blocked question dialog produces, are reported and never answered.
- The stale rule uses commit timestamps as a proxy for arrival on the default branch. It cannot infer when an older commit was fast-forwarded onto the base.
- Tests pin the helper's rules and the skill's wording. They cannot prove that the model copies a message unchanged; the Conductor transcript records every message sent.
- Hosts without the Conductor tools see a skill that stops at its first step.

## Alternatives Considered

### Merge everything that passes the gate

Rejected by the maintainer. With no approving review required, the checks would be the only reviewer of every diff, including a breaking change.

### Leave a worker's question waiting under `--auto`

Recommended by the implementer and rejected by the maintainer, who chose to send the recommended option so that an unattended run does not stall on routine questions.

### Limit a looped `--auto` to the workspaces on its first board

Recommended by the implementer and rejected by the maintainer, who chose to keep the loop open-ended.

### Rebase every Pull Request before it merges, or use no stale rule

Rebasing everything re-runs CI on every open Pull Request after each merge, and the slowest check takes about half an hour here. No stale rule lets two Pull Requests that share a file merge on checks that never saw the two together.

### Only report a Pull Request that has no workspace

Recommended by the implementer and rejected by the maintainer, who chose to let it join the merge train.

### Leave the sidebar alone

Recommended by the implementer, as the two earlier Conductor records deferred it, and rejected by the maintainer, who chose the sections.

### Let showtime start the next issue when a workspace finishes

Rejected. Starting work chooses what gets built, and `trackbed:linear:next` already owns that choice with its own consent.

### Read Conductor's database or CLI from the helper

Rejected. The control tools are the only documented local surface, so the model copies their results to a file that the helper validates.
