#!/usr/bin/env bats

bats_require_minimum_version 1.5.0

load 'test_helper/common'

setup() {
	SOURCE_SCRIPT="$BATS_TEST_DIRNAME/../scripts/run-skillspector.sh"
	SOURCE_LIBRARY="$BATS_TEST_DIRNAME/../scripts/lib/shell-helpers.sh"
	TMP_DIR="$(mktemp -d)"
	REPO="$TMP_DIR/repo"
	BIN_DIR="$TMP_DIR/bin"
	REPORT_DIR="$TMP_DIR/reports"
	MOCK_SOURCE="$BATS_TEST_DIRNAME/test_helper/mocks/skillspector"
	mkdir -p "$REPO/trackbed/scripts/lib" "$BIN_DIR" "$REPORT_DIR"
	cp "$BATS_TEST_DIRNAME/../Makefile" "$REPO/trackbed/Makefile"
	cp "$SOURCE_SCRIPT" "$REPO/trackbed/scripts/run-skillspector.sh"
	cp "$SOURCE_LIBRARY" "$REPO/trackbed/scripts/lib/shell-helpers.sh"
	chmod +x "$REPO/trackbed/scripts/run-skillspector.sh"
	ln -s "$MOCK_SOURCE" "$BIN_DIR/skillspector"
	export PATH="$BIN_DIR:$PATH"
	export MOCK_SKILLSPECTOR_LOG="$TMP_DIR/skillspector.log"
	unset MOCK_SKILLSPECTOR_EXIT
	unset MOCK_SKILLSPECTOR_JSON
	unset MOCK_SKILLSPECTOR_WRITE_OUTPUT
	unset MOCK_SKILLSPECTOR_PROBE

	init_test_git_repo "$REPO" --file README.md
	cd "$REPO"
	write_skill "kramme:one"
	write_skill "kramme:two"
	git add .
	git commit -m "add skills" >/dev/null
	git switch -c feature >/dev/null 2>&1
	SCRIPT="$REPO/trackbed/scripts/run-skillspector.sh"
}

teardown() {
	if [ -n "${TMP_DIR:-}" ] && [ -d "$TMP_DIR" ]; then
		rm -rf "$TMP_DIR"
	fi
}

write_skill() {
	local name="$1"
	local dir="$REPO/trackbed/skills/$name"
	mkdir -p "$dir/references"
	cat >"$dir/SKILL.md" <<EOF
---
name: $name
description: Test skill
disable-model-invocation: false
user-invocable: true
---
# $name
EOF
}

commit_file() {
	local file="$1"
	local content="$2"
	local message="$3"
	mkdir -p "$(dirname "$file")"
	printf '%s\n' "$content" >"$file"
	git add "$file"
	git commit -m "$message" >/dev/null
}

write_policy() {
	local file="$1"
	local body="$2"
	mkdir -p "$(dirname "$file")"
	printf '%s\n' "$body" >"$file"
}

count_invocations() {
	if [ ! -f "$MOCK_SKILLSPECTOR_LOG" ]; then
		printf '0\n'
		return
	fi
	wc -l <"$MOCK_SKILLSPECTOR_LOG" | tr -d ' '
}

@test "changed scan exits successfully when no skill directories changed" {
	commit_file "docs/notes.md" "notes" "change docs"

	run "$SCRIPT" --changed --base main --output-dir "$REPORT_DIR"

	[ "$status" -eq 0 ]
	[[ "$output" == *"No changed skill directories found against main"* ]] || false
	[ "$(count_invocations)" = "0" ]
}

@test "changed scan Make target does not require scanner when no skill directories changed" {
	run env PATH="/usr/bin:/bin" BASE_REF=HEAD make -C "$REPO/trackbed" --no-print-directory skill-security-changed

	[ "$status" -eq 0 ]
	[[ "$output" == *"No changed skill directories found against HEAD."* ]] || false
}

@test "changed scan explains a base ref it cannot resolve" {
	run "$SCRIPT" --changed --base origin/does-not-exist --output-dir "$REPORT_DIR"

	[ "$status" -eq 2 ]
	[[ "$output" == *"Cannot resolve a merge base between 'origin/does-not-exist' and HEAD."* ]] || false
	[[ "$output" == *"git fetch origin main"* ]] || false
	[[ "$output" != *"fatal:"* ]] || false
	[ "$(count_invocations)" = "0" ]
}

@test "changed scan maps resource changes to the owning skill directory" {
	commit_file "trackbed/skills/kramme:one/references/example.md" "example" "change skill resource"

	run "$SCRIPT" --changed --base main --output-dir "$REPORT_DIR"

	[ "$status" -eq 0 ]
	[ "$(count_invocations)" = "1" ]
	grep -q "trackbed/skills/kramme:one format=json" "$MOCK_SKILLSPECTOR_LOG"
}

@test "scan excludes source snapshots from scanner input" {
	commit_file "trackbed/skills/kramme:one/references/sources-snapshot/upstream.md" "upstream docs" "add source snapshot"

	run "$SCRIPT" --changed --base main --output-dir "$REPORT_DIR"

	[ "$status" -eq 0 ]
	[ "$(count_invocations)" = "1" ]
	grep -q "snapshot_exists=no" "$MOCK_SKILLSPECTOR_LOG"
	[ -f "$REPO/trackbed/skills/kramme:one/references/sources-snapshot/upstream.md" ]
}

@test "changed scan de-duplicates multiple changed files in one skill" {
	commit_file "trackbed/skills/kramme:one/references/one.md" "one" "change first resource"
	commit_file "trackbed/skills/kramme:one/references/two.md" "two" "change second resource"

	run "$SCRIPT" --changed --base main --output-dir "$REPORT_DIR"

	[ "$status" -eq 0 ]
	[ "$(count_invocations)" = "1" ]
}

@test "changed scan includes unstaged skill edits" {
	printf 'local edit\n' >>"trackbed/skills/kramme:one/SKILL.md"

	run "$SCRIPT" --changed --base main --output-dir "$REPORT_DIR"

	[ "$status" -eq 0 ]
	[ "$(count_invocations)" = "1" ]
	grep -q "trackbed/skills/kramme:one format=json" "$MOCK_SKILLSPECTOR_LOG"
}

@test "changed scan includes untracked skill files" {
	printf 'draft\n' >"trackbed/skills/kramme:two/references/draft.md"

	run "$SCRIPT" --changed --base main --output-dir "$REPORT_DIR"

	[ "$status" -eq 0 ]
	[ "$(count_invocations)" = "1" ]
	grep -q "trackbed/skills/kramme:two format=json" "$MOCK_SKILLSPECTOR_LOG"
}

@test "changed scan includes a changed shared resource topic" {
	commit_file "trackbed/shared/visual/references/guide.md" "guide" "change shared resource"

	run "$SCRIPT" --changed --base main --output-dir "$REPORT_DIR"

	[ "$status" -eq 0 ]
	[ "$(count_invocations)" = "1" ]
	grep -q "trackbed/shared/visual format=json" "$MOCK_SKILLSPECTOR_LOG"
	[ -f "$REPORT_DIR/shared_visual.json" ]
}

@test "all scan includes every shared resource topic" {
	commit_file "trackbed/shared/visual/references/guide.md" "guide" "add shared resource"

	run "$SCRIPT" --all --output-dir "$REPORT_DIR"

	[ "$status" -eq 0 ]
	[ "$(count_invocations)" = "3" ]
	grep -q "trackbed/shared/visual format=json" "$MOCK_SKILLSPECTOR_LOG"
}

@test "all scan uses static-only mode by default" {
	run "$SCRIPT" --all --output-dir "$REPORT_DIR"

	[ "$status" -eq 0 ]
	[ "$(count_invocations)" = "2" ]
	grep -q "no_llm=true" "$MOCK_SKILLSPECTOR_LOG"
}

@test "semantic scan omits static-only flag" {
	run "$SCRIPT" --all --semantic --output-dir "$REPORT_DIR"

	[ "$status" -eq 0 ]
	[ "$(count_invocations)" = "2" ]
	grep -q "no_llm=false" "$MOCK_SKILLSPECTOR_LOG"
}

@test "semantic scan keeps its reports apart from static reports by default" {
	RUNNER_TEMP="$TMP_DIR/runner" run "$SCRIPT" --all --semantic

	[ "$status" -eq 0 ]
	[ -f "$TMP_DIR/runner/skillspector-semantic/kramme_one.json" ]
	[ ! -e "$TMP_DIR/runner/skillspector" ]

	RUNNER_TEMP="$TMP_DIR/runner" run "$SCRIPT" --all

	[ "$status" -eq 0 ]
	[ -f "$TMP_DIR/runner/skillspector/kramme_one.json" ]
}

@test "semantic scan leaves out files listed in the semantic excludes" {
	commit_file "trackbed/skills/kramme:one/assets/vendor.min.js" "minified" "add vendored bundle"
	write_policy "$REPO/trackbed/config/skillspector-semantic-excludes.txt" "# vendored bundle
trackbed/skills/kramme:one/assets/vendor.min.js"
	export MOCK_SKILLSPECTOR_PROBE="assets/vendor.min.js"

	run "$SCRIPT" --changed --base main --semantic --output-dir "$REPORT_DIR"

	[ "$status" -eq 0 ]
	[ "$(count_invocations)" = "1" ]
	grep -q "no_llm=false .*probe_exists=no" "$MOCK_SKILLSPECTOR_LOG"
	[ -f "$REPO/trackbed/skills/kramme:one/assets/vendor.min.js" ]
}

@test "static scan keeps files listed in the semantic excludes" {
	commit_file "trackbed/skills/kramme:one/assets/vendor.min.js" "minified" "add vendored bundle"
	write_policy "$REPO/trackbed/config/skillspector-semantic-excludes.txt" "trackbed/skills/kramme:one/assets/vendor.min.js"
	export MOCK_SKILLSPECTOR_PROBE="assets/vendor.min.js"

	run "$SCRIPT" --changed --base main --output-dir "$REPORT_DIR"

	[ "$status" -eq 0 ]
	grep -q "no_llm=true .*probe_exists=yes" "$MOCK_SKILLSPECTOR_LOG"
}

@test "semantic excludes cannot reach outside the scanned directory" {
	commit_file "trackbed/skills/kramme:one/references/one.md" "one" "change skill resource"
	mkdir -p "$TMP_DIR/runner"
	printf 'keep\n' >"$TMP_DIR/runner/sentinel"
	write_policy "$REPO/trackbed/config/skillspector-semantic-excludes.txt" "trackbed/skills/kramme:one/../../sentinel"

	RUNNER_TEMP="$TMP_DIR/runner" run "$SCRIPT" --changed --base main --semantic --output-dir "$REPORT_DIR"

	[ "$status" -eq 0 ]
	[ -f "$TMP_DIR/runner/sentinel" ]
	grep -q "/repo/trackbed/skills/kramme:one format=json" "$MOCK_SKILLSPECTOR_LOG"
}

@test "semantic changed Make target runs one LLM scan per changed skill" {
	commit_file "trackbed/skills/kramme:one/references/one.md" "one" "change skill resource"

	run env RUNNER_TEMP="$TMP_DIR/runner" make -C "$REPO/trackbed" --no-print-directory skill-security-semantic-changed SKILLSPECTOR_BASE=main

	[ "$status" -eq 0 ]
	[ "$(count_invocations)" = "1" ]
	grep -q "trackbed/skills/kramme:one format=json .*no_llm=false" "$MOCK_SKILLSPECTOR_LOG"
	[ -f "$TMP_DIR/runner/skillspector-semantic/kramme_one.json" ]
}

@test "semantic scan workflow keeps the provider key on trusted main" {
	run node - "$BATS_TEST_DIRNAME/../.." <<'NODE'
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = process.argv[2];
const YAML = require(path.join(root, 'node_modules/yaml'));
const read = name => fs.readFileSync(path.join(root, '.github/workflows', name), 'utf8');
const workflow = YAML.parse(read('skill-security-semantic.yml'));

// Pull Request gates stay credential-free: the scan only runs after merge or by hand.
assert.deepEqual(Object.keys(workflow.on).sort(), ['push', 'workflow_dispatch']);
assert.deepEqual(workflow.on.push.branches, ['main']);
assert.deepEqual(workflow.on.push.paths, ['trackbed/skills/**', 'trackbed/shared/**']);
assert.deepEqual(workflow.permissions, {contents: 'read'});
assert.equal(workflow.concurrency['cancel-in-progress'], false);

const job = workflow.jobs['semantic-scan'];
assert.deepEqual(Object.keys(workflow.jobs), ['semantic-scan']);
assert.ok(job.if.includes("github.ref == 'refs/heads/main'"));
assert.ok(job.if.includes("vars.SKILLSPECTOR_SEMANTIC_MODEL != ''"));
assert.equal(job.env.SKILLSPECTOR_FAIL_ON, 'none');
assert.equal(job.env.SKILLSPECTOR_FORMAT, 'json');
assert.equal(job.steps[0].with['persist-credentials'], false);

// Only the LLM scan step receives the key, and nothing but the key.
const secretSteps = job.steps.filter(step => JSON.stringify(step).includes('secrets.'));
assert.equal(secretSteps.length, 1);
assert.equal(secretSteps[0].id, 'semantic');
assert.deepEqual(
  Object.entries(secretSteps[0].env).filter(([, value]) => value.includes('secrets.')),
  [['OPENAI_API_KEY', '${{ secrets.SKILLSPECTOR_OPENAI_API_KEY }}']],
);
assert.ok(secretSteps[0].run.includes('skill-security-semantic-changed'));
const registry = secretSteps[0].env.SKILLSPECTOR_MODEL_REGISTRY.replace('${{ github.workspace }}/', '');
assert.ok(fs.existsSync(path.join(root, registry)));

// Provider errors can name the account, so logs stay out of the public artifact.
const upload = job.steps.find(step => (step.uses || '').startsWith('actions/upload-artifact@'));
assert.equal(upload.if, '${{ always() }}');
assert.ok(upload.with.path.trim().split('\n').every(line => line.trim().endsWith('*.json')));

// All three workflows install the same SkillSpector commit.
const pin = job.env.SKILLSPECTOR_COMMIT;
assert.match(pin, /^[0-9a-f]{40}$/);
assert.equal(YAML.parse(read('skill-lint.yml')).jobs.skillspector.env.SKILLSPECTOR_COMMIT, pin);
assert.equal(YAML.parse(read('release.yml')).env.SKILLSPECTOR_REF, pin);
NODE
	[ "$status" -eq 0 ]
}

@test "missing skillspector prints a clear setup error" {
	rm -f "$BIN_DIR/skillspector"

	run -127 env PATH="/usr/bin:/bin:/usr/sbin:/sbin" "$SCRIPT" --all --output-dir "$REPORT_DIR"

	[ "$status" -eq 127 ]
	[[ "$output" == *"SkillSpector scanner not found on PATH"* ]] || false
}

@test "scanner process failure exits non-zero" {
	export MOCK_SKILLSPECTOR_EXIT=2
	export MOCK_SKILLSPECTOR_WRITE_OUTPUT=0

	run "$SCRIPT" --all --output-dir "$REPORT_DIR"

	[ "$status" -eq 1 ]
	[[ "$output" == *"SkillSpector scan failed"* ]] || false
}

@test "high threshold fails when JSON report contains a high finding" {
	export MOCK_SKILLSPECTOR_JSON='{"risk_assessment":{"score":25,"severity":"HIGH"},"issues":[{"severity":"HIGH","rule_id":"E4"}]}'

	run "$SCRIPT" --all --fail-on high --output-dir "$REPORT_DIR"

	[ "$status" -eq 1 ]
	[[ "$output" == *"Findings meet --fail-on high threshold"* ]] || false
}

@test "matching accepted finding is excluded from threshold failure" {
	local policy_file="$REPO/trackbed/config/skillspector-accepted-findings.json"
	export MOCK_SKILLSPECTOR_JSON='{"issues":[{"severity":"HIGH","id":"E4","location":{"file":"SKILL.md","start_line":1}}]}'
	write_policy "$policy_file" '{
  "accepted_findings": [
    {
      "path": "trackbed/skills/kramme:one/SKILL.md",
      "rule_id": "E4",
      "reason": "Reviewed false positive in test fixture.",
      "owner": "Security",
      "accepted_at": "2026-06-13",
      "expires_at": "2999-01-01"
    }
  ]
}'
	printf 'local edit\n' >>"trackbed/skills/kramme:one/SKILL.md"

	run "$SCRIPT" --changed --base main --fail-on high --output-dir "$REPORT_DIR"

	[ "$status" -eq 0 ]
	[[ "$output" == *"Accepted findings:"*"/trackbed/config/skillspector-accepted-findings.json"* ]] || false
	[[ "$output" == *"Findings: total=1 accepted=1 enforceable=0"* ]] || false
	[[ "$output" != *"Findings meet --fail-on high threshold"* ]] || false
}

@test "same rule on a different path is not accepted" {
	local policy_file="$TMP_DIR/accepted-findings.json"
	export MOCK_SKILLSPECTOR_JSON='{"issues":[{"severity":"HIGH","id":"E4","location":{"file":"SKILL.md","start_line":1}}]}'
	write_policy "$policy_file" '{
  "accepted_findings": [
    {
      "path": "trackbed/skills/kramme:two/SKILL.md",
      "rule_id": "E4",
      "reason": "Reviewed finding for the second skill only.",
      "owner": "Security",
      "accepted_at": "2026-06-13",
      "expires_at": "2999-01-01"
    }
  ]
}'
	printf 'local edit\n' >>"trackbed/skills/kramme:one/SKILL.md"

	run "$SCRIPT" --changed --base main --fail-on high --accepted-findings "$policy_file" --output-dir "$REPORT_DIR"

	[ "$status" -eq 1 ]
	[[ "$output" == *"Findings: total=1 accepted=0 enforceable=1"* ]] || false
	[[ "$output" == *"Findings meet --fail-on high threshold"* ]] || false
}

@test "different rule on the same path is not accepted" {
	local policy_file="$TMP_DIR/accepted-findings.json"
	export MOCK_SKILLSPECTOR_JSON='{"issues":[{"severity":"HIGH","id":"E4","location":{"file":"SKILL.md","start_line":1}}]}'
	write_policy "$policy_file" '{
  "accepted_findings": [
    {
      "path": "trackbed/skills/kramme:one/SKILL.md",
      "rule_id": "E5",
      "reason": "Reviewed a different rule only.",
      "owner": "Security",
      "accepted_at": "2026-06-13",
      "expires_at": "2999-01-01"
    }
  ]
}'
	printf 'local edit\n' >>"trackbed/skills/kramme:one/SKILL.md"

	run "$SCRIPT" --changed --base main --fail-on high --accepted-findings "$policy_file" --output-dir "$REPORT_DIR"

	[ "$status" -eq 1 ]
	[[ "$output" == *"Findings: total=1 accepted=0 enforceable=1"* ]] || false
	[[ "$output" == *"Findings meet --fail-on high threshold"* ]] || false
}

@test "accepted finding policy requires review metadata" {
	local policy_file="$TMP_DIR/accepted-findings.json"
	write_policy "$policy_file" '{
  "accepted_findings": [
    {
      "path": "trackbed/skills/kramme:one/SKILL.md",
      "rule_id": "E4",
      "reason": "Missing required owner and expiry metadata.",
      "accepted_at": "2026-06-13"
    }
  ]
}'

	run "$SCRIPT" --all --accepted-findings "$policy_file" --output-dir "$REPORT_DIR"

	[ "$status" -eq 1 ]
	[[ "$output" == *"Accepted-findings policy is invalid"* ]] || false
	[[ "$output" == *"accepted_findings[0].owner is required"* ]] || false
	[[ "$output" == *"accepted_findings[0] requires expires_at or review_after"* ]] || false
	[ "$(count_invocations)" = "0" ]
}

@test "changed scan validates accepted finding policy before no-skill early exit" {
	local policy_file="$TMP_DIR/accepted-findings.json"
	write_policy "$policy_file" 'not json'

	run "$SCRIPT" --changed --base main --accepted-findings "$policy_file" --output-dir "$REPORT_DIR"

	[ "$status" -eq 1 ]
	[[ "$output" == *"Accepted-findings policy is not valid JSON"* ]] || false
	[ "$(count_invocations)" = "0" ]
}

@test "expired accepted finding fails in blocking mode" {
	local policy_file="$TMP_DIR/accepted-findings.json"
	write_policy "$policy_file" '{
  "accepted_findings": [
    {
      "path": "trackbed/skills/kramme:one/SKILL.md",
      "rule_id": "E4",
      "reason": "Expired test exception.",
      "owner": "Security",
      "accepted_at": "2026-06-13",
      "expires_at": "2000-01-01"
    }
  ]
}'

	run "$SCRIPT" --all --fail-on high --accepted-findings "$policy_file" --output-dir "$REPORT_DIR"

	[ "$status" -eq 1 ]
	[[ "$output" == *"Accepted-findings policy contains expired entries"* ]] || false
	[[ "$output" == *"expired accepted finding: trackbed/skills/kramme:one/SKILL.md E4 expired on 2000-01-01"* ]] || false
	[ "$(count_invocations)" = "0" ]
}

@test "expired accepted finding warns in advisory mode and does not accept" {
	local policy_file="$TMP_DIR/accepted-findings.json"
	export MOCK_SKILLSPECTOR_JSON='{"issues":[{"severity":"HIGH","rule_id":"E4","path":"trackbed/skills/kramme:one/SKILL.md"}]}'
	write_policy "$policy_file" '{
  "accepted_findings": [
    {
      "path": "trackbed/skills/kramme:one/SKILL.md",
      "rule_id": "E4",
      "reason": "Expired test exception.",
      "owner": "Security",
      "accepted_at": "2026-06-13",
      "expires_at": "2000-01-01"
    }
  ]
}'

	run "$SCRIPT" --all --accepted-findings "$policy_file" --output-dir "$REPORT_DIR"

	[ "$status" -eq 0 ]
	[[ "$output" == *"WARNING: expired accepted finding: trackbed/skills/kramme:one/SKILL.md E4 expired on 2000-01-01"* ]] || false
	[[ "$output" == *"Findings: total=1 accepted=0 enforceable=1"* ]] || false
}

@test "review_after due accepted finding warns in advisory mode and does not accept" {
	local policy_file="$TMP_DIR/accepted-findings.json"
	export MOCK_SKILLSPECTOR_JSON='{"issues":[{"severity":"HIGH","rule_id":"E4","path":"trackbed/skills/kramme:one/SKILL.md"}]}'
	write_policy "$policy_file" '{
  "accepted_findings": [
    {
      "path": "trackbed/skills/kramme:one/SKILL.md",
      "rule_id": "E4",
      "reason": "Review due test exception.",
      "owner": "Security",
      "accepted_at": "2026-06-13",
      "review_after": "2000-01-01"
    }
  ]
}'

	run "$SCRIPT" --all --accepted-findings "$policy_file" --output-dir "$REPORT_DIR"

	[ "$status" -eq 0 ]
	[[ "$output" == *"WARNING: expired accepted finding: trackbed/skills/kramme:one/SKILL.md E4 expired on 2000-01-01"* ]] || false
	[[ "$output" == *"Findings: total=1 accepted=0 enforceable=1"* ]] || false
}

@test "primary markdown format writes markdown and json reports" {
	run "$SCRIPT" --all --format markdown --output-dir "$REPORT_DIR"

	[ "$status" -eq 0 ]
	[ -f "$REPORT_DIR/kramme_one.json" ]
	[ -f "$REPORT_DIR/kramme_one.md" ]
	grep -q "format=json" "$MOCK_SKILLSPECTOR_LOG"
	grep -q "format=markdown" "$MOCK_SKILLSPECTOR_LOG"
}

mock_discovery_failure() {
	export REAL_GIT
	REAL_GIT=$(command -v git)
	export FAILED_GIT_COMMAND="$1"
	cat >"$BIN_DIR/git" <<'SH'
#!/usr/bin/env bash
if [ "${3:-}" = "$FAILED_GIT_COMMAND" ]; then
  echo "fixture discovery error: $FAILED_GIT_COMMAND" >&2
  exit 42
fi
exec "$REAL_GIT" "$@"
SH
	chmod +x "$BIN_DIR/git"
}

@test "changed scan fails closed when diff discovery fails" {
	mock_discovery_failure diff
	run "$SCRIPT" --changed --base main --output-dir "$REPORT_DIR"
	[ "$status" -ne 0 ]
	[[ "$output" == *"fixture discovery error: diff"* ]] || false
	[[ "$output" == *"Changed-skill discovery failed"* ]] || false
	[[ "$output" != *"No changed skill directories found"* ]] || false
	[ "$(count_invocations)" = 0 ]
}

@test "changed scan fails closed when untracked discovery fails" {
	printf 'edit\n' >>trackbed/skills/kramme:one/SKILL.md
	mock_discovery_failure ls-files
	run "$SCRIPT" --changed --base main --output-dir "$REPORT_DIR"
	[ "$status" -ne 0 ]
	[[ "$output" == *"fixture discovery error: ls-files"* ]] || false
	[[ "$output" == *"Changed-skill discovery failed"* ]] || false
	[[ "$output" != *"No changed skill directories found"* ]] || false
	[ "$(count_invocations)" = 0 ]
}

write_expired_policy() {
	write_policy "$TMP_DIR/expired.json" '{"accepted_findings":[{
    "path":"trackbed/skills/kramme:one/SKILL.md","rule_id":"E4",
    "reason":"Fixture exception","owner":"Security",
    "accepted_at":"1999-01-01","review_after":"2000-01-01"
  }]}'
}

@test "unrelated expired acceptance does not block a changed skill" {
	write_expired_policy
	printf 'edit\n' >>trackbed/skills/kramme:two/SKILL.md
	run "$SCRIPT" --changed --base main --fail-on high --accepted-findings "$TMP_DIR/expired.json" --output-dir "$REPORT_DIR"
	[ "$status" -eq 0 ]
	[ "$(count_invocations)" = 1 ]
	[[ "$output" != *"expired accepted finding"* ]] || false
}

@test "expired acceptance does not block an empty changed set" {
	write_expired_policy
	run "$SCRIPT" --changed --base main --fail-on high --accepted-findings "$TMP_DIR/expired.json" --output-dir "$REPORT_DIR"
	[ "$status" -eq 0 ]
	[[ "$output" == *"No changed skill directories found"* ]] || false
	[ "$(count_invocations)" = 0 ]
}

@test "relevant expired acceptance reports its due date and blocks changed scan" {
	write_expired_policy
	printf 'edit\n' >>trackbed/skills/kramme:one/SKILL.md
	run "$SCRIPT" --changed --base main --fail-on high --accepted-findings "$TMP_DIR/expired.json" --output-dir "$REPORT_DIR"
	[ "$status" -eq 1 ]
	[[ "$output" == *"expired accepted finding: trackbed/skills/kramme:one/SKILL.md E4 expired on 2000-01-01"* ]] || false
	[ "$(count_invocations)" = 0 ]
}

assert_filtered_copy_cleanup() {
	mkdir -p "$TMP_DIR/runner"
	commit_file "trackbed/skills/kramme:one/references/sources-snapshot/upstream.md" "fixture" "add local snapshot"
	run env RUNNER_TEMP="$TMP_DIR/runner" "$SCRIPT" --changed --base main --output-dir "$REPORT_DIR"
	[ "$status" -eq "$1" ]
	[ -z "$(find "$TMP_DIR/runner" -name 'skillspector-scan.*' -print)" ]
	[ -f trackbed/skills/kramme:one/references/sources-snapshot/upstream.md ]
}

@test "filtered scan copy is reclaimed after success" {
	assert_filtered_copy_cleanup 0
	grep -q 'snapshot_exists=no' "$MOCK_SKILLSPECTOR_LOG"
}

@test "filtered scan copy is reclaimed after scanner failure" {
	export MOCK_SKILLSPECTOR_EXIT=2
	export MOCK_SKILLSPECTOR_WRITE_OUTPUT=0
	assert_filtered_copy_cleanup 1
}

@test "filtered scan copy is reclaimed after report evaluation failure" {
	export MOCK_SKILLSPECTOR_JSON='not json'
	assert_filtered_copy_cleanup 5
}

@test "filtered scan copy is reclaimed after copy preparation failure" {
	export REAL_CP
	REAL_CP=$(command -v cp)
	cat >"$BIN_DIR/cp" <<'SH'
#!/usr/bin/env bash
if [ "${1:-}" = -R ]; then
  echo "fixture copy failure" >&2
  exit 42
fi
exec "$REAL_CP" "$@"
SH
	chmod +x "$BIN_DIR/cp"
	assert_filtered_copy_cleanup 42
	[ "$(count_invocations)" = 0 ]
}
