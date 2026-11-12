# Clarifying Question Examples

Use this pattern for the Step 5.2 decision request when requirements or implementation choices are unclear. It asks three blocking questions in one request.

```text
Decision 1 of 3 · {issue-id}: should this include {related functionality}, or only {feature}?

The issue asks for {feature}; {related functionality} is mentioned in
{source} but has no acceptance criterion.

1. Only {feature} (recommended): implements what the acceptance criteria
   require. {related functionality} stays out and can get its own issue.
2. Include {related functionality}: also changes {files} in this PR, which
   grows the diff and adds {tests} to cover it.

Decision 2 of 3 · {issue-id}: follow pattern A or pattern B for {concern}?

Both appear in the codebase for similar features.

1. Pattern A - {description} (recommended): matches {files}, which most
   similar features use, so the change reuses {helper}.
2. Pattern B - {description}: matches {files}; it needs {extra work}, and
   the two patterns stay mixed.

Decision 3 of 3 · {issue-id}: which tests should cover this change?

The closest existing feature, {similar feature}, has {existing tests}.

1. Unit tests (recommended): covers every acceptance criterion with the
   fewest new tests. Interactions with {component} stay untested.
2. Unit and integration tests: also tests the interaction with
   {component}. More setup and a slower suite.

State: on branch {branch}, nothing committed or pushed; the issue is {status}.
```

In the host's question dialog, send each numbered decision as one question in the same call, with a short header such as `Scope`, `Approach`, or `Tests`. The last question carries the `State:` line. With a single question, drop the `Decision 1 of 1` numbering and start it with `Decision needed · {issue-id}:`.
