#!/usr/bin/env bats

setup() {
	cd "$BATS_TEST_DIRNAME/.."
	SKILL="skills/docs:track-rejected-enhancements/SKILL.md"
}

section() {
	awk -v start="$1" '
		$0 == start { in_section = 1; next }
		in_section && /^##+ / { exit }
		in_section { print }
	' "$SKILL"
}

@test "track-rejected-enhancements finds a reworded record by similarity before acting" {
	grep -qF '## Find an existing record' "$SKILL"
	grep -qF 'One concept keeps one record, however the request is worded.' "$SKILL"
	grep -qF 'list its filenames and apply the same similarity judgment as `check` step 3' "$SKILL"
	grep -qF 'If more than one record plausibly matches, list them and let the user pick one or none' "$SKILL"
	grep -qF 'The pick is the user'"'"'s choice, so the subcommand does not ask about that record again.' "$SKILL"
	grep -qF 'Never act on a similar match without the user'"'"'s explicit choice; a declined match counts as no record.' "$SKILL"

	section '### `record <concept>`' | grep -qF 'Slug the concept and run **Find an existing record**.'
	section '### `append <concept> <issue-ref>`' | grep -qF 'Slug the concept and run **Find an existing record**.'
	section '### `reconsider <concept>`' | grep -qF 'Slug the concept and run **Find an existing record**.'

	find_line=$(grep -nxF '## Find an existing record' "$SKILL" | cut -d: -f1)
	subcommands_line=$(grep -nxF '## Subcommands' "$SKILL" | cut -d: -f1)
	[ "$find_line" -lt "$subcommands_line" ]
}

@test "track-rejected-enhancements record offers a similar record before creating a file" {
	record=$(section '### `record <concept>`')
	grep -qF 'If only a similar record exists, offer it before creating a new file.' <<<"$record"
	grep -qF -- '- "Append to the existing record"' <<<"$record"
	grep -qF -- '- "Record a separate concept"' <<<"$record"
	grep -qF 'On cancel, stop without writing.' <<<"$record"
	grep -qF 'On append, continue with `append` from its duplicate-reference step' <<<"$record"

	offer=$(grep -nF 'offer it before creating a new file' <<<"$record" | cut -d: -f1)
	write=$(grep -nF 'Render and write `.out-of-scope/<slug>.md`' <<<"$record" | cut -d: -f1)
	[ "$offer" -lt "$write" ]
}

@test "track-rejected-enhancements append and reconsider act on the similar record" {
	append=$(section '### `append <concept> <issue-ref>`')
	grep -qF 'If only a similar record exists and the user has not already picked it, surface it' <<<"$append"
	grep -qF 'wait for an explicit yes before continuing against that file.' <<<"$append"
	grep -qF 'appended <issue-ref> to .out-of-scope/<record>.md' <<<"$append"

	reconsider=$(section '### `reconsider <concept>`')
	grep -qF 'say that it was found by similarity rather than by exact slug' <<<"$reconsider"
	grep -qF 'question: "Remove `.out-of-scope/<record>.md`? Future sessions will no longer surface it."' <<<"$reconsider"
	grep -qF 'removed .out-of-scope/<record>.md' <<<"$reconsider"
}

@test "track-rejected-enhancements never records a feature that already exists" {
	grep -qF -- '- **Already implemented** → point the requester to where the feature lives. Never record it' "$SKILL"
	record=$(section '### `record <concept>`')
	grep -qF -- '- "Feature already exists — cancel"' <<<"$record"
	grep -qF 'If the feature already exists, stop without writing' <<<"$record"
}

@test "track-rejected-enhancements file format says check matches filenames first" {
	grep -qF 'match on filenames first and read a file'"'"'s heading and body only for a plausible match' "$SKILL"
	! grep -qF '`check` matches against it.' "$SKILL" || false
	! grep -qF '`check` looks up files by slug and first-heading match' "$SKILL" || false
}
