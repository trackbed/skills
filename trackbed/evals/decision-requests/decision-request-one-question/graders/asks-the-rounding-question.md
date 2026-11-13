---
type: llm
---

PASS if the decision the reply asks for is how `--round` treats exactly 30 seconds: round half up (90 seconds prints `2m`) or always round down (`1m`).

FAIL if the reply asks a different question, asks several questions, or asks nothing.
