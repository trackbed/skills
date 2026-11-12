# Troubleshooting

Start with `/trackbed:setup`. It reports missing tools, the installed plugin version, and whether an update is waiting, and it changes nothing. Then find your symptom below.

## A command is missing

- **In Claude Code,** open `/plugin` to confirm the plugin is installed, then run `/reload-plugins` or restart the session. A new install or update is not active until you do.
- **In Codex,** run `codex plugin list`; the plugin appears as `trackbed@trackbed`. Commands start with `$` there, not `/`: `$trackbed:setup`.
- **The name starts with `kramme:`.** Release 1.0.0 renamed every command to `trackbed:`. [Renamed and Removed Commands](../../README.md#renamed-and-removed-commands) lists the replacements.
- **It is a Background skill.** These have no command; the host applies them on its own.
- **In Codex, every skill appears twice.** A copy from an earlier converter release is still installed. Run the checkout install again with `--yes` to remove it.

## Shell commands are blocked

- **A delete was refused.** The `block-rm-rf` hook stops destructive deletion and suggests `trash`. See [block-rm-rf](hooks.md#block-rm-rf) for what it blocks.
- **Every shell command is refused.** The safety hooks need `jq` and `python3`, and block shell commands when either is missing. Install them (see [Core Tools](../../README.md#core-tools)), or switch the safety hooks off as [Toggling Hooks](hooks.md#toggling-hooks) describes.
- **On native Windows,** run the host from Git Bash or WSL. PowerShell alone cannot run the hooks.
- **In Codex, a hook does not run.** Codex asks you to review and trust a new or changed plugin hook before it runs it.

## A commit asks for confirmation

The `confirm-review-responses` hook saw a report such as `REVIEW_OVERVIEW.md` among the staged files. Remove the reports with `/trackbed:workflow:cleanup-artifacts`, or confirm when the report belongs in the commit.

## Files are formatted when you did not expect it, or not at all

The `auto-format` hook formats a file after the agent edits it, using the formatter it detects in the project. [auto-format](hooks.md#auto-format) lists the formatters and the files it skips. To see why a formatter failed, set `TRACKBED_AUTOFORMAT_DEBUG=1`; see [Failure Diagnostics](hooks.md#failure-diagnostics). To switch it off, run `/trackbed:hooks:toggle auto-format disable`.

## A skill cannot reach Linear, GitHub, or a browser

- **Linear:** the Linear skills need the Linear MCP server connected and signed in. See [Linear](mcp-servers.md#linear).
- **GitHub:** Pull Request, review, and CI skills need the GitHub CLI signed in. Run `gh auth login`.
- **Browser:** `/trackbed:qa` and `/trackbed:browse` need Claude in Chrome, Chrome DevTools, or Playwright MCP. Without one, `/trackbed:qa` falls back to reading the code. See [Recommended MCP Servers](mcp-servers.md).

## A run stopped before it finished

- **It asked a question.** `/trackbed:linear:issue-to-pr` and `/trackbed:code:plan-to-pr` stop when they cannot decide something safely. Answer the [decision request](shipping.md#decision-requests) and the run continues.
- **The session ended in the middle of `issue-to-pr`.** Run it again with `--continue` on the same branch. See [Before Implementation](shipping.md#before-implementation).
- **A review or audit was cut off.** Run the same command with the same arguments within 24 hours on the unchanged code. Finished reviewers are reused. This needs `.context/` to be git-ignored. See [Resuming Interrupted Reviews and Audits](review.md#resuming-interrupted-reviews-and-audits).

## An update did not arrive or did not take effect

- The update notice is checked at most once a day, at the start of a session, so it can trail a release by a day.
- After updating, restart the host, or run `/reload-plugins` in Claude Code.
- Claude Code updates this plugin on its own only after you enable auto-update for the `trackbed` marketplace under `/plugin`.
- [Updating](../../README.md#updating) has the update command for each kind of install.

## SIW

The SIW guide has its own [troubleshooting list](siw.md#troubleshooting) for spec, issue, and Linear transfer problems.

## Still stuck

Open an issue at [trackbed/skills](https://github.com/trackbed/skills/issues) with the command you ran and the output of `/trackbed:setup`.
