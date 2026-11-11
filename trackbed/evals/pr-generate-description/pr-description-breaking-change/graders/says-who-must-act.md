---
type: llm
---

PASS if the Breaking changes section tells API clients what to change: pass `accountId` on every call to `GET /v1/reports`, because a call without it now gets a 400 response.

FAIL if the section is missing or does not say what callers must do.
