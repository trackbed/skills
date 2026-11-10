# Permit Guarded Model-Invocable Orchestration Children

- Status: ACCEPTED
- Date: 2026-08-29
- Amended: 2026-10-15, 2026-10-21, 2026-10-27, 2026-10-31, 2026-11-02, 2026-11-09, 2026-11-10
- Deciders: repository maintainers
- First safety review: 2026-11-29

## Context

Claude Code rejects Skill-tool invocation of any skill with `disable-model-invocation: true`, even when a directly invoked parent skill supplies the call. This made `trackbed:pr:create --auto` unable to invoke its required `trackbed:git:recreate-commits` and `trackbed:pr:generate-description` phases.

A 2026-10-21 review of every skill that hands work to another skill found parents whose instructions still invoke a model-disabled child. Claude Code rejects those calls, and the parent then reads the child's `SKILL.md` and follows it outside the child's own model contract or loses the step. Between 2026-10-06 and 2026-10-20 it rejected 36 calls from `trackbed:code:plan-to-pr` to `trackbed:code:work-from-plan`, plus calls from `trackbed:pr:github-review-reply` to `trackbed:pr:resolve-review` and from `trackbed:pr:github-review` to the former `kramme:pr:ux-review`.

## Decision

Permit a narrow exception to the default rule that side-effecting skills are model-disabled. Apply it only to these exact parent-child relationships:

- `trackbed:git:recreate-commits` is model-invocable only for direct user requests and delegation from `pr:create`. The parent always supplies `--require-unstacked`, `--no-push`, a pinned base commit, and a retry-safe backup ref. The child revalidates unstacked membership at the reset boundary, and the parent repeats that check at publication. The directly invoked parent owns the authorization represented by its auto mode or `--authorize-history-rewrite` and remains the sole remote publisher. Model callers cannot invent `--force-backup`; only `pr:create` may automatically supply its exact derived `--backup-ref`.
- `trackbed:pr:generate-description` is model-invocable, but every model caller must supply `--no-update`, including a caller of its `--check` mode. Only a direct user invocation may omit that guard and update an existing Pull Request.
- `trackbed:linear:issue-implement` is model-invocable only as the child of `trackbed:linear:issue-to-pr`, which must pass `--auto` and, for a fresh run, `--set-in-progress` with its validated status handoff, or, for continuation, its validated `--resume-current-branch` handoff. The child owns the status-only Linear write, applies it before branch setup, repeats the parent's confirmation race close, and verifies the result by reading the issue back. A model caller cannot invent `--set-in-progress`, cannot pass it without the parent-owned handoff, and cannot pass it with `--resume-current-branch`; only a direct user invocation may supply it bare, and it then answers the child's own non-backlog confirmation. The child keeps all Linear, branch, planning, scope, and verification gates.
- `trackbed:pr:review-convergence` is model-invocable only as a child of `trackbed:linear:issue-to-pr` or `trackbed:code:plan-to-pr`, which must pass their exact internal work ID, allowlisted archive key, and sentinel-last requirements handoff. Validation-only and plan-scope flags remain caller-owned and validated by the child.
- `trackbed:workflow:cleanup-artifacts` (renamed from `kramme:workflow-artifacts:cleanup` on 2026-10-27) is model-invocable only as the child of `trackbed:linear:issue-to-pr --ship`, with `--auto`; its destructive inventory, Trash requirement, dirty-artifact checks, and permanent-specification protections remain mandatory. Its `--siw` mode, merged from the former `kramme:siw:remove` on 2026-10-15, is direct-user-only: the child honors `--siw` only when the user typed the slash command or `$` mention with `--siw`, or explicitly asked in this session to retire the SIW workspace or to run cleanup with `--siw`. A model caller must never pass it on its own initiative, including after `trackbed:siw:transfer-to-linear` prints its removal suggestion inside an autonomous loop; the child stops without scanning when `--siw` arrives without that user request, a direct user request still goes through every SIW confirmation, and `--siw` combined with `--auto` fails closed before any scan or deletion.
- `trackbed:pr:create` is model-invocable only as a child of `trackbed:linear:issue-to-pr` or `trackbed:code:plan-to-pr`, with the caller's auto-mode authorization and required generated-description and issue/scope flags. It remains the sole owner of Pull Request publication and its existing backup and lease gates.
- `trackbed:pr:fix-ci` is model-invocable only as a child of `trackbed:linear:issue-to-pr`, `trackbed:code:plan-to-pr`, or `trackbed:pr:rebase`, with the parent's bounded `--no-consolidate`/scope or explicit rebase-mode arguments. It retains all CI, review-feedback, retry, and publication checks.
- `trackbed:pr:rebase` is model-invocable only as a child of `trackbed:pr:fix-ci`, which must pass the exact `--force-push` argument and must not omit it or invent `--fix-ci` or a base override. It retains all branch, stack, conflict, red-flag, verification, lease, and publication gates and remains the sole owner of the validated rebase push.
- `trackbed:pr:convention-review` and `trackbed:pr:overengineering-review` are model-invocable only as read-only gates of `trackbed:pr:review-convergence`, with that parent's inline, requirements, and report-lifecycle arguments. They never edit source or choose dispositions.
- `trackbed:discovery:interview` is model-invocable, including its SIW mode (`--siw`, a bare `siw`, or `siw/` paths), which writes only a new, existence-checked `siw/DISCOVERY_BRIEF.md` or `siw/SPEC_STRENGTHENING_PLAN.md` during an interactive interview. Every model caller, including `trackbed:siw:init` discover mode (which passes exactly `--siw <topic>`), must never pass `--apply`. Only a direct user request may enable `--apply`, which edits existing specifications and moves the strengthening plan to Trash, and the skill still confirms the exact edits in-session before changing any file.

Each child must narrowly route model use, document its least-side-effect model contract, and retain its existing confirmation and validation gates. Focused tests must pin the parent arguments.

Amended 2026-10-31: `trackbed:git:recreate-commits`, `trackbed:pr:create`, `trackbed:pr:fix-ci`, `trackbed:pr:generate-description`, and `trackbed:pr:rebase` now default to auto mode for direct user invocations. [That decision](2026-10-31-unattended-default-for-shipping-skills.md) keeps every other model-initiated call at `--manual`, or at `--no-update` for the description generator.

### Hand-off repair exceptions

Amended 2026-10-21. The exception list above gains these exact edges. Direct user invocation of each child is unchanged.

- `trackbed:code:work-from-plan` is model-invocable only as the implementation delegate of `trackbed:code:plan-to-pr`, after that parent has validated, archived, and claimed the plan on its deterministic plan branch. The parent passes exactly the validated archived plan path as the only argument, plus its continue-mode, prerequisite-readiness, and context-preparation facts as inert parent-owned context. The child implements only a `direct` route on the current branch inside the plan's In Scope paths and returns every other route as the blocker. Under this delegation it never invokes `trackbed:linear:issue-implement`, creates SIW files, requests the source index or other plans of the set, creates or switches branches, commits, pushes, or changes the plan archive; the parent keeps the commit boundary and the archive state. A model caller never passes inline plan text or any other plan path. Focused tests pin the parent's exact hand-off sentence and the child's contract.
- `trackbed:pr:resolve-review` is model-invocable only in `--implement-only` mode with a caller-scoped structured findings payload, and only from two parents. `trackbed:pr:github-review-reply` invokes it only after its user enabled implementation (`--implement`, `--auto`, or an explicit request to address the feedback), passing only the items it classified `needs-code-change`, never the Pull Request URL as the source, and never `--source online`. `trackbed:pr:review-convergence` invokes it only during normal-mode batch remediation, at most once per batch while the worktree is clean, passing only that batch's accepted code-changing findings, and never in validation-only mode. In this mode the child makes no GitHub write, writes no review file, drafts no reply, and creates no commit; it keeps its scope, validity, and verification checks and reports through `.context/resolve-review/implement-only-summary.json`. Each parent keeps reply, resolution, disposition, and commit ownership. A model caller never passes `--team`, `--granular`, `--source`, `--severity`, a URL, or a request without findings. Focused tests pin both parents' exact hand-offs.
- `trackbed:pr:adversarial-review` is model-invocable only as Gate 5 of `trackbed:pr:review-convergence`, and only when that convergence run's `--adversarial-review` came from the user, typed on the invocation or explicitly requested in the same session. That request is the repository-scoped consent the adversarial-review decision requires, and it covers only that convergence run. Since 2026-11-02, `trackbed:linear:issue-to-pr` may forward the flag the user gave its own invocation, under the [issue-to-pr cross-provider review record](2026-11-02-issue-to-pr-cross-provider-review.md), and convergence accepts it only from that caller. `trackbed:code:plan-to-pr` never forwards the flag, and convergence rejects it from that caller. Convergence passes exactly the sentinel-last frozen `--requirements` block, with optional `--provider` and `--model` values before it, and never `--base`. The child stays read-only and fails closed on any provider, authentication, isolation, parse, coverage, or tree-integrity failure. A model caller never adds the review on its own initiative, infers consent from CLI presence or an earlier run, or selects the host provider. Focused tests pin Gate 5's arguments, issue-to-pr's exact forwarding, and the absence of the flag from plan-to-pr.

These hand-off repairs need no side-effect exception:

- Under the 2026-11-02 cross-provider review decision, `trackbed:linear:issue-to-pr` may append one validated `--independent-review-line <line>` to its existing guarded `trackbed:pr:create` invocation. Creation forwards the same inert evidence to `trackbed:pr:generate-description` with `--no-update`. The shared Independent Review Record contract bounds the line, verifies its identities, and requires its exact preservation before publication. This carries evidence only; it grants no provider or publication authority beyond the existing parent invocation.
- `trackbed:pr:product-review` with `--inline` and `trackbed:linear:review-pr` are read-only: neither edits source, commits, or writes to GitHub or Linear, and product-review writes no report file with `--inline`. They become model-invocable so `trackbed:pr:github-review` can delegate to them, with descriptions that route model use as narrowly as the read-only convergence gates above.
- `trackbed:debug:triage-to-issue` stops invoking `trackbed:debug:investigate`; both skills load one plugin-level root-cause procedure, so investigate stays model-disabled and triage stays report-only.
- `trackbed:code:migrate` recommends `/trackbed:deps:audit` to the user, `kramme:pr:plan-split` gives the user an explicit `/trackbed:code:breakdown-findings` command, and `trackbed:siw:spec-audit --apply` owns its auto-fix procedure instead of delegating to a separate skill. Those targets stay model-disabled or are removed.
- `trackbed:docs:update-agents-md` becomes user-invocable and model-disabled, so the user routes in `trackbed:docs:adr` and `trackbed:docs:feature-spec` point at a command the user can run.

`trackbed:pr:code-review --loop` is not an authorized parent of `trackbed:pr:resolve-review`. Its closeout loop fixes accepted findings directly and may recommend `/trackbed:pr:resolve-review` to the user.

### Launch-time confirmation

Amended 2026-11-09. `trackbed:linear:next` Step 10 does not invoke `trackbed:linear:issue-to-pr` through the Skill tool. It starts a new Conductor cloud workspace whose first message runs the parent, so nobody is in that workspace to answer the parent's confirmation before it moves a non-backlog issue to its started status. Without this amendment, every launched To-do issue stopped at that gate.

- The user's yes to the launch question in `trackbed:linear:next` also answers `trackbed:linear:issue-to-pr`'s started-state confirmation, but only for issues whose state type is `unstarted`.
- `cloud-launch.py` writes `--launch-confirmed` into the first message, and only for the confirmed issues the skill named as `unstarted` in that run. A model never composes or edits that message.
- `trackbed:linear:issue-to-pr` honors `--launch-confirmed` only when the state it resolves at its own gate has type exactly `unstarted`. Started, completed, and canceled issues still get the gate's question, and `backlog` needs no confirmation. The parent's race close still applies: if the state changes before delegation, the gate runs again on the new state.
- The flag is accepted only from that launch message or from the user typing it. A model never adds it on its own initiative or infers it from an environment variable, a setting, or an earlier run. It has no effect with `--continue`, which never transitions the issue.
- This changes only who answers the parent's confirmation. The `--set-in-progress` status handoff, the child's write, and its read-back verification are unchanged.

### Pull Request shape-up delegations

Amended 2026-11-10. `trackbed:pr:shape-up` is a user-only parent that gets an open Pull Request ready to merge: it rebases a branch that is behind its target, fixes failing CI, and fixes and answers comments from AI reviewers. It changes nothing itself and adds these exact edges. Direct user invocation of each child is unchanged.

- `trackbed:pr:fix-ci` is also model-invocable as the branch pass of `trackbed:pr:shape-up`, which passes exactly `--rebase --no-consolidate` in its first round and exactly `--no-rebase --no-consolidate` in each later round. `--rebase` records that the user asked for a Pull Request behind its target to be rebased, and that rebase still runs through the existing `trackbed:pr:fix-ci` to `trackbed:pr:rebase --force-push` edge with every rebase gate. `--no-rebase` keeps a later round from rebasing again or asking, so a run rebases at most once. `--no-consolidate` turns off auto mode, so no pass rewrites history a second time. No other parent passes `--rebase` or `--no-rebase`.
- `trackbed:pr:github-review-reply` becomes model-invocable as the reply pass of `trackbed:pr:shape-up`, which passes exactly `--post --resolve --bot-only --no-implement --inline`, with no Pull Request URL and no instructions. Under that delegation the child edits no file, never invokes `trackbed:pr:resolve-review`, and drafts no reply to a person, because `--bot-only` drops every item that contains feedback from a person. The user's shape-up request is the request to post replies to bot and app reviewers that the child's Step 8 requires. The child keeps its pending-review, fix-on-head, per-item re-check, `answered-unresolved` confirmation, and rate-limit gates.
- Outside that delegation, a model caller of `trackbed:pr:github-review-reply` never adds `--auto`, `--implement`, `--post`, or `--resolve` on its own initiative, so a model-initiated run maps feedback and drafts replies only. Those flags need the user's own request, typed on the command or asked for in the message being answered.
- `trackbed:pr:shape-up` invokes both children from its own session, never from a subagent, and never invokes `trackbed:pr:rebase` directly.

Shape-up delegates instead of answering comments itself for the reason given under Alternatives Considered: a second copy of the reply workflow would drift. Letting the reply pass implement fixes was rejected because the reply skill never commits or pushes, so the parent would need its own stack-aware publish step; the branch pass already validates review feedback and pushes its fixes. This makes one more skill visible to the model, so its description stays short and names its parent. Focused tests pin both hand-offs and both child contracts.

## Consequences

- `trackbed:pr:create` can use the existing child skills through Claude Code's Skill tool without duplicating their workflows.
- `trackbed:pr:generate-description --check` compares an open Pull Request's title and body with the branch diff and is read-only for model callers, which pass `--check --no-update`. Only a direct user invocation without `--no-update` is offered a y/N prompt after Important or Critical drift; on `y`, the skill regenerates the description in output-only form, revalidates the exact Pull Request snapshot, checkout, head, base, and local work, and publishes through its own update path. The check mode replaced the separate verifier skill on 2026-10-15 and adds no new exception.
- One skill owns the started-state transition mechanics. `trackbed:linear:issue-to-pr` keeps the authorization, status resolution, and confirmation gate, and the parent's Conductor rename now runs after that gate rather than after a verified write.
- The children become visible to the model, and their routing and argument contracts are advisory rather than a platform-enforced authorization check.
- Additional side-effecting children remain model-disabled unless an accepted ADR names the exact parent-child exception.
- The 2026-10-21 repairs make five more skills visible to the model. Claude Code lists every model-invocable skill's name and description in each session within a small share of the context window and drops descriptions of the least-used skills when the list overflows, so each new child's description stays short and names its parent.
- Parents no longer depend on reading a model-disabled child's `SKILL.md` to finish a delegated step.

## Alternatives Considered

### Duplicate the child workflows inside `pr:create`

Rejected because parallel workflow text would drift and make ownership unclear.

### Keep the children model-disabled and rely on the read-the-skill fallback

Rejected because Claude Code rejects every such call first, the fallback runs the child's workflow outside the child's own model-invocation contract, and a parent that cannot locate the installed file loses the step.

### Make the children model-invocable without naming their parents

Rejected because file edits and cross-provider data transfer would then be reachable from any routing decision rather than only from parents whose arguments are pinned by tests.
