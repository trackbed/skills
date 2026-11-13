# code:optimize

Use it when a measurable result, such as build time, bundle size, search relevance, or prompt quality, could be improved in several plausible ways and you want each one tested against the same measurement. It records a baseline, tries the variants, keeps and commits the ones that measurably improve the result, and discards the rest. It is experimental. For a one-off performance fix with nothing to measure against, ask the agent directly.

## Before you run it

- A measurement command that prints JSON with the metric and the checks a valid result must pass. When quality needs judgment instead of a number, a scoring rubric as well.
- A clean working tree with no untracked files. Experiments start from the current commit.
- `.context/code-optimize/` ignored by Git. The run offers to add it to `.gitignore`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[spec.yaml]` | A path ending in `.yaml` or `.yml`: the optimization spec to read and validate. |
| `[optimization goal]` | Any other text: the goal, which the run turns into a spec with you. With neither, you are asked what to optimize and whether you have a measurement command. |

## Options

| Option | Effect |
| --- | --- |
| `--auto` | Choose conservative defaults and continue past the baseline without waiting for you, as long as costs are capped and the first run tests one variant at a time. You still approve the measurement command before its first run, any new dependency, and judge spending without a cost cap. |

## Examples

```text
# Describe the goal and build the spec together
/trackbed:code:optimize reduce bundle size; the measurement command is npm run measure:bundle

# Run from a spec you already wrote
/trackbed:code:optimize bundle-size.yaml

# Run from a spec with conservative defaults and fewer stops
/trackbed:code:optimize bundle-size.yaml --auto
```

## What you get

- `.context/code-optimize/<spec-name>/` with `spec.yaml`, `experiment-log.yaml` (the baseline, every idea tried, its result, and the current best), `strategy-digest.md` (what has been learned so far), and one `experiments/<iteration>/result.yaml` per measured experiment. Run the skill again with the same spec to resume from these files.
- The winning changes committed on a local optimization branch. Losing experiments are discarded and their worktrees removed.
- A summary: the metric from baseline to final, how many experiments were kept, reverted, or failed, the judge cost, and the changes that won.

The run stops when the target is reached, a limit on iterations, hours, or judge cost is hit, results stop improving, or no ideas are left. Nothing is pushed, no Pull Request is opened, and the experiment log is kept. The run offers `trackbed:verify:run` and `trackbed:pr:code-review` as next steps.
