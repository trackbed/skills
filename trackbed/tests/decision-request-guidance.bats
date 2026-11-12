#!/usr/bin/env bats

@test "issue-to-pr and plan-to-pr show every user stop as a shared decision request" {
	run bash -c '
		set -e
		cd "'"$BATS_TEST_DIRNAME"'/.."
		format="shared/implementation/references/decision-request.md"
		issue="skills/linear:issue-to-pr/SKILL.md"
		plan="skills/code:plan-to-pr/SKILL.md"
		guide="docs/shipping.md"
		read_rule="read \`\${CLAUDE_PLUGIN_ROOT}/shared/implementation/references/decision-request.md\` before the first one and follow it."

		# First line, option rule, state line, and what stays out.
		grep -qF "1. **First line:** \`Decision needed · {work-item}: {question}\`." "$format"
		grep -qF "The question is one sentence and ends with a question mark." "$format"
		grep -qF "The recommended option comes first and ends with \`(recommended)\`. Each option says what it causes next" "$format"
		grep -qF "4. **State:** one line that starts with \`State:\`." "$format"
		grep -qF "Leave out the run recap, the work done so far, and notes for reviewing the Pull Request later." "$format"
		grep -qF "Never leave a second decision in a closing paragraph." "$format"
		grep -qF "\`Action needed · {work-item}: {what is needed}\`" "$format"
		grep -qF "A stopped run shows a decision request instead of its success report." "$format"

		# Channel and the no-answer rule.
		grep -qF "Use the host'"'"'s question dialog when it has one and the choice is a few fixed options. Otherwise send a message with the same content." "$format"
		grep -qF "**Header:** a few words that name the decision" "$format"
		grep -qF "A cancelled, dismissed, or unanswered dialog is not an answer. Repeat the request as a message in this format and stop. Never pick an option for the user, including the recommended one." "$format"

		# Exactly one worked example, in the format it defines.
		[ "$(grep -c "^Decision needed · " "$format")" -eq 1 ]
		grep -qF "Decision needed · SKILLS-22: resume review for the open finding, or stop here?" "$format"
		grep -qF "1. Resume review (recommended): starts a new fix budget for this finding," "$format"
		grep -qF "State: nothing pushed, no PR, working tree clean; review archive in .context/linear-issue-to-pr/reviews/." "$format"

		# Both workflows load the shared format and stop with it instead of a success report.
		for skill in "$issue" "$plan"; do
			grep -qF "Show every stop that waits on the user, in this file or a reference it loads, as a decision request: $read_rule" "$skill"
			grep -qF "relay that exact question as a decision request and continue the same agent" "$skill"
		done
		grep -qF "A blocked run shows a decision request, never a Step 5 success template." "$issue"
		grep -qF "A run that stopped on a blocker or a question shows a decision request instead of either template." "$issue"
		! grep -qF "or the workflow stopped on a blocker, replace the success wording" "$issue" || exit 1
		grep -qF "Show each stop below that waits on the user as a decision request." "$issue"
		grep -qF "show its exact blocker as a decision request whose \`State:\` line names the archive" "$issue"
		grep -qF "show the exact \`trackbed:pr:fix-ci\` blocker as a decision request whose \`State:\` line carries the Pull Request URL" "$issue"
		grep -qF "Proceed with implementation and move the issue to {target-status-name}?\` Ask it as a decision request that keeps this question word for word; only its dialog header is short" "$issue"

		grep -qF "A blocked run shows a decision request, never a success completion result." "$plan"
		grep -qF "When the workflow stops, produce the Completion Return Contract below for archive finalization, but show the user a decision request instead of a success result." "$plan"
		! grep -qF "a check is skipped, or the workflow stops." "$plan" || exit 1
		grep -qF "give only the recovery the matching Completion Return Contract item reports, so the archived selected-plan path is a retry option only for \`prepublication_blocked\`." "$plan"
		grep -qF "Completion disposition: success | prepublication_blocked | published_blocked" "$plan"

		# The shipping guide shows what a request looks like.
		grep -qF "## Decision Requests" "$guide"
		grep -qF "A blocked run never reuses the success report." "$guide"
		grep -qF "Decision needed · SKILLS-22: resume review for the open finding, or stop here?" "$guide"
		grep -qF "Cancelling the dialog is not an answer" "$guide"
	'

	[ "$status" -eq 0 ] || { echo "$output"; false; }
}
