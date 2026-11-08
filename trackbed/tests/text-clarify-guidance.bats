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
