# Script Helper Library

This directory contains shared shell, Python, and Node helpers used by standalone
scripts in `trackbed/scripts/`. Keep script-specific policy in the calling
script; keep behavior shared by multiple scripts here.

## Files

| File | Responsibility |
| --- | --- |
| `branch-roles.sh` | Selects the workbench branch and decides which branches are protected, from `trackbed.baseBranch`, the pre-1.0.0 `kramme.baseBranch`, and the remote default branch; used by `resolve-base.sh` and `pr:rebase` batch mode. |
| `inline_page.py` | Builds self-contained HTML pages: reads inline assets that cannot close their element, encodes JSON script data, pins scripts with a hash-based Content Security Policy, fills templates, and writes the page; used by the visual report, decisions, and walkthrough generators. |
| `pr_staging.py` | Opens run directories below `.trackbed/` that Git's local exclude file hides, and reads, writes, and locates their manifests, for the helpers that stage Pull Request files; callers own what a staged file may be. |
| `review_process.py` | Runs bounded Python review commands with noninteractive environments and process-group cleanup, and provides the `run`, `tail`, `git`, `gh_json`, `is_ancestor`, and `valid_branch` helpers; callers supply deadlines, and `git` and `gh_json` raise the caller's exception type. |
| `review-artifacts.sh` | Provides `load_review_artifact_patterns` to read a protected review-report pattern list under a missing-or-empty policy, and `untracked_paths_without_visual_pages` to drop generated visual report pages from a NUL-delimited untracked path list. Shared by `confirm-review-responses.sh`, `collect-review-diff.sh`, and `review-artifact-patterns.sh`. |
| `transcripts.py` | Reads agent JSONL events and identifies user text and tool calls. Shares Claude Code and Codex discovery and shell command splitting between the practice audit and session analysis. |
| `sources.yaml` | Records the upstream sources and revisions for the shared transcript code. |
| `EveryInc-LICENSE` | Contains the MIT notice for adapted session code. |
| `review-scope.sh` | Provides `collect_review_scope` to load repository scope and normalize the caller directory, and `review_untracked_paths` to emit the raw NUL-delimited untracked subset for content handoffs. |
| `shell-helpers.sh` | Provides required-argument validation, shell assignment quoting, JSON object emit/decode with a single Python guard, bounded command execution, signal cleanup, and a noninteractive review command environment. |
| `trackbed-paths.sh` | Resolves trackbed state and configuration paths: override, former `KRAMME_` override, XDG or home `trackbed/` file, then pre-1.0.0 and plugin-local legacy files. Shared by every hook through `hooks/lib/check-enabled.sh` and by the setup checker. |
| `skill-usage-cost.js` | Transcript indexing for `scripts/skill-usage.js cost` and `decisions`, and per-session cost and token summaries and rendering for `cost`. |
| `skill-usage-decision-requests.js` | Run selection, per-run counts of where a workflow stopped for the user, and rendering for `scripts/skill-usage.js decisions`. |
| `skill-usage-hosts.js` | Host detection, plugin manifest version lookup, and Codex rollout parsing for `scripts/skill-usage.js`. |

## Usage

Resolve the library from the calling script's own location so sourcing works
regardless of the caller's current directory:

```bash
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
# shellcheck source=lib/shell-helpers.sh
source "$SCRIPT_DIR/lib/shell-helpers.sh"
```

Scripts in a subdirectory should adjust the source path from their own
`SCRIPT_DIR`, for example `"$SCRIPT_DIR/../lib/shell-helpers.sh"`.

Node scripts require helpers relative to their own file, for example
`require("./lib/skill-usage-hosts")`. Node helpers use only Node core modules
because they ship unchanged into the converted Codex plugin.

## Boundary Rules

- Shell helpers must not change shell options such as `errexit`, `nounset`, or
  `pipefail`; callers own those policies.
- Shell helpers must handle their own expected failure paths instead of relying on
  `set -e`.
- Keep command-line policy and user-facing success output in the calling
  script.

## Verification

Run shell lint after changing a shell helper:

```bash
make -C trackbed lint-shell
```

Run the focused tests and type check after changing `skill-usage-hosts.js`:

```bash
make -C trackbed test-node-file NODE_TEST_FILE=tests/node/skill-usage-hosts.test.js
make -C trackbed lint-js
```

Run the focused tests and type check after changing `skill-usage-cost.js`:

```bash
make -C trackbed test-node-file NODE_TEST_FILE=tests/node/skill-usage-cost.test.js
make -C trackbed lint-js
```

Run the focused tests and type check after changing
`skill-usage-decision-requests.js`:

```bash
make -C trackbed test-node-file NODE_TEST_FILE=tests/node/skill-usage-decision-requests.test.js
make -C trackbed lint-js
```
