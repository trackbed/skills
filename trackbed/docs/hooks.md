# Hook Reference

Hooks run on their own around the host's work: before a shell command, after a file edit, when a session starts. The [hook table](../../README.md#hooks) lists all five with the event each one listens to. This page covers how to switch a hook off and what each one does in detail.

| Hook | What it does for you |
| --- | --- |
| [`block-rm-rf`](#block-rm-rf) | Stops destructive deletion commands before they run. |
| [`confirm-review-responses`](#confirm-review-responses) | Asks before review artifacts are committed. |
| [`auto-format`](#auto-format) | Formats a file after the agent edits it, with your project's formatter. |
| [`update-check`](#update-check) | Tells you when a newer plugin version is out. |
| [`skill-usage-stats`](#skill-usage-stats) | Records which skills you use, locally. |

## Toggling Hooks

Use `/trackbed:hooks:toggle` to enable or disable hooks:

```bash
# List all hooks and their status
/trackbed:hooks:toggle status

# Disable a hook
/trackbed:hooks:toggle auto-format disable

# Enable a hook
/trackbed:hooks:toggle auto-format enable

# Toggle a hook (enable if disabled, disable if enabled)
/trackbed:hooks:toggle auto-format

# Reset all hooks to enabled
/trackbed:hooks:toggle reset
```

State is stored in `${XDG_STATE_HOME:-$HOME/.local/state}/trackbed/hook-state.json` by default, with `TRACKBED_HOOK_STATE_FILE` override support and legacy fallback to `hooks/hook-state.json`. Releases before 1.0.0 kept state under `kramme-cc-workflow/` and read `KRAMME_*` overrides; every hook state and config path still uses an existing file there until a `trackbed/` file exists, and still reads a `KRAMME_*` override while the `TRACKBED_*` one is unset. When a hook is disabled, the hook script drains stdin before exiting to avoid broken-pipe errors if the runner is piping JSON input.

## block-rm-rf

`block-rm-rf` requires both `jq` and `python3` at runtime. If either binary is missing, the hook fails closed and blocks the Bash tool call until the dependency is installed or the hook is explicitly disabled.

### Blocked Patterns

**Direct commands:**

- `rm -rf` (and variants: `-fr`, `-r -f`, `--recursive --force`)
- `shred`, `unlink`

**Path variants:**

- `/bin/rm -rf`, `/usr/bin/rm -rf`, `./rm -rf`

**Bypass attempts:**

- `command rm -rf`, `env rm -rf`, `\rm -rf`
- `sudo rm -rf`, `xargs rm -rf`

**Subshell execution:**

- `sh -c "rm -rf ..."`, `bash -c "rm -rf ..."`, `zsh -c "rm -rf ..."`

**Find commands:**

- `find . -delete`
- `find . -exec rm -rf {} \;`

### Analysis Bound

The hook follows supported nested shell commands, `eval`, shell functions, executable heredocs, and command/process substitutions through analysis depth 5. A command that would require deeper analysis is blocked with the generic `rm -rf` reason, even when the hidden payload would ultimately be safe. This fail-closed bound prevents extra nesting from turning an unclassified destructive command into an allow decision; simplify an over-nested command so the hook can classify it.

### Allowed Commands

- `git rm` (tracked by git, recoverable)
- `echo "rm -rf"` (quoted strings are safe)
- `rm file.txt` (no recursive+force)
- `rm -r dir/` (recursive but no force)

### Why use `trash` instead of `rm -rf`?

The `trash` command moves files to the system Trash instead of permanently deleting them:

- **Recoverable**: Files can be restored from Trash if deleted accidentally
- **Safe**: No risk of catastrophic data loss from typos or glob expansion errors
- **Familiar**: Works just like `rm` but with a safety net

Install: `brew install trash`

> **Note:** This is a best-effort defense, not a comprehensive security barrier. There will always be edge cases that aren't covered.

## confirm-review-responses

`confirm-review-responses` asks before a commit that includes a review artifact, such as `REVIEW_OVERVIEW.md`, so a report left in the working tree is not committed by accident.

Edit `hooks/confirm-review-artifacts.txt` to configure which staged files should trigger confirmation. Entries support shell-style glob patterns, so generated artifacts like `PR_PLAN_*.md` can be guarded without listing every file explicitly.

## auto-format

### Supported Formatters

| Language              | Formatter     | Detection                          |
| --------------------- | ------------- | ---------------------------------- |
| JavaScript/TypeScript | Prettier      | `"prettier"` in package.json       |
| JavaScript/TypeScript | Biome         | `"@biomejs/biome"` in package.json |
| CSS/SCSS/JSON/HTML/MD | Prettier      | `"prettier"` in package.json       |
| Python                | Black         | `black` in pyproject.toml          |
| Python                | Ruff          | `ruff` in pyproject.toml           |
| Go                    | gofmt         | go.mod exists                      |
| Rust                  | rustfmt       | Cargo.toml exists                  |
| C#                    | dotnet format | \*.csproj exists                   |
| Shell                 | shfmt         | globally available                 |
| Nx workspace          | nx format     | nx.json exists                     |

**Priority**: trusted CLAUDE.md override > Biome > Prettier > global tools

### CLAUDE.md Override

Add a format directive to your project's CLAUDE.md to specify a custom formatter:

```markdown
format: bun run format
```

Or use the `formatter:` key:

```markdown
formatter: npm run format
```

Because this directive is executable project-controlled code, the hook only runs it when the project root is listed in a user-side trust file outside the repository.

Default trust file: `${XDG_CONFIG_HOME:-$HOME/.config}/trackbed/autoformat-trusted-roots`

Override the trust file location with `TRACKBED_AUTOFORMAT_TRUST_FILE`.

The trust file format is one absolute project root per line. Blank lines and `#` comments are ignored:

```text
# auto-format trusts
/Users/me/src/my-project
```

If a CLAUDE.md directive exists but the project is not trusted, the hook skips that directive, falls through to detected formatters, and reports how to enable the directive in the system message. Project-wide npm format scripts are also skipped in this case because they are executable project-controlled code.

Trust is checked on every invocation, including when formatter detection comes from the cache. Cached command strings remain data: the hook validates the cache shape, decodes empty and escaped fields losslessly, and never sources or evaluates the cache file.

### Caching

Detection results are cached in `${XDG_CACHE_HOME:-$HOME/.cache}/claude-format` to avoid re-scanning project files on every write. The cache is automatically invalidated when any of these files change:

- `CLAUDE.md`, `package.json`, `pyproject.toml`, `nx.json`, `go.mod`, `Cargo.toml`

To clear the default cache manually: `trash ~/.cache/claude-format`

If you install or remove a global formatter binary after the first run, clear the cache manually unless one of the watched project config files also changed.

Malformed cache data is ignored and replaced by a fresh detection result.

### Failure Diagnostics

Set `TRACKBED_AUTOFORMAT_DEBUG=1` to retain bounded formatter failure evidence locally. The hook stores only the latest failed attempt for the project at `${XDG_CACHE_HOME:-$HOME/.cache}/claude-format/<project-cache-key>.last-error.log`, limits retained stderr to 64 KiB, creates the file with mode `0600`, and reports its path in the hook message. Successful-attempt output is discarded, raw diagnostics never enter hook JSON, and an inability to create the diagnostic file does not prevent formatting.

Debug retention is off by default. Unset `TRACKBED_AUTOFORMAT_DEBUG` or set it to any value other than `1` to keep formatter output ephemeral.

### Skipped Files

The hook automatically skips:

- **Binary files**: png, jpg, pdf, zip, exe, dll, woff, etc.
- **Generated directories**: exact path components named `node_modules/`, `dist/`, `build/`, `.git/`, `vendor/`, `__pycache__/`, `coverage/`, `.cache/`, `.next/`, `.nuxt/`, or `.output/` (names such as `redist/` and `rebuild/` are not skipped)
- **Lock files**: \*.lock, package-lock.json, pnpm-lock.yaml
- **Source maps**: \*.map
- **Minified files**: _.min.js, _.min.css

## update-check

`update-check` runs when a new session starts: it is registered on `SessionStart` with the `startup` matcher, so resuming, `/clear`, and compaction do not run it. It can show two notices. Both arrive as the hook's `systemMessage`, which the host shows to you; the hook prints no plain stdout or `additionalContext`, which would go into the model's context:

- **A newer version is available.** At most once a day, the hook fetches `trackbed/.claude-plugin/plugin.json` from the `main` branch on raw.githubusercontent.com with `curl --max-time 2`. Only release Pull Requests change that version, so it is the version an update would install. When it is newer than the installed copy, the notice names both versions and the host's update instructions. The notice appears in the session that ran the check, so an update you skip is mentioned again the next day.
- **The plugin was updated.** The first session that starts on a newer installed version names the previous and new versions once. In Claude Code it also counts the changelog entries marked breaking in between, from the plugin's bundled `CHANGELOG.md`; Codex packages do not include the changelog, so the count is omitted there.

Claude Code notices recommend `/plugin marketplace update trackbed`, then `/reload-plugins`. Codex notices give both install paths explicitly: Git marketplaces use `codex plugin marketplace upgrade trackbed`, then `codex plugin add trackbed@trackbed`; local/checkout installs, including `npx`, rerun their original install command. Restart Codex after updating. The hook does not inspect Codex configuration or invoke the Codex CLI to select a path.

State lives in `${XDG_STATE_HOME:-$HOME/.local/state}/trackbed/update-check.json` by default; set `TRACKBED_UPDATE_CHECK_FILE` to override the path. It holds three fields:

- `checkedAt`: epoch seconds of the last check attempt, successful or not. A failed check is not retried until the next day.
- `latestVersion`: the newest release the last successful check found.
- `seenVersion`: the newest version a session has started with. It only moves forward, so an older copy installed in another scope or project never triggers a notice. The first run records the installed version without a notice.

`/trackbed:setup` reports this record as `Plugin update` without fetching anything.

The hook holds a Python `fcntl` file lock across the state read, check, and write. Concurrent startups skip the check silently, leaving any pending installed-version notice for a later startup. The lock file is `<state-file>.lock`; the OS releases the lock when its processes exit, including after termination, so the file may remain without blocking future checks.

The fetch is one HTTPS request a day per state file. It sends nothing beyond what any request reveals, such as your IP address and curl's user agent. Set `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` to any non-empty value to skip it; the update notice still works because it needs no network. Turn the whole hook off with `/trackbed:hooks:toggle update-check disable`.

The hook is fail-open. Missing `jq`, Python file-locking support, or `curl`, an unavailable state/lock path, an installed manifest without a release version, an unreachable GitHub, or malformed state all end in `{}` with no error. Malformed state is replaced as if it were the first run.

The check runs synchronously because Claude Code never shows a background (`async`) hook's `systemMessage` to the user; it goes to the model on the next turn instead. Claude Code lets you type while `SessionStart` hooks run, but its first response waits for them, which is why the fetch has a two-second limit and runs at most once a day. Agent SDK clients, which may include Conductor, can receive the message as an informational event, and whether it is displayed depends on the client.

Claude Code's own auto-update is off by default for this marketplace. Turning it on under `/plugin` → Marketplaces → `trackbed` makes the available-version notice rare, because Claude Code then updates the plugin in the background and shows its own `Plugin updated` message. Codex has no auto-update; it shows `systemMessage` as a warning and asks you to review and trust a new or changed plugin hook before it runs.

See [the decision record](decisions/2026-10-28-plugin-update-notices.md) for the alternatives that were rejected.

## skill-usage-stats

`skill-usage-stats` records local JSONL usage events when a prompt contains a `/trackbed:*` skill invocation or when a Skill tool event names a `trackbed:*` skill.

Releases before 1.0.0 named skills `kramme:*` under the plugin name `kramme-cc-workflow`. The recorder maps those spellings, and `report` maps stored `kramme:` records, to the matching `trackbed:` name, so usage from before the rename counts toward the current name.

Each record's `platform` field names the host that produced the event. The recorder resolves it in this order:

1. A non-empty `platform` field in the hook payload.
2. A non-empty `TRACKBED_AGENT_PLATFORM` environment variable.
3. `codex` when the payload has a non-empty `turn_id` or a `transcript_path` named `rollout-*.jsonl`.
4. `claude-code` when `CLAUDECODE` is `1`.
5. Otherwise an empty string.

Codex markers are checked before `CLAUDECODE` because a Codex process started from a Claude Code shell inherits `CLAUDECODE=1`.

Each record's `pluginVersion` field is the `version` from the plugin manifest beside the recorder: `.claude-plugin/plugin.json` in Claude Code and `.codex-plugin/plugin.json` in the converted Codex plugin. It is empty when neither manifest is readable and absent from records written before the field existed; reports treat both as `unknown`. The manifest version changes only at release, so a local install of an unreleased checkout reports the last released version.

When a Skill tool event names a skill that contains the plugin name `trackbed` but maps to no shipped skill, the recorder writes that name to an `unrecognizedSkill` field in place of `skill`. A host that changes how it names plugin skills produces these records, so the change shows up in reports instead of silently dropping events. Only the Skill tool's skill-name fields count; prompts, and therefore Codex events, never produce them.

For Codex prompts, the recorder ignores everything up to the last Conductor `</system_instruction>` block and accepts both `$trackbed:*` and `/trackbed:*` invocations. Claude Code prompts keep the `/trackbed:*` rule. The converted Codex plugin ships this hook and its recorder, but Codex has no Skill tool, so only the `UserPromptSubmit` entry fires there. Codex may also require you to trust plugin hooks before they run.

Records are stored outside the repository at:

```text
~/.local/state/trackbed/skill-usage.jsonl
```

Set `TRACKBED_SKILL_USAGE_FILE` to override the path, for example in tests or when keeping separate per-platform stats.

Generate a report:

```bash
node scripts/skill-usage.js report --since 30d
node scripts/skill-usage.js report --kind explicit --json
node scripts/skill-usage.js report --json --strict
node scripts/skill-usage.js report --platform codex --since 30d
node scripts/skill-usage.js report --plugin-version 0.89.0
```

`--platform` accepts `claude-code`, `codex`, `unknown` (records with an empty `platform`), or `all` (the default). `--plugin-version` accepts a version, `unknown` (records without one), or `all` (the default); use it to compare how a skill was used before and after a release.

Every report also checks whether recording has stalled. It compares the records of the last 7 days with the median weekly count of the 8 weeks before them, across the whole usage file and regardless of report filters. When that median is at least 20 and the last 7 days hold under a quarter of it, the report writes a warning to stderr: recording may have stopped, or usage fell. Because the baseline follows the data, the warning catches the start of a gap; after about a month of low counts it stops. The warning never changes the exit status, even with `--strict`. `unrecognizedSkill` records count toward neither side; the skipped-line diagnostics below report them.

Scan existing transcript files for historical explicit invocations:

```bash
node scripts/skill-usage.js scan ~/.claude/projects --json
```

Scan Codex sessions the same way:

```bash
node scripts/skill-usage.js scan ~/.codex/sessions --since 30d --json
```

Scan treats a file whose first line is a Codex `session_meta` record as a Codex rollout and streams it line by line. Only the first `session_meta` classifies the file, because forked threads replay parent history after a second one. Subagent threads (`thread_source` `subagent`, or a `source` object with a `subagent` key) are skipped without reading further. In top-level threads, scan counts explicit invocations in user messages only. It skips injected `# AGENTS.md instructions for` and `<environment_context>` messages and ignores text before the last Conductor `</system_instruction>`. It also ignores developer and assistant messages and the user text that `event_msg` and `compacted` records repeat. Each thread id is one session, and `--since` filters by message timestamp. Large tool output can exceed the 1 MiB line limit, so whole-history Codex scans usually report a few overlong-line diagnostics. Once the Codex hook records events, do not add `scan` totals to `report --platform codex` totals for the same period; both count the same sessions.

Reports and scans tolerate degraded input by default. They retain valid totals, write skipped-line and read-failure diagnostics to stderr, and exit successfully. Healthy `--json` output remains an array. When diagnostics occur, JSON output is an object with `summary` and `diagnostics` fields instead. Add `--strict` to render the same result but exit nonzero when any input was skipped or could not be read. Individual JSONL records larger than 1 MiB are skipped with diagnostics so malformed or truncated lines cannot make memory use unbounded. Reports leave `unrecognizedSkill` records that match their filters out of the totals, count them as skipped lines, and name the latest one on stderr; `cost` ignores them, and earlier versions of the script skip them as invalid usage records.

Scan treats JSONL as its canonical streaming format. Whole-document JSON and plaintext use a compatibility fallback limited to 1 MiB per file. Larger non-JSONL files are skipped with diagnostics; `--strict` makes that condition fail the command after rendering the degraded result.

Each scan tracks physical directory and file identities across all supplied roots. Symlink aliases, directory cycles, hardlinks, and overlapping roots do not count the same transcript twice. Device/inode identity is used when available, with a resolved-path fallback when the filesystem supplies no inode. Distinct files with identical content and repeated events within a file still count separately. Identities reset for every scan invocation. Roots retain their supplied order, directory entries retain their sorted order, and directory pruning still applies to the encountered path before it is marked visited. The first encountered unpruned path supplies the transcript and any read diagnostics; later aliases do not retry it within that scan.

The hook is silent and fail-open. If Node.js is unavailable, if the payload cannot be parsed, or if recording fails, the hook returns `{}` and does not block the session.

### Estimate cost per entry skill

`cost` joins the usage file with local Claude Code transcripts to show where session budget goes, per entry skill and per subagent type:

```bash
node scripts/skill-usage.js cost --since 30d
node scripts/skill-usage.js cost --since 2026-10-06 --json
node scripts/skill-usage.js cost --projects /path/to/claude/projects --limit 10
```

Costs are API-equivalent estimates taken from Claude Code's `cost-state` records, including on subscription plans. They are not billed spend. The command is read-only, local, and offline. It reads only the transcripts of sessions named in the usage file, from `--projects`, which defaults to `$CLAUDE_CONFIG_DIR/projects` or `~/.claude/projects`.

- **Entry skill.** A session's entry skill is its earliest `explicit` record. Sessions with only `tool` records form a `(tool only)` row. `--since` applies to the entry record, or to the earliest record of a tool-only session. Records with `platform` `codex` are excluded because Codex rollouts have no `cost-state` records.
- **Session cost.** The last `cost-state` `totalCostUSD` in `<project>/<session-id>.jsonl`. Snapshots are cumulative and already include subagent usage. A session with `hasUnknownModelCost` counts toward `unknownModelCostSessions`.
- **Limit hits.** A session counts in `limitHitSessions` when its main transcript has an assistant record with `isApiErrorMessage: true` whose text contains "hit your session limit". The same phrase in user or queue records, and hits inside subagent transcripts, do not count.
- **Weighted tokens.** Each assistant `message.id` counts once per file, because Claude Code repeats the same usage on every content-block line. Weights are input + 1.25 × cache creation + 0.1 × cache read + 5 × output tokens. Subagent weights come from `<session-id>/subagents/agent-*.jsonl` and nested workflow directories, and the paired `agent-*.meta.json` supplies `agentType` and whether `model` overrides the parent model.

JSON rows have `entrySkill`, `sessions`, `sessionsWithTranscript`, `sessionsWithCost`, `totalCostUSD`, `medianCostUSD`, `maxCostUSD`, `unknownModelCostSessions`, `limitHitSessions`, `mainWeightedTokens`, `subagentWeightedTokens`, `subagentShare`, and `agentTypes` (`agentType`, `launches`, `modelOverrides`, `weightedTokens`, and `share` of the row's weighted tokens). Rows are sorted by total cost. The table shows the top three agent types, drops the pre-1.0.0 `kramme-cc-workflow:` prefix from older records, and ends with a totals line.

`cost` follows the same diagnostics and `--strict` contract as `report`. Unreadable transcript, subagent, or meta files are read failures. Malformed or overlong lines and invalid meta files are skipped lines; a subagent with invalid meta reports as `(unknown)`. Claude Code deletes old transcripts after its cleanup period, so a missing transcript is not a diagnostic; it shows as `sessions` minus `sessionsWithTranscript`. Large tool results exceed the 1 MiB line limit, so real histories usually report a few overlong-line diagnostics.

Stdout carries only skill names, agent types, counts, costs, and token weights. Prompts, subagent task descriptions, and paths stay off stdout; stderr diagnostics keep the `file=<path>` format.

### Count decision requests per workflow

`decisions` counts how often a `trackbed:linear:issue-to-pr` or `trackbed:code:plan-to-pr` run stopped for the user, and how easy those stops were to answer. Like `cost`, it joins the usage file with local Claude Code transcripts:

```bash
node scripts/skill-usage.js decisions --since 30d
node scripts/skill-usage.js decisions --since 2026-10-14 --until 2026-11-12
node scripts/skill-usage.js decisions --plugin-version 1.0.1 --json
```

The command is read-only, local, and offline. A run is a Claude Code session with an `explicit` record of one of the two workflows. Its first such record supplies the date and the plugin version. `--since` is inclusive and `--until` is exclusive. `--plugin-version` accepts a version, `unknown`, or `all` (the default). Codex sessions are excluded.

Counting starts at the message that invokes the workflow and stops at the workflow's final report. Subagent records are skipped.

- **Dialog request.** A call to a tool whose name contains `AskUserQuestion`. It is `answered` when a result came back, `cancelled` when the result is an error or says the question was cancelled or interrupted, and `unanswered` when no result exists.
- **Message request.** The last assistant message before a reply from the user.
  - `words` counts that message.
  - `replyWords` counts the reply as typed: without any Conductor instruction block, and without the elements Claude Code stores around a slash command.
  - `opensWithDecision` counts messages whose first three non-empty lines hold a question mark or start a decision request: `Decision needed`, `Decision N of M`, or `Action needed`.
- **Kind.** The first match wins:
  1. `state-gate`: the text says "proceed with implementation" or "move the issue to".
  2. `base-drift`: it says "base drift", or both "behind" and "rebase".
  3. `review-budget`: it says "budget", "cycle", or "round".
  4. `other`: everything else.

  A dialog is classified by its headers, questions, and option labels. A message is classified by its first three non-empty lines and its lines that hold a question mark, because the rest usually recaps the run.

- **Limit stall.** A reply to a Claude Code error or placeholder message, or a reply that is only `resume` or `continue` to a message that asks nothing. A message asks when it holds a question mark or opens with a decision request's first line; such a reply to it is a message request. A limit stall is not a decision request.
- **Report follow-up.** A user message after the final report. It is not a decision request.
- **Final report.** A message with a `Pull Request:` line that holds a link or `not created (--ship was not supplied)`, a `Completion disposition: success` line, or the phrase "What to focus on in review". A message that opens with a decision request's first line never counts as a report.

Two limits follow from these rules:

- A run that stops after its Pull Request is open still prints the Pull Request line, so replies to it count as follow-ups.
- A message the user never replied to is not counted, because nothing marks it as a request.

JSON rows have `skill`, `runs`, `runsWithTranscript`, `runsWithDecisionRequest`, `decisionRequests`, `requestsPerRun`, `byKind` (`kind`, `dialog`, `message`), `dialogs` (`total`, `answered`, `cancelled`, `unanswered`), `messages` (`total`, `opensWithDecision`, and `words` and `replyWords` with `median`, `p90`, and `max`), `limitStalls`, and `reportFollowUps`. `runs` counts every selected run. `runsWithTranscript` counts runs whose transcript was read and holds the invoking message, and every number after it comes from those runs.

`decisions` follows the same diagnostics and `--strict` contract as `cost`. Stdout carries only skill names and counts. Prompts, questions, replies, and paths stay off stdout; stderr diagnostics keep the `file=<path>` format.

## Codex Hook Command Support

Current generated Codex hook commands are POSIX shell command strings. Windows compatibility is not promised until `commandWindows` support is added to the converter and covered by tests.

Generated bootstrap code does not read from stdin. Hooks that parse or drain JSON input expect the runner to close stdin after writing the payload; a deliberately open pipe is outside the broad non-hang contract for those hook bodies.
