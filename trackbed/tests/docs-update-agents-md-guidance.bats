#!/usr/bin/env bats

setup() {
	cd "$BATS_TEST_DIRNAME/.."
	SKILL="skills/docs:update-agents-md/SKILL.md"
	SOURCES="skills/docs:update-agents-md/references/sources.yaml"
}

@test "update-agents-md verifies cited pointers before writing them" {
	grep -qF '## Verify Pointers' "$SKILL"
	grep -qF 'Run **Verify Pointers** below first, so the plan cites only pointers that exist.' "$SKILL"
	grep -qF 'check every path, script, command, and skill name an authored rule cites' "$SKILL"
	grep -qF 'find the package script, make target, or task-runner entry that defines it' "$SKILL"
	grep -qF 'confirm its fixed parent exists' "$SKILL"
	grep -qF 'Never write a rule that cites a pointer that failed the check.' "$SKILL"
	grep -qF 'List every fixed or dropped pointer in the plan and the final report.' "$SKILL"

	verify=$(grep -nxF '## Verify Pointers' "$SKILL" | cut -d: -f1)
	after=$(grep -nxF '## After Writing' "$SKILL" | cut -d: -f1)
	[ "$verify" -lt "$after" ]
}

@test "update-agents-md edits AGENTS.md alone when CLAUDE.md only imports it" {
	grep -qF 'only imports, links, or symlinks `AGENTS.md` (for example a lone `@AGENTS.md` line), edit `AGENTS.md` alone and leave the importing file untouched' "$SKILL"
	grep -qF 'do not write the new rules into both; edit `AGENTS.md` and report the separate copy' "$SKILL"
	! grep -qF 'mirror rules into the others' "$SKILL" || false
}

@test "update-agents-md omits installed-skill lists and tool-enforced rules" {
	grep -qF 'Do not add a list of installed skills' "$SKILL"
	grep -qF 'Add a skill pointer only when the rule gives a trigger or requirement the skill'"'"'s own description lacks.' "$SKILL"
	grep -qF -- '- Lists of installed skills or plugins, which the host already shows' "$SKILL"
	grep -qF -- '- Rules that configured lint, format, or type checks already enforce' "$SKILL"
	! grep -qF 'Reference each discovered skill' "$SKILL" || false
	! grep -qF 'Guides discovery of local skills' "$SKILL" || false
}

@test "update-agents-md routes structural rules to encode-constraint or refactor-opportunities" {
	grep -qF 'or `/trackbed:code:refactor-opportunities` to assess the refactor' "$SKILL"
}

@test "update-agents-md examples start each rule with a guideline keyword" {
	package=$(awk '/^### Package Manager$/{f=1; next} /^### /{f=0} f' "$SKILL")
	skills=$(awk '/^### Skill Pointers$/{f=1; next} /^### /{f=0} f' "$SKILL")
	grep -qF -- '- **ALWAYS** use **pnpm**' <<<"$package"
	grep -qF -- '- **ALWAYS** use `.claude/skills/db-migrate/SKILL.md`' <<<"$skills"
	! grep -qE '^(Use |- Use )' <<<"$package"$'\n'"$skills" || false
}

@test "update-agents-md credits the getsentry skill file, not its skills.sh listing" {
	entry=$(awk '/id: getsentry-agents-md-skill/{f=1} f&&/^  - id: /&&!/getsentry/{f=0} f' "$SOURCES")
	grep -qF 'url: https://raw.githubusercontent.com/getsentry/skills/main/skills/agents-md/SKILL.md' <<<"$entry"
	grep -qF 'baseline_commit: "e94f22214528d69899d09c627b3315ddc3544816"' <<<"$entry"
	! grep -qF 'skills.sh' "$SOURCES" || false
	! grep -qiE 'skill discovery|guideline keyword' <<<"$entry" || false
}
