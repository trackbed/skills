# setup

Use it after you install the plugin, when a skill fails because a tool may be missing, or before you start work in a new workspace. It checks the tools the skills depend on, the repository and workspace you are in, and the plugin's version and update status. It is read-only: it installs nothing and edits no configuration.

## Options

| Option   | Effect                                                          |
| -------- | --------------------------------------------------------------- |
| `--json` | Print the check results as JSON instead of the readable report. |
| `--help` | Show the checker's usage and run no checks.                     |

## Examples

```text
# Check the environment and get a readable report
/trackbed:setup

# Get the same check results as JSON
/trackbed:setup --json
```

## What you get

- A report in four groups. `Required` covers Bash, Git, `jq`, Python 3.10+, and Node.js 18+. `Recommended` covers tools for common Pull Request, verification, and conversion workflows, such as `gh`. `Optional` covers tools that only some skills need. `Context` covers the repository, the Conductor workspace, the cached plugin versions, the auto-update setting, and whether a newer release has been recorded.
- An install command for each missing tool, as a suggestion. The skill does not run it.
- `manual-check` for integrations it cannot inspect from the shell, such as the Linear and Figma connectors.
- A closing status: `Ready`, `Ready with optional gaps`, or `Blocked` when a required tool is missing, too old, or not working.
- Cleanup notes after the status, such as a `.context/` folder that Git does not ignore, leftovers from earlier Codex installs, or an available plugin update with the commands to install it. The skill does not act on them.
