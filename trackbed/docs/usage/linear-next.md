# linear:next

Use it when you are deciding what to pick up next from a Linear team. It collects unstarted issues that are assigned to you or unassigned, checks each for value, blockers, and readiness, recommends one, and looks for more that can be worked on in parallel. It is read-only, except that in a Conductor cloud workspace it offers to start the issues you confirm, each in a new workspace. To clean up the backlog first, use `trackbed:linear:backlog-refine`.

## Before you run it

- The Linear MCP server is connected. See [MCP servers](../mcp-servers.md#linear).

## Arguments

| Argument | Meaning |
| --- | --- |
| `[team or selection query]` | A team name, key, or ID, a request in plain words such as `find 5 agent-ready issues in Backlog`, or both. Without a team, the only team is used, or you are asked. |

## Options

| Option | Effect |
| --- | --- |
| `--state <name>` | Include only issues in this workflow state. Repeat the flag for several states. By default every backlog and unstarted state counts. |
| `--agent-ready` | List only issues an agent can finish and verify without a human decision, a missing design, special access, or sign-off. |
| `--interest <preference>` | Prefer this kind of work when ranking, such as `small bug fixes`. It filters only when you say `only`. |
| `--mine` | Consider only issues assigned to you. |
| `--unassigned` | Consider only unassigned issues. |
| `--both` | Consider issues assigned to you and unassigned ones. This is the default. |
| `--project <name>` | Consider only issues in this project. |
| `--label <name>` | Consider only issues with this label. |
| `--count <n>` | How many ready issues to find and rank. The default is 10 and the maximum is 25. |
| `--limit <n>` | Collect at most this many candidates each from your issues and from the unassigned ones, highest priority first. The default is 150 and the maximum is 250. |
| `--all` | Assess every matching issue in the backlog instead of stopping once enough ready ones are found. Cannot be combined with `--limit`. |

## Examples

```text
# Recommend the next issue from your team
/trackbed:linear:next

# Find five unassigned issues an agent can implement on its own
/trackbed:linear:next ENG --agent-ready --unassigned --count 5

# Describe the selection in plain words
/trackbed:linear:next find issues in Backlog or To-do that are ready for autonomous implementation

# Check the whole backlog and prefer small bug fixes
/trackbed:linear:next ENG --all --interest "small bug fixes"
```

## What you get

- The filters that were applied and how much of the backlog was covered.
- One recommended issue with a plain-language summary, the reasons for the choice, and its readiness.
- Up to four more ready issues that are independent of the recommendation and of each other.
- A ranked shortlist with an estimate of the UI/UX work in each issue, and the valuable issues that are not ready with what each one needs.
- In a Conductor cloud workspace, an offer to start the shortlisted issues an agent can finish there. Each one you confirm gets a new workspace that runs `trackbed:linear:issue-to-pr` with `--ship`.

Next, start the issue you picked with `trackbed:linear:issue-implement`.
