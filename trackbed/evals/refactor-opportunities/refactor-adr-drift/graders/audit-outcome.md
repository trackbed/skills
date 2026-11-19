---
type: llm
focus: { source: file, path: REFACTOR_OPPORTUNITIES_OVERVIEW.md }
---

PASS if the saved report keeps, as an active finding or fix, the dispatch preview's own copy of the next-day rule, which misses the skerry destination that the shared eligibility module and the README include, and also says that the code no longer follows ADR-0001: the API and CSV channels already import the shared eligibility module that ADR-0001 rejects, so the decision record or the code has to change. Proposing either to supersede the ADR or to return to per-channel checks passes, as long as the report names the conflict and keeps the preview finding.

FAIL if the saved report omits the preview's divergent copy, drops it or lists it only as not touched or filtered because ADR-0001 settles the question, or keeps it without ever saying that the code contradicts ADR-0001. For example, "ADR-0001 keeps eligibility in each channel, so consolidating the preview onto eligibility.js is out of scope. No active findings." fails. Judge the report's actual conclusions, not keyword presence.
