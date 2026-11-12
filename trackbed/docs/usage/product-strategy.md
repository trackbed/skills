# product:strategy

Use it to create or update `STRATEGY.md` at the repository root: a short product anchor that covers the target problem, the approach, who it is for, key metrics, active tracks, optional milestones, and non-goals. It asks you only about product decisions it cannot find in the existing file, your notes, or recent reports under `docs/pulse-reports/`, and it writes that one file. It is not for roadmaps or implementation plans; for the spec of a single feature, use `trackbed:docs:feature-spec`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[section or notes]` | Optional. A section to revisit (`problem`, `approach`, `users`, `metrics`, `tracks`, `milestones`, or `non-goals`), or notes on what changed. Without it, the skill creates the file when it is missing and updates it when it exists. |

## Examples

```text
# Create STRATEGY.md, or update the one that exists
/trackbed:product:strategy

# Revisit one section
/trackbed:product:strategy metrics

# Update from notes
/trackbed:product:strategy active tracks: mobile is paused so we can focus on onboarding
```

## What you get

- `STRATEGY.md` at the repository root, created or updated. A file in the skill's own layout carries a `last_updated` date in its frontmatter.
- In an existing file, only the section you named, sections that new evidence contradicts, and sections you confirm are weak are changed. The skill summarizes the changes and asks before it overwrites, unless you asked for a direct update.
- A `STRATEGY.md` that a person or another tool wrote in its own shape keeps its headings and order, and gets the smallest edit that records the update. The skill asks before it adds frontmatter or new sections to it.
- Markers on anything not confirmed: `UNVERIFIED:` for inferred claims, `STALE:` for old context still in use, and `MISSING PRODUCT CONTEXT:` for gaps.
- A closing report that says whether the file was created or updated, which sections changed, and which markers remain.

When there is no `STRATEGY.md` but the repository has a product doc such as `PRODUCT.md` or `VISION.md`, the skill drafts from it and asks whether to merge it or link to it. It never edits or deletes that doc.
