---
type: llm
---

PASS if the PR description says that reverting the PR does not bring back the dropped `legacy_plan` column or its data, for example that the drop is one-way or that the values are gone unless restored from a backup.

FAIL if it never says what a revert leaves behind, or presents the change as fully reversible by a revert.
