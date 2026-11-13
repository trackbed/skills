# code:encode-constraint

Use it when an agent keeps making the same mistake, or a reviewer keeps leaving the same comment, and you want the repository to reject it from now on. It turns one mistake into the strongest check the repository can enforce: a type or API change that makes the mistake impossible to write, a compiler or lint rule, or a test or check script, each with a failure message that names the fix. It edits files and leaves the changes uncommitted; it never commits, pushes, or opens a Pull Request. To find other places where the same bug occurs, use `trackbed:debug:find-sibling-bugs`; to audit agent instructions, use `trackbed:code:audit-agent-config`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[mistake description]` | Free text that describes the mistake. |
| `[path:line example]` | A location that holds an instance of the mistake. |
| `[review comment]` | A pasted review comment, or a link to one that the agent can read. |

Give one of these. With no argument, it uses the most recent correction you made to the agent's output in this conversation. It handles one mistake per run: when the input describes several unrelated ones, it takes the first and lists the rest.

## Examples

```text
# Encode your latest correction from this conversation
/trackbed:code:encode-constraint

# Describe the mistake
/trackbed:code:encode-constraint Modules outside src/billing import from src/billing/internal

# Point at an instance of it
/trackbed:code:encode-constraint src/orders/api.ts:42
```

## What you get

- Uncommitted changes that add the check, wire it into the repository's normal verification and CI, and fix the existing violations. When there are many, or a fix would change behavior, they are recorded in a baseline that can only shrink.
- A report in the conversation: the rule in one sentence, the mechanism chosen and why stronger ones were rejected, the exact failure message, proof that the check fails on the mistake and passes on the repository, and follow-ups.
- A question before it adds a dependency, a new tool, or a CI job, or changes a public interface.
- When no tool can decide the rule, a drafted instruction rule in the report and no check. Add it with `trackbed:docs:update-agents-md`.
- A list of existing instruction rules that the new check now enforces, with their locations. They are not edited.
