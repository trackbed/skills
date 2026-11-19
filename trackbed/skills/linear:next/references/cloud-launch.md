# Start Issues in New Conductor Workspaces

Follow this only after Step 10 chose a route: `cloud` when `detect` returned `ok`, or `local` when it returned `local` and Conductor's `CreateWorkspace` tool is present. Nothing here runs without the user's explicit yes in this run. `{cloud-launch-helper}` is the helper path named in SKILL.md Step 10.

Both routes start the same work with the same first messages, which the helper builds. They differ only in where each workspace runs and how it is created:

| Route | Each workspace | Created by |
| --- | --- | --- |
| `cloud` | A new Linux cloud workspace in this workspace's project | The helper's `launch`, through the Conductor CLI |
| `local` | A new local workspace on this Mac, in this repository | `CreateWorkspace`, with the messages from the helper's `messages` |

## 1. Choose the issues an agent can finish

Start from the ranked shortlist. Offer an issue only when it is `agent-ready` with startability `ready-to-start` under the autonomous agent-readiness checklist in `scoring-rubric.md`; classify it now when `--agent-ready` was not requested. Judge startability for the route's workspace:

- `cloud`: an issue whose work or verification needs the user's Mac, admin or account settings, credentials the workspace lacks, or a person's decision or sign-off is not ready to start there.
- `local`: the run has this Mac and the tools and credentials the user already gave agents here. An issue that needs admin or account settings an agent cannot change, a credential the user has not given agents, or a person's decision or sign-off is still not ready to start. Also require the exact `branchName` from Linear to be available for a new local branch. Validate it against `[A-Za-z0-9][A-Za-z0-9._/-]*` and `git check-ref-format --branch` before checking `git show-ref --verify --quiet 'refs/heads/{branchName}'` in this repository. Offer the issue only on exit 1, which means the exact ref is absent. Exit 0 means it already exists, including branches checked out in another worktree. A missing or invalid branch name or a Git error makes the issue ineligible for local launch.

List every shortlisted issue you leave out with the checklist item it fails. If no issue qualifies, say so and end.

## 2. Ask once

Ask these questions in one message and wait for the answer:

1. Whether to start the offered issues (all of them, a named subset, or none), each in its own new Conductor workspace of the route's kind whose first message runs `trackbed:linear:issue-to-pr {ISSUE-ID} --ship`. Say that each workspace implements the issue, reviews it, and opens and stabilizes a Pull Request. Name every offered issue whose state type is `unstarted`, such as a To-do issue: a yes here also confirms moving it to its started status, so `trackbed:linear:issue-to-pr` does not ask again in that workspace while the issue is still `unstarted` when the run reaches its state gate. Name every other offered issue whose state type is not `backlog`, such as a `started` issue: issue-to-pr still asks once in that workspace before taking it over, and waits there for a yes. Repeat any coordination caveat from the report, such as two issues that edit the same files. On the `local` route, say that runs can proceed in parallel on this Mac after each workspace finishes setup, with separate worktrees and dev-server ports and the user's local credentials.
2. Only when at least one offered issue has Medium or High UI/UX work: whether those issues should use a different model than the None and Low ones. Name the default, this session's agent and model: `session_model` from `detect` on the `cloud` route, or the `agent` and `model` of the session that Conductor's `WhoAmI` tool returns on the `local` route. Show the models the user can pick, with their agents: run `conductor model` on the `cloud` route, and call Conductor's `ListModels` tool for the `claude` and `codex` agents on the `local` route.
3. Whether the launched runs should use `--adversarial-review`: send their tracked snapshot, committed diff, and frozen issue requirements to the provider opposite each workspace's host for medium- and high-risk review. Explain that disagreements can pause a run for the user's decision. Only an explicit yes to this question in this session enables it; an unanswered question means no independent review, even when the user confirmed launching the issues.

Treat anything other than a clear yes with a selection as no, and start nothing. When the default model is unknown, also ask which model the other issues should use. Accept only the `claude` and `codex` agents, because other agents cannot run this plugin's skills.

## 3. Start the confirmed issues

### Cloud route

Run the helper once with every confirmed issue, in ranked order:

```bash
python3 "{cloud-launch-helper}" launch --project-id '{project_id}' [--adversarial-review] [--unstarted '{ISSUE-ID}' [--unstarted ...]] --item '{ISSUE-ID}' '{agent}' '{model}' [--item ...]
```

- The default agent is `claude` when this session runs in Claude Code and `codex` when it runs in Codex, with `session_model` or the model the user named.
- Medium and High UI/UX issues use the agent and model the user picked for them; every other issue uses the default.
- Validate each issue identifier and model id before interpolating it, and pass every value as its own single-quoted argument.
- Pass `--unstarted '{ISSUE-ID}'` for every confirmed issue whose state type, as fetched in this run, is exactly `unstarted`. The helper then writes `--launch-confirmed` into that issue's first message, which carries the user's yes to issue-to-pr. Never pass it for any other state type.
- Pass `--adversarial-review` only after that separate explicit yes. The helper writes the flag into each first message; never compose or edit a launch message yourself, and never infer consent from settings, environment variables, installed CLIs, or an earlier session.

The helper builds each first message for its agent, creates the workspaces one at a time, and stops at the first failure. Conductor does not deduplicate workspace creation, so a lost response may still have created a workspace. The helper retries only an HTTP 429 rate limit, which creates nothing, after the wait Conductor names, and waits at most one minute in total across the run. Run it in the foreground with the longest command timeout the host allows, at least 10 minutes, because a killed helper reports nothing. Never run `launch` again for the same issues in this run, and never create workspaces with `conductor` directly.

### Local route

Repeat the local branch check for the confirmed issues after the user's answer. Report any issue that is no longer eligible and omit it from the launch. Apply the same agent, model, `--unstarted`, and `--adversarial-review` rules as the cloud route, then run the helper once with the remaining confirmed issues, in ranked order. If none remain, end without calling the helper.

```bash
python3 "{cloud-launch-helper}" messages [--adversarial-review] [--unstarted '{ISSUE-ID}' [--unstarted ...]] --item '{ISSUE-ID}' '{agent}' '{model}' [--item ...]
```

It validates the items exactly as `launch` does and returns one `message` per issue without calling Conductor. Then create the workspaces one at a time, in its order:

1. Generate three new UUIDs for the issue, a workspace ID, a session ID, and a message ID, and keep them for every retry of this issue.
2. Call `CreateWorkspace` with `workspaceId`, `name` set to the issue identifier, and `firstSession` holding the session ID, the message ID, the item's `agent` and `model`, and its `message` exactly as the helper returned it. Leave out `repositoryId`, so the workspace uses this repository, and `baseBranch`, because issue-to-pr resolves its own base. Never compose, edit, or append to a message.
3. When the call returns the workspace, record `created` with its `appUrl` when present. When it returns an error, record `rejected` with the error. When it times out or returns nothing usable, call it once more with the same three IDs, which returns what the first call created instead of creating a second workspace; if that also fails, record `unknown`.
4. Stop at the first issue that is not `created`, and record every later issue as `not_started`.

`CreateWorkspace` can return before Conductor creates the worktree, runs setup, and sends the first message. After the last call, read each created workspace's state once with `GetWorkspaces` when present. Record `failed` with its `failureReason` for a `failed` workspace, or explain that startup failed and Conductor cleaned up the workspace for an ID in `missingIds`. Record `ready` or `initializing` as returned. If the state check is unavailable or fails, record `startup_unverified`. Do not wait for implementation. Never create a failed or `unknown` issue again in this run, never use the `conductor` CLI on this route, and never message, cancel, or archive the workspaces you created.

## 4. Report

Use only the headline for the selected route.

```text
Conductor cloud workspaces: {started} of {confirmed} started
Conductor local workspaces: {ready} of {confirmed} ready
| Issue | UI/UX work | Agent and model | Workspace | Outcome |
| --- | --- | --- | --- | --- |
| ... | ... | ... | ... | ... |
```

- Count `created` on the cloud route and `ready` on the local route in the headline. Link their workspace through `deep_link` or `appUrl`, respectively.
- `initializing` or `startup_unverified`: link the local workspace when possible and report that startup is pending or unverified.
- `unknown`: say that the workspace may exist and to check Conductor before starting that issue again.
- `auth_error`: say that this workspace's Conductor credential cannot create workspaces, and that a user API key in `CONDUCTOR_API_KEY` may allow it.
- `rejected`: report the CLI's `detail`, or the error `CreateWorkspace` returned.
- `failed`: report the failure reason and link the workspace if it still exists. Say that no run started.
- `rate_limited`: say that Conductor kept rate-limiting workspace creation, that no workspace was created for that issue, and that it can be started again later.
- `not_started`: report the issue whose branch became unavailable or that was skipped after an earlier launch failure, with the reason.
