#!/usr/bin/env bats

@test "the shared final report puts the outcome and attention items before the narrative and status block" {
	run bash -c '
		set -e
		cd "'"$BATS_TEST_DIRNAME"'/.."
		format="shared/implementation/references/final-report.md"

		# Order: outcome, attention, what was done, what review uncovered, status block last.
		outcome=$(grep -nF "1. **Outcome:**" "$format" | cut -d: -f1)
		attention=$(grep -nF "2. **Needs your attention:**" "$format" | cut -d: -f1)
		done_part=$(grep -nF "3. **What was done:**" "$format" | cut -d: -f1)
		review=$(grep -nF "4. **What review uncovered:**" "$format" | cut -d: -f1)
		status_block=$(grep -nF "5. **Status block:**" "$format" | cut -d: -f1)
		[ "$outcome" -lt "$attention" ]
		[ "$attention" -lt "$done_part" ]
		[ "$done_part" -lt "$review" ]
		[ "$review" -lt "$status_block" ]
		grep -qF "Include the Pull Request link when one exists" "$format"
		grep -qF "with its field names unchanged, because later steps and tools read them" "$format"
		grep -qF "It does not shorten the report: every fact the workflow reports keeps a place." "$format"
		grep -qF "A stopped run shows a decision request instead." "$format"

		# Attention sources, item wording, and the empty case.
		grep -qF "questions the issue or plan left open;" "$format"
		grep -qF "choices the workflow made on its own that the user may want to change;" "$format"
		grep -qF "things the workflow could not verify;" "$format"
		grep -qF "judgment calls, risk areas, and advisory notes that review surfaced;" "$format"
		grep -qF "Open with the outcome sentence, unlabeled" "$format"
		grep -qF "Start each item with what to check or decide" "$format"
		grep -qF "End with a suggested answer when the workflow has one" "$format"
		grep -qF "When nothing qualifies, say so in one line instead of leaving the part out" "$format"
		grep -qF "never claim one that is not true" "$format"

		# The example follows the order it defines.
		ex_attention=$(grep -nFx "**Needs your attention**" "$format" | cut -d: -f1)
		ex_done=$(grep -nFx "**What was done**" "$format" | cut -d: -f1)
		ex_review=$(grep -nFx "**What review uncovered**" "$format" | cut -d: -f1)
		ex_status=$(grep -nF "Pull Request: https://github.com/org/repo/pull/123" "$format" | cut -d: -f1)
		[ "$ex_attention" -lt "$ex_done" ]
		[ "$ex_done" -lt "$ex_review" ]
		[ "$ex_review" -lt "$ex_status" ]
	'

	[ "$status" -eq 0 ] || { echo "$output"; false; }
}

@test "issue-to-pr and plan-to-pr load the shared final report and end with their status blocks" {
	run bash -c '
		set -e
		cd "'"$BATS_TEST_DIRNAME"'/.."
		issue="skills/linear:issue-to-pr/SKILL.md"
		plan="skills/code:plan-to-pr/SKILL.md"
		plan_shipping="skills/code:plan-to-pr/references/shipping-contract.md"
		guide="docs/shipping.md"
		read_rule="read \`\${CLAUDE_PLUGIN_ROOT}/shared/implementation/references/final-report.md\` and follow it."

		grep -qiF "$read_rule" "$issue"
		grep -qiF "$read_rule" "$plan"

		# issue-to-pr: four prose parts in order, then the status block.
		step5=$(sed -n "/^## Step 5: Report the Outcome$/,/^## Artifact Lifecycle$/p" "$issue")
		printf "%s\n" "$step5" | grep -qF "post them with the status block for this result last, as one message."
		printf "%s\n" "$step5" | grep -qF "For a review-ready result without \`--ship\`, end the report with:"
		printf "%s\n" "$step5" | grep -qF "For a shipped result, end the report with:"
		sections=$(printf "%s\n" "$step5" | sed -n "/^### Report Sections$/,/^### Clarity Pass$/p")
		o=$(printf "%s\n" "$sections" | grep -nF -- "- **Outcome**" | cut -d: -f1)
		a=$(printf "%s\n" "$sections" | grep -nF -- "- **Needs your attention**" | cut -d: -f1)
		d=$(printf "%s\n" "$sections" | grep -nF -- "- **What was done**" | cut -d: -f1)
		r=$(printf "%s\n" "$sections" | grep -nF -- "- **What review uncovered**" | cut -d: -f1)
		[ "$o" -lt "$a" ]
		[ "$a" -lt "$d" ]
		[ "$d" -lt "$r" ]
		printf "%s\n" "$sections" | grep -qF "decisions this workflow made autonomously that the issue did not settle"
		printf "%s\n" "$step5" | grep -qF "list it under **Needs your attention** as well"

		# The clarity pass stays and the workflow continues after it.
		printf "%s\n" "$step5" | grep -qF "raw text to \`trackbed:text:clarify\`"
		printf "%s\n" "$step5" | grep -qF "the rewrite is one step of this workflow, which continues after it"
		printf "%s\n" "$step5" | grep -qF "The clarify output is input to this report, not the report itself."
		printf "%s\n" "$step5" | grep -qF "never end the turn on the rewrite alone"
		! grep -qF "What to focus on in review" "$issue" || exit 1

		# plan-to-pr: same order; the completion result stays intact for archive finalization.
		step7=$(sed -n "/^## Step 7: Report$/,/^## Error Handling$/p" "$plan")
		o=$(printf "%s\n" "$step7" | grep -nF -- "- **Outcome**" | cut -d: -f1)
		a=$(printf "%s\n" "$step7" | grep -nF -- "- **Needs your attention**" | cut -d: -f1)
		d=$(printf "%s\n" "$step7" | grep -nF -- "- **What was done**" | cut -d: -f1)
		r=$(printf "%s\n" "$step7" | grep -nF -- "- **What review uncovered**" | cut -d: -f1)
		s=$(printf "%s\n" "$step7" | grep -nF "End with the shared completion result from Step 6, its field names unchanged because archive finalization and usage tooling read them" | cut -d: -f1)
		[ "$o" -lt "$a" ]
		[ "$a" -lt "$d" ]
		[ "$d" -lt "$r" ]
		[ "$r" -lt "$s" ]
		printf "%s\n" "$step7" | grep -qF "each assumption from the implementation closeout'"'"'s \`ASSUMPTIONS\` list as a choice to confirm (on a completion resume, that none were recorded)"
		grep -qF "JSON-decode its \`Reviewer handoff JSON\` field, require exactly \`gut_check\`, \`findings\`, and \`focus\` arrays" "$plan"
		grep -qF "retain it as the only source for the Step 7 review sections" "$plan"
		grep -qF "as the source for the Step 7 report'"'"'s review sections" "$plan_shipping"
		! grep -qF "this workflow does not summarize it" "$plan_shipping" || exit 1

		# The shipping guide describes the order.
		grep -qF "## Final Reports" "$guide"
		grep -qF "its report puts what needs you first" "$guide"
	'

	[ "$status" -eq 0 ] || { echo "$output"; false; }
}
