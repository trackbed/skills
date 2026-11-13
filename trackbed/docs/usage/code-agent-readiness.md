# code:agent-readiness

Use it to find out how well a codebase suits AI coding agents. It scores five dimensions from 1 to 5 (Fully Typed, Traversable, Test Coverage, Feedback Loops, and Self-Documenting) and turns what it finds into a prioritized refactoring plan. It writes one report file and does not change your code. To audit the agent instructions, skills, and settings themselves, use `trackbed:code:audit-agent-config`; to look for refactoring candidates in general, use `trackbed:code:refactor-opportunities`.

## Before you run it

- Run it from the root of a project that holds source code. Without recognizable source code it stops.
- In a monorepo it audits the root-level configuration only. Run it per package for more depth.

## Options

| Option | Effect |
| --- | --- |
| `--subagent-model <model>` | Run the three dimension agents on this model: a model class, a model ID, or `inherit`. See [Reviewer Models](../review.md#reviewer-models). |
| `--auto` | When an earlier report exists, write a fresh one with a score comparison instead of asking whether to replace it, compare, or abort. |
| `--visual` | Also write `AGENT_NATIVE_AUDIT.html`, an interactive page of the same report. See [Visual Reports](../visual-reports.md). |

## Examples

```text
# Score the codebase and write the report
/trackbed:code:agent-readiness

# Re-run after improvements and compare with the previous scores without being asked
/trackbed:code:agent-readiness --auto

# Run the dimension agents on Sonnet and add the interactive page
/trackbed:code:agent-readiness --subagent-model sonnet --visual
```

## What you get

- `AGENT_NATIVE_AUDIT.md` in the project root: a scorecard with each dimension's score and an overall score rated from Agent-Native down to Agent-Hostile, the evidence and findings behind each score, and a refactoring plan in four phases, from quick wins to polish.
- When a report already exists and you did not pass `--auto`, a question whether to replace it, compare against it, or abort. Comparing adds the score changes to the new report.
- A summary in the conversation with the scores, the number of findings by severity, and the number of actions in each phase.

Next, turn the findings into plans with `trackbed:code:breakdown-findings`. Re-run an interrupted audit to [resume it](../review.md#resuming-interrupted-reviews-and-audits).
