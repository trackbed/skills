# How trackbed Works

trackbed adds three kinds of components to your coding agent: skills you run, agents that skills delegate to, and hooks that run on their own. This page explains each one and what they leave behind in your repository.

## Skills

A skill is a named workflow, such as reviewing a branch or opening a Pull Request. Everything the plugin does is a skill.

- **Running one.** Type `/trackbed:<name>` in Claude Code or `$trackbed:<name>` in Codex, followed by any arguments: `/trackbed:pr:code-review --base develop`.
- **Names.** Most names are `<area>:<action>`, so `pr:fix-ci` works on Pull Requests and `linear:next` works with Linear. [Find a Skill by Task](../../README.md#find-a-skill-by-task) maps what you want to do to the skill for it.
- **Who can start it.** A skill marked **User** runs only when you type it. A skill marked **User, Auto** can also be started by the host when your request matches it. A **Background** skill is applied by the host and has no command. Each skill's page shows its mode.
- **What it accepts.** Each skill's page lists its arguments and options, with examples.

## Agents

An agent is a specialist that a skill hands part of its work to, such as `trackbed:security-reviewer` or `trackbed:pr-test-analyzer`. `/trackbed:pr:code-review` starts the review agents that apply to your changes and combines what they report.

You rarely start an agent yourself. Most agents only report findings and cannot edit files; each [agent's page](../../README.md#agents) says whether it changes code and which skills use it.

## Hooks

A hook runs without being asked, around the host's own actions. `block-rm-rf` stops a destructive delete before it runs, `auto-format` formats a file after the agent edits it, and `update-check` tells you when a new version is out.

Every hook can be switched off with `/trackbed:hooks:toggle`. The [Hook Reference](hooks.md) describes each one.

## Reports

Many skills write their result as a Markdown file in your project, such as `REVIEW_OVERVIEW.md` from a code review. Other skills read that file: `/trackbed:pr:resolve-review` fixes the findings a review wrote down.

- Add `--inline` to get the result in the conversation instead of a file, on skills that support it.
- Add `--visual` to also get an interactive page. See [Visual Reports](visual-reports.md).
- These files are working files, not part of your change. `/trackbed:workflow:cleanup-artifacts` removes them, and the `confirm-review-responses` hook asks before one is committed.
- Skills that can resume after an interruption keep their progress under `.context/`, which must be git-ignored.

## Two Hosts, One Plugin

The plugin is written for Claude Code and converted into a native Codex plugin from the same source, so both hosts get the same skills and hooks. Two things differ:

- Commands start with `/` in Claude Code and `$` in Codex.
- In Codex, each agent is packaged as a skill.

## Where to Go Next

- [Quick Start](../../README.md#quick-start) installs the plugin and runs a first skill.
- [Workflows](../../README.md#workflows) shows the skills in the order a change moves through them.
- [Troubleshooting](troubleshooting.md) covers what to check when something does not work.
