# pr:review-convergence

Use it on a committed branch to review and fix it against a fixed set of requirements before you publish it. It starts with a quick first-read check, runs the code, convention, overengineering, and refactor reviews that apply at the branch's risk level, fixes the findings it accepts in new commits, and ends with the project's full verification. It edits files and commits on your branch, but never pushes, opens a Pull Request, or updates Linear. `trackbed:linear:issue-to-pr` and `trackbed:code:plan-to-pr` run it for you; for one review without fixes, use `trackbed:pr:code-review`.

## Before you run it

- The work is committed, the working tree is clean, and you are on a feature branch with at least one commit its base lacks.
- `.context/pr-review-convergence/reviews/` is ignored by Git. The review reports are kept there.
- The Linear MCP server is connected when a Linear issue supplies the requirements.
- The other model provider is available and signed in when you pass `--adversarial-review`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `LINEAR-ISSUE` | A Linear issue ID such as `DISC-202`, or its `linear.app` URL. The requirements are read from the issue, its comments, and the documents that define them. Without any requirements argument, they come from what you said in the conversation. |

## Options

| Option | Effect |
| --- | --- |
| `--subagent-model <model>` | Run the review agents on this model: a model class, a model ID, or `inherit`. See [Reviewer Models](../review.md#reviewer-models). |
| `--strict` | Require an evidence-based decision on every review finding, and use the full review profile. |
| `--rounds <1-5>` | How many fix-and-review rounds the run may take. The default is 5. |
| `--depth <balanced\|full>` | Raise the review profile above the one the branch's risk calls for. It never lowers it. |
| `--adversarial-review` | Once the other reviews have nothing left to fix, also get a review from the other model provider. The run stops as blocked when that review cannot run. |
| `--adversarial-provider claude\|codex` | Choose the provider for that review. It must differ from the one you are running in, and needs `--adversarial-review`. |
| `--adversarial-model <id>` | Choose the model for that review. Needs `--adversarial-review`. |
| `--derive` | Draft the requirements from the conversation and the branch's commits, diff, and tests, ask you targeted questions, and wait for your approval. Cannot be combined with a Linear issue or `--requirements`. |
| `--requirements <authoritative requirements>` | Use the text after this flag as the requirements. Put it last: everything after it is read as requirements, not as flags. |

## Examples

```text
# Review and fix the branch against what you described in this conversation
/trackbed:pr:review-convergence

# Use a Linear issue as the requirements
/trackbed:pr:review-convergence DISC-202

# Decide every finding on evidence, with at most three fix rounds
/trackbed:pr:review-convergence --strict --rounds 3 DISC-202

# Give the requirements yourself; they go last
/trackbed:pr:review-convergence --depth full --requirements Export invoices as CSV. Amounts keep two decimals. The PDF export does not change.
```

## What you get

- New commits on your branch with the fixes for the findings the run accepted. Nothing is pushed.
- A closing report that starts with `Review convergence: passed` or `blocked`. It gives the review profile, the reviews that ran or were skipped, the fix rounds used, how many findings were fixed, rejected, deferred, or blocked, each issue it did not fix, and the verification result.
- The review reports in `.context/pr-review-convergence/reviews/`.
- In a Conductor workspace, code-review findings posted as comments on the diff.

The [review guide](../review.md#review-convergence) explains the review steps, the profiles, and the fix budget.
