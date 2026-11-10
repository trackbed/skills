#!/usr/bin/env bats

RECREATE="skills/git:recreate-commits/SKILL.md"

setup() {
	cd "$BATS_TEST_DIRNAME/.."
}

line_of() {
	grep -nF -- "$1" "$RECREATE" | head -1 | cut -d: -f1
}

# Claude Code re-attaches only the first 5,000 tokens of an invoked skill after
# compaction; 12,000 bytes stays well inside that budget.
assert_in_retained_prefix() {
	local offset
	offset=$(python3 -c 'import sys; print(open(sys.argv[1], "rb").read().find(sys.argv[2].encode()))' "$RECREATE" "$1")
	[ "$offset" -ge 0 ]
	[ "$offset" -lt 12000 ]
}

@test "recreate-commits parses its arguments in one explicit step before Step 1" {
	[ "$(grep -cF '$ARGUMENTS' "$RECREATE")" -eq 1 ]
	grep -qxF '**Arguments:** "$ARGUMENTS"' "$RECREATE"
	grep -qF "Before Step 1, parse the arguments above once as shell-style tokens" "$RECREATE"
	grep -qF "Stop before Step 1 and name the offending token on an unknown flag, a duplicate flag, a valued flag whose value is missing or starts with \`--\`, a positional token, or \`--coarse\` combined with \`--granular\`." "$RECREATE"
	grep -qF "Every later step reads its flags from this line. An \`unset\` value leaves the matching Step 1 shell variable empty." "$RECREATE"
	grep -qF "writing \`unset\` for an absent value and \`AUTO_MODE=false\` for \`--manual\` or any invocation the Model Invocation Contract runs as \`--manual\`" "$RECREATE"
	grep -qxF 'PARSED ARGS: AUTO_MODE=<true|false> GRANULARITY=<unpinned|coarse|atomic> BASE_FLAG=<branch|unset> BASE_COMMIT_FLAG=<oid|unset> BACKUP_REF_FLAG=<branch|unset> AFTER_ARG=<commit|unset> FORCE_BACKUP=<0|1> REQUIRE_UNSTACKED=<true|false> NO_PUSH=<true|false> AUTHORIZE_HISTORY_REWRITE=<true|false>' "$RECREATE"

	parse_line=$(line_of "### Parse Arguments")
	steps_line=$(line_of "## Steps")
	[ "$parse_line" -lt "$steps_line" ]
	assert_in_retained_prefix '**Arguments:** "$ARGUMENTS"'
	assert_in_retained_prefix "PARSED ARGS: AUTO_MODE="

	parse_section=$(awk '/^### Parse Arguments$/{found=1; next} found && /^## /{exit} found' "$RECREATE")
	hint=$(sed -n 's/^argument-hint: //p' "$RECREATE")
	flags=$(grep -oE -- '--[a-z-]+' <<<"$hint" | sort -u)
	[ -n "$flags" ]
	while IFS= read -r flag; do
		[[ "$parse_section" == *"\`$flag\`"* || "$parse_section" == *"\`$flag "* ]] || {
			echo "Parse Arguments does not handle $flag" >&2
			return 1
		}
	done <<<"$flags"
	[[ "$parse_section" == *"Ignore a leftover \`--auto\`."* ]] || false

	! grep -qF "If \`--coarse\` was combined with \`--granular\`, stop" "$RECREATE"
}

@test "recreate-commits resumes a compacted run without rerunning Step 1" {
	resume_line=$(line_of "### Resume After Compaction")
	contract_line=$(line_of "### Model Invocation Contract")
	parse_line=$(line_of "### Parse Arguments")
	[ "$contract_line" -lt "$resume_line" ]
	[ "$resume_line" -lt "$parse_line" ]
	assert_in_retained_prefix "### Resume After Compaction"
	assert_in_retained_prefix "Never rerun Step 1 after it succeeded"

	grep -qF 'Re-read this skill in full from `${CLAUDE_PLUGIN_ROOT}/skills/git:recreate-commits/SKILL.md`' "$RECREATE"
	grep -qF "Take the flags from the earlier \`PARSED ARGS:\` line, never by parsing the file again" "$RECREATE"
	grep -qF 'It also leaves `${CLAUDE_PLUGIN_ROOT}` unsubstituted, so replace that placeholder with the plugin root shown in the path above' "$RECREATE"
	grep -qF 'During the rebuild, compare `git log --oneline "$RESET_POINT..HEAD"` with the plan to find the next planned commit.' "$RECREATE"
	grep -qF 'If `ORIGINAL_TIP` was lost, read it from the recovery backup with `git rev-parse --verify "refs/heads/$BACKUP_REF^{commit}"`' "$RECREATE"
	grep -qF '`BACKUP_REF` is `<ORIGINAL_BRANCH>-recreate-backup`' "$RECREATE"
	grep -qF "Continue the step that was in progress." "$RECREATE"
	grep -qF "Never rerun Step 1 after it succeeded" "$RECREATE"
	grep -qF "Recover the Step 1 assignments, the selected granularity, and the \`PLAN\` storyline" "$RECREATE"
	grep -qF "If the \`PARSED ARGS:\` line, the selected granularity, or another Step 1 value cannot be recovered" "$RECREATE"
	grep -qF 'stop and report `git reset --hard "$BACKUP_REF"` as the recovery' "$RECREATE"
	grep -qF 'BACKUP_REF="${ORIGINAL_BRANCH}-recreate-backup"' scripts/resolve-base.sh
}

@test "recreate-commits checks each rebuilt commit against its plan" {
	grep -qF "Before each commit, compare the staged change with that commit's planned summary" "$RECREATE"
	grep -qF "unstage every hunk that belongs to another planned commit and drop it from the working tree with \`git restore --staged --worktree --source=HEAD -p -- <path>\`" "$RECREATE"
	grep -qF "Skip that run during this replay unless the user asks for it" "$RECREATE"
	grep -qF "Never keep edits such a run makes" "$RECREATE"
	grep -qF "The Step 5 rule that skips a pre-commit \`verify\` or \`simplify\` run applies to this commit too." "$RECREATE"
	grep -qF "Commit-time hooks that auto-fix files can rewrite staged content." "$RECREATE"
	grep -qF "every path the commit completes to match \`\$ORIGINAL_TIP\` (\`git diff --quiet \"\$ORIGINAL_TIP\" HEAD -- <paths>\`)" "$RECREATE"
	grep -qF "amend the commit once; if a hook rewrites it again, treat that as a hook failure under Step 6." "$RECREATE"

	check_line=$(line_of "Before each commit, compare the staged change")
	reset_line=$(line_of 'git reset --hard "$RESET_POINT"')
	identity_line=$(line_of 'git diff "$ORIGINAL_TIP" HEAD')
	[ "$reset_line" -lt "$check_line" ]
	[ "$check_line" -lt "$identity_line" ]
}

@test "recreate-commits keeps coarse and medium commits building" {
	grep -qF "At coarse and medium granularity, order the storyline so every commit builds: put definitions before their uses, and configuration before the code that reads it." "$RECREATE"
	grep -qF "Fine and atomic granularity may keep intermediate commits that do not build." "$RECREATE"
	grep -qF "At fine and atomic granularity only, an intermediate commit may fail to build, and \`git commit --no-verify\`" "$RECREATE"
	grep -qF "to get past such a known-failing state or a hook that keeps rewriting a planned commit." "$RECREATE"
	grep -qF "At coarse and medium granularity, never use \`--no-verify\`: when a commit-time hook fails or keeps rewriting a planned commit, reorder or merge the planned commits until each one passes. If no order does, stop and report the failing hook, the planned commit it rejected, and \`git reset --hard \"\$BACKUP_REF\"\` as the recovery." "$RECREATE"
	grep -qF "at fine and atomic granularity intermediate commits not building is tolerable, a wrong end state never is." "$RECREATE"
	grep -qF "\`POTENTIAL CONCERNS\` names every commit known or suspected not to build, by short SHA and subject, at any granularity." "$RECREATE"
	grep -qF "commits known or suspected not to build, planned commits merged or reordered because of a hook;" "$RECREATE"
	! grep -qF "Individual commits need not pass tests" "$RECREATE" || false

	order_line=$(line_of "**Build order.**")
	rebuild_line=$(line_of "5. **Reimplement the work**")
	[ "$order_line" -lt "$rebuild_line" ]
}

@test "recreate-commits credits the Addy source only for what it supplies" {
	local sources="skills/git:recreate-commits/references/sources.yaml"

	addy=$(awk '/- id: addy-git-workflow-versioning/{found=1} found && /rationale:/{print; exit}' "$sources")
	[[ "$addy" == *"save-point view of commits"* ]] || false
	[[ "$addy" != *"attribution"* ]] || false
	grep -qF "Never add AI attribution to any commit subject or body." "$RECREATE"
}
