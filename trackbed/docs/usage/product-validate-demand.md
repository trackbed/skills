# product:validate-demand

Use it to decide whether one concrete product idea has enough real demand evidence to earn more work. It asks, one question at a time, about the target user, what they already do about the problem, today's workaround, the cost of switching, and the smallest thing they would pay for, then gives a verdict: `GO`, `PIVOT`, `KILL`, or `INSUFFICIENT EVIDENCE`. It replies in the conversation and writes a file only when you ask. For broad questions about blind spots, use `trackbed:discovery:strategic-inquiry`; for the product direction in `STRATEGY.md`, use `trackbed:product:strategy`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[idea or evidence]` | The idea to judge and any evidence you already have. The skill needs one concrete idea and one target user, and asks for whichever is missing. |

## Options

| Option | Effect |
| --- | --- |
| `--output <repo-relative-path>` | Write the decision record to this file, a path relative to the repository root that stays inside the repository. The skill asks before it replaces an existing file, and before it writes one that Git tracks or does not ignore, because that file may be committed. |

## Examples

```text
# Judge an idea in the conversation
/trackbed:product:validate-demand Spend alerts for finance leads at small SaaS companies

# Judge it and keep the decision record as a file
/trackbed:product:validate-demand Spend alerts for finance leads at small SaaS companies --output docs/demand/spend-alerts.md
```

## What you get

- A decision record titled `Demand Validation: <idea>` with the verdict, the confidence in it, and the target user.
- An evidence table in which every claim is labelled `OBSERVED`, `USER-REPORTED`, `INFERRED`, or `UNAVAILABLE`. Compliments and hypothetical interest do not support `GO`.
- Today's workaround and the switching cost, the smallest paid wedge, the reasoning with the strongest counterevidence, and a falsifier: one observable result that would change the verdict.
- For every verdict except `KILL`, one next real-world action with a pass result, a fail result, and a time box. The skill does not carry it out.
- With `--output`, the record is written to that file and no other file is created. Outside a Git repository, the skill offers the reply in the conversation instead.

`GO` means the idea is worth defining, not building. The skill never starts another workflow on its own.
