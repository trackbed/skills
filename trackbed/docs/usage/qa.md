# qa

Use it to test a running web app and get findings with evidence. It opens a few key routes, the routes your branch changed, or one route you name, and records screenshots, console output, and failed requests. It reports problems and recommends fixes; it does not change code. To log bugs you found by hand, use `trackbed:qa:intake`; to trace one bug to its cause, use `trackbed:debug:investigate`.

## Before you run it

- The app is running and reachable at the URL.
- A browser MCP server is connected: Claude in Chrome, Chrome DevTools, or Playwright. See [MCP servers](../mcp-servers.md#claude-in-chrome). Without one, the run falls back to reading the code and says so in the report.

## Arguments

| Argument | Meaning |
| --- | --- |
| `<url\|auto>` | The URL to test, such as `http://localhost:3000`, or `auto` to find a running local dev server. |
| `quick` | The default mode: the landing page plus two or three key routes. |
| `diff-aware` | Test the routes affected by the UI files your branch changed. |
| `targeted <route>` | Test one route, such as `/settings/profile`. |

## Options

| Option | Effect |
| --- | --- |
| `--base <branch>` | Compare against `<branch>` instead of the detected base branch. Used by `diff-aware` mode. |
| `--regression` | Compare this run with the `QA_BASELINE.json` from an earlier run, and report which issues are fixed, new, persistent, or not checked again. |
| `--inline` | Reply with the report in the conversation instead of writing `QA_REPORT.md`. `QA_BASELINE.json` is still written. Cannot be combined with `--visual`. |
| `--visual` | Also write `QA_REPORT.html`, an interactive page of the same report. See [Visual Reports](../visual-reports.md). |
| `--legacy-console` | For an older app with a noisy console: warnings become Info findings instead of Minor or Major. Console errors are still findings. |

## Examples

```text
# Smoke-test the landing page and a few key routes
/trackbed:qa http://localhost:3000

# Find the running dev server and test the routes this branch changed
/trackbed:qa auto diff-aware --base develop

# Test one route
/trackbed:qa http://localhost:3000 targeted /settings/profile

# Compare with the previous run and also get the interactive page
/trackbed:qa http://localhost:3000 --regression --visual
```

## What you get

- `QA_REPORT.md` in the project root: every planned route with its result, findings numbered `QA-001`, `QA-002`, and so on with severity, steps to reproduce, expected and actual behavior, and a recommended fix, a health score from 0 to 100, and a recommendation of ready, not ready, or ready with caveats.
- `QA_BASELINE.json` in the project root, which later `--regression` runs compare against.
- A short summary in the conversation with the verdict and the number of findings per severity.

The run asks before any action that could change shared data, such as submitting a form. Do not commit the two files; `trackbed:workflow:cleanup-artifacts` removes them.
