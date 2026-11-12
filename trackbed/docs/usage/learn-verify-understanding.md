# learn:verify-understanding

Use it when you want to confirm that you understand a specific topic: a Pull Request, branch, feature, document, spec, design decision, or bug fix. It builds a checklist for the topic, asks you to explain each area before it explains anything, fills the gaps, and quizzes you until you have shown that you understand every item. It writes only its own checklist file under `.context/verify-understanding/`. It is not for a plain explanation without checking, and it does not check that code or tests are correct.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[topic]` | What to verify: a Pull Request, branch, feature, document, spec, and so on. Without it, the skill uses the subject of the conversation when there is exactly one, and asks otherwise. |

## Options

| Option | Effect |
| --- | --- |
| `--answer-options` | Prefer quiz questions with 3 to 5 answer choices. You still explain your choice before it counts, and areas that need tracing or a restatement stay open-ended. |
| `--choices` | The same as `--answer-options`. |

## Examples

```text
# Verify that you understand the changes on a branch
/trackbed:learn:verify-understanding the changes on this branch

# Verify a spec with multiple-choice questions
/trackbed:learn:verify-understanding docs/specs/rate-limiting.md --choices
```

## What you get

- `.context/verify-understanding/<topic-slug>.md`: a checklist that covers the problem, why it matters, the solution, the rationale, design decisions, business logic, edge cases, impact, and evidence, followed by Demonstrated Understanding, Gaps To Revisit, and a Quiz Log.
- An item is checked off only after you demonstrate it, for example by restating it, predicting an outcome, or walking through the code. Where you struggle, the gap is recorded and the skill keeps teaching that area.
- Running the skill again on the same topic continues the same file and keeps your progress.
- When every item is verified, a report with the topic, the file path, the items verified, and anything to revisit later. If you stop early, the report lists the unchecked items and the next question to continue with.

The checklist is a working file. `trackbed:workflow:cleanup-artifacts` removes the `.context/verify-understanding/` folder, and your progress with it.
