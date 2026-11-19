# Decision Requests

Use this format for every stop that waits on the user in a workflow that loads this file: a question, a confirmation, an approval, or a blocker only the user can clear. A stopped run shows a decision request instead of its success report. The format sets order and content, not length.

## Order

1. **First line:** `Decision needed · {work-item}: {question}`. The work item is the tracker issue ID or the plan's execution label. The question is one sentence and ends with a question mark.
2. **Evidence:** a few sentences with only the facts that change the choice.
3. **Options:** a numbered list. The recommended option comes first and ends with `(recommended)`. Each option says what it causes next: what the workflow does and what stays undone.
4. **State:** one line that starts with `State:`. It says what is published and what is not, such as the pushed branch, the Pull Request, and the tracker status, and where the details are, such as a report or archive path.

Leave out the run recap, the work done so far, and notes for reviewing the Pull Request later. Those belong in the final report.

## Several Decisions

Number each decision on its own first line (`Decision 1 of 2 · ...`) and give it its own evidence and options. Never leave a second decision in a closing paragraph. One `State:` line closes the request.

## Action Needed Instead of a Choice

When the user must act rather than choose, such as granting missing access, use the same order: `Action needed · {work-item}: {what is needed}`, then why it is needed, including the command that resumes the run when there is one, then the `State:` line.

## Relayed Questions

When a delegated skill hands back a question for the user, keep its question wording on the first line and its options with their consequences. Add the work item and the `State:` line; do not add a recap. When the delegated skill hands back a complete request without a `State:` line, such as the `Decision request` field from `trackbed:pr:review-convergence`, show it unchanged and add only the `State:` line.

## Channel

Use the host's question dialog when it has one and the choice is a few fixed options. Otherwise send a message with the same content. The dialog text must stand on its own:

- **Header:** a few words that name the decision, such as `Start issue` or `Review budget`.
- **Question:** the one-sentence question, then its evidence and the `State:` line.
- **Options:** the recommended option first with `(recommended)` in its label. Each description says what that option causes next.

## No Answer

A cancelled, dismissed, or unanswered dialog is not an answer. Repeat the request as a message in this format and stop. Never pick an option for the user, including the recommended one.

## Example

```text
Decision needed · SKILLS-22: resume review for the open finding, or stop here?

Review used its whole fix budget and one required finding is open: no
test covers an end tag outside a dropped region. The reviewer proposed
two tests that would close it.

1. Resume review (recommended): starts a new fix budget of up to 2 cycles
   for this finding, adds the two tests, and reruns review and full
   verification; the proposed tests should close it.
2. Stop here (0 cycles): the branch stays local for you to finish by hand.

State: nothing pushed, no PR, working tree clean; review archive in .context/linear-issue-to-pr/reviews/.
```
