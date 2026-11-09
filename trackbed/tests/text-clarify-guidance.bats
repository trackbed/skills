#!/usr/bin/env bats

setup() {
	cd "$BATS_TEST_DIRNAME/.."
	CLARIFY="skills/text:clarify"
	REPLY="skills/pr:github-review-reply/SKILL.md"
	GITHUB_REVIEW="skills/pr:github-review"
}

@test "humanize is merged into clarify and no skill names the removed command" {
	test ! -e "skills/kramme:text:humanize"
	! grep -rqF "text:humanize" skills shared || false
}

@test "clarify exposes humanize mode and keeps its default-mode contract" {
	grep -E '^argument-hint:' "$CLARIFY/SKILL.md" | grep -qF -- "--humanize"
	grep -E '^description:' "$CLARIFY/SKILL.md" | grep -qF -- "--humanize"
	! grep -E '^description:' "$CLARIFY/SKILL.md" | grep -qF "Not for removing AI-writing patterns" || false
	grep -qF 'references/humanize-mode.md' "$CLARIFY/SKILL.md"
	grep -qF '${CLAUDE_PLUGIN_ROOT}/shared/writing/references/plain-language-rubric.md' "$CLARIFY/SKILL.md"
	grep -qF 'references/ai-writing-patterns.md' "$CLARIFY/references/humanize-mode.md"
}

@test "humanize mode uses clarify's input contract instead of the slash stop" {
	grep -qF "Treat a nonexistent argument as a path only when the complete single-line value is path-shaped" "$CLARIFY/SKILL.md"
	grep -qF "This contract applies in both modes." "$CLARIFY/SKILL.md"
	local file
	for file in "$CLARIFY/SKILL.md" "$CLARIFY/references/humanize-mode.md"; do
		! grep -qF "Do not silently treat a missing path as raw text" "$file" || false
	done
}

@test "the copied Wikipedia catalog keeps its notice and provenance under clarify" {
	test -f "$CLARIFY/references/ai-writing-patterns.md"
	test -f "$CLARIFY/references/WIKIPEDIA-CONTENT-LICENSE.md"
	local entry
	entry="$(awk '/^  - id: /{inside = ($3 == "wikipedia-signs-of-ai-writing")} inside' "$CLARIFY/references/sources.yaml")"
	[[ "$entry" == *"usage: copied"* ]]
	[[ "$entry" == *"notice: references/WIKIPEDIA-CONTENT-LICENSE.md"* ]]
	grep -qF '`text:clarify/references/ai-writing-patterns.md` is an adapted work based on Wikipedia' ../THIRD_PARTY_NOTICES.md
}

@test "the catalog declares humanizer as a copied MIT source with its notice" {
	local commit="3e1da8bfce43ecbe43a56f3cb00b62fbdf1cbd56"
	local entry
	entry="$(awk '/^  - id: /{inside = ($3 == "blader-humanizer")} inside' "$CLARIFY/references/sources.yaml")"
	[[ "$entry" == *"usage: copied"* ]]
	[[ "$entry" == *'license: "MIT"'* ]]
	[[ "$entry" == *"notice: references/blader-humanizer-LICENSE"* ]]
	[[ "$entry" == *"upstream_path: SKILL.md"* ]]
	[[ "$entry" == *"upstream_commit: $commit"* ]]
	grep -qF "MIT License" "$CLARIFY/references/blader-humanizer-LICENSE"
	grep -qF "Copyright (c) 2025 Siqi Chen" "$CLARIFY/references/blader-humanizer-LICENSE"
	grep -qF "Permission is hereby granted, free of charge" "$CLARIFY/references/blader-humanizer-LICENSE"
	grep -qF "in the Software without restriction, including without limitation the rights" "$CLARIFY/references/blader-humanizer-LICENSE"
	grep -qF "The above copyright notice and this permission notice shall be included" "$CLARIFY/references/blader-humanizer-LICENSE"
	grep -qF 'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND' "$CLARIFY/references/blader-humanizer-LICENSE"
	grep -qF "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM" "$CLARIFY/references/blader-humanizer-LICENSE"
	local header
	header="$(sed -n '1,10p' "$CLARIFY/references/ai-writing-patterns.md")"
	[[ "$header" == *"WikiProject AI Cleanup, at revision 1366684471, under CC BY-SA 4.0"* ]]
	[[ "$header" == *"[blader/humanizer](https://github.com/blader/humanizer) at commit \`$commit\`, under the MIT License"* ]]
	[[ "$header" == *"blader-humanizer-LICENSE"* ]]
	grep -qF '`text:clarify/references/ai-writing-patterns.md` adapts text from `SKILL.md` in [`blader/humanizer`]' ../THIRD_PARTY_NOTICES.md
	grep -qF "trackbed/skills/text:clarify/references/blader-humanizer-LICENSE" ../THIRD_PARTY_NOTICES.md
}

@test "GitHub review sends its humanize passes through clarify's mode" {
	grep -qF '/trackbed:text:clarify --humanize' "$GITHUB_REVIEW/references/comment-drafting.md"
	grep -qF '/trackbed:text:clarify --humanize' "$GITHUB_REVIEW/references/clarity-check.md"
	grep -qF '## Step 10: Humanize the Draft Comments' "$GITHUB_REVIEW/SKILL.md"
}

@test "clarify continues a calling workflow instead of ending the turn on a delegated rewrite" {
	local step8 delegated otherwise
	step8="$(awk '/^8\. \*\*Present and optionally save\.\*\*/{inside = 1} /^## Error Handling/{inside = 0} inside' "$CLARIFY/SKILL.md")"
	grep -qF "**Delegated run:** when this skill runs as one step of another skill's workflow, the rewrite is input to that workflow, not your reply." <<< "$step8"
	grep -qF "continue with the calling workflow's next step without ending the turn" <<< "$step8"
	grep -qF "end the turn only where that workflow ends or pauses" <<< "$step8"
	grep -qF "Otherwise, return the complete clarified text in a copy-ready block." <<< "$step8"
	delegated="$(grep -nF '**Delegated run:**' "$CLARIFY/SKILL.md" | cut -d: -f1)"
	otherwise="$(grep -nF 'Otherwise, return the complete clarified text in a copy-ready block.' "$CLARIFY/SKILL.md" | cut -d: -f1)"
	[ "$delegated" -lt "$otherwise" ]
	grep -qF "In a delegated run, follow Step 8 instead: the calling workflow decides what the user sees and when the turn ends." "$CLARIFY/SKILL.md"
}

@test "clarify's callers keep going after its output instead of ending the turn" {
	grep -qF "and that the rewrite is one step of this review, which continues after it." "$GITHUB_REVIEW/references/comment-drafting.md"
	grep -qF "When the clarify skill finishes, never end the turn on its output" "$GITHUB_REVIEW/references/comment-drafting.md"
	grep -qF "Do this in the same response as the clarify output, without ending the turn, then continue to stage 7." "$GITHUB_REVIEW/references/clarity-check.md"
	grep -qF "The clarify output is input to this step, not a reply to the user." "$REPLY"
	grep -qF "make the calling step's next tool call: saving Step 10's result, or the next action of the clarity-check stage or Step 12 edit that sent these bodies." "$GITHUB_REVIEW/references/comment-drafting.md"
	grep -qF "then apply the resolve rules below and continue to Step 7." "$REPLY"
}

@test "GitHub review reply humanizes replies only on request" {
	grep -E '^argument-hint:' "$REPLY" | grep -qF -- "--humanize"
	grep -qF 'trackbed:text:clarify --humanize' "$REPLY"
	grep -qF 'HUMANIZE=false' "$REPLY"
	grep -qF 'If `--humanize` is present, set `HUMANIZE=true`.' "$REPLY"
	grep -qF 'Humanized: skipped' "$REPLY"
	grep -qF '`yes`, `no`, or `skipped`' "$REPLY"
}

@test "the Linear reviewer summary keeps clarify's default mode" {
	! grep -qF -- "--humanize" skills/linear:issue-to-pr/SKILL.md || false
}

@test "the shared rubric tests caveats and claims with four outcomes" {
	local rubric="shared/writing/references/plain-language-rubric.md"
	grep -qxF "## Caveats and Claims" "$rubric"
	grep -qF -- "- **Drop** a caveat that no reader decision depends on" "$rubric"
	grep -qF -- "- **Narrow** a claim to the scope that was verified." "$rubric"
	grep -qF -- "- **Move** a caveat to the step where the reader makes the choice it affects." "$rubric"
	grep -qF -- "- **Keep** a caveat that evidence backs and a reader decision needs, and a claim the evidence fully supports." "$rubric"
	grep -qF -- "- **Your own draft**, such as a PR description you are writing: apply all four." "$rubric"
	grep -qF -- "- **Someone else's text**: apply only Move. Leave each Drop and Narrow candidate in place and list it for the author" "$rubric"
	grep -qF "Keep ordinary qualifiers" "$rubric"
	grep -qF "Put warnings immediately before the action that creates the risk. This is the Move outcome" "$rubric"
	grep -qF "Did every factual claim, caveat, citation, and uncertainty survive accurately? In your own draft, the only exceptions are caveats you dropped and claims you narrowed under Caveats and Claims." "$rubric"
}

@test "clarify moves caveats but lists Drop and Narrow candidates for the author" {
	grep -qF "Apply its Caveats and Claims test as an editor of someone else's text" "$CLARIFY/SKILL.md"
	grep -qF "move a caveat to the step where the reader decides" "$CLARIFY/SKILL.md"
	grep -qF "never drop a caveat or narrow a claim yourself" "$CLARIFY/SKILL.md"
	grep -qF "In default mode, after the rewrite, list each Drop and Narrow candidate from Step 3 for the author" "$CLARIFY/SKILL.md"
	grep -qF "In default mode, always follow it with the Drop and Narrow candidates for the author" "$CLARIFY/SKILL.md"
	grep -qF "id: egm-style-persona" "$CLARIFY/references/sources.yaml"
	grep -qF "elephant-goldfish-model/6efc127defc561e3a672b3d155b8216255a10e25/agents/style.md" "$CLARIFY/references/sources.yaml"
}
