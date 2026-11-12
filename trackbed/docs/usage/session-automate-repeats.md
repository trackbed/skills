# session:automate-repeats

Use it to find the work you keep asking agents to do by hand, and the friction that keeps coming back, across recent agent sessions in this repository. It proposes improvements to the skill or subagent that already owns the work, and it can create new skills or subagents for repeated work that nothing covers yet. It never edits an existing skill or subagent. It is not for summarizing one session.

## Before you run it

- Claude Code or Codex session logs for this repository exist on your machine, or you pass paths to session files. Without a readable source, the skill asks for an export path and stops.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[session-paths]` | Session files or directories to review instead of the automatic search. A directory contributes its `.jsonl` files. A missing or unreadable path stops the run. |

## Options

| Option | Effect |
| --- | --- |
| `--recent N` | Review the N most recent sessions for this repository. |
| `--effectiveness` | Also report, for each skill, how often it ran when it fit the task, was missed, or ran when it did not fit. The counts are sample evidence, not a score. |
| `--create` | Create the new skills and subagents that qualify without asking you to confirm first. Existing files are never overwritten. |
| `--auto` | Same as `--create`. |

## Examples

```text
# Review this repository's sessions from the last 30 days and propose automation
/trackbed:session:automate-repeats

# Review the 15 most recent sessions and report how well the skills were used
/trackbed:session:automate-repeats --recent 15 --effectiveness

# Review exported sessions and create the new skills and subagents that qualify
/trackbed:session:automate-repeats exports/sessions --create
```

## What you get

- A closing summary in labelled parts: `REVIEWED`, `EFFECTIVENESS` when requested, `IMPROVE EXISTING`, `CREATED`, `NOT CREATED`, and `UNVERIFIED`.
- Under `IMPROVE EXISTING`, proposals only: the affected skill or subagent, how many sessions showed the problem, the proposed change, and how to check that it worked. Applying one is a separate request.
- New `SKILL.md` files under the repository's skills folder and new subagent files under its agents folder, after you confirm the plan or pass `--create`. When the repository's own instructions require it, the skill also adds a row for each one to the README or skill index. A pattern qualifies only when it shows up in at least two sessions or three separate requests.
- Working files under `.context/session-search/<timestamp>/automate-repeats/`, including `effectiveness.json` with `--effectiveness`.

The skill works from extracted outlines of your sessions and paraphrases what it finds. Remove the working files with `trackbed:workflow:cleanup-artifacts`.
