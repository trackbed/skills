#!/usr/bin/env bats

load 'test_helper/common'

@test "linear issue implement maps referenced Linear context into research and plan" {
	run bash -c '
    set -e
    cd "'"$BATS_TEST_DIRNAME"'/.."
    skill="skills/linear:issue-implement"

    test -f "$skill/SKILL.md"
    test -f "$skill/references/display-templates.md"
    test -f "$skill/assets/technical-plan.md"

	    grep -qF "Local SIW work must be transferred to Linear first." "$skill/SKILL.md"
	    grep -qF "run \`trackbed:siw:transfer-to-linear\` first" "$skill/SKILL.md"
	    ! grep -qF "kramme:siw:issue-implement" "$skill/SKILL.md"
	    grep -qF "Reject direct, incomplete, mismatched, or duplicate use" "$skill/SKILL.md"
	    grep -qF "Require current \`HEAD\`, committed paths, and dirty paths to equal the captured entry handoff" "$skill/references/branch-setup.md"

    branch_line=$(grep -nF "[Branch Setup] -> IMMEDIATELY create/switch to Linear'\''s branchName" "$skill/SKILL.md" | head -n1 | cut -d: -f1)
    reference_line=$(grep -nF "[Reference Mapping] -> Fetch linked Linear issues/docs and record inaccessible assets" "$skill/SKILL.md" | head -n1 | cut -d: -f1)
    [ "$branch_line" -lt "$reference_line" ]
  '

	assert_required_contracts_registered \
		linear-issue-implement-reference-mapping \
		linear-issue-implement-display-template \
		linear-issue-implement-plan-template \
		linear-issue-implement-public-note

	[ "$status" -eq 0 ]
}

@test "linear issue implement transitions Linear only under --set-in-progress" {
	run bash -c '
    set -e
    cd "'"$BATS_TEST_DIRNAME"'/.."
    skill="skills/linear:issue-implement/SKILL.md"
    transition="skills/linear:issue-implement/references/status-transition.md"
    templates="skills/linear:issue-implement/references/display-templates.md"
    parent="skills/linear:issue-to-pr/SKILL.md"

    test -f "$transition"

    grep -qF "argument-hint: \"<ISSUE-ID> [--auto] [--set-in-progress]\"" "$skill"
    grep -qF "If \`--set-in-progress\` is present, set \`SET_IN_PROGRESS=true\`" "$skill"
    grep -qF "reject it together with \`--resume-current-branch\`" "$skill"
    grep -qF "Default \`SET_IN_PROGRESS=false\`, which leaves every Linear workflow status untouched." "$skill"
    grep -qF "A model caller may pass \`--set-in-progress\` only as that exact gated parent" "$skill"
    grep -qF "### 1.4 Apply the Authorized Status Transition" "$skill"
    grep -qF "read \`references/status-transition.md\` and follow it completely before Step 2" "$skill"
    grep -qF "The Step 1.4 status transition is the only Linear write in this skill" "$skill"
    grep -qF "Linear transition: {transition-outcome}" "$templates"

    grep -qF "It is the only Linear write in this skill." "$transition"
    grep -qF "never edit the title, description, labels, assignee, project, estimate, or any other mutable field" "$transition"
    grep -qF "In delegated mode, skip this section" "$transition"
    grep -qF "\`AUTO_MODE=true\` does not remove this confirmation." "$transition"
    grep -qF "Classify the invocation by the presence of a parent-owned status handoff, never by \`AUTO_MODE\`" "$transition"
    grep -qF "In direct invocation, prove the worktree can still reach branch setup before writing" "$transition"
    grep -qF "so a moved issue is never left without its branch" "$transition"
    grep -qF "the parent treats a delegated failure as a workflow failure" "$transition"
    grep -qF "Capture \`{transition-outcome}\` for Step 8'"'"'s success output" "$transition"
    grep -qF "set \`{transition-outcome}\` to \`not requested (--set-in-progress was not supplied)\`" "$skill"
    grep -qF "already {target-status-name} (continuation; no transition performed)" "$parent"

    grep -qF -- "{issue-id} --auto --set-in-progress" "$parent"

    transition_line=$(grep -nF "### 1.4 Apply the Authorized Status Transition" "$skill" | head -n1 | cut -d: -f1)
    branch_line=$(grep -nF "## Step 2: Branch Setup" "$skill" | head -n1 | cut -d: -f1)
    [ "$transition_line" -lt "$branch_line" ]

    diagram_transition=$(grep -nF "[Status Transition] -> ONLY with --set-in-progress" "$skill" | head -n1 | cut -d: -f1)
    diagram_branch=$(grep -nF "[Branch Setup] -> IMMEDIATELY create/switch" "$skill" | head -n1 | cut -d: -f1)
    [ "$diagram_transition" -lt "$diagram_branch" ]
  '

	assert_required_contracts_registered linear-issue-implement-status-transition

	[ "$status" -eq 0 ] || { echo "$output"; false; }
}

@test "linear issue implement loads tools, shows the issue, bounds fixes, and verifies outside criteria" {
	run bash -c '
    set -e
    cd "'"$BATS_TEST_DIRNAME"'/.."
    dir="skills/linear:issue-implement"
    skill="$dir/SKILL.md"
    errors="$dir/references/error-handling.md"
    transition="$dir/references/status-transition.md"
    workflows="$dir/references/implementation-workflows.md"
    plan="$dir/assets/technical-plan.md"

    grep -qF "load the Linear tools through the host'"'"'s tool discovery and make one real call first" "$skill"
    grep -qF "load its Linear tools through the host'"'"'s tool discovery" "$errors"
    grep -qF "and make one real Linear call" "$errors"
    grep -qF "Only when discovery finds no Linear tools, or that call fails with a connection error" "$errors"
    grep -qF "An authentication error is the \"Authentication\" case and a not-found result is the \"Not found\" case below, not a disconnected server" "$errors"
    if grep -qF "Linear MCP operations unavailable: Linear MCP server is not connected" "$errors"; then false; fi

    grep -qF "As soon as the fetch succeeds, display \`Linear issue: {identifier} — {title}\`" "$skill"
    grep -qF "before the Step 1.4 status write and before any Step 2 branch change" "$skill"
    show_line=$(grep -nF "**Show the issue before changing anything.**" "$skill" | head -n1 | cut -d: -f1)
    fetch_line=$(grep -nF "### 1.2 Fetch Issue Details" "$skill" | head -n1 | cut -d: -f1)
    transition_line=$(grep -nF "### 1.4 Apply the Authorized Status Transition" "$skill" | head -n1 | cut -d: -f1)
    [ "$fetch_line" -lt "$show_line" ]
    [ "$show_line" -lt "$transition_line" ]
    grep -qF "includes the issue identifier and title, current state name and type" "$transition"

    grep -qF "**Stop after two failed fixes for the same check.** Do not try a third edit." "$workflows"
    grep -qF "Name the belief both attempts relied on" "$workflows"
    grep -qF "and re-check it against the source" "$workflows"
    grep -qF "If it was wrong and correcting it stays within the issue'"'"'s scope, correct it and note the change" "$workflows"
    grep -qF "Otherwise stop with a blocker that names the check, both attempts, and the belief that failed" "$workflows"
    grep -qF "the two-failed-fixes stop in step 3 applies here too" "$workflows"

    grep -qF "Ensure every in-repository acceptance criterion is met, and mark each one met only from evidence for it" "$workflows"
    if grep -qF "{criterion not yet met}" "$workflows"; then false; fi
    grep -qF "For a criterion that lives outside the repository" "$workflows"
    grep -qF "Mark it met only from what the live system shows through an available tool; otherwise list it as pending user action" "$workflows"
    grep -qF "Pending user action:" "$workflows"
    grep -qF "| Requirement | Technical Implementation | Verified In |" "$plan"

    grep -qF "after a context reset or compaction, when drift symptoms appear" "$workflows"
    grep -qF "Order each task'"'"'s new or changed interface and the tests that pin it before the implementation behind it" "$workflows"
    grep -qF "Order each new or changed interface and the tests that pin it before the implementation behind it" "$workflows"
    interface_line=$(grep -nF "Define {interface for task 1} and add the tests that pin it" "$workflows" | head -n1 | cut -d: -f1)
    implement_line=$(grep -nF "Implement {task 1 from requirements} behind that interface" "$workflows" | head -n1 | cut -d: -f1)
    [ "$interface_line" -lt "$implement_line" ]
    grep -qF "an implementation-only task skips its interface item and keeps a test item after its implementation" "$workflows"
    if grep -qF "Add tests for {task 1}" "$workflows"; then false; fi
  '

	[ "$status" -eq 0 ] || { echo "$output"; false; }
}
