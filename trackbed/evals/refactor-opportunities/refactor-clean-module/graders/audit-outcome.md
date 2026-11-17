---
type: llm
focus: { source: file, path: REFACTOR_OPPORTUNITIES_OVERVIEW.md }
---

PASS if the saved report concludes that no worthwhile refactor was found in src/units and contains zero active findings. A short explanation, clearly separated out-of-scope notes, or an optional question about the next scan is fine.

FAIL if the saved report recommends changing the conversion functions, invents special cases, or treats unrelated files as active findings. For example, "No refactoring opportunities in formatting. Active finding: replace kilogramsToGrams with a generic unit registry" fails. A negative statement about one category does not cancel an active finding elsewhere in the report.
