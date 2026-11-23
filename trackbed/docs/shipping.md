# Implementing and Shipping

This guide covers the skills that implement work and publish it as a Pull Request. [Workflows](../../README.md#workflows) has the short version of each one.

| You want to | Run | Read |
| --- | --- | --- |
| Take a Linear issue to an open Pull Request | `/trackbed:linear:issue-to-pr <ISSUE-ID> --ship` | [Linear Issue to Pull Request](#linear-issue-to-pull-request) |
| Implement a saved plan the same way | `/trackbed:code:plan-to-pr <plan> --ship` | [Plan to Pull Request](#plan-to-pull-request) |
| Publish the branch you have | `/trackbed:pr:create` | [Publishing a Pull Request](#publishing-a-pull-request) |
| Get an open Pull Request ready to merge | `/trackbed:pr:shape-up` | [Shaping Up an Open Pull Request](#shaping-up-an-open-pull-request) |
| Move every Conductor workspace of a repository toward merge | `/trackbed:conductor:showtime` | [Driving Conductor Workspaces to Merge](#driving-conductor-workspaces-to-merge) |
| Rewrite a branch's commits into a clear history | `/trackbed:git:recreate-commits` | [Rewriting History](#rewriting-history) |
| Start new work from a branch other than the default | `git config --local trackbed.baseBranch <branch>` | [Base Branch](#base-branch) |

Two things hold across these skills. When a run cannot decide something safely, it stops with a [decision request](#decision-requests). And five of them [run without prompts](#unattended-by-default) unless you pass `--manual`.

## Linear Issue to Pull Request

`/trackbed:linear:issue-to-pr` takes one Linear issue through implementation, review convergence, verification, and optional publication. The [issue-to-pr definition](../skills/linear:issue-to-pr/SKILL.md) owns Linear sequencing and shipping safeguards.

```text
/trackbed:linear:issue-to-pr DISC-202 --ship             # implement, review, verify, open the PR, and fix CI
/trackbed:linear:issue-to-pr DISC-202                    # stop after verification, before anything is published
/trackbed:linear:issue-to-pr DISC-202 --continue --ship  # resume an interrupted run
```

You get a branch with the implementation committed, a [final report](#final-reports) that starts with what you need to check or decide, and with `--ship` an open Pull Request whose checks pass.

### Before Implementation

Before implementation, `issue-to-pr` validates Linear's target branch and verifies that it has no existing Pull Request or remote branch on `origin`. A normal invocation requires a clean tree.

It shows the resolved issue identifier and title before any mutation. Intake stops on research, decision, or diagnosis-only issues and parents whose work is already split into sub-issues, naming a suggested skill without invoking it. Unclear cases proceed through the existing implementation gates.

`--continue` instead preserves an interrupted local implementation only when all of these hold:

- Linear already places the issue in the resolved started status;
- the current branch exactly matches its unpublished issue branch;
- no Git operation is in progress;
- local work exists relative to the fetched base;
- every committed or dirty path is issue-related.

Unrelated or ambiguous work remains a blocker.

### Starting the Issue

A Backlog issue is moved automatically to the team's resolved started status, preferring a status named In Progress. Any other current state requires explicit confirmation before the status changes or implementation starts.

- `issue-to-pr` owns that authorization, status resolution, and confirmation, then hands the gated write to `/trackbed:linear:issue-implement --set-in-progress`.
- That child repeats the pre-write race close, updates the status field alone, and verifies it by reading the issue back before it creates a branch.
- Resume mode never performs this transition.

`--launch-confirmed` supplies that confirmation for an issue whose state type is still `unstarted` at the gate, such as a To-do issue. `/trackbed:linear:next` writes it into the first message of a cloud or local workspace it starts after your yes, or you can type it yourself. Started, completed, and canceled issues still ask.

Once the state gate passes, a detected Conductor workspace is renamed best-effort to `ISSUE-ID: normalized issue title`. Detection uses `CONDUCTOR_WORKSPACE_PATH`; a missing workspace identifier skips the rename before probing the CLI. Missing CLI access, authentication, or rename support is reported without blocking canonical work. Continuations preserve the existing workspace name.

### Review, Verification, and Shipping

After implementation, `issue-to-pr` freezes the Linear issue's bounded requirements and delegates the prepared branch to `trackbed:pr:review-convergence`. The [review guide](review.md#review-convergence) describes the gates, remediation budget, and review profiles.

- With `--strict`, every review finding receives an evidence-based disposition rather than blind implementation.
- With `--adversarial-review`, review includes a pass by the model provider opposite your host on medium- and high-risk work, and the final report gains an `Independent review` line.
- With `--ship`, `issue-to-pr` opens the Pull Request against the validated base branch and runs `/trackbed:pr:fix-ci --no-consolidate` until CI and review feedback are clear.
- If the base moves after the Pull Request opens, `/trackbed:pr:fix-ci` keeps the pushed head without asking unless the movement touches the Pull Request's files, CI configuration, lockfiles, or shared build tooling. Then it asks whether to rebase.
- Add `--rebase` or `--no-rebase` to `--ship` to answer in advance. `--rebase` rebases the Pull Request once through `/trackbed:pr:rebase --force-push`, and `--no-rebase` never rebases or asks. The final report's `Base drift` line says what happened.
- Omit `--ship` to stop after implementation, review, and verification.

The checked independent-review line also goes into the generated PR description. If CI remediation changes the tree, the final validation pass requests another provider review unless the full change's stable patch ID matches the completed review. A light-profile skip cannot be reused as a completed review.

### Implementing an Issue Directly

`/trackbed:linear:issue-implement` fetches issue details plus referenced Linear issues/documents when accessible, reports inaccessible referenced assets, and uses that context during planning.

It writes to Linear only with `--set-in-progress`. That flag moves the issue to its team's resolved started status, preferring a status named In Progress, before branch setup. It asks for confirmation first when the issue is not in Backlog, and stops without creating a branch if that transition is declined or unverified.

Stack history rewrites capture every remote branch's original commit before fetching or rebasing. The shared publisher sends explicit commits in one atomic push with those frozen leases; a later fetch cannot accept a collaborator's intervening push. Routine stack sync separates local rebase, publication, and PR metadata updates, retaining the snapshot when any phase fails.

## Plan to Pull Request

`/trackbed:code:plan-to-pr` implements one self-contained `PR_PLAN_*.md` and uses the same review-convergence phase as `issue-to-pr`, preserving its own requirements and scope contract.

Its `--continue` mode requires the selected archived plan already to be `IN_PROGRESS`, the exact deterministic unpublished plan branch, and only in-scope existing changes.

`/trackbed:code:breakdown-findings --reconcile` can infer `DONE` from a proven merged plan branch only while the selected in-scope source state still matches the landed implementation. Later scoped changes or reversions require review and block automatic completion and dependent unblocking, including with `--auto`. When other work has already fixed a plan's problem, reconcile proposes closing the plan as `SUPERSEDED` instead of refreshing it, and waits for your confirmation, even with `--auto`.

## Final Reports

When `issue-to-pr` or `plan-to-pr` finishes successfully, its report puts what needs you first. Every report has the same order:

1. The outcome in one or two sentences, with the Pull Request link when there is one.
2. **Needs your attention:** questions the issue or plan left open, choices the run made on its own, things it could not verify, judgment calls and risks review surfaced, and limitations. Each item says what to check or decide, with a suggested answer when there is one. When nothing needs you, the report says so.
3. **What was done:** the change as built.
4. **What review uncovered:** what the review gates found and what happened to each finding.
5. The status block, last, with the field names later steps and tools read.

Shipped reports describe the final tree: they merge CI fixes and the final validation pass when publication changed the branch. `issue-to-pr` also passes the prose parts through `trackbed:text:clarify` for plain-language editing. The [shared format](../shared/implementation/references/final-report.md) defines every rule.

## Decision Requests

When `issue-to-pr` or `plan-to-pr` stops and waits for you, it shows a decision request instead of a status report. A blocked run never reuses the success report. Every request has the same order:

1. `Decision needed`, the issue or plan label, and the question, all on the first line.
2. Only the evidence that changes the choice.
3. Numbered options. The recommended one comes first and is marked, and each says what happens next.
4. One `State:` line: what is published, what is not, and where the details are.

The run recap and review notes stay out; they belong in the final report. Several decisions are numbered separately. When review stops for you, `pr:review-convergence` writes the request itself, and the workflow shows it unchanged with its own `State:` line. A stop that needs an action, such as missing access, says what is needed, why, and the state.

```text
Decision needed · SKILLS-22: resume review for the open finding, or stop here?

Review used its whole fix budget and one required finding is open: no
test covers an end tag outside a dropped region. The reviewer proposed
two tests that would close it.

1. Resume review (recommended): starts a new fix budget of up to 2 cycles
   for this finding, adds the two tests, and reruns review and full
   verification; the proposed tests should close it.
2. Stop here (0 cycles): the branch stays local for you to finish by hand.

State: nothing pushed, no PR, working tree clean; review archive in .context/linear-issue-to-pr/reviews/.
```

When the host has a question dialog and the choice is a few fixed options, the request uses it: a short header, the question and evidence in the question, and each option's consequence in its description. Cancelling the dialog is not an answer: the workflow repeats the request as a message and stops without choosing for you.

Questions raised during implementation use the same format. `issue-implement` collects every question that blocks its plan and asks them all in one request. `work-from-plan` returns its blocking question with options and a recommendation, and `plan-to-pr` shows it without rewriting it.

The [shared format](../shared/implementation/references/decision-request.md) defines every rule.

## Unattended by Default

These five skills run in auto mode when you type them. Pass `--manual` to keep their prompts.

| Command | Default | With `--manual` |
| --- | --- | --- |
| `/trackbed:pr:create` | Commits all uncommitted work, rewrites unpublished history behind a backup unless its commits are already well formed, and publishes without a final confirmation | Asks about uncommitted work and commit structure, and confirms before publishing |
| `/trackbed:git:recreate-commits` | Chooses the granularity, rewrites history, and force-pushes with a lease | Asks for the granularity on a large diff, and confirms before the reset and the push |
| `/trackbed:pr:fix-ci` | Decides whether to rebase a stale branch, and consolidates `[FIX PIPELINE]` commits | Asks about both |
| `/trackbed:pr:generate-description` | Skips its prompts and updates an open Pull Request directly | Asks its clarifying questions and prints the result for copy-paste |
| `/trackbed:pr:rebase` | Continues past red flags and force-pushes with a lease, without verification | Keeps every conflict, red-flag, verification, and confirmation gate |

- `/trackbed:pr:rebase --force-push` is the safe unattended option: it skips only the final confirmation and keeps every other gate. Both skills that delegate a rebase use it.
- `/trackbed:pr:fix-ci --no-consolidate` also turns off auto mode, so `--ship` never rebases an open Pull Request without your `--rebase` flag or your answer; `--manual` asks every time.
- `--check`, `--all-open`, and `--scope-plan` keep their own gates.
- The default covers only the message being answered: a slash command or `$` mention at its start, or the skill's name later in it when your wording asks for a run. A saved prompt your host sends as your message counts too. The parent delegations each skill names keep the gates their own flags select.
- A mention that only discusses the skill, a request from an earlier message, and a request that arrives through another agent, including a subagent that preloads the skill or a Conductor message that another chat sent, do not. In those cases, and when the model picks one of these skills for a request that does not name it, the skill behaves as `--manual`, or as `--no-update` for `trackbed:pr:generate-description`.

The [decision record](decisions/2026-10-31-unattended-default-for-shipping-skills.md) covers the tradeoffs.

## Publishing a Pull Request

`/trackbed:pr:create` is fully non-interactive by default, including the backup-protected local history rewrite when applicable and final publication.

- It chooses documented deterministic branch defaults or stops on a hard blocker without asking a question or opening a terminal credential prompt.
- It never publishes placeholder title/body content.
- It restores the invocation's entry checkout on failures before publication when the captured local state is still safe to restore.
- After an ambiguous publication attempt, it preserves the prepared local state for recovery.

### Existing Remote Branches

Fresh branches require remote absence and an absence-leased publication. A current branch that already exists remotely can preserve its published commits:

- a clean exact-tip remote skips the push;
- a clean remote tip that is a strict ancestor of local `HEAD` receives one OID-leased fast-forward;
- dirty auto-mode work is committed and reorganized only after the observed remote tip before the same OID-leased append.

These remain hard blockers: non-current branches, open Pull Requests, ambiguous, credential-bearing, executable, or unsupported push destinations, hidden tracked changes, remote-only commits, genuine divergence, and any remote change after classification.

### Commit History

A direct invocation on a fresh branch keeps unpublished commits that already follow the repository's commit conventions instead of rewriting them. `trackbed:code:plan-to-pr` and `trackbed:linear:issue-to-pr` always get the narrative rewrite.

### Screenshots

For a change a reviewer can see, `/trackbed:pr:create` tries to put before and after screenshots in the description, side by side. `gh pr create --attach` uploads them, so it needs GitHub CLI 2.102 or later and a github.com repository.

- **After.** `trackbed:pr:generate-description` captures the changed screen from a running local app. When nothing is running, it starts the app once, but only with the base branch's unchanged development command, with dependencies already installed and no install, migration, or credential step.
- **Before.** It never runs the old version. It uses an image you pass, an image on the linked issue, a URL you named for the old version, or an old state the current app can still show. Otherwise the description gets the after image and one sentence about the old state.
- **Video.** Only for motion or a multi-step interaction a still image cannot show.
- **Your own files.** Pass `--attach before.png --attach after.png`, starting each alt text or file name with `Before` or `After` to pair them. A file inside the repository must be committed or ignored, or the run stops, because the run would otherwise commit it.

A failed capture or upload never blocks the Pull Request; the closing message says what was attached or why nothing was. Capture uses only an app served from this checkout, and it reports any file it leaves in the worktree. Pass `--no-capture` to skip it. Files are staged under `.trackbed/pr-evidence/`, which Git ignores locally; `trackbed:workflow:cleanup-artifacts` removes them.

### Artifacts

`/trackbed:pr:create` can attempt to attach Markdown, text, and HTML documents through [GitHub's preview issue artifacts API](https://docs.github.com/en/rest/issues/artifacts#create-an-issue-artifact). GitHub documents this API for issues. Successful creation and display on Pull Requests are unverified.

- **What is uploaded.** Documents about this change that a reviewer looks at or decides from, in this order: a prototype or a page that explains the change, such as a walkthrough or diagram; a decision record or decision page; then the plan or specification, research notes, or a root-cause analysis.
- **Review output.** At most one QA, review, or audit report, and only when it adds what the diff and description lack: what was tested and the result, or a finding accepted instead of fixed. Archived review reports under `.context/<workflow>/reviews/` are never collected.
- **Screenshots.** Artifacts are text documents. Images and videos travel as attachments; see [Screenshots](#screenshots).
- **What is not.** Logs, drafts, and other working state, anything you supplied as input, files Git already tracks, plans the change no longer follows, decision pages that do not show what was chosen, and review or audit reports with a finding that is neither fixed nor accepted.
- **The check.** The workflow stages the exact bytes it inspects and skips documents containing credentials, personal or customer data, internal addresses, or unfixed security weaknesses. Private excerpts and security write-ups require a confirmed private or internal destination.
- **Local reports.** If the include-all commit would pick up a local-only report, auto mode stops and manual mode offers to stash and exclude uncommitted work. Move untracked reports outside the checkout or make Git ignore them. Documentation intended for the diff stays part of the normal commit flow.
- **Your own files.** Pass `--artifact plan.md`, adding `#name` to name the artifact. The workflow validates explicit files before any rebase. A file inside the repository must be ignored or committed without local changes.

The upload attempt happens after the Pull Request exists. The closing message distinguishes confirmed and uncertain results and includes any returned artifact links. Pass `--no-artifacts` to collect only the files you name. `trackbed:workflow:cleanup-artifacts` removes local copies from `.trackbed/pr-artifacts/`.

`trackbed:linear:issue-to-pr --ship` and `trackbed:code:plan-to-pr --ship` disable automatic document uploads. The Linear workflow also deletes its review reports and other disposable files before creating the Pull Request.

Review archives stay local during automatic collection. A direct `/trackbed:pr:create` invocation can still collect eligible archived plans. Pass `--artifact` to attach an archived report yourself.

## Shaping Up an Open Pull Request

`/trackbed:pr:shape-up` gets the current branch's open Pull Request ready to merge in one run. It reads the Pull Request first and runs only the passes it needs; a Pull Request that is already in shape gets a report and nothing else.

| Need | What starts it | What handles it |
| --- | --- | --- |
| Rebase | The branch is behind the Pull Request's target branch | The first `trackbed:pr:fix-ci --rebase --no-consolidate` pass, which rebases through `trackbed:pr:rebase --force-push` |
| Green CI | A check that was not skipped failed, was cancelled, or is still running | The `trackbed:pr:fix-ci` pass, which fixes and pushes until the checks are green; later rounds pass `--no-rebase` instead of `--rebase` |
| AI review comments | An unresolved inline thread from a bot or app reviewer, such as CodeRabbit or Copilot, that you have not answered | The `trackbed:pr:fix-ci` pass makes the valid code changes, then `trackbed:pr:github-review-reply --bot-only` posts replies and resolves the threads they settle |

- The skill takes no arguments and never edits, commits, pushes, or posts by itself. The two delegated skills keep every gate they have when you run them directly, and their questions and blockers reach you unchanged.
- The rebase keeps its conflict, red-flag, verification, and lease gates. The pass's `[FIX PIPELINE]` commits stay as they are; run `/trackbed:pr:fix-ci` afterwards to consolidate them.
- It never answers a person. The `trackbed:pr:fix-ci` pass still validates all review feedback, so it may fix a valid request from a person; reply to people with `/trackbed:pr:github-review-reply`.
- Feedback an AI reviewer left only in a review summary or a Pull Request comment does not start a run by itself. When the reply pass runs, it covers those too.
- Your checkout must match the Pull Request head. Push or pull first when it does not.
- It repeats for at most three rounds, for checks that are not green or AI threads that arrived during the run. Only the first round may rebase, so a target branch that moves during the run is reported, not chased.
- The final report says `in shape` only when a fresh read of the Pull Request shows no need left.

The delegation is recorded in the [orchestration-children decision](decisions/2026-08-29-model-invocable-orchestration-children.md#pull-request-shape-up-delegations).

## Driving Conductor Workspaces to Merge

`/trackbed:conductor:showtime` takes one pass over every Conductor workspace of the current repository and moves each one a step toward a merged Pull Request. It runs only in a local Conductor workspace. Run it again for the next step, or under `/loop` in Claude Code to keep going.

A helper script reads the workspaces, their chats, your open Pull Requests, and each checkout, and places every workspace on one stage:

| Stage | What it means | What the pass does |
| --- | --- | --- |
| Agent working, Checks running | A chat is running, or required checks are pending | Nothing |
| Work done, no PR | Committed work, a clean checkout, and no Pull Request | Sends the chat `trackbed:pr:create` |
| PR not in shape | A conflict, a branch that must be up to date and is behind, a failing required check, stale checks, or an open thread from an AI reviewer | Sends the chat `trackbed:pr:shape-up` |
| Merge-ready | The Pull Request passes the merge gate and matches no hold rule | Merges it (asks first without `--auto`) |
| Held | It passes the gate and matches a hold rule | Reports it with the reason |
| Merged | The checkout is at the head of a merged Pull Request | Archives the workspace (asks first without `--auto`) |
| Everything else | A question, a setup failure, uncommitted changes, human review, a draft, a missing required review, a branch behind a past Pull Request | Reports it in the table; the ones that need you appear under "Waiting on you" |

- **It never changes code.** A change happens in the workspace's own chat, through one of those two commands, each with every gate it has when you type it.
- **Commands go to idle chats only.** A chat must have been idle for ten minutes, and a chat whose last message is a question gets none. The same problem gets at most two commands.
- **The merge gate.** A Pull Request merges only when it is your own, targets the default branch, and is not a draft; its required checks are green; it has no unresolved review thread, no conflict, no missing required review, and no other branch-protection block; its chat is idle and its checkout has nothing uncommitted; and its checks are not stale.
- **Stale checks.** Checks are stale when a commit that reached the default branch after the Pull Request's head commit touches a file it changes, CI configuration, a lockfile, or shared build tooling. Such a Pull Request is rebased by `trackbed:pr:shape-up` and must go green again.
- **Hold rules.** A Pull Request that passes the gate is held when its risk signals are high or could not be computed, when it is marked as a breaking change, or when a person's latest review requests changes or a person's comment is unanswered.
- **Merging.** The helper rechecks the gate for each PR in the repository at `origin`, merges synchronously with the approved head pinned, skips a PR the recheck refuses, and rebuilds the board once when the train ends. Repositories requiring a merge queue need to use GitHub for that step.
- **The sidebar.** Workspaces move into the sections "Working", "Needs me", "Needs a nudge", "Merge-ready", and "Merged". One you placed in a section of your own, or pinned, stays there.

Without `--auto`, you can approve the PR commits and archive candidates shown in the preview. With `--auto`, the pass merges unheld PRs, archives eligible workspaces, and answers a chat that stopped on a [decision request](#decision-requests) with the first option when that option alone is marked recommended. A chat that waits on a dialog or a permission prompt is never answered. Conductor applies **Delete branch on archive** to each archive.

An open Pull Request whose workspace is gone can still pass the gate and merge. Showtime starts no new work; `/trackbed:linear:next` does that. The design is recorded in the [showtime decision](decisions/2026-11-22-conductor-showtime.md).

## Rewriting History

By default, `/trackbed:git:recreate-commits` authorizes one backup-protected unstacked history rewrite and any required lease-protected force-push. Before it resets anything, it:

- rejects visible or assume-unchanged tracked edits, ordinary untracked work, and reset-colliding ignored work;
- refuses mismatched or base-branch upstreams, renamed push destinations, and effective push-destination commits missing locally;
- honors `branch.<name>.pushRemote` and `remote.pushDefault`;
- freezes one push URL, branch, and lease, and disables tag following;
- revalidates the checkout immediately before reset.

Automatic stack-wide rewriting additionally requires `--authorize-history-rewrite`. A `--manual` stacked invocation may instead use separate interactive confirmations that enumerate the full stack before authorizing the local reset/restack and the atomic whole-stack force-push.

`trackbed:pr:rebase` and routine syncs in `trackbed:pr:stack` fetch every open branch and stop if local and remote histories diverge. Integrate those commits before retrying; behind-only branches are allowed. Stack pushes and syncs clear `GH_STACK_NO_ATOMIC` to keep Git ref updates atomic. PR/API updates remain separate.

## Verification

The optional regression red-green check in `/trackbed:verify:run` restores the fix by stash commit ID and retains the stash entry, reporting its tag and commit ID for later identification. It leaves cleanup to the user because other workspaces share the stash list.

## Base Branch

The skills select a workbench branch separately for each repository. Review of an existing Pull Request uses its target branch; creating independent work uses the repository workbench even when the current branch has a Pull Request.

For new work, set the local Git configuration when the workbench differs from the remote default:

```bash
git config --local trackbed.baseBranch development
```

Repositories configured before 1.0.0 can keep `kramme.baseBranch`; the skills read it when `trackbed.baseBranch` is unset.

If batch rebase previously protected a branch through your global Git configuration, set that branch with `git config --local trackbed.baseBranch <branch>` in each affected repository.

- For a repository where `main` is the workbench and releases use tags, the remote default can remain `main`; no setting is needed when Conductor also names `main`. Set `trackbed.baseBranch` to `main` if a host suggests a different branch.
- An explicit `--base <branch>` on a base-aware skill overrides the default for that run.
- Without an explicit or local setting, the shared resolver checks Conductor's configured branch when it has a local `origin` tracking ref, then the remote default, `origin/main`, and `origin/master`. It gets the remote default from `origin/HEAD` or queries `origin` when that symbolic ref is unavailable.
- A failed GitHub PR lookup stops existing-branch workflows unless GitHub confirms there is no PR; it cannot silently choose the workbench.
- New worktrees can use a cached workbench ref during a fetch failure, and local repositories without `origin` or a configured workbench start from `HEAD`.

Configure the workbench in each repository rather than assuming a branch's role from its name.
