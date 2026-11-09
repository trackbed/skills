#!/usr/bin/env bats

@test "feature spec template preserves raw marker prefixes" {
	run bash -c '
    cd "'"$BATS_TEST_DIRNAME"'/.."
    template="skills/docs:feature-spec/assets/feature-spec-template.md"

    grep -q -- "^- POTENTIAL CONCERNS:" "$template" ||
      { echo "missing raw POTENTIAL CONCERNS marker"; exit 1; }

    if grep -q -- "^- \`POTENTIAL CONCERNS:\`" "$template"; then
      echo "template backticks the POTENTIAL CONCERNS marker"
      exit 1
    fi
  '

	[ "$status" -eq 0 ]
}

@test "agent-instruction rules route to the user-run update-agents-md command" {
	run bash -c '
    set -e
    cd "'"$BATS_TEST_DIRNAME"'/.."
    skill="skills/docs:update-agents-md/SKILL.md"
    frontmatter="$(awk "/^---\$/{n++; next} n==1" "$skill")"

    grep -qx "disable-model-invocation: true" <<<"$frontmatter" ||
      { echo "update-agents-md must be model-disabled"; exit 1; }
    grep -qx "user-invocable: true" <<<"$frontmatter" ||
      { echo "update-agents-md must appear in the slash menu"; exit 1; }

    for route in skills/docs:feature-spec/SKILL.md skills/docs:adr/SKILL.md; do
      grep -qF "/trackbed:docs:update-agents-md" "$route" ||
        { echo "$route no longer routes to /trackbed:docs:update-agents-md"; exit 1; }
    done
  '

	[ "$status" -eq 0 ] || { echo "$output"; false; }
}

@test "feature spec keeps rejected approaches inside its six areas" {
  run bash -c '
    set -euo pipefail
    cd "'"$BATS_TEST_DIRNAME"'/.."
    skill="skills/docs:feature-spec/SKILL.md"
    template="skills/docs:feature-spec/assets/feature-spec-template.md"

    scope=$(grep -nxF "## 2. Scope & Non-goals" "$template" | cut -d: -f1)
    rejected=$(grep -nxF "### Rejected approaches" "$template" | cut -d: -f1)
    boundaries=$(grep -nxF "## 3. Boundaries" "$template" | cut -d: -f1)
    [ "$scope" -lt "$rejected" ]
    [ "$rejected" -lt "$boundaries" ]
    [ "$(grep -cE "^## [0-9]+\\. " "$template")" -eq 6 ]

    grep -qF "Omit this subsection when no real alternative was weighed." "$template"
    grep -qF "Do not invent alternatives to fill the subsection" "$skill"
    grep -qF "Copy the six-area structure" "$skill"
    grep -qF "Rejected approaches: <count>" "$skill"
  '

  [ "$status" -eq 0 ] || { echo "$output"; false; }
}

@test "feature spec ends the turn after the draft and takes approval only from a later reply" {
	run bash -c '
    set -euo pipefail
    cd "'"$BATS_TEST_DIRNAME"'/.."
    skill="skills/docs:feature-spec/SKILL.md"

    grep -qF "End the turn after the \`PLAN:\` block, in every mode." "$skill"
    grep -qF "The turn still ends after the draft, and the Phase 3 approval gate stays" "$skill"
    grep -qF "Approval counts only from a user reply after the draft." "$skill"
    grep -qF "A request that asked for the spec and the build together" "$skill"
  '

	[ "$status" -eq 0 ] || { echo "$output"; false; }
}

@test "feature spec reads a named plan as its origin and never writes into it or STRATEGY.md" {
	run bash -c '
    set -euo pipefail
    cd "'"$BATS_TEST_DIRNAME"'/.."
    skill="skills/docs:feature-spec/SKILL.md"
    template="skills/docs:feature-spec/assets/feature-spec-template.md"
    routing="skills/code:work-from-plan/references/routing.md"

    grep -qxF "## Origin documents" "$skill"
    grep -qF "Write a new spec at the Phase 2 destination and never edit, overwrite, or move the origin." "$skill"
    grep -qF "it is the spec under revision, not an origin" "$skill"
    grep -qF "A path argument that names an existing document is an origin (see Origin documents), not a destination." "$skill"
    grep -qF "\`trackbed:docs:feature-spec <plan-path>\`" "$routing"
    grep -qF "could be either the origin or the file to revise" "$skill"
    grep -qF "decisions and the options they beat, success criteria, and open questions" "$skill"
    grep -qF "Reject reserved destinations: \`AGENTS.md\`, \`CLAUDE.md\`, the repository'"'"'s \`STRATEGY.md\`, the origin document" "$skill"
    grep -qF "is strategy context for Phase 0, never an origin or a destination" "$skill"
    grep -q "^Origin: <" "$template"
  '

	[ "$status" -eq 0 ] || { echo "$output"; false; }
}

@test "feature spec credits rejections to the user and tests each flagged interface" {
	run bash -c '
    set -euo pipefail
    cd "'"$BATS_TEST_DIRNAME"'/.."
    skill="skills/docs:feature-spec/SKILL.md"
    template="skills/docs:feature-spec/assets/feature-spec-template.md"

    grep -qF "A rejection is the user'"'"'s call by default" "$skill"
    grep -qF "linked issue, PR, or decision record names them" "$skill"
    grep -qF "rejected by <the user, unless" "$template"
    grep -qF "Testing Strategy names the behavior that tests verify through that module'"'"'s interface" "$skill"
    grep -qF "name the behavior that tests verify through that module'"'"'s interface" "$template"
  '

	[ "$status" -eq 0 ] || { echo "$output"; false; }
}
