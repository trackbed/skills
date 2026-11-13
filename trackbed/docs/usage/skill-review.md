# skill:review

Use it to check a skill against the skill-authoring standards: focused scope, prompt size, portability, safety, retry behavior, error handling, and documentation. It reads the skill and reports findings in the conversation. It edits nothing and writes no file. To scaffold a new skill, use `trackbed:skill:create`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[skill-path \| skill-name \| proposed skill text]` | A path to a `SKILL.md` or a skill directory, a skill name that is looked up under `skills/` in the current directory, or pasted draft text. Without it, every `skills/*/SKILL.md` changed in the current diff is reviewed. |

## Examples

```text
# Review the skills changed in the current diff
/trackbed:skill:review

# Review one skill by name
/trackbed:skill:review pr:code-review

# Review a skill by path
/trackbed:skill:review skills/qa/SKILL.md
```

## What you get

- Findings ordered by severity: Critical, Major, Minor, Nit. Each has a location, the problem, why it matters, and a concrete fix.
- A snapshot that marks each review area `Pass`, `Watch`, or `Fail`, or `N/A` when it does not apply.
- For a skill on disk, the results of a static SkillSpector scan when the `skillspector` CLI is installed. High and critical scanner findings are treated as review findings unless inspection shows they are false positives.
- With several changed skills, one findings section per skill and a combined snapshot.

If you also ask for fixes, the review is completed first and the edits are a separate step.
