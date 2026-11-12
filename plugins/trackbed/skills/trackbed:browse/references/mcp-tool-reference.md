# Browser MCP Tool Reference

Maps each browser action to the correct MCP tool per provider.

## Tool Mappings

| Action | claude-in-chrome | chrome-devtools | playwright |
| --- | --- | --- | --- |
| Navigate | `mcp__claude-in-chrome__navigate` | `mcp__chrome-devtools__navigate_page` | `mcp__playwright__browser_navigate` |
| Page snapshot | `mcp__claude-in-chrome__read_page` | `mcp__chrome-devtools__take_snapshot` | `mcp__playwright__browser_snapshot` |
| Screenshot | `mcp__claude-in-chrome__computer` (action: screenshot) | `mcp__chrome-devtools__take_screenshot` | `mcp__playwright__browser_take_screenshot` |
| Click | `mcp__claude-in-chrome__computer` (action: click) | `mcp__chrome-devtools__click` | `mcp__playwright__browser_click` |
| Fill input | `mcp__claude-in-chrome__form_input` | `mcp__chrome-devtools__fill` | `mcp__playwright__browser_type` |
| Fill form (batch) | `mcp__claude-in-chrome__form_input` | `mcp__chrome-devtools__fill_form` | `mcp__playwright__browser_fill_form` |
| Read console | `mcp__claude-in-chrome__read_console_messages` | `mcp__chrome-devtools__list_console_messages` | `mcp__playwright__browser_console_messages` |
| Read network | `mcp__claude-in-chrome__read_network_requests` | `mcp__chrome-devtools__list_network_requests` | `mcp__playwright__browser_network_requests` |
| Hover | `mcp__claude-in-chrome__computer` (action: hover) | `mcp__chrome-devtools__hover` | `mcp__playwright__browser_hover` |
| Press key | `mcp__claude-in-chrome__computer` (action: key) | `mcp__chrome-devtools__press_key` | `mcp__playwright__browser_press_key` |
| Get page text | `mcp__claude-in-chrome__get_page_text` | N/A | N/A |
| Tab management | `mcp__claude-in-chrome__tabs_create_mcp` | `mcp__chrome-devtools__new_page` | N/A |

## Detection Strategy

To detect which MCP is available, check for any tool starting with the prefix:

- `mcp__claude-in-chrome__` -> claude-in-chrome is available
- `mcp__chrome-devtools__` -> chrome-devtools is available
- `mcp__playwright__` -> playwright is available

Use the first available provider in the priority order for the target (SKILL.md Step 2):

- Local targets (`auto`, `localhost`, `127.0.0.1`, `[::1]`): chrome-devtools, then playwright, then claude-in-chrome. The first two normally run their own browser profile, which keeps the user's accounts out of reach.
- Other targets: claude-in-chrome, then chrome-devtools, then playwright. claude-in-chrome has the broadest capabilities.

## Provider-Specific Notes

### claude-in-chrome

- Runs in the user's own Chrome profile, with their signed-in accounts and open tabs
- Uses `computer` tool for screenshots, clicks, and hover with an `action` parameter
- Has `form_input` for filling inputs (more reliable than click-then-type)
- Has `get_page_text` for extracting full page text
- Supports GIF recording via `gif_creator`
- Tab management via `tabs_context_mcp` and `tabs_create_mcp`

### chrome-devtools

- Starts its own browser profile by default (`--isolated` makes it temporary); it reaches the user's browser only when configured to connect to an already running Chrome
- Direct `click`, `fill`, `hover` tools (no composite `computer` tool)
- Has `take_snapshot` for DOM snapshot and `take_screenshot` for visual
- Has `fill_form` for batch form filling
- Supports `evaluate_script` for running JavaScript

### playwright

- Starts its own browser profile by default (`--isolated` keeps it in memory); it reaches an existing browser only when configured to
- `browser_snapshot` returns an accessibility tree (useful for understanding page structure)
- `browser_take_screenshot` for visual screenshots
- Supports `browser_evaluate` for running JavaScript
- Has `browser_install` for installing browser binaries
