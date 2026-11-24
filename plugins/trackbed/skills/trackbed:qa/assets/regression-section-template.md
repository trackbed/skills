# Regression Section Template

Use this section in `QA_REPORT.md` when a regression comparison ran.

```markdown
## Regression (vs. baseline from {baseline_date})

**Score delta:** {current_score} vs. {baseline_score} ({+N / -N})

### Fixed ({N})

- QA-{NNN}: {title} (was {severity})

### Not re-checked ({N})

- QA-{NNN}: {title} ({severity}) — route {not verified | not in this run's plan}

### New ({N})

- QA-{NNN}: {title} ({severity})

### Persistent ({N})

- QA-{NNN}: {title} ({severity})
```
