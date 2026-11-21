#!/usr/bin/env bats

load 'test_helper/common'

setup() {
  TMP_ROOT="$(mktemp -d)"
  SCRIPT="$BATS_TEST_DIRNAME/../scripts/lint-skill-contracts.py"
  COMPONENT_GENERATOR="$BATS_TEST_DIRNAME/../scripts/generate-component-reference.py"
  RESERVATION_HELPER="$BATS_TEST_DIRNAME/../scripts/siw-issue-reservation.sh"
}

teardown() {
  rm -rf "$TMP_ROOT"
}

file_mode() {
  python3 -c 'import os, stat, sys; print(f"{stat.S_IMODE(os.stat(sys.argv[1]).st_mode):04o}")' "$1"
}

write_minimal_skill() {
  local path="$1"
  local body="$2"
  write_file "$path" <<EOF
---
name: test-skill
description: Test skill
disable-model-invocation: false
user-invocable: true
---
$body
EOF
}

write_text_contract_inventory_fixture() {
  write_file "$TMP_ROOT/contracts/a.md" <<'EOF'
Canonical inventory marker: alpha
EOF
  write_file "$TMP_ROOT/contracts/b.md" <<'EOF'
Canonical inventory marker: alpha
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "text_contracts": [
    {
      "name": "sample-inventoried-contract",
      "extract_regex": "Canonical inventory marker: ([A-Za-z]+)",
      "inventory": {
        "glob": "contracts/*.md",
        "marker": "Canonical inventory marker:"
      },
      "paths": [
        "contracts/a.md",
        "contracts/b.md"
      ]
    }
  ]
}
EOF
}

siw_spec_exclusion_expected_paths() {
  printf '%s\n' \
    "trackbed/skills/discovery:interview/references/siw-mode.md" \
    "trackbed/skills/siw:generate-phases/SKILL.md" \
    "trackbed/skills/siw:init/SKILL.md" \
    "trackbed/skills/siw:spec-audit/SKILL.md" \
    "trackbed/skills/siw:spec-audit/references/spec-resolution.md" \
    "trackbed/skills/siw:transfer-to-linear/references/artifact-extraction.md" \
    "trackbed/skills/workflow:cleanup-artifacts/references/siw-mode.md"
}

write_reference_skill() {
  local path="$1"
  local name="$2"
  local description="$3"
  local disable_model_invocation="$4"
  local user_invocable="$5"
  local argument_hint="${6:-}"

  if [ -n "$argument_hint" ]; then
    write_file "$path" <<EOF
---
name: $name
description: $description
argument-hint: $argument_hint
disable-model-invocation: $disable_model_invocation
user-invocable: $user_invocable
---
# $name
EOF
  else
    write_file "$path" <<EOF
---
name: $name
description: $description
disable-model-invocation: $disable_model_invocation
user-invocable: $user_invocable
---
# $name
EOF
  fi
}

write_readme_skill_sync_registry() {
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "readme_skill_sync": {
    "readme": "README.md",
    "skills_dir": "trackbed/skills",
    "start_marker": "<!-- BEGIN SOURCE-SYNCED SKILL ROWS -->",
    "end_marker": "<!-- END SOURCE-SYNCED SKILL ROWS -->"
  }
}
EOF
}

write_component_catalog_registry() {
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "component_catalog": {
    "path": "trackbed/docs/component-catalog.json",
    "generated_by": "trackbed/scripts/generate-component-reference.py",
    "canonical_reference": "README.md"
  },
  "readme_skill_sync": {
    "readme": "README.md",
    "skills_dir": "trackbed/skills",
    "start_marker": "<!-- BEGIN SOURCE-SYNCED SKILL ROWS -->",
    "end_marker": "<!-- END SOURCE-SYNCED SKILL ROWS -->"
  },
  "readme_agent_sync": {
    "readme": "README.md",
    "agents_dir": "trackbed/agents",
    "start_marker": "<!-- BEGIN SOURCE-SYNCED AGENT ROWS -->",
    "end_marker": "<!-- END SOURCE-SYNCED AGENT ROWS -->"
  },
  "readme_hook_sync": {
    "readme": "README.md",
    "hooks_json": "trackbed/hooks/hooks.json",
    "start_marker": "<!-- BEGIN SOURCE-SYNCED HOOK ROWS -->",
    "end_marker": "<!-- END SOURCE-SYNCED HOOK ROWS -->",
    "descriptions": {
      "sample-hook": "Runs a sample hook"
    }
  }
}
EOF
}

write_component_catalog_tree() {
  write_reference_skill \
    "$TMP_ROOT/trackbed/skills/sample/SKILL.md" \
    "sample" \
    "Sample skill description" \
    "false" \
    "true" \
    "[target]"
  write_reference_agent \
    "$TMP_ROOT/trackbed/agents/reviewer.md" \
    "reviewer" \
    "Reviews fixture code"
  write_hook_manifest "$TMP_ROOT/trackbed/hooks/hooks.json" "sample-hook"
  write_file "$TMP_ROOT/trackbed/hooks/sample-hook.sh" <<'EOF'
#!/usr/bin/env bash
EOF
  write_file "$TMP_ROOT/README.md" <<'EOF'
# Fixture

## Skills

<!-- BEGIN SOURCE-SYNCED SKILL ROWS -->

| Skill | Invocation | Arguments | Description |
| --- | --- | --- | --- |
| `/trackbed:sample` | User, Auto | `[target]` | Sample skill description |

<!-- END SOURCE-SYNCED SKILL ROWS -->

## Agents

<!-- BEGIN SOURCE-SYNCED AGENT ROWS -->
| Agent | Description |
| --- | --- |
| `trackbed:reviewer` | Reviews fixture code |
<!-- END SOURCE-SYNCED AGENT ROWS -->

## Hooks

<!-- BEGIN SOURCE-SYNCED HOOK ROWS -->
| Hook | Event | Description |
| --- | --- | --- |
| `sample-hook` | PreToolUse (Bash) | Runs a sample hook |
<!-- END SOURCE-SYNCED HOOK ROWS -->
EOF
  write_component_catalog_registry
}

catalog_path() {
  printf '%s\n' "$TMP_ROOT/trackbed/docs/component-catalog.json"
}

write_reference_agent() {
  local path="$1"
  local name="$2"
  local description="$3"

  write_file "$path" <<EOF
---
name: $name
description: $description
model: opus
color: green
---
# $name
EOF
}

write_hook_manifest() {
  local path="$1"
  local hook_name="$2"
  local event="${3:-PreToolUse}"
  local matcher="${4:-Bash}"

  if [ -n "$matcher" ]; then
    write_file "$path" <<EOF
{
  "hooks": {
    "$event": [
      {
        "matcher": "$matcher",
        "hooks": [
          {
            "type": "command",
            "command": "bash \${CLAUDE_PLUGIN_ROOT}/hooks/$hook_name.sh"
          }
        ]
      }
    ]
  }
}
EOF
  else
    write_file "$path" <<EOF
{
  "hooks": {
    "$event": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \${CLAUDE_PLUGIN_ROOT}/hooks/$hook_name.sh"
          }
        ]
      }
    ]
  }
}
EOF
  fi
}

make_body_lines() {
  local count="$1"
  local index
  for ((index = 1; index <= count; index++)); do
    printf '# body line %03d\n' "$index"
  done
}

@test "real synced contract registry passes current tree" {
  run python3 "$SCRIPT"

  [ "$status" -eq 0 ]
  [[ "$output" == *"skill contract lint passed."* ]] || false
}

@test "review diff collection uses one synchronized NUL consumer contract" {
  run python3 - \
    "$BATS_TEST_DIRNAME/../scripts/synced-contracts.yaml" \
    "$BATS_TEST_DIRNAME/../.." <<'PY'
import json
import pathlib
import re
import shlex
import sys

registry_path, repo_root = map(pathlib.Path, sys.argv[1:])
registry = json.loads(registry_path.read_text())
contracts = {
    entry["name"]: entry
    for entry in registry["text_contracts"]
}
contract_name = "pr-review-collect-review-diff-nul-block"
shared_args = ["--strict", "--format", "nul"]
# Review producers opt into stack context; the other consumers read an empty field.
review_args = [*shared_args, "--stack-context"]
expected_args = {
    "trackbed/skills/pr:code-review/SKILL.md": review_args,
    "trackbed/skills/pr:product-review/SKILL.md": review_args,
    "trackbed/skills/code:copy-review/SKILL.md": shared_args,
    "trackbed/skills/pr:convention-review/SKILL.md": review_args,
    "trackbed/skills/pr:overengineering-review/SKILL.md": [
        *review_args,
        "--exclude-review-artifacts",
        "--require-local-artifact",
        "OVERENGINEERING_REVIEW_OVERVIEW.md",
    ],
    "trackbed/skills/pr:gut-check/SKILL.md": [
        *shared_args,
        "--exclude-review-artifacts",
        "--stack-context",
    ],
    "trackbed/skills/pr:triage-risk/SKILL.md": review_args,
    "trackbed/skills/debug:find-sibling-bugs/SKILL.md": [
        *shared_args,
        "--exclude-review-artifacts",
    ],
}
expected_paths = list(expected_args)

def extract(name, relative):
    text = (repo_root / relative).read_text().replace("`", "")
    match = re.search(contracts[name]["extract_regex"], text, flags=re.MULTILINE)
    if match is None:
        raise SystemExit(f"{name} does not match {relative}")
    value = match.group(1) if match.lastindex else match.group(0)
    return "\n".join(line.strip() for line in value.strip().splitlines())


contract = contracts.get(contract_name)
if contract is None:
    raise SystemExit(f"missing review-diff consumer contract: {contract_name}")
if "pr-review-collect-review-diff-json-block" in contracts:
    raise SystemExit("legacy review-diff JSON contract still exists")
if contract["paths"] != expected_paths:
    raise SystemExit(f"{contract_name} paths do not match the final consumer inventory")
if len({extract(contract_name, relative) for relative in expected_paths}) != 1:
    raise SystemExit(f"{contract_name} contains divergent consumer blocks")

scope_call = extract(contract_name, expected_paths[0])
if 'source "${CLAUDE_PLUGIN_ROOT}/scripts/lib/review-scope.sh" || exit 1' not in scope_call:
    raise SystemExit("consumer must source the installed scope helper")
if 'collect_review_scope "${COLLECT_ARGS[@]}" || exit 1' not in scope_call:
    raise SystemExit("consumer must pass its safety options and stop on failure")

code_review_contract = next(
    item
    for item in registry["required_file_contracts"]
    if item["name"] == "pr-code-review-invocation-shape"
)
if "COLLECT_ARGS=(--strict --format nul --stack-context)" not in code_review_contract["contains"]:
    raise SystemExit("code-review required-text contract still expects legacy JSON")

for consumer_path in expected_paths:
    consumer_text = (repo_root / consumer_path).read_text().replace("`", "")
    collect_args = re.search(
        r"^[ \t]*COLLECT_ARGS=\((.*?)\)\n"
        r'(?=[ \t]*\[ -n "\$\{BASE_BRANCH_OVERRIDE:-\}" \] '
        r'&& COLLECT_ARGS\+=\(--base "\$BASE_BRANCH_OVERRIDE"\)$)',
        consumer_text,
        flags=re.MULTILINE | re.DOTALL,
    )
    actual_args = (
        shlex.split(collect_args.group(1), comments=True, posix=True)
        if collect_args is not None
        else None
    )
    if actual_args != expected_args[consumer_path]:
        raise SystemExit(
            f"consumer collector arguments do not match the safety contract: "
            f"{consumer_path}: {actual_args!r}"
        )
PY

  [ "$status" -eq 0 ]
}

@test "Conductor workspace contract retains independent safety invariants" {
  run python3 - "$BATS_TEST_DIRNAME/../scripts/synced-contracts.yaml" <<'PY'
import json
import pathlib
import sys

registry = json.loads(pathlib.Path(sys.argv[1]).read_text())
contract = next(
    entry
    for entry in registry["text_contracts"]
    if entry["name"] == "conductor-workspace-boundary-guidance"
)
contract_regex = contract["extract_regex"]
required_invariants = {
    "branch changes require explicit approval": "stay on the current branch absent explicit approval",
    "isolation uses Conductor instead of raw Git": "use another Conductor workspace—not raw worktrees or throwaway branches—for isolation",
    "workspace lifecycle stays host-neutral": "Never remove, reset, or re-point a Conductor workspace path",
    "workspace archival stays in Conductor": "archive workspaces through Conductor",
    "workspace creation needs the user's approval": "create one through Conductor only after the user approves it in this run",
    "agents archive only workspaces their run created": "archive only one this run created, after the user approves it",
    "host detection never widens authority": "Conductor changes defaults, not permissions or safety gates",
}
missing = [
    name for name, clause in required_invariants.items() if clause not in contract_regex
]
if missing:
    raise SystemExit("missing Conductor workspace safety invariants: " + ", ".join(missing))
PY

  [ "$status" -eq 0 ]
}

@test "registry consumers reject every non-object JSON kind with path context" {
  local consumer
  local fixture

  for consumer in "$SCRIPT" "$COMPONENT_GENERATOR"; do
    for fixture in "null" "[]" '"scalar"' "false" "42"; do
      printf '%s\n' "$fixture" >"$TMP_ROOT/registry.yaml"

      run python3 "$consumer" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

      [ "$status" -eq 1 ]
      [[ "$output" == *"$TMP_ROOT/registry.yaml"* ]] || false
      [[ "$output" == *"registry must be a JSON object"* ]] || false
    done
  done
}

@test "registry consumers report a clean error for an unreadable registry path" {
  local consumer
  local registry_path

  mkdir "$TMP_ROOT/registry.yaml"
  registry_path="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$TMP_ROOT/registry.yaml")"

  for consumer in "$SCRIPT" "$COMPONENT_GENERATOR"; do
    run python3 "$consumer" --repo-root "$TMP_ROOT" --registry "$registry_path"

    [ "$status" -eq 1 ]
    [[ "$output" == *"$registry_path"* ]] || false
    [[ "$output" == *"cannot read registry"* ]] || false
    [[ "$output" != *"Traceback"* ]] || false
  done
}

@test "malformed contract entries fail cleanly instead of crashing with a traceback" {
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "text_contracts": [
    { "extract_regex": "x" }
  ]
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" != *"Traceback"* ]] || false
  [[ "$output" == *"entry missing required string key 'name'"* ]] || false
}

@test "copy review rubric is owned by the code skill with automatic PR mode" {
  local registry="$BATS_TEST_DIRNAME/../scripts/synced-contracts.yaml"
  local code_skill="$BATS_TEST_DIRNAME/../skills/code:copy-review/SKILL.md"
  local code_rubric="$BATS_TEST_DIRNAME/../skills/code:copy-review/references/copy-review-rubric.md"
  local pr_skill="$BATS_TEST_DIRNAME/../skills/pr:copy-review/SKILL.md"

  test -f "$code_skill"
  test -f "$code_rubric"
  test ! -f "$pr_skill"
  grep -qF 'Canonical owner: `trackbed:code:copy-review`.' "$code_rubric"
  grep -qF 'If `FORCE_PR_MODE=true`, set `SCAN_MODE=false`' "$code_skill"
  grep -qF 'equals `BASE_BRANCH`, set `SCAN_MODE=true`' "$code_skill"
  grep -qF 'differs from `BASE_BRANCH`, set `SCAN_MODE=false`.' "$code_skill"
  grep -qF 'the repo root for `--all` or automatic base-branch audit mode' "$code_skill"
  ! grep -qF '"name": "copy-review-rubric"' "$registry" || false
  ! grep -qF '"name": "copy-review-redundancy-scope"' "$registry" || false
  ! grep -qF '"name": "copy-review-ui-relevant-file-types"' "$registry" || false
}

@test "spec-audit fix-confidence rubric is one shared resource for audit and apply mode" {
  local skills="$BATS_TEST_DIRNAME/../skills"
  local apply_now="$skills/siw:spec-audit/references/apply-now.md"
  local shared_rubric="$BATS_TEST_DIRNAME/../shared/siw/references/fix-confidence-rubric.md"
  local shared_reference='${CLAUDE_PLUGIN_ROOT}/shared/siw/references/fix-confidence-rubric.md'

  test -f "$shared_rubric"
  [ ! -e "$skills/siw:apply-spec-audit-fixes" ]
  [ ! -e "$skills/siw:spec-audit/references/fix-confidence-rubric.md" ]
  grep -qF "$shared_reference" "$apply_now"
  grep -qF "$shared_reference" "$skills/siw:spec-audit/SKILL.md"
  grep -qF 'Critical findings in Completeness, Scope, or Rationale Documentation dimensions always require decisions; treat the legacy `Value Proposition` label in older reports as Rationale Documentation.' "$apply_now"
  grep -qF 'Severity is Critical AND dimension is Completeness, Scope, or Rationale Documentation (`Value Proposition` in legacy reports)' "$shared_rubric"
}

@test "spec-audit rationale documentation contract reaches downstream consumers" {
  local issue_template="$BATS_TEST_DIRNAME/../skills/siw:resolve-audit/assets/issue-spec.md.template"
  local report_format="$BATS_TEST_DIRNAME/../skills/siw:spec-audit/assets/spec-audit-report-format.md"
  local report_summary="$BATS_TEST_DIRNAME/../skills/siw:spec-audit/assets/spec-audit-summary.md"
  local team_mode="$BATS_TEST_DIRNAME/../skills/siw:spec-audit/references/team-mode.md"

  grep -qF 'actionability/testability/rationale documentation/technical design' "$issue_template"
  ! grep -qF 'actionability/testability/value/technical design' "$issue_template" || false
  grep -qF -- '- **Rationale Documentation or Technical Design gaps** -> message design-auditor' "$team_mode"
  ! grep -qF -- '- **Design flaws or value gaps** -> message design-auditor' "$team_mode" || false
  grep -qF '| Rationale Documentation |' "$report_format"
  ! grep -qF '| Value Proposition |' "$report_format" || false
  grep -qF 'Rationale Documentation:' "$report_summary"
  ! grep -qF 'Value Proposition:' "$report_summary" || false
  grep -qxF '**Dimension:** {dimension}' "$report_format"
  grep -qxF '**Severity:** Critical' "$report_format"
  grep -qxF '**Fix Confidence:** {score}/100 ({MECHANICAL|HIGH_CONFIDENCE|MODERATE_CONFIDENCE|REQUIRES_DECISION})' "$report_format"
  grep -qxF '**Location:** {source_file} > {source_section}' "$report_format"
}

@test "readme skill sync accepts source-generated frontmatter rows" {
  write_reference_skill \
    "$TMP_ROOT/trackbed/skills/sample/SKILL.md" \
    "sample" \
    "Sample skill description" \
    "false" \
    "true" \
    "[target]"
  write_file "$TMP_ROOT/README.md" <<'EOF'
# Fixture

## Skills

<!-- BEGIN SOURCE-SYNCED SKILL ROWS -->

| Skill | Invocation | Arguments | Description |
| --- | --- | --- | --- |
| `/trackbed:sample` | User, Auto | `[target]` | Sample skill description |

<!-- END SOURCE-SYNCED SKILL ROWS -->

## Agents
EOF
  write_readme_skill_sync_registry

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
  [[ "$output" == *"skill contract lint passed."* ]] || false
}

@test "readme skill sync normalizes quoted boolean frontmatter rows" {
  write_reference_skill \
    "$TMP_ROOT/trackbed/skills/hidden/SKILL.md" \
    "hidden" \
    "Hidden quoted skill" \
    '"true"' \
    '"false"'
  write_reference_skill \
    "$TMP_ROOT/trackbed/skills/user-only/SKILL.md" \
    "user-only" \
    "User-only quoted skill" \
    '"true"' \
    '"true"' \
    "[target]"
  write_file "$TMP_ROOT/README.md" <<'EOF'
# Fixture

## Skills

<!-- BEGIN SOURCE-SYNCED SKILL ROWS -->

| Skill | Invocation | Arguments | Description |
| --- | --- | --- | --- |
| `trackbed:hidden` | Hidden | — | Hidden quoted skill |
| `/trackbed:user-only` | User | `[target]` | User-only quoted skill |

<!-- END SOURCE-SYNCED SKILL ROWS -->

## Agents
EOF
  write_readme_skill_sync_registry

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
  [[ "$output" == *"skill contract lint passed."* ]] || false
}

@test "readme skill sync catches invocation arguments and description drift" {
  write_reference_skill \
    "$TMP_ROOT/trackbed/skills/sample/SKILL.md" \
    "sample" \
    "Sample skill description" \
    "false" \
    "true" \
    "[target]"
  write_file "$TMP_ROOT/README.md" <<'EOF'
# Fixture

## Skills

<!-- BEGIN SOURCE-SYNCED SKILL ROWS -->

| Skill | Invocation | Arguments | Description |
| --- | --- | --- | --- |
| `/trackbed:sample` | User | — | Stale copied description |

<!-- END SOURCE-SYNCED SKILL ROWS -->

## Agents
EOF
  write_readme_skill_sync_registry

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"readme skill sync"* ]] || false
  [[ "$output" == *"invocation differs from SKILL.md frontmatter"* ]] || false
  [[ "$output" == *"arguments differs from SKILL.md frontmatter"* ]] || false
  [[ "$output" == *"description differs from SKILL.md frontmatter"* ]] || false
}

@test "readme skill sync uses frontmatter fields from shared schema" {
  write_file "$TMP_ROOT/trackbed/skills/custom/SKILL.md" <<'EOF'
---
name: custom
description: Custom schema skill
prompt: "[topic]"
no-ai: true
manual: true
---
# trackbed:custom
EOF
  write_file "$TMP_ROOT/schema.json" <<'EOF'
{
  "skill_frontmatter": {
    "fields": {
      "name": {"type": "string", "required": true},
      "description": {"type": "string", "required": true},
      "prompt": {
        "type": "string",
        "required": false,
        "loader_property": "argumentHint"
      },
      "no-ai": {
        "type": "boolean",
        "required": true,
        "loader_property": "disableModelInvocation"
      },
      "manual": {
        "type": "boolean",
        "required": true,
        "loader_property": "userInvocable"
      }
    }
  },
  "source_manifest": {
    "required_fields": [],
    "one_of_fields": []
  }
}
EOF
  write_file "$TMP_ROOT/README.md" <<'EOF'
# Fixture

## Skills

<!-- BEGIN SOURCE-SYNCED SKILL ROWS -->

| Skill | Invocation | Arguments | Description |
| --- | --- | --- | --- |
| `/trackbed:custom` | User | `[topic]` | Custom schema skill |

<!-- END SOURCE-SYNCED SKILL ROWS -->

## Agents
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "contract_schema": "schema.json",
  "readme_skill_sync": {
    "readme": "README.md",
    "skills_dir": "trackbed/skills",
    "start_marker": "<!-- BEGIN SOURCE-SYNCED SKILL ROWS -->",
    "end_marker": "<!-- END SOURCE-SYNCED SKILL ROWS -->"
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
  [[ "$output" == *"skill contract lint passed."* ]] || false
}

@test "component reference generator check reports drift and write syncs rows" {
  write_reference_skill \
    "$TMP_ROOT/trackbed/skills/sample/SKILL.md" \
    "sample" \
    "Sample skill description" \
    "false" \
    "true" \
    "[target]"
  write_file "$TMP_ROOT/README.md" <<'EOF'
# Fixture

## Skills

<!-- BEGIN SOURCE-SYNCED SKILL ROWS -->

| Skill | Invocation | Arguments | Description |
| --- | --- | --- | --- |
| `/trackbed:sample` | User | — | Stale copied description |

<!-- END SOURCE-SYNCED SKILL ROWS -->

## Agents
EOF
  write_readme_skill_sync_registry

  run python3 "$COMPONENT_GENERATOR" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml" --check

  [ "$status" -eq 1 ]
  [[ "$output" == *"component reference sync check failed:"* ]] || false
  [[ "$output" == *"run python3 trackbed/scripts/generate-component-reference.py --write"* ]] || false

  run python3 "$COMPONENT_GENERATOR" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml" --write

  [ "$status" -eq 0 ]
  [[ "$output" == *"updated README.md component reference rows."* ]] || false
  [[ "$(cat "$TMP_ROOT/README.md")" == *"| \`/trackbed:sample\` | User, Auto | \`[target]\` | Sample skill description |"* ]] || false
}

@test "component reference generator check rejects ghost skill rows" {
  write_reference_skill \
    "$TMP_ROOT/trackbed/skills/real/SKILL.md" \
    "real" \
    "Real skill description" \
    "false" \
    "true"
  write_file "$TMP_ROOT/README.md" <<'EOF'
# Fixture

## Skills

<!-- BEGIN SOURCE-SYNCED SKILL ROWS -->

| Skill | Invocation | Arguments | Description |
| --- | --- | --- | --- |
| `/trackbed:real` | User, Auto | — | Real skill description |
| `/trackbed:ghost` | User | — | Ghost skill description |

<!-- END SOURCE-SYNCED SKILL ROWS -->

## Agents
EOF
  write_readme_skill_sync_registry

  run python3 "$COMPONENT_GENERATOR" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml" --check

  [ "$status" -eq 1 ]
  [[ "$output" == *"component reference sync failed:"* ]] || false
  [[ "$output" == *"documents 'trackbed:ghost'"* ]] || false
  [[ "$output" == *"does not exist"* ]] || false
}

@test "readme agent sync catches missing source agent rows" {
  write_reference_agent \
    "$TMP_ROOT/trackbed/agents/reviewer.md" \
    "reviewer" \
    "Reviews fixture code"
  write_file "$TMP_ROOT/README.md" <<'EOF'
# Fixture

## Agents

<!-- BEGIN SOURCE-SYNCED AGENT ROWS -->
| Agent | Description |
| --- | --- |
<!-- END SOURCE-SYNCED AGENT ROWS -->
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "readme_agent_sync": {
    "readme": "README.md",
    "agents_dir": "trackbed/agents",
    "start_marker": "<!-- BEGIN SOURCE-SYNCED AGENT ROWS -->",
    "end_marker": "<!-- END SOURCE-SYNCED AGENT ROWS -->"
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"readme agent sync"* ]] || false
  [[ "$output" == *"missing agent 'trackbed:reviewer'"* ]] || false
}

@test "readme hook sync catches missing hook rows" {
  write_hook_manifest "$TMP_ROOT/trackbed/hooks/hooks.json" "sample-hook"
  write_file "$TMP_ROOT/README.md" <<'EOF'
# Fixture

## Hooks

<!-- BEGIN SOURCE-SYNCED HOOK ROWS -->
| Hook | Event | Description |
| --- | --- | --- |
<!-- END SOURCE-SYNCED HOOK ROWS -->
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "readme_hook_sync": {
    "readme": "README.md",
    "hooks_json": "trackbed/hooks/hooks.json",
    "start_marker": "<!-- BEGIN SOURCE-SYNCED HOOK ROWS -->",
    "end_marker": "<!-- END SOURCE-SYNCED HOOK ROWS -->",
    "descriptions": {
      "sample-hook": "Runs a sample hook"
    }
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"readme hook sync"* ]] || false
  [[ "$output" == *"missing hook 'sample-hook'"* ]] || false
}

@test "component reference generator writes agent and hook rows" {
  write_reference_agent \
    "$TMP_ROOT/trackbed/agents/reviewer.md" \
    "reviewer" \
    "Reviews fixture code"
  write_hook_manifest "$TMP_ROOT/trackbed/hooks/hooks.json" "sample-hook" "PostToolUse" "Write|Edit"
  write_file "$TMP_ROOT/README.md" <<'EOF'
# Fixture

## Agents

<!-- BEGIN SOURCE-SYNCED AGENT ROWS -->
| Agent | Description |
| --- | --- |
<!-- END SOURCE-SYNCED AGENT ROWS -->

## Hooks

<!-- BEGIN SOURCE-SYNCED HOOK ROWS -->
| Hook | Event | Description |
| --- | --- | --- |
<!-- END SOURCE-SYNCED HOOK ROWS -->
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "readme_agent_sync": {
    "readme": "README.md",
    "agents_dir": "trackbed/agents",
    "start_marker": "<!-- BEGIN SOURCE-SYNCED AGENT ROWS -->",
    "end_marker": "<!-- END SOURCE-SYNCED AGENT ROWS -->"
  },
  "readme_hook_sync": {
    "readme": "README.md",
    "hooks_json": "trackbed/hooks/hooks.json",
    "start_marker": "<!-- BEGIN SOURCE-SYNCED HOOK ROWS -->",
    "end_marker": "<!-- END SOURCE-SYNCED HOOK ROWS -->",
    "descriptions": {
      "sample-hook": "Runs a sample hook"
    }
  }
}
EOF

  run python3 "$COMPONENT_GENERATOR" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml" --write

  [ "$status" -eq 0 ]
  [[ "$output" == *"updated README.md component reference rows."* ]] || false
  [[ "$(cat "$TMP_ROOT/README.md")" == *"| \`trackbed:reviewer\` | Reviews fixture code |"* ]] || false
  [[ "$(cat "$TMP_ROOT/README.md")" == *"| \`sample-hook\` | PostToolUse (Write\\|Edit) | Runs a sample hook |"* ]] || false
}

@test "real component catalog stays synchronized with the current tree" {
  run python3 "$COMPONENT_GENERATOR" --check

  [ "$status" -eq 0 ]
  [[ "$output" == *"component reference docs are in sync."* ]] || false
}

@test "component catalog indexes every component type by name and source path" {
  write_component_catalog_tree

  run python3 "$COMPONENT_GENERATOR" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml" --write

  [ "$status" -eq 0 ]
  [[ "$output" == *"updated trackbed/docs/component-catalog.json component catalog."* ]] || false

  run python3 -c '
import json, sys
document = json.load(open(sys.argv[1], encoding="utf-8"))
print(document["canonical_reference"])
print(document["generated_by"])
print(json.dumps(document["skills"]))
print(json.dumps(document["agents"]))
print(json.dumps(document["hooks"]))
' "$(catalog_path)"

  [ "$status" -eq 0 ]
  [[ "$output" == *"README.md"* ]] || false
  [[ "$output" == *"trackbed/scripts/generate-component-reference.py"* ]] || false
  [[ "$output" == *'{"name": "trackbed:sample", "invocation": "User, Auto", "path": "trackbed/skills/sample/SKILL.md"}'* ]] || false
  [[ "$output" == *'{"name": "trackbed:reviewer", "path": "trackbed/agents/reviewer.md"}'* ]] || false
  [[ "$output" == *'{"name": "sample-hook", "event": "PreToolUse (Bash)", "path": "trackbed/hooks/sample-hook.sh"}'* ]] || false

  # No component description is copied into the catalog; the README stays canonical.
  ! grep -qF "Sample skill description" "$(catalog_path)" || false
  ! grep -qF "Reviews fixture code" "$(catalog_path)" || false
  ! grep -qF "Runs a sample hook" "$(catalog_path)" || false
}

@test "component generator normalizes supported invocation scalars in README and catalog" {
  write_component_catalog_tree
  write_reference_skill \
    "$TMP_ROOT/trackbed/skills/sample/SKILL.md" \
    "sample" \
    "Sample skill description" \
    '"true" # User invocation only' \
    'true' \
    "[target]"

  run python3 "$COMPONENT_GENERATOR" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml" --write
  [ "$status" -eq 0 ]
  grep -qF '| `/trackbed:sample` | User | `[target]` | Sample skill description |' "$TMP_ROOT/README.md"
  run python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["skills"][0]["invocation"])' "$(catalog_path)"
  [ "$status" -eq 0 ]
  [ "$output" = "User" ]

  write_reference_skill \
    "$TMP_ROOT/trackbed/skills/sample/SKILL.md" \
    "sample" \
    "Sample skill description" \
    $'|-\n  true' \
    '"\x66alse" # Not in slash menu' \
    "[target]"

  run python3 "$COMPONENT_GENERATOR" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml" --write
  [ "$status" -eq 0 ]
  grep -qF '| `trackbed:sample` | Hidden | — | Sample skill description |' "$TMP_ROOT/README.md"
  run python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["skills"][0]["invocation"])' "$(catalog_path)"
  [ "$status" -eq 0 ]
  [ "$output" = "Hidden" ]

  run python3 "$COMPONENT_GENERATOR" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml" --check
  [ "$status" -eq 0 ]
}

@test "component catalog generation is idempotent" {
  write_component_catalog_tree

  run python3 "$COMPONENT_GENERATOR" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml" --write
  [ "$status" -eq 0 ]
  cp "$(catalog_path)" "$TMP_ROOT/first-pass.json"

  run python3 "$COMPONENT_GENERATOR" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml" --write
  [ "$status" -eq 0 ]
  [[ "$output" == *"component reference docs are in sync."* ]] || false
  cmp "$TMP_ROOT/first-pass.json" "$(catalog_path)"

  run python3 "$COMPONENT_GENERATOR" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml" --check
  [ "$status" -eq 0 ]
  [[ "$output" == *"component reference docs are in sync."* ]] || false
}

@test "component catalog lint reports a missing catalog artifact" {
  write_component_catalog_tree

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"component catalog: registered path is missing: trackbed/docs/component-catalog.json"* ]] || false
}

@test "component catalog lint reports added and removed component drift" {
  write_component_catalog_tree
  run python3 "$COMPONENT_GENERATOR" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml" --write
  [ "$status" -eq 0 ]

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"
  [ "$status" -eq 0 ]

  write_reference_agent \
    "$TMP_ROOT/trackbed/agents/auditor.md" \
    "auditor" \
    "Audits fixture code"

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"
  [ "$status" -eq 1 ]
  [[ "$output" == *"component catalog: trackbed/docs/component-catalog.json is stale"* ]] || false
  [[ "$output" == *"run python3 trackbed/scripts/generate-component-reference.py --write"* ]] || false

  rm "$TMP_ROOT/trackbed/agents/auditor.md"
  rm -r "$TMP_ROOT/trackbed/skills/sample"

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"
  [ "$status" -eq 1 ]
  [[ "$output" == *"component catalog: trackbed/docs/component-catalog.json is stale"* ]] || false
}

@test "component catalog rejects an emitted component path that does not exist" {
  write_component_catalog_tree
  rm "$TMP_ROOT/trackbed/hooks/sample-hook.sh"

  run python3 "$COMPONENT_GENERATOR" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml" --write

  [ "$status" -eq 1 ]
  [[ "$output" == *"component reference sync failed:"* ]] || false
  [[ "$output" == *"would document 'sample-hook' at missing path trackbed/hooks/sample-hook.sh"* ]] || false
  [ ! -f "$(catalog_path)" ]
}

@test "component catalog defers once to the readme sync checks on broken source metadata" {
  write_component_catalog_tree
  run python3 "$COMPONENT_GENERATOR" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml" --write
  [ "$status" -eq 0 ]

  write_file "$TMP_ROOT/trackbed/skills/broken/SKILL.md" <<'EOF'
# trackbed:broken without frontmatter
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"readme skill sync: trackbed/skills/broken/SKILL.md is missing YAML frontmatter"* ]] || false
  [[ "$output" == *"component catalog: cannot generate trackbed/docs/component-catalog.json until component source metadata is valid"* ]] || false

  # The catalog defers to the owning check instead of repeating its diagnostics.
  [ "$(grep -c "readme skill sync: .* is missing YAML frontmatter" <<<"$output")" -eq 1 ]
  [ "$(grep -c "^::error::component catalog:" <<<"$output")" -eq 1 ]
}

@test "component catalog requires the readme sync configs it is generated from" {
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "component_catalog": {
    "path": "trackbed/docs/component-catalog.json"
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"is generated from README sync metadata"* ]] || false
  [[ "$output" == *"readme_skill_sync"* ]] || false
  [[ "$output" == *"readme_agent_sync"* ]] || false
  [[ "$output" == *"readme_hook_sync"* ]] || false
}

@test "verify-understanding supports answer option prompts" {
  local skill_text
  skill_text="$(cat "$BATS_TEST_DIRNAME/../skills/learn:verify-understanding/SKILL.md")"

  [[ "$skill_text" == *'[--answer-options|--choices]'* ]] || false
  [[ "$skill_text" == *'`--answer-options` or `--choices`: Prefer verification prompts with explicit answer options.'* ]] || false
  [[ "$skill_text" == *'After removing invocation options, use the remaining non-option text as the topic.'* ]] || false
  [[ "$skill_text" == *'still require the human to explain their choice before counting it as demonstrated understanding'* ]] || false
}

@test "siw transfer-to-linear gates duplicate issue content before creation" {
  local skill_text
  local mapping_text
  local extraction_text
  local docs_text

  skill_text="$(cat "$BATS_TEST_DIRNAME/../skills/siw:transfer-to-linear/SKILL.md")"
  mapping_text="$(cat "$BATS_TEST_DIRNAME/../skills/siw:transfer-to-linear/references/linear-mapping.md")"
  extraction_text="$(cat "$BATS_TEST_DIRNAME/../skills/siw:transfer-to-linear/references/artifact-extraction.md")"
  docs_text="$(cat "$BATS_TEST_DIRNAME/../docs/siw.md")"

  [[ "$skill_text" == *'Duplicate-content preflight per `references/linear-mapping.md`'* ]] || false
  [[ "$skill_text" == *'Cross-reference rewrite plan per `references/linear-mapping.md`'* ]] || false
  [[ "$skill_text" == *'Run the final duplicate-content preflight immediately before issue creation'* ]] || false
  [[ "$skill_text" == *'If any unresolved duplicate-content group is found, stop before creating any issue'* ]] || false

  [[ "$mapping_text" == *'**Duplicate content preflight**'* ]] || false
  [[ "$mapping_text" == *'do not silently `skip-existing` on content alone'* ]] || false
  [[ "$mapping_text" == *'Before creating Linear issues, run the duplicate-content preflight above against the final rewritten issue descriptions.'* ]] || false
  [[ "$mapping_text" == *'**Issue-to-issue references:**'* ]] || false
  [[ "$mapping_text" == *'DEV-123 (P4-001)'* ]] || false
  [[ "$mapping_text" == *'Do not rewrite IDs embedded in filenames, paths, URLs, markdown link destinations, inline code, fenced code, or source provenance lines'* ]] || false
  [[ "$mapping_text" == *'Do not rewrite the issue'\''s own canonical `- SIW ID: {id}` metadata line'* ]] || false
  [[ "$mapping_text" == *'Before assembling the Linear description, remove the source issue'\''s inline metadata line'* ]] || false
  [[ "$mapping_text" == *'Preserve escaped table pipes (`\|`)'* ]] || false

  [[ "$extraction_text" == *'Raw substantive body content for duplicate-content preflight.'* ]] || false
  [[ "$extraction_text" == *'Reference inventory from the body and metadata'* ]] || false
  [[ "$docs_text" == *'checks for duplicate issue content before creating Linear issues'* ]] || false
}

@test "text contract drift fails with precise contract name" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" "Contract: alpha"
  write_minimal_skill "$TMP_ROOT/trackbed/skills/b/SKILL.md" "Contract: beta"
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "text_contracts": [
    {
      "name": "sample-text-contract",
      "extract_regex": "Contract: ([A-Za-z]+)",
      "paths": [
        "trackbed/skills/a/SKILL.md",
        "trackbed/skills/b/SKILL.md"
      ]
    }
  ]
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"sample-text-contract"* ]] || false
  [[ "$output" == *"differs"* ]] || false
}

@test "text contract inventory accepts a fully synchronized tree" {
  write_text_contract_inventory_fixture

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
}

@test "text contract inventory rejects an unregistered marked copy" {
  write_text_contract_inventory_fixture
  write_file "$TMP_ROOT/contracts/unregistered.md" <<'EOF'
Canonical inventory marker: alpha
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"discovered unregistered contract copy: contracts/unregistered.md"* ]] || false
  [[ "$output" == *"registered inventory count 2 does not equal discovered count 3"* ]] || false
}

@test "text contract inventory rejects a missing registered copy" {
  write_text_contract_inventory_fixture
  rm "$TMP_ROOT/contracts/b.md"

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"registered path is missing: contracts/b.md"* ]] || false
  [[ "$output" == *"registered contract copy is not discoverable: contracts/b.md"* ]] || false
  [[ "$output" == *"registered inventory count 2 does not equal discovered count 1"* ]] || false
}

@test "text contract inventory still rejects divergent marked values" {
  write_text_contract_inventory_fixture
  write_file "$TMP_ROOT/contracts/b.md" <<'EOF'
Canonical inventory marker: beta
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"sample-inventoried-contract"* ]] || false
  [[ "$output" == *"differs"* ]] || false
}

@test "text contract inventory rejects duplicate markers in one copy" {
  write_text_contract_inventory_fixture
  write_file "$TMP_ROOT/contracts/b.md" <<'EOF'
Canonical inventory marker: alpha
Canonical inventory marker: alpha
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"contracts/b.md contains 2 inventory markers; expected exactly 1"* ]] || false
}

@test "siw spec exclusion inventory detects marker removal from every runtime copy" {
  local repo_root="$BATS_TEST_DIRNAME/../.."
  local source_registry="$BATS_TEST_DIRNAME/../scripts/synced-contracts.yaml"
  local fixture_root="$TMP_ROOT/siw-inventory"
  local fixture_registry="$fixture_root/registry.yaml"
  local expected_paths_file="$fixture_root/expected-paths.txt"
  local path

  mkdir -p "$fixture_root"
  siw_spec_exclusion_expected_paths >"$expected_paths_file"

  python3 - \
    "$source_registry" \
    "$repo_root" \
    "$fixture_root" \
    "$fixture_registry" \
    "$expected_paths_file" <<'PY'
import json
import pathlib
import shutil
import sys

source_registry, repo_root, fixture_root, fixture_registry, expected_paths_file = map(
    pathlib.Path, sys.argv[1:]
)
registry = json.loads(source_registry.read_text())
contract = next(
    item
    for item in registry["text_contracts"]
    if item["name"] == "siw-spec-exclusion-list"
)
expected_paths = expected_paths_file.read_text().splitlines()
if contract["paths"] != expected_paths:
    raise SystemExit("siw spec exclusion registry does not match the independent test inventory")
for relative in expected_paths:
    destination = fixture_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(repo_root / relative, destination)
(fixture_root / "registry.yaml").write_text(
    json.dumps(
        {
            "text_contracts": [contract],
            "mechanical": {"max_skill_lines": 10000},
        }
    )
)
PY

  while IFS= read -r path; do
    python3 - "$source_registry" "$repo_root/$path" "$fixture_root/$path" <<'PY'
import json
import pathlib
import sys

registry_path, source_path, fixture_path = map(pathlib.Path, sys.argv[1:])
contract = next(
    item
    for item in json.loads(registry_path.read_text())["text_contracts"]
    if item["name"] == "siw-spec-exclusion-list"
)
marker = contract["inventory"]["marker"]
text = source_path.read_text()
if text.count(marker) != 1:
    raise SystemExit(f"expected one canonical marker in {source_path}")
fixture_path.write_text(text.replace(marker, "Unsynchronized SIW spec-exclusion contract:", 1))
PY

    run python3 "$SCRIPT" --repo-root "$fixture_root" --registry "$fixture_registry"

    [ "$status" -eq 1 ]
    [[ "$output" == *"$path"* ]] || false
    cp "$repo_root/$path" "$fixture_root/$path"
  done <"$expected_paths_file"
}

@test "siw main spec ambiguity contract drift fails with precise contract name" {
  write_file "$TMP_ROOT/trackbed/skills/a/SKILL.md" <<'EOF'
Synced SIW main-spec ambiguity contract (keep aligned across SIW spec detectors): when multiple spec candidates remain after deterministic heading/filename matching, auto mode stops with MISSING REQUIREMENT and interactive mode asks the user which file is the main spec.
EOF
  write_file "$TMP_ROOT/trackbed/skills/b/SKILL.md" <<'EOF'
Synced SIW main-spec ambiguity contract (keep aligned across SIW spec detectors): when multiple spec candidates remain after deterministic heading/filename matching, auto mode picks the first candidate and interactive mode asks the user which file is the main spec.
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "text_contracts": [
    {
      "name": "siw-main-spec-ambiguity-rule",
      "extract_regex": "Synced SIW main-spec ambiguity contract \\(keep aligned across SIW spec detectors\\):\\s*(when multiple spec candidates remain after deterministic heading/filename matching, auto mode .*? and interactive mode asks the user which file is the main spec\\.)",
      "paths": [
        "trackbed/skills/a/SKILL.md",
        "trackbed/skills/b/SKILL.md"
      ]
    }
  ]
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"siw-main-spec-ambiguity-rule"* ]] || false
  [[ "$output" == *"differs"* ]] || false
}


@test "siw issue creation keeps one reservation protocol after the single-issue skill removal" {
  local generate_phases_text publication_recovery_text generate_phases_contract_text tracker_schema_text triage_text
  generate_phases_text="$(cat "$BATS_TEST_DIRNAME/../skills/siw:generate-phases/SKILL.md")"
  publication_recovery_text="$(cat "$BATS_TEST_DIRNAME/../skills/siw:generate-phases/references/publication-recovery.md")"
  generate_phases_contract_text="${generate_phases_text}"$'\n'"${publication_recovery_text}"
  tracker_schema_text="$(cat "$BATS_TEST_DIRNAME/../skills/siw:generate-phases/references/tracker-schema.md")"
  triage_text="$(cat "$BATS_TEST_DIRNAME/../skills/debug:triage-to-issue/SKILL.md")"

  [ -x "$RESERVATION_HELPER" ]

  [[ "$generate_phases_text" == *'Before approving replacement, read `references/publication-recovery.md`'* ]] || false
  [[ "$generate_phases_text" == *'Before Phase 6 performs its first mutation, read `references/publication-recovery.md`'* ]] || false

  [ ! -e "$BATS_TEST_DIRNAME/../skills/siw:issue-define" ]
  ! grep -rqF "siw:issue-define" "$BATS_TEST_DIRNAME/../skills" || false

  [[ "$generate_phases_text" == *'plan exactly one General issue'* ]] || false
  [[ "$generate_phases_text" == *'no existing issue already covers'* ]] || false
  [[ "$triage_text" == *'this skill owns its SIW write path'* ]] || false
  [[ "$triage_text" == *'never reuse or overwrite an existing issue number'* ]] || false
  [[ "$triage_text" == *'normalized form'*'existing open issue headings'* ]] || false
  [[ "$triage_text" == *'scripts/siw-issue-reservation.sh'* ]] || false
  [[ "$triage_text" == *'new-owner'*'acquire siw'*'reserve siw'* ]] || false
  [[ "$triage_text" == *'publish-receipt siw'*'release siw'*'release-publication siw'* ]] || false
  [[ "$triage_text" == *'preserving its existing 5-, 6-, or 7-column schema'* ]] || false
  [[ "$triage_text" == *'Mixed — see issue files for exact guidance'* ]] || false

  [[ "$generate_phases_contract_text" == *'scripts/siw-issue-reservation.sh'* ]] || false
  [[ "$generate_phases_contract_text" == *'serializes its own invocations'* ]] || false
  [[ "$generate_phases_contract_text" == *'operation claim is reclaimed only after its recorded process no longer exists'* ]] || false
  [[ "$generate_phases_contract_text" == *'Immediately before the first mutation'* ]] || false
  [[ "$generate_phases_contract_text" == *'owner-bound baseline manifest'* ]] || false
  [[ "$generate_phases_contract_text" == *'collision-resistant owner token'* ]] || false
  [[ "$generate_phases_contract_text" == *'sh <helper> new-owner'* ]] || false
  [[ "$generate_phases_contract_text" == *'publish-receipt siw <owner-token>'* ]] || false
  [[ "$generate_phases_contract_text" == *'verify-receipt siw <owner-token>'* ]] || false
  [[ "$generate_phases_contract_text" == *'legacy-only zero-ID recovery receipt'* ]] || false
  [[ "$generate_phases_contract_text" == *'legacy lock with an owned reservation'*'reject'* ]] || false
  [[ "$generate_phases_contract_text" == *'every ID whose issue file, overview row, or log entry changed since acquisition'* ]] || false
  [[ "$generate_phases_contract_text" == *'separate normal-path `verify-receipt`'*'unnecessary'* ]] || false
  [[ "$generate_phases_contract_text" == *"During normal contention, never copy or reuse a token"* ]] || false
  [[ "$generate_phases_contract_text" == *"A later recovery session may use the retained token only after the user explicitly confirms"* ]] || false
  [[ "$generate_phases_contract_text" == *'without exposing its token'* ]] || false
  [[ "$generate_phases_contract_text" == *'Never publish from the'*'snapshot'* ]] || false
  [[ "$generate_phases_contract_text" == *'retries collisions with exclusive atomic claims'* ]] || false
  [[ "$generate_phases_contract_text" == *'Never delete a reservation based on age or filename'* ]] || false
  [[ "$generate_phases_contract_text" == *"never clean up a different owner's token"* ]] || false

  [[ "$publication_recovery_text" == *'Build the complete provisional-to-final map'* ]] || false
  [[ "$publication_recovery_text" == *'reserve-batch siw <prefix> <owner-token> 100 <provisional-id>...'* ]] || false
  [[ "$publication_recovery_text" == *'release-batch siw <owner-token> <final-issue-id>...'* ]] || false
  [[ "$publication_recovery_text" == *'update filenames, headings, dependencies, related IDs, overview rows, and log ranges before writing'* ]] || false
  [[ "$publication_recovery_text" == *'REPLACE_APPROVED_SNAPSHOT'*'git hash-object'* ]] || false
  [[ "$publication_recovery_text" == *'compare it with `REPLACE_APPROVED_SNAPSHOT`, regardless of `git status`'* ]] || false
  [[ "$publication_recovery_text" == *'replacement issue path must be a non-symlink regular file'* ]] || false
  [[ "$publication_recovery_text" == *'path_hash="$(git hash-object "$path")" || exit 1'* ]] || false
  [[ "$publication_recovery_text" == *'separate sort defined in the `Replacement approval snapshot` section above'* ]] || false
  [[ "$publication_recovery_text" == *'release-publication siw <owner-token>'*'because no replacement IDs have been reserved yet'* ]] || false
  [[ "$publication_recovery_text" == *'reacquire with the retained token'*'recompute the snapshot'* ]] || false
  [[ "$publication_recovery_text" == *'REMOVED_ISSUE_IDS'* ]] || false
  [[ "$publication_recovery_text" == *'append every `REMOVED_ISSUE_IDS` value after the final IDs'* ]] || false
  [[ "$publication_recovery_text" == *'release only the completed final-ID reservations'* ]] || false
  [[ "$publication_recovery_text" == *'failed multi-ID reservation attempt must unwind every exact reservation created by that attempt'* ]] || false
  [[ "$publication_recovery_text" == *'Once replacement deletion starts, never abandon any replacement reservation'* ]] || false
  [[ "$publication_recovery_text" == *'batches all issue-file digests within each immutable operation snapshot'* ]] || false
  [[ "$tracker_schema_text" == *'Phase 6.2'* ]] || false
  [[ "$tracker_schema_text" != *'ask the user whether'* ]] || false
}

@test "ordered heading drift fails" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" $'## Current Progress\n\n### Last Completed\n\n### Project Status'
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "ordered_heading_contracts": [
    {
      "name": "sample-heading-contract",
      "headings": [
        "## Current Progress",
        "### Project Status",
        "### Last Completed"
      ],
      "paths": [
        "trackbed/skills/a/SKILL.md"
      ]
    }
  ]
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"sample-heading-contract"* ]] || false
  [[ "$output" == *"missing or out-of-order heading"* ]] || false
}

@test "required file contract accepts frontmatter and required text" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" $'PLAN ROUTE: direct\nMISSING REQUIREMENT'
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "required_file_contracts": [
    {
      "name": "sample-required-file-contract",
      "path": "trackbed/skills/a/SKILL.md",
      "frontmatter": {
        "name": "test-skill",
        "user-invocable": "true"
      },
      "contains": [
        "PLAN ROUTE:",
        "MISSING REQUIREMENT"
      ]
    }
  ]
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
  [[ "$output" == *"skill contract lint passed."* ]] || false
}

@test "required file contract frontmatter drift fails with precise field" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" "PLAN ROUTE: direct"
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "required_file_contracts": [
    {
      "name": "sample-required-file-contract",
      "path": "trackbed/skills/a/SKILL.md",
      "frontmatter": {
        "name": "expected-skill"
      },
      "contains": [
        "PLAN ROUTE:"
      ]
    }
  ]
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"sample-required-file-contract"* ]] || false
  [[ "$output" == *"frontmatter field 'name' expected 'expected-skill'"* ]] || false
}

@test "required file contract missing marker fails" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" "PLAN ROUTE: direct"
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "required_file_contracts": [
    {
      "name": "sample-required-file-contract",
      "path": "trackbed/skills/a/SKILL.md",
      "contains": [
        "MISSING REQUIREMENT"
      ]
    }
  ]
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"sample-required-file-contract"* ]] || false
  [[ "$output" == *"is missing required text 'MISSING REQUIREMENT'"* ]] || false
}

@test "migrated guidance contracts stay registered" {
  assert_required_contracts_registered \
    pr-create-gh-prevalidation \
    pr-create-description-generation-contract \
    pr-create-linear-id-normalization \
    pr-create-branch-linear-state \
    pr-create-body-file-contract \
    pr-create-edit-loop-linear-normalization \
    pr-create-state-restoration-contract \
    pr-generate-description-subskill-contract \
    pr-generate-description-main-guidance \
    pr-generate-description-template-discovery \
    pr-generate-description-template-and-test-plan-rules \
    pr-generate-description-section-template-rules \
    pr-generate-description-output-cleanliness \
    pr-generate-description-antipattern-examples \
    pr-generate-description-cold-read-gate \
    pr-generate-description-direct-update-safety \
    pr-generate-description-save-and-checklist-contract \
    pr-generate-description-direct-update-checklist \
    pr-plan-reconcile-safety \
    pr-plan-reconcile-migration-guidance \
    pr-plan-split-reconcile-scope \
    linear-issue-implement-reference-mapping \
    linear-issue-implement-display-template \
    linear-issue-implement-plan-template \
    linear-issue-implement-public-note \
    code-optimize-shell-permission \
    code-optimize-source-manifest \
    workflow-artifact-cleanup-names
}

@test "reconcile workflow stays in the base diff scope" {
  run python3 - "$BATS_TEST_DIRNAME/../scripts/synced-contracts.yaml" <<'PY'
import json
import pathlib
import sys

registry = json.loads(pathlib.Path(sys.argv[1]).read_text())
reconcile_path = (
    "trackbed/skills/code:breakdown-findings/"
    "references/reconcile-workflow.md"
)
base_diff_paths = set(registry.get("base_diff_scope", {}).get("paths", []))
if reconcile_path not in base_diff_paths:
    raise SystemExit("reconcile workflow is missing from base_diff_scope paths")
PY

  [ "$status" -eq 0 ]
}

@test "shared contract-registry assertion reports unregistered contract names" {
  run assert_required_contracts_registered \
    workflow-artifact-cleanup-names \
    definitely-not-a-registered-contract

  [ "$status" -ne 0 ]
  [[ "$output" == *"missing required_file_contracts: definitely-not-a-registered-contract"* ]] || false
}

@test "multiline text contract drift fails" {
  write_file "$TMP_ROOT/trackbed/skills/a/SKILL.md" <<'EOF'
---
name: test-skill-a
description: Test skill A
disable-model-invocation: false
user-invocable: true
---
```bash
COLLECT_ARGS=(--strict --format json)
[ -n "${BASE_BRANCH_OVERRIDE:-}" ] && COLLECT_ARGS+=(--base "$BASE_BRANCH_OVERRIDE")

RESOLVED=$(${CLAUDE_PLUGIN_ROOT}/scripts/collect-review-diff.sh "${COLLECT_ARGS[@]}") || {
  echo "Base/diff collection failed; see the message above and stop." >&2
  exit 1
}

parse_review_diff_json() {
  local field="$1"
  REVIEW_DIFF_JSON="$RESOLVED" REVIEW_DIFF_FIELD="$field" python3 - <<'PY'
import json
PY
}

BASE_REF=$(parse_review_diff_json base_ref) || exit 1
BASE_BRANCH=$(parse_review_diff_json base_branch) || exit 1
MERGE_BASE=$(parse_review_diff_json merge_base) || exit 1
CHANGED_FILES=$(parse_review_diff_json changed_files) || exit 1
```
EOF
  write_file "$TMP_ROOT/trackbed/skills/b/SKILL.md" <<'EOF'
---
name: test-skill-b
description: Test skill B
disable-model-invocation: false
user-invocable: true
---
```bash
COLLECT_ARGS=(--strict --format json)
[ -n "${BASE_BRANCH_OVERRIDE:-}" ] && COLLECT_ARGS+=(--base "$BASE_BRANCH_OVERRIDE")

RESOLVED=$(${CLAUDE_PLUGIN_ROOT}/scripts/collect-review-diff.sh "${COLLECT_ARGS[@]}") || {
  echo "Base/diff collection failed; see the message above and stop." >&2
  exit 2
}

parse_review_diff_json() {
  local field="$1"
  REVIEW_DIFF_JSON="$RESOLVED" REVIEW_DIFF_FIELD="$field" python3 - <<'PY'
import json
PY
}

BASE_REF=$(parse_review_diff_json base_ref) || exit 1
BASE_BRANCH=$(parse_review_diff_json base_branch) || exit 1
MERGE_BASE=$(parse_review_diff_json merge_base) || exit 1
CHANGED_FILES=$(parse_review_diff_json changed_files) || exit 1
```
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "text_contracts": [
    {
      "name": "sample-multiline-text-contract",
      "extract_regex": "(?s)(COLLECT_ARGS=\\(--strict --format json\\).*?CHANGED_FILES=\\$\\(parse_review_diff_json changed_files\\) \\|\\| exit 1)",
      "paths": [
        "trackbed/skills/a/SKILL.md",
        "trackbed/skills/b/SKILL.md"
      ]
    }
  ]
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"sample-multiline-text-contract"* ]] || false
  [[ "$output" == *"differs"* ]] || false
}

@test "linewise multiline text contract catches line-boundary drift" {
  write_file "$TMP_ROOT/trackbed/skills/a/SKILL.md" <<'EOF'
---
name: test-skill-a
description: Test skill A
disable-model-invocation: false
user-invocable: true
---
```bash
COLLECT_ARGS=(--strict --format json)
[ -n "${BASE_BRANCH_OVERRIDE:-}" ] && COLLECT_ARGS+=(--base "$BASE_BRANCH_OVERRIDE")

RESOLVED=$(${CLAUDE_PLUGIN_ROOT}/scripts/collect-review-diff.sh "${COLLECT_ARGS[@]}") || {
  echo "Base/diff collection failed; see the message above and stop." >&2
  exit 1
}

parse_review_diff_json() {
  local field="$1"
  REVIEW_DIFF_JSON="$RESOLVED" REVIEW_DIFF_FIELD="$field" python3 - <<'PY'
import json
PY
}

BASE_REF=$(parse_review_diff_json base_ref) || exit 1
BASE_BRANCH=$(parse_review_diff_json base_branch) || exit 1
MERGE_BASE=$(parse_review_diff_json merge_base) || exit 1
CHANGED_FILES=$(parse_review_diff_json changed_files) || exit 1
```
EOF
  write_file "$TMP_ROOT/trackbed/skills/b/SKILL.md" <<'EOF'
---
name: test-skill-b
description: Test skill B
disable-model-invocation: false
user-invocable: true
---
```bash
COLLECT_ARGS=(--strict --format json)
[ -n "${BASE_BRANCH_OVERRIDE:-}" ] && COLLECT_ARGS+=(--base "$BASE_BRANCH_OVERRIDE")

RESOLVED=$(${CLAUDE_PLUGIN_ROOT}/scripts/collect-review-diff.sh "${COLLECT_ARGS[@]}") || {
  echo "Base/diff collection failed; see the message above and stop." >&2
  exit 1
}

parse_review_diff_json() {
  local field="$1"
  REVIEW_DIFF_JSON="$RESOLVED" REVIEW_DIFF_FIELD="$field" python3 - <<'PY'
import json
PY
}

BASE_REF=$(parse_review_diff_json base_ref) || exit 1
BASE_BRANCH=$(parse_review_diff_json base_branch) || exit 1
MERGE_BASE=$(parse_review_diff_json merge_base) || exit 1 CHANGED_FILES=$(parse_review_diff_json changed_files) || exit 1
```
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "text_contracts": [
    {
      "name": "sample-linewise-multiline-text-contract",
      "extract_regex": "(?s)(COLLECT_ARGS=\\(--strict --format json\\).*?CHANGED_FILES=\\$\\(parse_review_diff_json changed_files\\) \\|\\| exit 1)",
      "normalizer": "linewise",
      "paths": [
        "trackbed/skills/a/SKILL.md",
        "trackbed/skills/b/SKILL.md"
      ]
    }
  ]
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"sample-linewise-multiline-text-contract"* ]] || false
  [[ "$output" == *"differs"* ]] || false
}

@test "malformed hooks json fails" {
  write_file "$TMP_ROOT/trackbed/hooks/hooks.json" <<'EOF'
{"hooks":
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "hooks_json": {
    "path": "trackbed/hooks/hooks.json"
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"hooks json"* ]] || false
  [[ "$output" == *"invalid JSON"* ]] || false
}

@test "unknown hooks json event fails" {
  write_file "$TMP_ROOT/trackbed/hooks/hooks.json" <<'EOF'
{
  "hooks": {
    "BadEvent": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo ok"
          }
        ]
      }
    ]
  }
}
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "hooks_json": {
    "path": "trackbed/hooks/hooks.json"
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"unknown event 'BadEvent'"* ]] || false
}

@test "hook entry missing command fails" {
  write_file "$TMP_ROOT/trackbed/hooks/hooks.json" <<'EOF'
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command"
          }
        ]
      }
    ]
  }
}
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "hooks_json": {
    "path": "trackbed/hooks/hooks.json"
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"must define a non-empty command"* ]] || false
}

@test "hook command missing local plugin path fails" {
  write_file "$TMP_ROOT/trackbed/hooks/hooks.json" <<'EOF'
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/missing.sh"
          }
        ]
      }
    ]
  }
}
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "hooks_json": {
    "path": "trackbed/hooks/hooks.json",
    "plugin_root": "trackbed"
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"command references missing path trackbed/hooks/missing.sh"* ]] || false
}

@test "skill directory missing from readme fails" {
  write_reference_skill \
    "$TMP_ROOT/trackbed/skills/sample/SKILL.md" \
    "sample" \
    "Sample skill description" \
    "false" \
    "true"
  write_file "$TMP_ROOT/README.md" <<'EOF'
# Test README

## Skills

<!-- BEGIN SOURCE-SYNCED SKILL ROWS -->

<!-- END SOURCE-SYNCED SKILL ROWS -->

## Agents
EOF
  write_readme_skill_sync_registry

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"readme skill sync"* ]] || false
  [[ "$output" == *"missing skill 'trackbed:sample'"* ]] || false
}

@test "readme sync requires exact documented skill rows" {
  write_reference_skill \
    "$TMP_ROOT/trackbed/skills/qa/SKILL.md" \
    "qa" \
    "QA skill description" \
    "false" \
    "true"
  write_reference_skill \
    "$TMP_ROOT/trackbed/skills/qa:intake/SKILL.md" \
    "qa:intake" \
    "QA intake skill description" \
    "true" \
    "true"
  write_file "$TMP_ROOT/README.md" <<'EOF'
# Test README

Try /trackbed:qa for live checks.

## Skills

<!-- BEGIN SOURCE-SYNCED SKILL ROWS -->

| Skill | Invocation | Arguments | Description |
| --- | --- | --- | --- |
| `/trackbed:qa:intake` | User | — | QA intake skill description |

<!-- END SOURCE-SYNCED SKILL ROWS -->

## Agents
EOF
  write_readme_skill_sync_registry

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"readme skill sync"* ]] || false
  [[ "$output" == *"missing skill 'trackbed:qa'"* ]] || false
}

@test "readme sync accepts background skill rows but ignores agent rows" {
  write_reference_skill \
    "$TMP_ROOT/trackbed/skills/background/SKILL.md" \
    "background" \
    "Background skill description" \
    "false" \
    "false"
  write_file "$TMP_ROOT/README.md" <<'EOF'
# Test README

## Skills

<!-- BEGIN SOURCE-SYNCED SKILL ROWS -->

### Background Skills

| Skill | Invocation | Arguments | Description |
| --- | --- | --- | --- |
| `trackbed:background` | Background | — | Background skill description |

<!-- END SOURCE-SYNCED SKILL ROWS -->

## Agents

| Agent | Description |
| --- | --- |
| `trackbed:missing-agent` | Agent, not a skill. |
EOF
  write_readme_skill_sync_registry

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
  [[ "$output" == *"skill contract lint passed."* ]] || false
}

@test "readme ghost skill fails" {
  write_reference_skill \
    "$TMP_ROOT/trackbed/skills/real/SKILL.md" \
    "real" \
    "Real skill description" \
    "false" \
    "true"
  write_file "$TMP_ROOT/README.md" <<'EOF'
# Test README

## Skills

<!-- BEGIN SOURCE-SYNCED SKILL ROWS -->

| Skill | Invocation | Arguments | Description |
| --- | --- | --- | --- |
| `/trackbed:real` | User, Auto | — | Real skill description |
| `/trackbed:ghost` | User | — | Ghost skill description |

<!-- END SOURCE-SYNCED SKILL ROWS -->

## Agents
EOF
  write_readme_skill_sync_registry

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"documents 'trackbed:ghost'"* ]] || false
  [[ "$output" == *"does not exist"* ]] || false
}

@test "marker manifest empty field fails unless allowlisted" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" "SIMPLICITY CHECK: minimum viable change"
  write_file "$TMP_ROOT/trackbed/skills/a/references/sources.yaml" <<'EOF'
sources:
  - id: source-a
    url: https://example.com/source-a
    title: Source A
    rationale: Used for test fixture.
    last_reviewed_at: 2026-06-10
    baseline_hash: ""
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "marker_implies_manifest": {
    "skill_glob": "trackbed/skills/*/SKILL.md",
    "manifest": "references/sources.yaml",
    "markers": [
      "SIMPLICITY CHECK"
    ],
    "required_fields": [
      "id",
      "title",
      "rationale",
      "last_reviewed_at",
      "baseline_hash"
    ],
    "one_of_fields": [
      "url",
      "context7_library"
    ],
    "allow_empty_fields": []
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"marker manifest"* ]] || false
  [[ "$output" == *"empty 'baseline_hash'"* ]] || false
}

@test "marker manifest accepts exact allowlisted empty field with reason" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" "SIMPLICITY CHECK: minimum viable change"
  write_file "$TMP_ROOT/trackbed/skills/a/references/sources.yaml" <<'EOF'
sources:
  - id: source-a
    url: https://example.com/source-a
    title: Source A
    rationale: Used for test fixture.
    last_reviewed_at: 2026-06-10
    baseline_hash: ""
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "marker_implies_manifest": {
    "skill_glob": "trackbed/skills/*/SKILL.md",
    "manifest": "references/sources.yaml",
    "markers": [
      "SIMPLICITY CHECK"
    ],
    "required_fields": [
      "id",
      "title",
      "rationale",
      "last_reviewed_at",
      "baseline_hash"
    ],
    "one_of_fields": [
      "url",
      "context7_library"
    ],
    "allow_empty_fields": [
      {
        "path": "trackbed/skills/a/references/sources.yaml",
        "entry_id": "source-a",
        "field": "baseline_hash",
        "reason": "Historical baseline hash debt in this fixture."
      }
    ]
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
  [[ "$output" == *"skill contract lint passed."* ]] || false
}

@test "marker manifest rejects stale empty-field allowance" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" "SIMPLICITY CHECK: minimum viable change"
  write_file "$TMP_ROOT/trackbed/skills/a/references/sources.yaml" <<'EOF'
sources:
  - id: source-a
    url: https://example.com/source-a
    title: Source A
    rationale: Used for test fixture.
    last_reviewed_at: 2026-06-10
    baseline_hash: sha256:abc123
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "marker_implies_manifest": {
    "skill_glob": "trackbed/skills/*/SKILL.md",
    "manifest": "references/sources.yaml",
    "markers": [
      "SIMPLICITY CHECK"
    ],
    "required_fields": [
      "id",
      "title",
      "rationale",
      "last_reviewed_at",
      "baseline_hash"
    ],
    "one_of_fields": [
      "url",
      "context7_library"
    ],
    "allow_empty_fields": [
      {
        "path": "trackbed/skills/a/references/sources.yaml",
        "entry_id": "source-a",
        "field": "baseline_hash",
        "reason": "Historical baseline hash debt in this fixture."
      }
    ]
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"marker manifest"* ]] || false
  [[ "$output" == *"allow_empty_fields entry"* ]] || false
  [[ "$output" == *"does not match an empty required field"* ]] || false
}

@test "marker manifest allowlisted empty field requires reason" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" "SIMPLICITY CHECK: minimum viable change"
  write_file "$TMP_ROOT/trackbed/skills/a/references/sources.yaml" <<'EOF'
sources:
  - id: source-a
    url: https://example.com/source-a
    title: Source A
    rationale: Used for test fixture.
    last_reviewed_at: 2026-06-10
    baseline_hash: ""
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "marker_implies_manifest": {
    "skill_glob": "trackbed/skills/*/SKILL.md",
    "manifest": "references/sources.yaml",
    "markers": [
      "SIMPLICITY CHECK"
    ],
    "required_fields": [
      "id",
      "title",
      "rationale",
      "last_reviewed_at",
      "baseline_hash"
    ],
    "one_of_fields": [
      "url",
      "context7_library"
    ],
    "allow_empty_fields": [
      {
        "path": "trackbed/skills/a/references/sources.yaml",
        "entry_id": "source-a",
        "field": "baseline_hash",
        "reason": ""
      }
    ]
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"marker manifest"* ]] || false
  [[ "$output" == *"allow_empty_fields[1]"* ]] || false
  [[ "$output" == *"non-empty 'reason'"* ]] || false
}

@test "marker manifest required fields come from shared schema" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" "SIMPLICITY CHECK: minimum viable change"
  write_file "$TMP_ROOT/trackbed/skills/a/references/sources.yaml" <<'EOF'
sources:
  - id: source-a
    url: https://example.com/source-a
    title: Source A
EOF
  write_file "$TMP_ROOT/schema.json" <<'EOF'
{
  "skill_frontmatter": {
    "fields": {
      "name": {"type": "string", "required": true}
    }
  },
  "source_manifest": {
    "required_fields": [
      "id",
      "title",
      "audit_token"
    ],
    "one_of_fields": [
      "url"
    ]
  }
}
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "contract_schema": "schema.json",
  "marker_implies_manifest": {
    "skill_glob": "trackbed/skills/*/SKILL.md",
    "manifest": "references/sources.yaml",
    "markers": [
      "SIMPLICITY CHECK"
    ],
    "allow_empty_fields": []
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"marker manifest"* ]] || false
  [[ "$output" == *"missing 'audit_token'"* ]] || false
}

@test "schema-backed marker manifest rejects duplicate registry field lists" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" "SIMPLICITY CHECK: minimum viable change"
  write_file "$TMP_ROOT/trackbed/skills/a/references/sources.yaml" <<'EOF'
sources:
  - id: source-a
    url: https://example.com/source-a
    title: Source A
EOF
  write_file "$TMP_ROOT/schema.json" <<'EOF'
{
  "skill_frontmatter": {
    "fields": {
      "name": {"type": "string", "required": true}
    }
  },
  "source_manifest": {
    "required_fields": ["id", "title"],
    "one_of_fields": ["url"]
  }
}
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "contract_schema": "schema.json",
  "marker_implies_manifest": {
    "skill_glob": "trackbed/skills/*/SKILL.md",
    "manifest": "references/sources.yaml",
    "markers": [
      "SIMPLICITY CHECK"
    ],
    "required_fields": [
      "id"
    ],
    "allow_empty_fields": []
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"marker manifest"* ]] || false
  [[ "$output" == *"required_fields must come from contract_schema"* ]] || false
}

@test "source provenance rejects committed source snapshots" {
  write_file "$TMP_ROOT/trackbed/skills/a/references/sources-snapshot/upstream.md" <<'EOF'
copied upstream body
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "source_provenance": {
    "manifest_glob": "trackbed/skills/*/references/sources.yaml",
    "forbidden_snapshot_globs": [
      "trackbed/skills/*/references/sources-snapshot"
    ]
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"committed upstream source bodies are forbidden"* ]] || false
  [[ "$output" == *"sources-snapshot"* ]] || false
}

@test "source provenance requires copied-source rights and immutable origin" {
  write_file "$TMP_ROOT/trackbed/skills/a/references/sources.yaml" <<'EOF'
sources:
  - id: copied-source
    url: https://example.com/copied
    title: Copied source
    rationale: "Copied into scripts/copied.sh."
    usage: copied
    last_reviewed_at: 2026-07-29
    baseline_hash: "sha256:abc123"
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "source_provenance": {
    "manifest_glob": "trackbed/skills/*/references/sources.yaml"
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"copied entry 'copied-source' is missing non-empty 'license'"* ]] || false
  [[ "$output" == *"copied entry 'copied-source' is missing non-empty 'notice'"* ]] || false
  [[ "$output" == *"copied entry 'copied-source' is missing non-empty 'upstream_path'"* ]] || false
  [[ "$output" == *"copied entry 'copied-source' is missing an immutable upstream revision"* ]] || false
}

@test "source provenance accepts copied source with skill-local notice" {
  write_file "$TMP_ROOT/trackbed/skills/a/references/sources.yaml" <<'EOF'
sources:
  - id: copied-source
    url: https://example.com/copied
    title: Copied source
    rationale: "Copied into scripts/copied.sh."
    usage: copied
    license: MIT
    notice: references/UPSTREAM-LICENSE
    upstream_path: scripts/copied.sh
    upstream_commit: 0123456789abcdef0123456789abcdef01234567
    last_reviewed_at: 2026-07-29
    baseline_hash: "sha256:abc123"
EOF
  write_file "$TMP_ROOT/trackbed/skills/a/references/UPSTREAM-LICENSE" <<'EOF'
Upstream license notice
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "source_provenance": {
    "manifest_glob": "trackbed/skills/*/references/sources.yaml"
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
  [[ "$output" == *"skill contract lint passed."* ]] || false
}

@test "base diff scope rejects hand-rolled remote base snippets" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" $'```bash\nBASE_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2> /dev/null)\ngit fetch origin refs/heads/${BASE_BRANCH}:refs/remotes/origin/${BASE_BRANCH}\ngit merge-base "origin/${BASE_BRANCH}" HEAD\ngit diff --name-only "origin/$BASE_BRANCH"...HEAD\n```'
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "base_diff_scope": {
    "paths": [
      "trackbed/skills/a/SKILL.md"
    ],
    "forbidden_patterns": [
      {
        "name": "manual-origin-head-base-detection",
        "regex": "git\\s+symbolic-ref(?:\\s+--(?:quiet|short))*\\s+refs/remotes/origin/HEAD"
      },
      {
        "name": "manual-base-fetch",
        "regex": "git\\s+fetch\\s+origin\\s+[\"']?refs/heads/(?:\\$BASE_BRANCH|\\$\\{BASE_BRANCH\\})(?::refs/remotes/origin/(?:\\$BASE_BRANCH|\\$\\{BASE_BRANCH\\}))?[\"']?"
      },
      {
        "name": "manual-origin-base-merge-base",
        "regex": "git\\s+merge-base\\s+[\"']?origin/(?:\\$BASE_BRANCH|\\$\\{BASE_BRANCH\\})[\"']?\\s+HEAD"
      },
      {
        "name": "manual-origin-base-diff",
        "regex": "git\\s+diff\\s+(?:--name-only\\s+)?[\"']?origin/(?:\\$BASE_BRANCH|\\$\\{BASE_BRANCH\\})[\"']?\\.\\.\\.HEAD"
      }
    ]
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"base-diff-scope"* ]] || false
  [[ "$output" == *"manual-origin-head-base-detection"* ]] || false
  [[ "$output" == *"manual-base-fetch"* ]] || false
  [[ "$output" == *"manual-origin-base-merge-base"* ]] || false
  [[ "$output" == *"manual-origin-base-diff"* ]] || false
}

@test "base diff scope accepts canonical shared script snippets" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" $'```bash\nRESOLVED=$("${CLAUDE_PLUGIN_ROOT}/scripts/resolve-base.sh" --strict)\nRESOLVED=$("${CLAUDE_PLUGIN_ROOT}/scripts/collect-review-diff.sh" --strict)\n```'
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "base_diff_scope": {
    "paths": [
      "trackbed/skills/a/SKILL.md"
    ],
    "forbidden_patterns": [
      {
        "name": "manual-origin-head-base-detection",
        "regex": "git\\s+symbolic-ref(?:\\s+--(?:quiet|short))*\\s+refs/remotes/origin/HEAD"
      },
      {
        "name": "manual-origin-base-diff",
        "regex": "git\\s+diff\\s+(?:--name-only\\s+)?[\"']?origin/(?:\\$BASE_BRANCH|\\$\\{BASE_BRANCH\\})[\"']?\\.\\.\\.HEAD"
      }
    ]
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
  [[ "$output" == *"skill contract lint passed."* ]] || false
}

@test "forbidden epilogue heading fails" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" $'## Red Flags — STOP\n\n- never\n\n## Verification\n\n- [ ] done'
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "epilogue_forbidden": {
    "skill_glob": "trackbed/skills/*/SKILL.md",
    "forbidden_heading_regexes": [
      "^#{2,3}\\s+Common Rationalizations\\b",
      "^#{2,3}\\s+Red Flags\\b"
    ],
    "allowlist": []
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"epilogue forbidden"* ]] || false
  [[ "$output" == *"Red Flags"* ]] || false
}

@test "trimmed verification section passes epilogue check" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" $'## Verification\n\n- [ ] the artifact exists'
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "epilogue_forbidden": {
    "skill_glob": "trackbed/skills/*/SKILL.md",
    "forbidden_heading_regexes": [
      "^#{2,3}\\s+Common Rationalizations\\b",
      "^#{2,3}\\s+Red Flags\\b"
    ],
    "allowlist": []
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
  [[ "$output" == *"skill contract lint passed."* ]] || false
}

write_shipped_epilogue_registry() {
  python3 - "$BATS_TEST_DIRNAME/../scripts/synced-contracts.yaml" "$TMP_ROOT/registry.yaml" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    registry = json.load(handle)
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump({"epilogue_forbidden": registry["epilogue_forbidden"]}, handle)
PY
}

@test "retired epilogue names inside a heading fail with the shipped patterns" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" $'## When To Apply — Red Flags That Mean STOP\n\n- claims\n\n## Rationalization Prevention\n\n- never'
  write_shipped_epilogue_registry

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"epilogue forbidden"* ]] || false
  [[ "$output" == *"When To Apply — Red Flags That Mean STOP"* ]] || false
  [[ "$output" == *"Rationalization Prevention"* ]] || false
}

@test "retired epilogue names inside a heading fail with the default patterns" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" $'## When To Apply — Red Flags That Mean STOP\n\n- claims\n\n## Rationalization Prevention\n\n- never'
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "epilogue_forbidden": {
    "skill_glob": "trackbed/skills/*/SKILL.md",
    "allowlist": []
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"epilogue forbidden"* ]] || false
  [[ "$output" == *"When To Apply — Red Flags That Mean STOP"* ]] || false
  [[ "$output" == *"Rationalization Prevention"* ]] || false
}

@test "ordinary headings pass the broadened epilogue patterns" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" $'## Design rationale\n\n- why\n\n## Verification\n\n- [ ] the artifact exists'
  write_shipped_epilogue_registry

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
  [[ "$output" == *"skill contract lint passed."* ]] || false
}

@test "mechanical frontmatter regression fails" {
  write_file "$TMP_ROOT/trackbed/skills/a/SKILL.md" <<'EOF'
---
name: test-skill
description: Test skill
disable-model-invocation: false
---
# Test
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "mechanical": {
    "skill_glob": "trackbed/skills/*/SKILL.md",
    "max_skill_lines": 500,
    "max_description_chars": 1024,
    "required_frontmatter": [
      "name",
      "description",
      "disable-model-invocation",
      "user-invocable"
    ],
    "allow_line_count_over": []
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"missing frontmatter field 'user-invocable'"* ]] || false
}

@test "mechanical frontmatter accepts every schema-declared primitive type" {
  write_file "$TMP_ROOT/trackbed/skills/a/SKILL.md" <<'EOF'
---
name: test-skill
description: Test skill
argument-hint: "[target]"
disable-model-invocation: "false"
user-invocable: true
trackbed-platforms: [claude-code, "codex"]
---
# Test
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "mechanical": {
    "skill_glob": "trackbed/skills/*/SKILL.md"
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
  [[ "$output" == *"skill contract lint passed."* ]] || false
}

@test "mechanical frontmatter accepts block arrays after comments and blank lines" {
  write_file "$TMP_ROOT/trackbed/skills/a/SKILL.md" <<'EOF'
---
name: test-skill
description: Test skill
disable-model-invocation: false
user-invocable: true
trackbed-platforms:
  # Supported targets

  - claude-code
  - codex
---
# Test
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "mechanical": {
    "skill_glob": "trackbed/skills/*/SKILL.md"
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
  [[ "$output" == *"skill contract lint passed."* ]] || false
}

@test "mechanical frontmatter accepts an indented continued string" {
  write_file "$TMP_ROOT/trackbed/skills/a/SKILL.md" <<'EOF'
---
name: test-skill
description:
  Test skill continued on the next line
disable-model-invocation: false
user-invocable: true
---
# Test
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "mechanical": {
    "skill_glob": "trackbed/skills/*/SKILL.md"
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
  [[ "$output" == *"skill contract lint passed."* ]] || false
}

@test "mechanical frontmatter rejects empty block scalar strings" {
  write_file "$TMP_ROOT/trackbed/skills/a/SKILL.md" <<'EOF'
---
name: test-skill
description: |
disable-model-invocation: false
user-invocable: true
---
# Test
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "mechanical": {
    "skill_glob": "trackbed/skills/*/SKILL.md"
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"frontmatter field 'description' must be a non-empty string"* ]] || false
}

@test "mechanical frontmatter reports every invalid schema-declared primitive type" {
  write_file "$TMP_ROOT/trackbed/skills/a/SKILL.md" <<'EOF'
---
name: false
description:
argument-hint: false
disable-model-invocation: maybe
user-invocable: 0
trackbed-platforms: codex
---
# Test
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "mechanical": {
    "skill_glob": "trackbed/skills/*/SKILL.md"
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"skills/a/SKILL.md frontmatter field 'name' must be a non-empty string"* ]] || false
  [[ "$output" == *"skills/a/SKILL.md frontmatter field 'description' must be a non-empty string"* ]] || false
  [[ "$output" == *"skills/a/SKILL.md frontmatter field 'argument-hint' must be a non-empty string"* ]] || false
  [[ "$output" == *"skills/a/SKILL.md frontmatter field 'disable-model-invocation' must be a boolean"* ]] || false
  [[ "$output" == *"skills/a/SKILL.md frontmatter field 'user-invocable' must be a boolean"* ]] || false
  [[ "$output" == *"skills/a/SKILL.md frontmatter field 'trackbed-platforms' must be a non-empty array of non-empty strings"* ]] || false
}

@test "mechanical frontmatter rejects non-string nodes in arrays" {
  write_file "$TMP_ROOT/trackbed/skills/a/SKILL.md" <<'EOF'
---
name: test-skill
description: Test skill
disable-model-invocation: false
user-invocable: true
trackbed-platforms: [codex, [nested]]
---
# Test
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "mechanical": {
    "skill_glob": "trackbed/skills/*/SKILL.md"
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"frontmatter field 'trackbed-platforms' must be a non-empty array of non-empty strings"* ]] || false

  write_file "$TMP_ROOT/trackbed/skills/a/SKILL.md" <<'EOF'
---
name: test-skill
description: Test skill
disable-model-invocation: false
user-invocable: true
trackbed-platforms: [codex, .5]
---
# Test
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"frontmatter field 'trackbed-platforms' must be a non-empty array of non-empty strings"* ]] || false

  write_file "$TMP_ROOT/trackbed/skills/a/SKILL.md" <<'EOF'
---
name: test-skill
description: Test skill
disable-model-invocation: false
user-invocable: true
trackbed-platforms: [codex, 0x10]
---
# Test
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"frontmatter field 'trackbed-platforms' must be a non-empty array of non-empty strings"* ]] || false

  write_file "$TMP_ROOT/trackbed/skills/a/SKILL.md" <<'EOF'
---
name: test-skill
description: Test skill
disable-model-invocation: false
user-invocable: true
trackbed-platforms:
  - codex
  - [nested]
---
# Test
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"frontmatter field 'trackbed-platforms' must be a non-empty array of non-empty strings"* ]] || false
}

@test "mechanical agent frontmatter name must match filename" {
  write_file "$TMP_ROOT/trackbed/agents/other-agent.md" <<'EOF'
---
name: sample-agent
description: Test agent
model: inherit
color: blue
---
# Test
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "mechanical": {
    "agent_glob": "trackbed/agents/*.md"
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"frontmatter name 'sample-agent' does not match agent filename 'other-agent'"* ]] || false
}

@test "skill contract coverage accepts one suite protecting multiple skills" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" "# A"
  write_minimal_skill "$TMP_ROOT/trackbed/skills/b/SKILL.md" "# B"
  write_file "$TMP_ROOT/trackbed/tests/shared-guidance.bats" <<'EOF'
#!/usr/bin/env bats
cat "$ROOT/skills/a/SKILL.md" "$ROOT/skills/b/SKILL.md"
EOF
  write_file "$TMP_ROOT/config/coverage.json" <<'EOF'
{
  "skill_contracts": [
    {
      "kind": "guidance",
      "suite": "trackbed/tests/shared-guidance.bats",
      "skills": [
        "trackbed/skills/a/SKILL.md",
        "trackbed/skills/b/SKILL.md"
      ]
    }
  ]
}
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "skill_contract_coverage": {
    "inventory": "config/coverage.json",
    "mechanical_only": []
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
  [[ "$output" == *"skill contract lint passed."* ]] || false
}

@test "skill contract coverage fails when required configuration is missing" {
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "mechanical": {
    "require_skill_contract_coverage": true
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"mechanical: skill_contract_coverage is required"* ]] || false
}

@test "skill contract coverage rejects mappings to missing skills" {
  write_file "$TMP_ROOT/trackbed/tests/guidance.bats" <<'EOF'
#!/usr/bin/env bats
EOF
  write_file "$TMP_ROOT/config/coverage.json" <<'EOF'
{
  "skill_contracts": [
    {
      "kind": "guidance",
      "suite": "trackbed/tests/guidance.bats",
      "skills": ["trackbed/skills/missing/SKILL.md"]
    }
  ]
}
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "skill_contract_coverage": {
    "inventory": "config/coverage.json",
    "mechanical_only": []
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"skill does not exist: trackbed/skills/missing/SKILL.md"* ]] || false
}

@test "skill contract coverage rejects mappings to missing suites" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" "# A"
  write_file "$TMP_ROOT/config/coverage.json" <<'EOF'
{
  "skill_contracts": [
    {
      "kind": "guidance",
      "suite": "trackbed/tests/missing.bats",
      "skills": ["trackbed/skills/a/SKILL.md"]
    }
  ]
}
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "skill_contract_coverage": {
    "inventory": "config/coverage.json",
    "mechanical_only": []
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"suite does not exist: trackbed/tests/missing.bats"* ]] || false
}

@test "skill contract coverage rejects non-string contract kinds" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" "# A"
  write_file "$TMP_ROOT/trackbed/tests/guidance.bats" <<'EOF'
#!/usr/bin/env bats
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "skill_contract_coverage": {
    "inventory": "config/coverage.json",
    "mechanical_only": []
  }
}
EOF

  for kind in '[]' '{}'; do
    write_file "$TMP_ROOT/config/coverage.json" <<EOF
{
  "skill_contracts": [
    {
      "kind": $kind,
      "suite": "trackbed/tests/guidance.bats",
      "skills": ["trackbed/skills/a/SKILL.md"]
    }
  ]
}
EOF

    run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

    [ "$status" -eq 1 ]
    [[ "$output" == *"kind must be one of evaluation, executable, guidance, registry"* ]] || false
    [[ "$output" != *"Traceback"* ]] || false
  done
}

@test "skill contract coverage rejects duplicate relationships" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/a/SKILL.md" "# A"
  write_file "$TMP_ROOT/trackbed/tests/guidance.bats" <<'EOF'
#!/usr/bin/env bats
EOF
  write_file "$TMP_ROOT/config/coverage.json" <<'EOF'
{
  "skill_contracts": [
    {
      "kind": "guidance",
      "suite": "trackbed/tests/guidance.bats",
      "skills": [
        "trackbed/skills/a/SKILL.md",
        "trackbed/skills/a/SKILL.md"
      ]
    }
  ]
}
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "skill_contract_coverage": {
    "inventory": "config/coverage.json",
    "mechanical_only": []
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"duplicate skill contract mapping: trackbed/skills/a/SKILL.md -> trackbed/tests/guidance.bats"* ]] || false
}

@test "skill contract coverage requires new skills to be classified" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/new/SKILL.md" "# New"
  write_file "$TMP_ROOT/config/coverage.json" <<'EOF'
{"skill_contracts": []}
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "skill_contract_coverage": {
    "inventory": "config/coverage.json",
    "mechanical_only": []
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"skill contract coverage is unclassified: trackbed/skills/new/SKILL.md"* ]] || false
}

@test "skill contract coverage warns for explicit mechanical-only debt" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/uncovered/SKILL.md" "# Uncovered"
  write_file "$TMP_ROOT/config/coverage.json" <<'EOF'
{"skill_contracts": []}
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "skill_contract_coverage": {
    "inventory": "config/coverage.json",
    "mechanical_only": [
      "trackbed/skills/uncovered/SKILL.md"
    ]
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
  [[ "$output" == *"::warning::mechanical: skill-contract burndown: trackbed/skills/uncovered/SKILL.md has mechanical checks only"* ]] || false
  [[ "$output" == *"skill contract lint passed."* ]] || false
}

write_routing_skill() {
  # Frontmatter names and folders carry no prefix; prose uses the qualified name.
  local name="${1#trackbed:}"
  local description="$2"
  local disable_model_invocation="${3:-false}"
  write_file "$TMP_ROOT/trackbed/skills/$name/SKILL.md" <<EOF
---
name: $name
description: $description
disable-model-invocation: $disable_model_invocation
user-invocable: true
---
Body.
EOF
}

@test "routing distinctness fails overlapping auto-invocable descriptions" {
  write_routing_skill "alpha" "Review branch changes accessibility problems report findings"
  write_routing_skill "beta" "Review branch changes accessibility problems report findings keyboard focus contrast"
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "routing_distinctness": {
    "skill_glob": "trackbed/skills/*/SKILL.md",
    "warn_similarity": 0.3,
    "fail_similarity": 0.6,
    "stopwords": []
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"::error::routing distinctness: trackbed/skills/alpha/SKILL.md and trackbed/skills/beta/SKILL.md descriptions score 0.70 (fail at 0.60)"* ]] || false
  [[ "$output" == *"routing_distinctness.recorded_boundaries entry with a positive one-clause routing rule"* ]] || false
}

@test "routing distinctness records adjudicated pairs and warns on nearest neighbours" {
  write_routing_skill "alpha" "Review branch changes accessibility problems report findings"
  write_routing_skill "beta" "Review branch changes accessibility problems report findings keyboard focus contrast"
  write_routing_skill "epsilon" "Generate release notes merged pull requests"
  write_routing_skill "zeta" "Generate release notes tagged commits changelog entries"
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "routing_distinctness": {
    "skill_glob": "trackbed/skills/*/SKILL.md",
    "warn_similarity": 0.3,
    "fail_similarity": 0.6,
    "stopwords": [],
    "recorded_boundaries": [
      {
        "skills": [
          "trackbed/skills/alpha/SKILL.md",
          "trackbed/skills/beta/SKILL.md"
        ],
        "boundary": "Alpha audits a whole branch; beta audits one keyboard flow."
      }
    ]
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
  [[ "$output" == *"skill contract lint warnings:"* ]] || false
  [[ "$output" == *"::warning::routing distinctness: nearest-pair burndown: trackbed/skills/epsilon/SKILL.md and trackbed/skills/zeta/SKILL.md score 0.30 (warn at 0.30, fail at 0.60)"* ]] || false
  [[ "$output" != *"trackbed/skills/alpha/SKILL.md and trackbed/skills/beta/SKILL.md"* ]] || false
  [[ "$output" == *"skill contract lint passed."* ]] || false
}

write_invocation_skill() {
  # Frontmatter names and folders carry no prefix; prose uses the qualified name.
  local name="${1#trackbed:}"
  local body="$2"
  local disable_model_invocation="${3:-false}"
  local user_invocable="${4:-true}"
  write_file "$TMP_ROOT/trackbed/skills/$name/SKILL.md" <<EOF
---
name: $name
description: Test skill.
disable-model-invocation: $disable_model_invocation
user-invocable: $user_invocable
---
$body
EOF
}

write_invocation_registry() {
  local allowlist="${1:-[]}"
  write_file "$TMP_ROOT/registry.yaml" <<EOF
{
  "invocation_graph": {
    "skill_glob": "trackbed/skills/*/SKILL.md",
    "scan_globs": ["trackbed/skills/*/**/*.md"],
    "allowlist": $allowlist
  }
}
EOF
}

@test "invocation graph fails a hand-off to a model-disabled skill" {
  write_invocation_skill "trackbed:test:parent" 'Then invoke `trackbed:test:child` with the plan.'
  write_invocation_skill "trackbed:test:child" "Body." true
  write_invocation_registry

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"::error::invocation graph: trackbed/skills/test:parent/SKILL.md:7 hands off to trackbed:test:child (invoke), but trackbed:test:child sets disable-model-invocation: true"* ]] || false
  [[ "$output" == *"add an invocation_graph.allowlist entry with a reason"* ]] || false
}

@test "invocation graph fails a slash command for a hidden skill" {
  write_invocation_skill "trackbed:test:parent" 'Record the rule with `/trackbed:test:child`.'
  write_invocation_skill "trackbed:test:child" "Body." false false
  write_invocation_registry

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"::error::invocation graph: trackbed/skills/test:parent/SKILL.md:7 tells the user to run /trackbed:test:child, but trackbed:test:child sets user-invocable: false"* ]] || false
}

@test "invocation graph allowlist suppresses a reasoned hand-off and warns on unused entries" {
  write_invocation_skill "trackbed:test:parent" 'Then invoke `trackbed:test:child` with the plan.'
  write_invocation_skill "trackbed:test:child" "Body." true
  write_invocation_registry '[
    {"source": "trackbed/skills/test:parent/SKILL.md", "target": "trackbed:test:child", "reason": "The user runs this step."},
    {"source": "trackbed/skills/test:parent/SKILL.md", "target": "trackbed:test:gone", "reason": "Removed skill."}
  ]'

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
  [[ "$output" != *"hands off to"* ]] || false
  [[ "$output" == *"::warning::invocation graph: allowlist entry trackbed/skills/test:parent/SKILL.md -> trackbed:test:gone matches no finding; remove it"* ]] || false
  [[ "$output" == *"skill contract lint passed."* ]] || false
}

@test "deps audit hands SIW creation to the user" {
  local skill_text
  skill_text="$(cat "$BATS_TEST_DIRNAME/../skills/deps:audit/SKILL.md")"

  [[ "$skill_text" == *'Never read that skill'"'"'s `SKILL.md` and run its steps yourself.'* ]] || false
  [[ "$skill_text" != *"follow its steps inline"* ]] || false
}

@test "mechanical long-skill warning reports near-threshold candidates" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/below/SKILL.md" "$(make_body_lines 4)"
  write_minimal_skill "$TMP_ROOT/trackbed/skills/near/SKILL.md" "$(make_body_lines 6)"
  write_minimal_skill "$TMP_ROOT/trackbed/skills/high/SKILL.md" "$(make_body_lines 8)"
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "mechanical": {
    "skill_glob": "trackbed/skills/*/SKILL.md",
    "max_skill_lines": 20,
    "warn_skill_lines": 12,
    "skill_line_report_limit": 2,
    "max_description_chars": 1024,
    "required_frontmatter": [
      "name",
      "description",
      "disable-model-invocation",
      "user-invocable"
    ],
    "allow_line_count_over": []
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
  [[ "$output" == *"skill contract lint warnings:"* ]] || false
  [[ "$output" == *"::warning::mechanical: long-skill burndown: trackbed/skills/high/SKILL.md has 14 lines"* ]] || false
  [[ "$output" == *"::warning::mechanical: long-skill burndown: trackbed/skills/near/SKILL.md has 12 lines"* ]] || false
  [[ "$output" != *"trackbed/skills/below/SKILL.md"* ]] || false
  [[ "$output" == *"skill contract lint passed."* ]] || false
}

@test "mechanical hard line budget still fails above max" {
  write_minimal_skill "$TMP_ROOT/trackbed/skills/over/SKILL.md" "$(make_body_lines 15)"
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "mechanical": {
    "skill_glob": "trackbed/skills/*/SKILL.md",
    "max_skill_lines": 20,
    "warn_skill_lines": 12,
    "skill_line_report_limit": 2,
    "max_description_chars": 1024,
    "required_frontmatter": [
      "name",
      "description",
      "disable-model-invocation",
      "user-invocable"
    ],
    "allow_line_count_over": []
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"::warning::mechanical: long-skill burndown: trackbed/skills/over/SKILL.md has 21 lines"* ]] || false
  [[ "$output" == *"::error::mechanical: trackbed/skills/over/SKILL.md has 21 lines, exceeds 20"* ]] || false
}

@test "mechanical description warnings are ordered capped and warning-only" {
  write_routing_skill "below" "four"
  write_routing_skill "at" "fives"
  write_routing_skill "middle" "middle"
  write_routing_skill "zeta" "another"
  write_routing_skill "alpha" "seventh"
  write_routing_skill "high" "ninechars"
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "mechanical": {
    "skill_glob": "trackbed/skills/*/SKILL.md",
    "max_description_chars": 10,
    "warn_description_chars": 5,
    "skill_description_report_limit": 4
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
  [[ "$output" == *"skill contract lint warnings:"* ]] || false
  [[ "$output" == *"::warning::mechanical: long-description burndown: trackbed/skills/high/SKILL.md description is 9 chars"* ]] || false
  [[ "$output" == *"::warning::mechanical: long-description burndown: trackbed/skills/alpha/SKILL.md description is 7 chars"* ]] || false
  [[ "$output" == *"::warning::mechanical: long-description burndown: trackbed/skills/zeta/SKILL.md description is 7 chars"* ]] || false
  [[ "$output" == *"::warning::mechanical: long-description burndown: trackbed/skills/middle/SKILL.md description is 6 chars"* ]] || false
  [[ "$output" != *"long-description burndown: trackbed/skills/at/SKILL.md"* ]] || false
  [[ "$output" != *"long-description burndown: trackbed/skills/below/SKILL.md"* ]] || false
  [[ "$output" == *"skill contract lint passed."* ]] || false
}

@test "mechanical hard description budget still fails above max" {
  write_routing_skill "over" "ninechars"
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "mechanical": {
    "skill_glob": "trackbed/skills/*/SKILL.md",
    "max_description_chars": 8,
    "warn_description_chars": 5,
    "skill_description_report_limit": 2
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 1 ]
  [[ "$output" == *"::warning::mechanical: long-description burndown: trackbed/skills/over/SKILL.md description is 9 chars"* ]] || false
  [[ "$output" == *"::error::mechanical: trackbed/skills/over/SKILL.md description is 9 chars, exceeds 8"* ]] || false
}

@test "mechanical file size budgets warn for baselined and new executable debt" {
  write_file "$TMP_ROOT/trackbed/scripts/baselined.py" <<'EOF'
one
two
three
four
five
six
EOF
  write_file "$TMP_ROOT/trackbed/scripts/new-tool.sh" <<'EOF'
one
two
three
four
five
six
seven
EOF
  write_file "$TMP_ROOT/trackbed/scripts/small.js" <<'EOF'
one
two
three
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "mechanical": {
    "file_line_budgets": [
      {
        "name": "production code",
        "globs": ["trackbed/scripts/*"],
        "warn_lines": 5,
        "baseline": {
          "trackbed/scripts/baselined.py": 6
        },
        "excluded": []
      }
    ]
  }
}
EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
  [[ "$output" == *"::warning::mechanical: production code size baseline: trackbed/scripts/baselined.py has 6 lines (at baseline 6; warn at 5)"* ]] || false
  [[ "$output" == *"::warning::mechanical: production code size budget: unbaselined trackbed/scripts/new-tool.sh has 7 lines (warn at 5)"* ]] || false
  [[ "$output" != *"small.js"* ]] || false
  [[ "$output" == *"skill contract lint passed."* ]] || false
}

@test "mechanical file size baseline reports growth without failing" {
  write_file "$TMP_ROOT/trackbed/tests/growing.bats" <<'EOF'
one
two
three
four
five
six
seven
EOF
  write_file "$TMP_ROOT/registry.yaml" <<'EOF'
{
  "mechanical": {
    "file_line_budgets": [
      {
        "name": "test code",
        "globs": ["trackbed/tests/*.bats"],
        "warn_lines": 5,
        "baseline": {
          "trackbed/tests/growing.bats": 6
        },
        "excluded": []
      }
    ]
  }
}

EOF

  run python3 "$SCRIPT" --repo-root "$TMP_ROOT" --registry "$TMP_ROOT/registry.yaml"

  [ "$status" -eq 0 ]
  [[ "$output" == *"::warning::mechanical: test code size baseline: trackbed/tests/growing.bats has 7 lines (1 line above baseline 6; warn at 5)"* ]] || false
  [[ "$output" == *"skill contract lint passed."* ]] || false
}
