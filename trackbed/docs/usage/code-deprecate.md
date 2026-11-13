# code:deprecate

Use it to retire code, a feature, an API version, or a persistent data shape that has a replacement. It first decides whether deprecation is the right call, then works through four steps in order: build the replacement, announce, migrate the callers, and remove the old code. It keeps its state in a plan file, so a later run resumes where the last one stopped, and it edits code along the way. For a framework or library upgrade, use `trackbed:code:migrate`; for a refactor that removes no public surface, use `trackbed:code:refactor-pass`.

## Before you run it

- The target has a replacement, built or committed. Without one, the skill treats the removal as a decision to delete the feature and stops.
- The code has an owner. For code that nobody owns but other code depends on, it stops and asks you to establish an owner first.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[deprecation target]` | The symbol, feature, or API to retire, such as `Billing v1 API`. The plan file is named after it, and on a later run it selects the plan to resume. |

## Options

| Option | Effect |
| --- | --- |
| `--visual` | Also write `DEPRECATION_PLAN_<slug>.html`, an interactive status page of the same plan. See [Visual Reports](../visual-reports.md). |

## Examples

```text
# Start the deprecation of an API version, or resume it
/trackbed:code:deprecate Billing v1 API

# Start or resume a deprecation and also write a status page of the plan
/trackbed:code:deprecate LegacyAuthAdapter --visual
```

## What you get

- `DEPRECATION_PLAN_<slug>.md` in the repository root, such as `DEPRECATION_PLAN_billing-v1-api.md`: the owner, replacement, migration pattern, target removal date, known call sites, a migration log, decisions, and a checklist for every step. Each run resumes at the earliest unfinished step.
- A decision: Deprecate, Keep and maintain, or Defer. For the last two, the outcome and the event or date that reopens it are archived in your project docs, the plan file is deleted, and nothing is announced.
- For Deprecate, changes to your code in step order, ending with the removal of the old code, its tests, its docs, and the deprecation notices together.
- `ASK FIRST` stops before risky moves, such as deprecating a public API, forcing a migration with under 30 days' notice, or removing code while an `UNVERIFIED` assumption is still open.

The plan is a working file. When the deprecation closes, delete it or archive the final decision in your project docs.
