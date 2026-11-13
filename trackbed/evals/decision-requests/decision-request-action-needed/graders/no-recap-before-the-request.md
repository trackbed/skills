---
type: llm
---

PASS if the reply starts with what the user must decide or do: nothing comes before the first question or request except, at most, a heading or a one-line label.

FAIL if anything before the first question or request recaps the run, such as a summary of the plan, a route decision like `PLAN ROUTE:`, the files read, or the checks run.
