---
type: llm
---

PASS if the reply tells the author, outside the PR description itself, that context about the database migration is missing and must be supplied before publishing: why the column is needed, or how to roll the migration back.

FAIL if the reply never says that migration context is missing.
