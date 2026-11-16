---
type: llm
focus: { source: file, path: REFACTOR_OPPORTUNITIES_OVERVIEW.md }
---

PASS if the saved report identifies the next-day delivery eligibility requirement shared by the API, CSV import, and preview callers and proposes one shared policy or equivalent single fix covering all three. The report may use domain labels rather than literal filenames.

FAIL if the saved report misses the common requirement, covers fewer than all three callers, or recommends only separate local fixes. For example, "Scanned api.js, csv.js, and preview.js. Eligibility is local to each channel. Fix each condition separately; keep implementations independent" fails even though every filename appears. Judge the actual recommendation, not keyword presence.
