# Skill-change evals compare a base commit with the working tree

- Status: ACCEPTED
- Date: 2026-11-11
- Deciders: repository maintainer (explicit request)

## Context

The [skill quality regime](2026-07-06-skill-quality-regime.md) capped committed behavior evals at the `trackbed:skill:review` pilot and left every other skill to dogfooding. Its expansion criteria came from SkillOpt, a prompt optimizer: train, validation, and test splits, text fixtures, and a candidate gate. The [eval scope review](2026-08-08-eval-scope-review.md) tested those criteria on `trackbed:pr:resolve-review` and found them unmet, mainly because checking a fix needs a runnable repository. That is the normal shape of an agent test, and not something an optimizer split provides.

Three things have changed since:

- **Skills change faster than dogfooding can judge.** In the 30 days to 2026-11-11, 155 commits touched skills and 72 of 202 merged Pull Requests were fixes. Nothing compares a skill before and after an edit, so a change counts as an improvement on its author's reading.
- **Claude Code runs evals itself.** Version 2.1.269 added `claude plugin eval`. It runs case folders in the real host with the plugin loaded, repeats each case, and grades the reply, the files, and the tool calls. It needs no adapter from this repository.
- **The pilot measures little that changes.** `trackbed:skill:review` has no recorded use since local usage records begin on 2026-10-06, and none of the 72 fixes touched it. Its harness scores phrases and runs in a read-only profile without a shell or subagents.

On 2026-11-11 the maintainer asked for evals that show whether a change to a skill is an improvement.

## Decision

Permit committed eval suites for any shipped skill, and run them as a comparison of two versions of the plugin.

- **Format.** A suite is a folder under `evals/` holding a `suite.json` and one case folder per scenario, in the layout `claude plugin eval` reads. No new scorer, adapter, or runner is added.
- **Comparison.** `scripts/skill-eval-compare.js` snapshots a base commit and the working tree, runs the working tree's cases against both, and reports each check's pass count on each version. A check counts as changed when its pass rate moves by more than half its runs, with at least three graded runs on each side. The verdict is better, worse, mixed, no detectable difference, or incomplete.
- **Cases.** Each case exists because of an observed failure, a merged fix, or a contract another skill relies on, and its `expected_outcome` says which. Checks grade the outcome: the final reply, the files, and the tool calls. Every case checks that the skill fired. Fixtures are invented code, because this repository is public.
- **Use.** A comparison is advisory and local. It never gates a merge and never runs in CI, because each run is a paid model session and a small suite detects only large effects.
- **First suite.** `pr-generate-description`, seven cases. The skill changed in 17 commits and ran 313 times in the 30 days to 2026-11-11, costs under a dollar a run, and runs without touching a Pull Request.

What stays as it was:

- The July 6 cap still governs the SkillOpt bridge, bespoke scorers and adapters, and train/val/test splits: one pilot, no expansion. The cases in these suites are not split, and no optimizer runs against them.
- Dogfooding and the post-model-upgrade smoke ritual remain the quality signal for skills without a suite.
- The [live skill-review adapters](2026-10-24-sequential-credit-evals.md) and the [review-completion exception](2026-09-08-review-execution-evidence.md) are unchanged.

This record supersedes the proposed eval scope review, which recommended reaffirming the cap. Its open question, whether the cap covers trigger-selection evaluation, no longer needs a ruling: a case that checks whether a skill is chosen for a prompt is a case like any other.

Review this decision by 2027-01-11. Keep it, extend it to more skills, or remove it, based on whether a comparison changed what was merged.

## Alternatives considered

- **Keep the cap and rely on the [monthly improvement review](2026-10-28-monthly-skill-improvement-review.md).** That proposal measures a change in real use two weeks after its release. It covers what no case anticipates, but it answers after the merge. The two complement each other.
- **Extend the skill-review harness to more skills.** Its scorer matches phrases, its profile has no shell, subagents, or Git, and every new skill would need adapter work.
- **Use the runner's own comparison with and without the plugin.** That shows whether the plugin helps at all, not whether an edit helped. In a first probe the run without the plugin passed five of six checks.
- **Gate merges on a suite in CI.** A comparison of the first suite costs about $28, needs credentials on the runner, and is noisy at three runs: a check that passes nine times in ten is reported as changed by chance in about 4% of comparisons.

## Consequences

Positive:

- A skill change can be compared with what it replaces, on cases written before the change.
- A suite records the failures a skill has had, in a form that fails again if one returns.
- The repository maintains cases and one comparison script; the host maintains the runner.

Negative:

- A full comparison of the first suite is 42 model sessions. On a subscription they count against the session limit.
- Three runs per case detect a check that flips and miss a small shift, so no detectable difference will be a frequent answer.
- A run differs from real use. Shell commands have no network, so `gh` and Linear lookups fail, and the first suite's prompts pass `--base main` for that reason. The judge is a small model.
- Only Claude Code is evaluated. The converted Codex plugin is not.
- A check can be wrong in ways that look like a skill defect. Both mistakes found while building the first suite were in the checks, not the skill.

Follow-up:

- Decide at the review whether the skill-review harness and its credit pools still earn their place.
- If the pilot proves useful, the next suites are `trackbed:pr:rebase` and then `trackbed:pr:code-review`. A code-review run cost about $7 on the 2026-10-20 baseline, ten times a description run.

## Verification

Offline, with no model: `tests/node/skill-eval-compare.test.js` covers the options, the grants, both snapshots through a fake runner, the verdict rule, and the reports. `tests/skill-eval-suites.bats` validates every case and builds every Git fixture.

Live, on 2026-11-11 with Claude Code 2.1.322: the suite compared commit `3b84f295`, the parent of #1101, with the working tree at `e0bbfb69`. The 42 runs cost $28.07 at list price.

- **It detected a merged fix.** #1101 told the skill to say when the old behavior stops working after a breaking change. That check passed in 1 of 3 runs before the fix and 3 of 3 after.
- **Three other behaviors #1101 targeted showed no difference.** The upper-case template, the new runtime dependency, and the effect of a revert passed on both versions, because the model already handled them. Those cases can only show a regression.
- **It found a defect that both versions share.** On a branch named `abildtoft/skills-15-…`, the description linked issue `SKILLS-15` in 1 of 3 runs on each version. The skill's issue pattern accepts team keys of two to five letters, and `SKILLS` has six.
- **It showed an unreliable contract.** The literal `MISSING REQUIREMENT:` line that calling skills read appeared in 3 of 6 runs for a missing issue ID and 4 of 6 for a migration without a rationale. A later single run also reworded the `Cold read:` line.
- **Two checks were wrong, and both are now guarded.** One pattern contained `---`, which ends a grader's settings block, so its case did not load; a static test now rejects that, and the comparison warns when the runner reports a problem. Two patterns matched the skill's run notes instead of the description and reported a regression that was not there; they now look only inside the description, and they were re-scored against the saved replies.
