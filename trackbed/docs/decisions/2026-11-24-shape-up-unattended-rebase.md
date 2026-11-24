# Rebase Unattended in Shape-Up and Regenerate Conflicted Generated Files

- Status: ACCEPTED
- Date: 2026-11-24
- Deciders: repository maintainer (requested on 2026-11-24 after a shape-up run stopped on a conflicted generated file)
- Amends: [2026-08-29-model-invocable-orchestration-children.md](2026-08-29-model-invocable-orchestration-children.md#pull-request-shape-up-delegations), [2026-10-31-unattended-default-for-shipping-skills.md](2026-10-31-unattended-default-for-shipping-skills.md)

## Context

`trackbed:pr:shape-up` rebased a Pull Request that was behind its target through `trackbed:pr:fix-ci --rebase`, which runs `trackbed:pr:rebase --force-push`. That mode aborts on any red flag. On 2026-11-24 a shape-up run on a Pull Request 30 commits behind `main` hit a conflict in a generated Convex validator (`_generated/.../*.d.ts`). The generated-artifact red flag aborted the rebase. Nothing was pushed, and the report told the maintainer to rebase by hand. Shape-up exists so the maintainer does not have to do that.

The red flag was right to stop a text merge: a hand-merged generated file can stop matching its source, and nothing checks that during a rebase. The usual fix is to run the generator again, and no rebase mode did that.

## Decision

- **Regenerate route.** During conflict resolution, `trackbed:pr:rebase` runs the owning generator on staged inputs in a private scratch directory. It runs in the owning project or the repository's documented working directory. The resulting generated files must be stable on a second run and safe to import over the active conflict. A lockfile-only update follows the usual conflict rules. Other regenerated lockfiles must account for the replayed commit's intended resolutions. A verified result clears the generated-artifact red flag and still counts as a resolved conflict for `--force-push` verification. The usual red-flag rules apply when safe regeneration is unavailable. Migration files follow the migration conflict rules.
- **Shape-up rebases in auto mode.** Shape-up's first branch pass becomes `trackbed:pr:fix-ci --rebase --shape-up --no-consolidate`. With `--shape-up`, fix-ci delegates `trackbed:pr:rebase --shape-up --base <BASE>` instead of `--force-push`. Only shape-up passes the flag to fix-ci, and only that fix-ci run passes it to the rebase. In `trackbed:pr:rebase`, `--shape-up` selects auto mode and cannot be combined with `--manual`, `--force-push`, or `--all-open`. In auto mode the rebase resolves every conflict it can, continues past red flags, and pushes with its pinned lease without waiting for verification. The CI pass that follows on the new head serves as verification. fix-ci returns each red flag the rebase bypassed on a `Rebase concerns:` line, and shape-up lists them under "Left for you". Later rounds still pass `--no-rebase`, and the run still rebases at most once.
- Everything else stays the same. `--no-consolidate` keeps fix-ci itself out of auto mode, so `[FIX PIPELINE]` commits are not squashed. The lease, stack, other-workspace, and protected-branch checks still apply, and a conflict the model cannot resolve still aborts and restores the branch.

## Consequences

- A shape-up run on a branch with conflicts in generated files or lockfiles finishes without help when the repository can run their generator. Other conflicts are resolved and pushed too, with each risky one reported instead of stopping the run.
- `trackbed:pr:create --rebase`, `trackbed:linear:issue-to-pr --rebase`, and `trackbed:pr:fix-ci --rebase` keep `--force-push`. They gain the regenerate route only, so a regenerated file no longer stops them, but they still verify before pushing.
- A shape-up run can now force-push a hand-merged migration or a resolution the model did not fully understand. The Pull Request's CI run is the only check before a human sees the result. This is the same risk the 2026-10-31 decision accepted for a direct `/trackbed:pr:rebase`, now reached through a user-only parent that the maintainer starts.
- Shape-Up requires a direct request or a verified Conductor Showtime relay. One Showtime run can start several authorized rebases, each in its own workspace's chat. The Showtime merge gate still requires green checks.
- Running a generator executes repository code during a rebase. The route runs only commands that the repository or a fixed lockfile table names, with a time limit. Lockfile commands may reach the package registry.

## Alternatives Considered

### Keep `--force-push` in shape-up and add only the regenerate route

This fixes the run that prompted the change and keeps every red flag. Rejected because the maintainer asked shape-up to do as much as it can without stopping. Other red flags, such as a block-deleting resolution, would still end the run with a manual rebase.

### Let shape-up invoke `trackbed:pr:rebase` directly

Rejected because fix-ci already owns the base re-check before delegation, the proof that the push landed, and the return to CI on the new head. Shape-up still never invokes the rebase skill itself.

### Pass `--auto` to the rebase

Rejected because the 2026-10-31 decision removed `--auto` from the shipping skills' interfaces, and its tests forbid any component from passing it. A flag named for the one delegation that grants auto mode, like `trackbed:pr:create --showtime`, says who granted it. A model cannot mistake it for a general switch.

### Turn on fix-ci auto mode in shape-up

Rejected because it would also squash the pass's `[FIX PIPELINE]` commits in a second force-push. That makes neither the rebase nor CI any more likely to finish.

### Merge generated files as text and flag them

This is what auto mode did before. Rejected as the first choice because a generated file that no longer matches its source can pass review unnoticed. It remains the auto-mode fallback when no generator can run.
