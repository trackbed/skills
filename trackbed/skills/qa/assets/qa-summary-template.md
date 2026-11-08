# QA Summary Template

After writing the report, display an inline summary in this shape:

```markdown
## QA Summary: $TARGET_URL

**Mode:** {quick | diff-aware | targeted} **Routes Verified:** {N} of {N planned} **Journey Matrix Rows:** {N, if diff-aware} **Browser:** {claude-in-chrome | chrome-devtools | playwright | code-only} **Framework:** {DETECTED_FRAMEWORK or "not detected"} **Health Score:** {HEALTH_SCORE}/100 ({HEALTH_LABEL})

### Verdict: {READY | NOT READY | READY WITH CAVEATS}

{If NOT READY: list blockers with brief description} {If READY WITH CAVEATS: list major issues and every planned route that was not verified, with brief description} {If READY: confirm no blockers or major issues found and every planned route verified}

- Blockers: {N}
- Major: {N}
- Minor: {N}
- Info: {N}

{If REGRESSION_MODE and baseline found:}

### Regression vs. {baseline_date}

Score: {baseline_score} -> {current_score} ({+N / -N}) Fixed: {N} | Not re-checked: {N} | New: {N} | Persistent: {N}

Report output: {inline reply | QA_REPORT.md} {If blockers found: "Fix blockers and re-run: /trackbed:qa <url>"}
```
