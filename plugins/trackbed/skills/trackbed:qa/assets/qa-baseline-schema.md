# QA Baseline Schema

Write `QA_BASELINE.json` at the project root with this shape:

Record every route in the run's test plan under `routes`, in every mode. A regression comparison counts a baseline finding as fixed only when the current run verified its route.

```json
{
  "date": "{ISO 8601 timestamp}",
  "url": "{TARGET_URL}",
  "mode": "{TEST_MODE}",
  "framework": "{DETECTED_FRAMEWORK or null}",
  "browserMcp": "{BROWSER_MCP or 'code-only'}",
  "healthScore": {HEALTH_SCORE},
  "healthLabel": "{HEALTH_LABEL}",
  "routesTested": {N},
  "routes": [
    {
      "route": "{URL path}",
      "result": "{pass|fail|blocked|skipped|UNVERIFIED|code-only}",
      "reason": "{why, unless pass or fail}"
    }
  ],
  "journeyMatrix": [
    {
      "routeOrScreen": "{route or screen}",
      "journey": "{user task}",
      "changedFiles": ["{path}"],
      "stateOrDataSetup": "{state}",
      "expectedBehavior": "{expected result}",
      "evidence": "{screenshot, console/network note, a11y note, code-only note, or skipped reason}",
      "result": "{pass|fail|blocked|skipped|code-only}",
      "followUp": "{QA-NNN|issue|none}"
    }
  ],
  "findings": [
    {
      "id": "QA-001",
      "title": "{title}",
      "severity": "{Blocker|Major|Minor|Info}",
      "category": "{Console|Network|Visual|Functional|Data|Interaction|Content|Accessibility}",
      "route": "{URL path}"
    }
  ],
  "severityCounts": {
    "blocker": {N},
    "major": {N},
    "minor": {N},
    "info": {N}
  }
}
```
