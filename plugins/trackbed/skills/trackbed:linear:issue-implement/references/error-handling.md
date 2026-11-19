# Error Handling

## Git Errors

- Merge conflicts: Ask user to resolve manually
- Push failures: Suggest manual push command
- Branch conflicts: Offer rename options

## Linear API Errors

- Linear MCP operations unavailable: before concluding that the server is not connected, load its Linear tools through the host's tool discovery (Claude Code can defer MCP tools until a `ToolSearch` query loads them) and make one real Linear call, such as the Step 1.2 issue lookup. Only when discovery finds no Linear tools, or that call fails with a connection error, stop and ask the user to connect the Linear MCP server. An authentication error is the "Authentication" case and a not-found result is the "Not found" case below, not a disconnected server
- Rate limits: Wait and retry
- Authentication: Direct user to check MCP setup
- Not found: Verify issue ID and access
- Workflow status ambiguous under `--set-in-progress`: stop before branch setup and report the current state metadata and the team statuses that could not be matched; never infer that a Todo or Ready display name has backlog type
- Status transition declined or failed under `--set-in-progress`: stop before branch setup with the prior state, intended target status, and update error or read-back mismatch; do not implement on an unverified transition

## Implementation Errors

- Test failures: Present errors, ask how to proceed
- Build failures: Show full error output
- Lint errors: Fix automatically if minor, ask if significant
