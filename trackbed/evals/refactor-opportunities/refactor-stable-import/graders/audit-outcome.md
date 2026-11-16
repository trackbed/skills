---
type: llm
focus: { source: file, path: REFACTOR_OPPORTUNITIES_OVERVIEW.md }
---

PASS if the saved report flags the dependency from the stable quote.js module to the volatile tariff.js module, explains the stability/churn mismatch, and reports measured change counts for both sides: quote once and tariff thirteen times, or zero versus twelve when explicitly excluding the initial commit. It need not repeat the number of importers.

FAIL if the saved report misses the dependency, reverses the import direction or counts, or merely calls one side stable and the other volatile without measured counts for both. For example, "quote.js changed 13 times; tariff.js changed 1 time. The dependency is stable, so no dependency refactor is needed" fails. Names and unrelated numbers elsewhere do not establish the finding.
