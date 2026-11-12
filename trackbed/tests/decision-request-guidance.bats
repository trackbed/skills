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
		grep -qF "1. Resume review (recommended): starts a new fix budget of up to 2 cycles" "$format"
		grep -qF "2. Stop here (0 cycles): the branch stays local for you to finish by hand." "$format"
		grep -qF "State: nothing pushed, no PR, working tree clean; review archive in .context/linear-issue-to-pr/reviews/." "$format"

		# Both workflows load the shared format and stop with it instead of a success report.
		for skill in "$issue" "$plan"; do
			grep -qF "Show every stop that waits on the user, in this file or a reference it loads, as a decision request: $read_rule" "$skill"
			grep -qF "On either path, when a blocked handoff carries a \`Decision request\`, show that request to the user unchanged, adding only the \`State:\` line this workflow owns." "$skill"
			grep -qF "When the answer resumes review, continue the same run with it, in the same delegated agent when there is one, instead of starting a new invocation; any other answer ends the run on the blocked handoff it already returned." "$skill"
			grep -qF "Ask each review question once, here: later stop and report steps report its answer and never ask it again, and a resumed run'"'"'s new blocked handoff is relayed the same way." "$skill"
			grep -qF "When a blocked handoff returns \`Decision request: none\`, build the decision request from its exact blocker, unless it lists at least one open item and the user already declined each of them; then report those declines with the \`State:\` line." "$skill"
			! grep -qF "relay that exact question as a decision request" "$skill" || exit 1
		done
		grep -qF "A blocked run shows a decision request, never a Step 5 success template." "$issue"
		grep -qF "A run that stopped on a blocker or a question shows a decision request instead of either template." "$issue"
		! grep -qF "or the workflow stopped on a blocker, replace the success wording" "$issue" || exit 1
		grep -qF "Show each stop below that waits on the user as a decision request." "$issue"
		grep -qF "Ask its review question only as Step 3 describes, with a \`State:\` line that names the archive; after an answer that ends the run, report that choice and the \`State:\` line without asking again." "$issue"
		grep -qF "show the exact \`trackbed:pr:fix-ci\` blocker as a decision request whose \`State:\` line carries the Pull Request URL" "$issue"
		grep -qF "Proceed with implementation and move the issue to {target-status-name}?\` Ask it as a decision request that keeps this question word for word; only its dialog header is short" "$issue"

		grep -qF "A blocked run shows a decision request, never a success completion result." "$plan"
		grep -qF "When review convergence stopped the run, ask its review question only as Step 6 describes; after an answer that ends the run, report that choice with the recovery above and do not ask again." "$plan"
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

@test "implementation questions reach the user as one decision request with options and a recommendation" {
	run bash -c '
		set -e
		cd "'"$BATS_TEST_DIRNAME"'/.."
		implement="skills/linear:issue-implement/SKILL.md"
		examples="skills/linear:issue-implement/references/question-examples.md"
		work="skills/code:work-from-plan/SKILL.md"
		plan="skills/code:plan-to-pr/SKILL.md"
		guide="docs/shipping.md"
		read_format="read \`\${CLAUDE_PLUGIN_ROOT}/shared/implementation/references/decision-request.md\`"

		# issue-implement collects blocking questions and asks them all at once in the shared format.
		step=$(sed -n "/^### 5.2 Ask Clarifying Questions$/,/^### 5.3 /p" "$implement")
		printf "%s\n" "$step" | grep -qF "Collect every question that blocks implementation before asking any of them."
		printf "%s\n" "$step" | grep -qF "Ask the remaining questions together in one decision request: $read_format and follow it for this request, with the issue identifier as the work item."
		printf "%s\n" "$step" | grep -qF "with the recommended option first and marked \`(recommended)\`"
		printf "%s\n" "$step" | grep -qF "In the host'"'"'s question dialog, send every question in one call"
		printf "%s\n" "$step" | grep -qF "Never wait for one answer before asking the next question."
		! printf "%s\n" "$step" | grep -qF "Use AskUserQuestion for each unclear aspect" || exit 1

		# The --auto default rule is unchanged.
		printf "%s\n" "$step" | grep -qF "In \`AUTO_MODE\`, first choose conservative defaults when the codebase and issue text clearly support them"
		printf "%s\n" "$step" | grep -qF "If an ambiguity would change product scope, data model, security posture, public API, or user-visible behavior, ask even in \`AUTO_MODE\`."

		# Out of scope: the approach selection and the Linear state gate keep their wording.
		grep -qF "question: \"How would you like to proceed with implementing this issue?\"" "$implement"
		grep -qF "this exact question: \`Proceed with implementation and move the issue to {target-status-name}?\`" skills/linear:issue-implement/references/status-transition.md

		# The example request numbers three decisions, puts a recommended option first in each, and closes with one State line.
		[ "$(grep -c "^Decision [0-9] of 3 · {issue-id}: " "$examples")" -eq 3 ]
		[ "$(grep -c "^1\. .* (recommended): " "$examples")" -eq 3 ]
		[ "$(grep -c "^State: " "$examples")" -eq 1 ]

		# work-from-plan returns its question in the format; plan-to-pr relays it unchanged.
		grep -qF "Write the question in the shared decision-request format: $read_format first." "$work"
		grep -qF "numbered options that say what each one causes, the recommended option first and ending with \`(recommended)\`" "$work"
		grep -qF "Leave out the work item and the \`State:\` line; the parent adds them." "$work"
		grep -qF "Keep its question, evidence, and options unchanged; only put \`Decision needed · {execution-label}: \` before the question and add the \`State:\` line." "$plan"

		grep -qF "Questions raised during implementation use the same format." "$guide"
	'

	[ "$status" -eq 0 ] || { echo "$output"; false; }
}

@test "review convergence hands back a ready decision request when it stops for the user" {
	run bash -c '
		set -e
		cd "'"$BATS_TEST_DIRNAME"'/.."
		format="shared/implementation/references/decision-request.md"
		skill="skills/pr:review-convergence/SKILL.md"
		policy="skills/pr:review-convergence/references/review-convergence.md"
		guide="docs/shipping.md"
		review_guide="docs/review.md"

		# The request is the last field of the handoff template, after the field it is built from.
		request=$(grep -nF "Decision request: {none | follows}" "$skill" | cut -d: -f1)
		body=$(grep -nF "{only after \`follows\`: the decision request, from its first line through its last option, with no \`State:\` line}" "$skill" | cut -d: -f1)
		[ "$body" -eq $((request + 1)) ]
		[ "$(sed -n "$((body + 1))p" "$skill")" = "\`\`\`" ]
		grep -qF -- "- Required unresolved: {none | gate + summary + why unresolved + smallest next decision or dependency}" "$skill"
		grep -qF "after reading \`\${CLAUDE_PLUGIN_ROOT}/shared/implementation/references/decision-request.md\`, the shared format." "$skill"
		grep -qF "A caller shows it to the user unchanged and adds only the \`State:\` line it owns." "$skill"
		grep -qF "In direct user mode, show the same request yourself, with a \`State:\` line that says review pushed nothing, names \`{work-branch}\` and whether the worktree is clean, and names \`{review-archive}\`, then wait for the answer." "$skill"
		grep -qF "then wait for the answer. When the answer resumes review, return the resumed run'"'"'s handoff; otherwise, including a dismissed or unanswered request, print this handoff with the request as its last field, followed by its \`State:\` line, before stopping." "$skill"
		grep -qF "stop with paths or commits and return a \`Decision request\` that asks the user to resolve ownership." "$skill"

		# When the request is built, how findings are grouped, and what each option says.
		grep -qF "## Decision Request" "$policy"
		grep -qF "Every question this policy asks the user about an open finding or Gut Check item reaches them through the handoff'"'"'s \`Decision request\` field" "$policy"
		grep -qF "a finding whose final disposition is \`required_unresolved\` or \`blocked\`, or a Gut Check item whose final disposition is \`blocked\`, that the user has not already declined in an earlier request. Otherwise return \`Decision request: none\`." "$policy"
		grep -qF "Validation-only mode always returns \`none\`" "$policy"
		grep -qF "Each open item'"'"'s \`next_decision_or_dependency\` and \`attempted_fix_evidence\` are its raw material." "$policy"
		grep -qF "Put open items that one answer settles into one decision" "$policy"
		grep -qF "Give an item its own decision when it needs its own product, scope, public-contract, security, or external-access choice." "$policy"
		grep -qF "Each open item appears in exactly one decision, never in two and never left out." "$policy"
		grep -qF "**Work item:** \`{work-id}\`, or \`{work-branch}\` in a direct run without a tracker issue." "$policy"
		! grep -qF "Decision needed · {work-id}" "$policy" || exit 1
		grep -qF "Number several decisions as the shared format'"'"'s Several Decisions section shows." "$policy"
		grep -qF "When the run ended at a bounded stop or with no cycles left, resuming starts a new budget of up to \`MAX_AUTOMATIC_REMEDIATION_CYCLES\` cycles for the covered items, under the Bounded Stop rule; otherwise resuming continues the current loop on the cycles left, which the option states. Resumed decisions in one request share that budget" "$policy"
		grep -qF "one or two sentences for each open item the decision covers" "$policy"
		grep -qF "the recommended option gives its reason, and each option says what it costs in fix cycles." "$policy"
		grep -qF "**No \`State:\` line:** the caller adds the one it owns" "$policy"
		grep -qF "The user'"'"'s answer to a decision applies to every item that decision covers and to nothing else." "$policy"
		grep -qF "An answer that resumes nothing, such as stopping here, ends the run: the blocked handoff already returned stands, and no new request follows." "$policy"
		grep -qF "When the user resumes some decisions and declines others, record each declined answer in its items'"'"' \`next_decision_or_dependency\`; those items keep their disposition and never return in a later request" "$policy"

		# Each ask about an open item goes through the request.
		grep -qF "Stop the workflow and ask through the Decision Request" "$policy"
		grep -qF "as the one decision you need in the Decision Request" "$policy"
		grep -qF "Ask once for the exact decision or dependency through the Decision Request" "$policy"
		grep -qF "Treat that reply as confirmation only for the findings its decision covers" "$policy"

		# The shared format and guides describe the relay.
		grep -qF "such as the \`Decision request\` field from \`trackbed:pr:review-convergence\`, show it unchanged and add only the \`State:\` line." "$format"
		grep -qF "\`pr:review-convergence\` writes the request itself, and the workflow shows it unchanged with its own \`State:\` line." "$guide"
		grep -qF "it asks one [decision request](shipping.md#decision-requests)" "$review_guide"
		grep -qF "2. Stop here (0 cycles): the branch stays local for you to finish by hand." "$guide"
	'

	[ "$status" -eq 0 ] || { echo "$output"; false; }
}
