# Implementing and Shipping

This guide covers the workflows that implement work and publish it as a Pull Request: choosing the base branch, Linear issue to Pull Request, plan to Pull Request, Pull Request creation, history rewrites, and verification. The root [README](../../README.md#workflows) has the short version of each workflow.

## Base Branch

The skills select a workbench branch separately for each repository. Review of an existing Pull Request uses its target branch; creating independent work uses the repository workbench even when the current branch has a Pull Request.

For new work, set the local Git configuration when the workbench differs from the remote default:

```bash
git config --local trackbed.baseBranch development
```

Repositories configured before 1.0.0 can keep `kramme.baseBranch`; the skills read it when `trackbed.baseBranch` is unset.

- For a repository where `main` is the workbench and releases use tags, the remote default can remain `main`; no setting is needed when Conductor also names `main`. Set `trackbed.baseBranch` to `main` if a host suggests a different branch.
- An explicit `--base <branch>` on a base-aware skill overrides the default for that run.
- Without an explicit or local setting, the shared resolver checks Conductor's configured branch when it has a local `origin` tracking ref, then `origin/HEAD`, `origin/main`, and `origin/master`.
- A failed GitHub PR lookup stops existing-branch workflows unless GitHub confirms there is no PR; it cannot silently choose the workbench.
- New worktrees can use a cached workbench ref during a fetch failure, and local repositories without `origin` or a configured workbench start from `HEAD`.

Configure the workbench in each repository rather than assuming a branch's role from its name.

## Linear Issue to Pull Request

`/trackbed:linear:issue-to-pr` takes one Linear issue through implementation, review convergence, verification, and optional publication. The [issue-to-pr definition](../skills/linear:issue-to-pr/SKILL.md) owns Linear sequencing and shipping safeguards.

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

`--launch-confirmed` supplies that confirmation for an issue whose state type is still `unstarted` at the gate, such as a To-do issue. `/trackbed:linear:next` writes it into the first message of a cloud workspace it starts after your yes, or you can type it yourself. Started, completed, and canceled issues still ask.

Once the state gate passes, a detected Conductor workspace is renamed best-effort to `ISSUE-ID: normalized issue title`. Detection uses `CONDUCTOR_WORKSPACE_PATH`; a missing workspace identifier skips the rename before probing the CLI. Missing CLI access, authentication, or rename support is reported without blocking canonical work. Continuations preserve the existing workspace name.

### Review, Verification, and Shipping

After implementation, `issue-to-pr` freezes the Linear issue's bounded requirements and delegates the prepared branch to `trackbed:pr:review-convergence`. The [review guide](review.md#review-convergence) describes the gates, remediation budget, and review profiles.

- With `--strict`, every review finding receives an evidence-based disposition rather than blind implementation.
- With `--adversarial-review`, review includes a pass by the model provider opposite your host on medium- and high-risk work, and the final report gains an `Independent review` line.
- With `--ship`, `issue-to-pr` opens the Pull Request against the validated base branch and runs `/trackbed:pr:fix-ci --no-consolidate` until CI and review feedback are clear.
- Omit `--ship` to stop after implementation, review, and verification.

The checked independent-review line also goes into the generated PR description. If CI remediation changes the tree, the final validation pass requests another provider review unless the full change's stable patch ID matches the completed review. A light-profile skip cannot be reused as a completed review.

### Reviewer Handoff Summary

When the workflow finishes successfully, its report closes with a reviewer handoff summary: what was implemented, what the convergence review uncovered, and what to focus on when reviewing the result. The focus list covers open questions, decisions the workflow made autonomously, and deferred optional findings.

Shipped summaries merge CI remediation and final-tree validation evidence when publication fixes changed the branch, then pass the complete prose through `trackbed:text:clarify` for plain-language editing.

### Implementing an Issue Directly

`/trackbed:linear:issue-implement` fetches issue details plus referenced Linear issues/documents when accessible, reports inaccessible referenced assets, and uses that context during planning.

It writes to Linear only with `--set-in-progress`. That flag moves the issue to its team's resolved started status, preferring a status named In Progress, before branch setup. It asks for confirmation first when the issue is not in Backlog, and stops without creating a branch if that transition is declined or unverified.

## Plan to Pull Request

`/trackbed:code:plan-to-pr` implements one self-contained `PR_PLAN_*.md` and uses the same review-convergence phase as `issue-to-pr`, preserving its own requirements and scope contract.

Its `--continue` mode requires the selected archived plan already to be `IN_PROGRESS`, the exact deterministic unpublished plan branch, and only in-scope existing changes.

`/trackbed:code:breakdown-findings --reconcile` can infer `DONE` from a proven merged plan branch only while the selected in-scope source state still matches the landed implementation. Later scoped changes or reversions require review and block automatic completion and dependent unblocking, including with `--auto`.

## Decision Requests

When `issue-to-pr` or `plan-to-pr` stops and waits for you, it shows a decision request instead of a status report. A blocked run never reuses the success report. Every request has the same order:

1. `Decision needed`, the issue or plan label, and the question, all on the first line.
2. Only the evidence that changes the choice.
3. Numbered options. The recommended one comes first and is marked, and each says what happens next.
4. One `State:` line: what is published, what is not, and where the details are.

The run recap and review notes stay out; they belong in the final report. Several decisions are numbered separately. A stop that needs an action, such as missing access, says what is needed, why, and the state.

```text
Decision needed · SKILLS-22: resume review for the open finding, or stop here?

Review used its whole fix budget and one required finding is open: no
test covers an end tag outside a dropped region. The reviewer proposed
two tests that would close it.

1. Resume review (recommended): starts a new fix budget for this finding,
   adds the two tests, and reruns review and full verification.
2. Stop here: the branch stays local for you to finish by hand.

State: nothing pushed, no PR, working tree clean; review archive in .context/linear-issue-to-pr/reviews/.
```

When the host has a question dialog and the choice is a few fixed options, the request uses it: a short header, the question and evidence in the question, and each option's consequence in its description. Cancelling the dialog is not an answer: the workflow repeats the request as a message and stops without choosing for you.

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
- `/trackbed:pr:fix-ci --no-consolidate` also turns off auto mode, so `--ship` never rebases an open Pull Request without asking.
- `--check`, `--all-open`, and `--scope-plan` keep their own gates.
- The default covers only the message being answered: a slash command or `$` mention at its start, or the skill's name later in it when your wording asks for a run. A saved prompt your host sends as your message counts too. The parent delegations each skill names keep the gates their own flags select.
- A mention that only discusses the skill, a request from an earlier message, and a request that arrives through another agent, including a subagent that preloads the skill, do not. In those cases, and when the model picks one of these skills for a request that does not name it, the skill behaves as `--manual`, or as `--no-update` for `trackbed:pr:generate-description`.

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
