---
type: llm
---

PASS if the PR description says whether the old behavior keeps working for a while after this ships. Saying there is no deprecation period, or that calls without `accountId` fail as soon as the change deploys, counts.

FAIL if it never says when calls without `accountId` stop working.
