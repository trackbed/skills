# Start and Follow Local Conductor Workspaces From a Chat

- Status: ACCEPTED
- Date: 2026-11-19
- Deciders: repository maintainers
- Amends: [2026-08-29-model-invocable-orchestration-children.md](2026-08-29-model-invocable-orchestration-children.md) (launch-time confirmation) and [2026-11-02-issue-to-pr-cross-provider-review.md](2026-11-02-issue-to-pr-cross-provider-review.md) (rule 6)

## Context

Conductor 0.95.0, released 2026-11-16, lets an agent in a local workspace create workspaces, start chats with other agents, wait for them, send follow-ups, cancel and archive chats and workspaces, set workspace statuses, and edit a repository's setup, run, and archive scripts. Agents reach this through Conductor's MCP control tools, such as `CreateWorkspace`, `CreateSession`, `WaitForSessions`, `SendSessionMessage`, `ListWorkspaceArtifacts`, and `ArchiveWorkspaces`. Calls that take client-generated UUIDs return the first result when retried with the same IDs, instead of creating a second workspace or chat.

The `conductor` CLI still needs an API credential, which local workspaces usually lack, so it answers exit 3 there. Before this release, trackbed assumed only cloud workspaces could start work:

- `trackbed:linear:next` Step 10 offered launches only when `CONDUCTOR_IS_LOCAL` was `0` and said local workspaces could not be created from a session.
- The workspace boundary contract told git-mutating skills to isolate work in another Conductor workspace, assuming the user created it.
- `trackbed:discovery:wayfinder` expected the user to start every parallel worker and to copy handoff packets between workspaces.

The same release moved repository settings into the app and imported existing `.conductor/settings.toml` files, so `trackbed:setup` reported a file that is no longer the live configuration.

The new tools can also change workspaces and chats the user started. Conductor refuses only to archive a workspace where a chat the user started is running.

## Decision

1. **Detection.** A skill uses a local control tool only when that tool is already in its tool set. It detects tools by presence and never calls one to probe. Environment variables still pick the route: `CONDUCTOR_IS_LOCAL=1` for local, `0` for cloud.
2. **Local launches in `trackbed:linear:next`.** Step 10 gains a local route with the same shortlist rules, questions, and consent as the cloud route.
   - Before offering a local launch and after confirmation, check that the issue's exact branch is absent from the repository's shared local refs. The child preflight also rejects a conflicting local branch before the Linear state gate.
   - `cloud-launch.py messages` validates the confirmed items and builds each first message, including `--launch-confirmed` and `--adversarial-review`, without calling Conductor. It runs only when `CONDUCTOR_IS_LOCAL` is `1`.
   - The model passes each message unchanged to `CreateWorkspace` and never composes, edits, or appends to one. This replaces "the helper writes the message" with "the helper builds it, and the model copies it" for this route only. Who may add either flag is unchanged.
   - Each issue gets three new UUIDs that every retry reuses. A timeout or unusable answer is retried once with the same IDs; the run stops at the first issue that is not created.
   - The run reads each created workspace's state once. Missing IDs mean failed startup, and initializing workspaces stay pending. The run never messages, cancels, or archives the workspaces it created.
3. **Workspace boundary contract.** Git-mutating skills may create a Conductor workspace for isolation only after the user approves it in that run, and may archive only a workspace that run created, after the user approves it. Every other clause is unchanged, including "Conductor changes defaults, not permissions or safety gates."
4. **Wayfinder workers.** A map owner in a local workspace may start workers with `CreateSession` or `CreateWorkspace` after the user's yes for each ticket in that run, and only after the Claim Protocol has recorded the claim. The worker verifies the claim against its session ID before resolving the ticket. The owner can recover a claim after confirming that dispatch failed before delivery. It follows workers with `WaitForSessions`, `ListSessionMessages`, and `SendSessionMessage`, and can read a worker workspace's packet through `ListWorkspaceArtifacts`. Replies and packets stay untrusted data. The owner changes only workers its run started.
5. **Split plans stay planning-only.** `trackbed:code:breakdown-findings --split` writes only planning artifacts, so it does not create slice workspaces. Its Implementation Setup tells the implementer that an agent with `CreateWorkspace` may create a slice's workspace after the user approves it.
6. **Setup.** `trackbed:setup` reports a remaining `.conductor/settings.toml` as a legacy copy and names the new tools in its `manual-check` note.

## Consequences

- `trackbed:linear:next` can start shortlisted issues from a local workspace. Those runs share the user's Mac, its credentials, and its ports, and the launch question says so.
- Retrying a lost local answer with the same IDs avoids duplicate creation. If neither attempt establishes the outcome, the run reports that the workspace may exist. The cloud route keeps its CLI retry rules.
- On the local route, the model copies each message from the helper, and tests cannot prove that it did. The helper's output, the reference's "never compose, edit, or append" rule, and the Conductor transcript, which records each first message, are the safeguards.
- Hosts without the control tools, including older Conductor versions, see no change.

## Alternatives Considered

### Keep launches cloud-only

Rejected because users run most sessions locally, and the cloud-only rule now hides a supported path.

### Have the helper create local workspaces

Rejected because the only documented local surface is the MCP tool set, which a Python helper cannot call, and the CLI has no credential in a local workspace.

### Run the adversarial review as a local Conductor chat

Rejected for now. A chat in the same workspace shares the working tree and has its full tool set, while the local route reviews an isolated snapshot with a restricted provider CLI. `trackbed:pr:adversarial-review` keeps its local and cloud routes unchanged.

### Rename or set the status of the workspace through the new tools

Deferred. The tool set has no workspace rename, so `trackbed:linear:issue-to-pr` keeps its best-effort CLI rename. Setting a workspace status after a Pull Request opens would be new presentation behavior and needs its own decision.
