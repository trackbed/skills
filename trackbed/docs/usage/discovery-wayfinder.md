# discovery:wayfinder

Use it when an initiative is too large or too uncertain to plan in one session. It charts the open decisions as a local map of tickets under `.context/`, then resolves one ticket per session until the route is clear enough for normal planning. It is planning only: it does not implement the initiative, and it never creates or changes Linear, GitHub, or Jira records. When the route is already clear, use `trackbed:siw:init` or `trackbed:linear:issue-define` instead.

## Before you run it

- Git ignores `.context` in the worktree. If it does not, the skill stops and asks for an ignored location or permission to update the ignore rules.
- When several agents or workspaces work on one map, you name one map owner. Only the owner assigns tickets and edits the map.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[initiative description]` | Chart a new map for this initiative. Charting takes the whole session, and no ticket is resolved in it. |
| `[map-path]` | The path to an existing `MAP.md`, or to its folder. Resolves the first ticket that is ready and unclaimed. |
| `[ticket-id]` | After a map path: resolve this ticket, such as `WF-003`. If it is blocked, claimed, resolved, out of scope, or missing, the skill says so and stops. |

## Examples

```text
# Chart a new map for an uncertain initiative
/trackbed:discovery:wayfinder Move billing from per-seat to usage-based pricing

# Resolve the next ready ticket on an existing map
/trackbed:discovery:wayfinder .context/wayfinder/usage-based-pricing/MAP.md

# Resolve one named ticket
/trackbed:discovery:wayfinder .context/wayfinder/usage-based-pricing/MAP.md WF-003
```

## What you get

- From charting: `.context/wayfinder/<map-slug>/MAP.md` and one file per ticket under `tickets/`. The map names the destination and lists the decisions so far, every ticket with its status and blockers, the areas not yet specified, and what is out of scope. The skill reports the map path and the tickets that are ready.
- From a ticket session: the answer and its evidence written to the ticket file, and the map updated. The skill reports the answer in one line, the tickets that became ready, and what is still unclear. Then it stops, even when other tickets are ready.
- Each ticket is one question of type `research`, `prototype`, `grilling`, or `task`. Questions that need your judgment are put to you; the skill does not answer them for you.
- When nothing is left open: `WAYFINDER CLEAR`, a `WAYFINDER EXIT BRIEF` with the destination, each decision, and the remaining assumptions, and a recommended next workflow. The skill does not start that workflow.

If the initiative does not need a map, the skill stops with `WAYFINDER NOT NEEDED` and recommends a smaller workflow.
