# Run Shipping Skills Unattended by Default

- Status: ACCEPTED
- Date: 2026-10-31
- Deciders: repository maintainers

## Context

`trackbed:git:recreate-commits`, `trackbed:pr:create`, `trackbed:pr:fix-ci`, `trackbed:pr:generate-description`, and `trackbed:pr:rebase` each paired an interactive default with an opt-in `--auto`. The maintainer wants the `--auto` behavior on about 99% of direct runs, so the flag was typed on nearly every invocation and the default served only the exception.

The interactive default was also a safety property: a caller that forgot a flag got prompts rather than a history rewrite or a force-push. All five skills are model-invocable under [guarded exceptions](2026-08-29-model-invocable-orchestration-children.md) whose contracts are advisory rather than platform-enforced, so the flip has to keep that omission safe for model callers.

## Decision

- All five skills default to auto mode, the behavior `--auto` used to select, and take `--manual` to restore what the no-flag invocation used to do. `--auto` leaves their interfaces. A leftover `--auto` is ignored so saved prompts keep working.
- Auto mode belongs to a direct user invocation, meaning a typed slash command or `$` mention or a request in the session that names the skill, and to the parent delegations each skill names. A saved PR-creation prompt that names `trackbed:pr:create` therefore gets auto mode. Every other invocation runs as `--manual`, whether or not it passes that flag, including one where the model picks the skill for a request that does not name it. `trackbed:pr:generate-description` instead treats such a call as `--no-update`, because its generated text has no side effect until it edits a Pull Request. [Amended 2026-11-10](#amendment-2026-11-10): a direct invocation covers only the request being answered.
- `trackbed:pr:rebase` takes its former `--auto` behavior in full, including continuing past red flags and pushing without verification. The maintainer chose this knowingly.
- `--force-push` now overrides that default instead of losing to it, so `trackbed:pr:fix-ci` and `trackbed:pr:create --rebase`, which both pass it, keep every rebase gate.
- `--no-consolidate` turns off auto mode in `trackbed:pr:fix-ci`. Otherwise `trackbed:linear:issue-to-pr --ship` and `trackbed:code:plan-to-pr --ship` would inherit an unattended rebase decision and break their promise not to rewrite an open Pull Request. Their invocations stay byte-identical. [Amended 2026-11-12](#amendment-2026-11-12): drift that cannot affect the Pull Request no longer asks, and `trackbed:linear:issue-to-pr` appends the user's own `--rebase` or `--no-rebase`.
- Modes with their own gates do not inherit the default: `trackbed:pr:generate-description --check`, `trackbed:pr:rebase --all-open`, and `trackbed:pr:fix-ci --scope-plan`.
- Every other skill's `--auto` stays opt-in.

## Consequences

- A typed command that used to prompt now acts. `/trackbed:pr:create` commits all uncommitted work and publishes, `/trackbed:pr:generate-description` edits an open Pull Request, and `/trackbed:pr:rebase` force-pushes after any completed rebase. Saved prompts that relied on the prompts must add `--manual`.
- A forgotten `--manual` no longer fails safe for a direct user. For `trackbed:pr:rebase` this is a deliberate exception to the back-pressure principle in [agent autonomy](../agent-autonomy.md): a force-push without verification is expensive to find wrong, though the lease and the rebase's own failure handling still apply.
- The rule that separates direct from model-initiated calls is advisory, like the rest of the model-invocation contracts. Focused tests pin it and the parent arguments, but they cannot enforce it at run time. A request that does not name the skill, such as "open a PR", still prompts, because the model chose the skill.
- Stacked history rewrites stay gated: `trackbed:git:recreate-commits` stops in auto mode without `--authorize-history-rewrite`, and `--manual` offers the stack-wide confirmations.
- Conflicted branches from `trackbed:pr:rebase --all-open` are routed to `--manual`, because a conflict is the case where the default is least safe.
- The catalog now has two conventions for the same word: five skills are unattended unless `--manual`, and the rest are interactive unless `--auto`.

## Alternatives Considered

### Make `--force-push` the rebase default

This keeps conflict, red-flag, and verification gates while skipping only the final confirmation. Rejected because the maintainer asked for the existing `--auto` behavior on this skill, with its risk already known. `--force-push` remains available for any run that wants those gates.

### Keep `--auto` and add a setting for the default

Rejected because a per-repository or per-user setting would make the same command behave differently across hosts and would add a second configuration surface for one maintainer's preference.

### Reject a leftover `--auto`

Rejected because the flag's meaning is now the default, so a stop would cost a rerun without preventing any mistake.

### Count only typed commands as direct

Rejected because a saved prompt that names the skill, such as a host's PR-creation instructions, would then prompt on the user's most common path.

### Let model callers inherit the default

Rejected because a model call that dropped a flag would rewrite history or force-push with no human in the loop, which the guarded exceptions exist to prevent.

## Amendment (2026-11-10)

The Decision above counted a request "in the session" that names the skill as a direct invocation. That let an early by-name request authorize a later history rewrite or force-push that the model started on its own. The Claude Code [skills documentation](https://code.claude.com/docs/en/skills) ("Control who invokes a skill") limits the consent a skill name carries to the message that contains it, so the five skills now use the same narrower rule.

- A direct invocation covers only the request being answered: the user's current message decides it. Session-wide consent is retired.
- A slash command or `$` mention at the start of the message invokes the skill directly.
- The skill's name later in the message, written as its own word, permits a run for that message only, and only when the wording asks for one.
- A mention that only discusses the skill permits no run, and a request in an earlier message never authorizes a later run.
- A saved prompt that the host sends as the user's message, such as a host's PR-creation instructions, is the current request and keeps auto mode. Counting only typed commands as direct stays rejected for the reason in Alternatives Considered.
- A request that reaches a skill through another agent, including a subagent that preloads it, is not a direct request. The guarded parent delegations each skill names, such as the `trackbed:pr:create` handoff to `trackbed:git:recreate-commits`, remain the only exception and keep only the authority their contract gives them.

Keeping session-wide consent was rejected because a by-name request early in a session would keep authorizing unattended history rewrites and force-pushes for the rest of it, long after the request it answered was done.

All five skills carry this rule as one synced paragraph that the skill-contract linter keeps identical. Like the rest of the model-invocation contracts, it is advisory: focused tests pin the wording, but nothing enforces it at run time.

## Amendment (2026-11-12)

`--no-consolidate` made `trackbed:pr:fix-ci` ask about every branch that was behind its base. After `trackbed:linear:issue-to-pr --ship` opened a Pull Request, that question was the most common stop: 57 of the 130 question dialogs across 125 measured runs. It came late, and 32 of the 57 got no answer, some because the dialog was cancelled or interrupted. The 25 answers split 15 rebase, 9 skip, and 1 other.

- `--no-consolidate` still turns off auto mode and still never rebases on its own. When nothing that moved on the base touches the Pull Request's files, CI configuration, lockfiles, or shared build tooling, it keeps the pushed head without asking and says so in one line. Otherwise it asks in the shared decision request format, with how far behind the branch is, what overlaps, and what each option causes.
- An explicit `--manual` keeps asking every time, as before.
- `trackbed:linear:issue-to-pr` accepts `--rebase` or `--no-rebase` with `--ship` and passes it to `trackbed:pr:fix-ci`. `--rebase` is the user's permission to rebase and force-push the Pull Request that run opened, once, through `trackbed:pr:rebase --force-push` with every rebase gate. `--no-rebase` keeps the pushed head and never asks. The helper refuses the two together and refuses either without `--ship`.
- Its final report gains a `Base drift` line that says whether the drift was kept or rebased.
- `trackbed:code:plan-to-pr` is unchanged: its scoped mode keeps its own drift rule and never rebases.

Keeping unrelated drift without asking still honors the `--ship` promise, because the pushed head is not rewritten. A rebase changes the tree, so the shared shipping contract's validation-only review and final-tree verification run afterwards, as they already did when the user answered "rebase".

Two alternatives were rejected. Defaulting to a rebase would force-push an open Pull Request without the user's permission. Defaulting to a skip whenever drift exists would hide a base movement that can break the Pull Request.
