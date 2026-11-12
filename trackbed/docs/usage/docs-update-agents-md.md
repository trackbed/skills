# docs:update-agents-md

Use it to add or change rules in `AGENTS.md`, the instruction file your agents read. It writes each rule as one bullet that starts with a strength keyword (`ALWAYS`, `NEVER`, `PREFER`, `CAN`, or `NOTE`), points to existing docs, scripts, and skills instead of copying them, and checks that every path, command, and skill it cites exists. It shows you the planned additions and edits the file after you confirm. It can also insert the Hard-Cut Greenfield Policy, a no-compatibility-code policy for projects with no released users.

## Examples

```text
# Add a rule you describe after the command
/trackbed:docs:update-agents-md Always use pnpm, never npm or yarn

# Add the no-compatibility-code policy to a project without released users
/trackbed:docs:update-agents-md Add the Hard-Cut Greenfield Policy
```

## What you get

- The planned additions, or a diff, for you to confirm before anything is written.
- The edited instruction file. The skill prefers `AGENTS.md`, uses `CLAUDE.md` or another instruction file when the project has only that, and creates `AGENTS.md` when there is none. When `CLAUDE.md` only imports `AGENTS.md`, it edits `AGENTS.md` alone.
- New rules placed in an existing section when one fits. A rule that already exists is updated in place, so running the skill again does not create duplicates.
- A list of every cited path, command, or skill it corrected or dropped because the target did not exist.
- For a rule about the code's structure that a lint rule, type, test, or script could enforce, that alternative proposed alongside the rule, with `trackbed:code:encode-constraint` suggested to build the check.

For the Hard-Cut Greenfield Policy, the skill inserts the policy text unchanged under the heading `## Hard-Cut Greenfield Policy`. It stops when the project already has users or the heading is already in the file.
