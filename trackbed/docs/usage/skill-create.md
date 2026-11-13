# skill:create

Use it to start a new plugin skill. It asks what the skill should do, how it is triggered, and what it needs, checks that a new skill is warranted, settles the name and frontmatter with you, and then creates the skill's directory with a `SKILL.md` to fill in. It writes new files under `skills/` and never overwrites an existing skill. It does not edit existing skills; to check a skill against the authoring standards, use `trackbed:skill:review`.

## Before you run it

- Run it from a plugin root that contains a `skills/` directory.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[skill-name or description]` | A name in `domain:action` form, such as `docs:check-links`, or a free-text description of what the skill should do. Without it, the interview starts with the purpose. |

## Examples

```text
# Start the interview with nothing decided
/trackbed:skill:create

# Start with a name
/trackbed:skill:create docs:check-links

# Start with a description
/trackbed:skill:create a skill that checks Markdown files for dead links
```

## What you get

- `skills/{skill-name}/SKILL.md` with the frontmatter you approved and TODO placeholders for the body.
- For a skill with supporting files, placeholder files under `references/` and `assets/`, and under `scripts/` for the most complex tier.
- `references/sources.yaml` when the skill draws on external sources.
- The result of a checklist over structure, frontmatter, and content, with a fix for each failing check. When the SkillSpector scanner is available, a static scan is part of it.
- A summary of the files created and the next steps. If the plugin keeps a skills index, a table row to add to it.

Nothing is committed. A name that is malformed or already taken stops the run and asks for another.
