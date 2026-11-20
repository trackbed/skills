#!/usr/bin/env bats

setup() {
	cd "$BATS_TEST_DIRNAME/.."
	GLOSSARY="shared/architecture/references/architecture-language.md"
	GLOSSARY_PATH='${CLAUDE_PLUGIN_ROOT}/shared/architecture/references/architecture-language.md'
}

@test "shared glossary measures depth at the interface and defines deepening" {
	test -f "$GLOSSARY"
	grep -qF "| **Depth** | How much behavior a caller can use per unit of interface it has to learn." "$GLOSSARY"
	grep -qF "Ranking depth by implementation size" "$GLOSSARY"
	grep -qF "| **Internal import** |" "$GLOSSARY"
	grep -qF "| **Interface impact** |" "$GLOSSARY"
	grep -qF "5. **Internal seams stay internal.**" "$GLOSSARY"
	grep -qF "### Deepening candidates — gather behind one interface" "$GLOSSARY"
	grep -qF "**One concept, many files.**" "$GLOSSARY"
	grep -qF "**Leaks across a seam.**" "$GLOSSARY"
	grep -qF "**Helpers extracted only for testability.**" "$GLOSSARY"
	grep -qF "A **deepening candidate** proposes a module that does not exist yet" "$GLOSSARY"
}

@test "every glossary consumer names the shared path and declares the glossary sources" {
	local skill
	for skill in code:refactor-opportunities code:agent-readiness code:api-design pr:code-review; do
		grep -qF "$GLOSSARY_PATH" "skills/$skill/SKILL.md"
		grep -qF "id: pocock-improve-codebase-architecture-language" "skills/$skill/references/sources.yaml"
		grep -qF "id: aihero-codebases-ai-agents-love" "skills/$skill/references/sources.yaml"
	done
	test ! -e "skills/code:refactor-opportunities/references/architecture-language.md"
}

@test "agent readiness scores module depth, boundaries, and interface tests instead of file length" {
	local rubrics="skills/code:agent-readiness/references/dimension-rubrics.md"
	local skill="skills/code:agent-readiness/SKILL.md"
	if grep -qF "All files under 500 lines" "$rubrics"; then
		echo "Traversable must not reward file length" >&2
		return 1
	fi
	grep -qF "1. **Domain-shaped layout.**" "$rubrics"
	grep -qF "5. **Module depth.**" "$rubrics"
	grep -qF "6. **Module boundaries.**" "$rubrics"
	grep -qF "Count internal imports" "$rubrics"
	grep -qF "8. **Boundary enforcement.**" "$rubrics"
	grep -qF "Behavioral assertions through module interfaces." "$rubrics"
	grep -qF "{architecture_glossary_path}" "skills/code:agent-readiness/references/dimension-agent.md"
	grep -qF "| **Phase 3: Structural** | High or Medium impact + Significant effort |" "$skill"
	grep -qF "| **Phase 4: Polish** | Low impact + Moderate or Significant effort |" "$skill"
	grep -qF "### Phase 3: Structural" "skills/code:agent-readiness/assets/audit-report.md"
}

@test "agent readiness measures search uniqueness and treats wildcard re-exports as weak entry points" {
	local rubrics="skills/code:agent-readiness/references/dimension-rubrics.md"
	grep -qF "9. **Search uniqueness.**" "$rubrics"
	grep -qF "report the share with exactly one definition plus the worst collisions" "$rubrics"
	grep -qF 'names a framework requires, such as `index.*`, `page.*`, and `__init__.py`, do not count.' "$rubrics"
	grep -qF 'a wildcard re-export (`export *`, `from x import *`) forwards everything and hides which file defines each name.' "$rubrics"
	grep -qF "Does a file-name search for a source file's name also find its test" "$rubrics"
	grep -qF "id: modem-how-coding-agents-read-your-code" "skills/code:agent-readiness/references/sources.yaml"
}

@test "implementation context searches for a new exported name before adding it" {
	local reference="shared/implementation/references/context-preparation.md"
	grep -qF "Before adding a new exported name or file, search the repository's contents and file paths for that name." "$reference"
	grep -qF "When the search finds other definitions, add the domain term the change is about" "$reference"
	grep -qF "Keep a name that a framework or an implemented interface requires" "$reference"
	local skill
	for skill in code:plan-to-pr code:work-from-plan linear:issue-implement; do
		grep -qF '${CLAUDE_PLUGIN_ROOT}/shared/implementation/references/context-preparation.md' "skills/$skill/SKILL.md"
		grep -qF "id: modem-how-coding-agents-read-your-code" "skills/$skill/references/sources.yaml"
	done
}

@test "refactor opportunities collects co-change evidence and reports deepening candidates" {
	local skill="skills/code:refactor-opportunities/SKILL.md"
	grep -qF "**Collect co-change evidence**" "$skill"
	grep -qF 'Store the pairs whose files both still exist as `CO_CHANGE`' "$skill"
	grep -qF 'Pass it `CO_CHANGE` and the resolved glossary path' "$skill"
	grep -qF "## Deepening Candidates" "skills/code:refactor-opportunities/assets/report-template.md"
	grep -qF "Deepening candidates — behavior that belongs behind one smaller interface" "skills/code:refactor-opportunities/references/checklist.md"
}

@test "refactor opportunities looks for behavior that is hard to test through its interface" {
	local checklist="skills/code:refactor-opportunities/references/checklist.md"
	grep -qF "  - Hard to test through its interface:" "$checklist"
	grep -qF "names the interface-level tests the deepening makes possible" "$checklist"
	grep -qF "id: aihero-improve-codebase-architecture-guide" "skills/code:refactor-opportunities/references/sources.yaml"
}

@test "the co-change pipeline counts repeated pairs across separate modules only" {
	local skill="$PWD/skills/code:refactor-opportunities/SKILL.md"
	local pipeline
	pipeline=$(awk '
		index($0, "git log --since=\"12 months ago\" --no-merges") { grab = 1 }
		grab && /^   ```$/ { exit }
		grab { sub(/^   /, ""); print }
	' "$skill")
	[[ "$pipeline" == *"<in-scope source paths>"* ]] || false
	pipeline=${pipeline//<in-scope source paths>/src}

	local repo="$BATS_TEST_TMPDIR/co-change"
	mkdir -p "$repo/src/billing/internal" "$repo/src/orders"
	cd "$repo"
	git init -q -b main
	git config user.email test@example.invalid
	git config user.name "Co-change Test"
	git config commit.gpgsign false
	local round
	for round in 1 2 3; do
		echo "$round" >src/billing/invoice.ts
		echo "$round" >src/billing/internal/tax.ts
		echo "$round" >src/orders/checkout.ts
		git add -A
		git commit -q -m "round $round"
	done

	run bash -c "$pipeline"
	[ "$status" -eq 0 ]
	[[ "$output" == *"3 src/billing/invoice.ts"$'\t'"src/orders/checkout.ts"* ]] || false
	[[ "$output" == *"3 src/billing/internal/tax.ts"$'\t'"src/orders/checkout.ts"* ]] || false
	[[ "$output" != *"src/billing/internal/tax.ts"$'\t'"src/billing/invoice.ts"* ]] || false
}

@test "code review runs the architecture reviewer as a conditional dimension with the shared glossary" {
	local skill="skills/pr:code-review/SKILL.md"
	local agent="agents/architecture-strategist.md"
	grep -qF '`trackbed:architecture-strategist` — if the diff adds, removes, or moves a module' "$skill"
	grep -qF '`architecture` → architecture-strategist' "$skill"
	grep -qF "pass \`trackbed:architecture-strategist\` the resolved path of \`$GLOSSARY_PATH\`" "$skill"
	grep -qF "**architecture-strategist** -- If module structure changed" "skills/pr:code-review/references/team-mode.md"
	grep -qF '"architecture": {' "skills/pr:code-review/references/execution-contract.md"
	grep -qF "**Read-only agent.**" "$agent"
	grep -qF 'end with one FYI finding at location `review-scope` that lists each changed interface' "$agent"
	if grep -qF "SOLID" "$agent"; then
		echo "the architecture reviewer must use the depth vocabulary, not SOLID" >&2
		return 1
	fi
}

@test "specs, issues, and plans record interface impact per module" {
	grep -qF "record that under Boundaries as an Ask First rule naming the module and its interface impact" "skills/docs:feature-spec/SKILL.md"
	grep -qF "Module map: each module this work creates or changes" "skills/siw:init/assets/spec-templates.md"
	grep -qF "### Module Map" "skills/discovery:interview/assets/template-feature.md"
	local template
	for template in \
		skills/siw:generate-phases/references/issue-template.md \
		skills/linear:issue-define/assets/comprehensive-template.md; do
		grep -qF "### Interface Impact" "$template"
		grep -qF "new | changed | implementation-only" "$template"
	done
	grep -qF -- "- **Interface-aware** -" "skills/siw:generate-phases/SKILL.md"
	grep -qF "HITL — needs architectural decision" "skills/siw:generate-phases/SKILL.md"
	grep -qF "## Interfaces" "skills/linear:issue-implement/assets/technical-plan.md"
}

@test "agent-config audit prefers enforcement and structure over compensating prose" {
	grep -qF "**structural compensation**" "skills/code:audit-agent-config/SKILL.md"
	grep -qF "verify the tool is configured in the repository before naming it" "skills/code:audit-agent-config/SKILL.md"
}

@test "test audit, sibling bugs, onboarding, and API design apply the module-depth lens" {
	grep -qF "imports another module's implementation files instead of its public entry point" "skills/test:audit/references/audit-rubric.md"
	grep -qF "need the same fix invariant at three or more sites" "skills/debug:find-sibling-bugs/SKILL.md"
	grep -qF "### Deepening Candidate" "skills/debug:find-sibling-bugs/assets/report-template.md"
	grep -qF "roughly 7–9 top-level chunks" "skills/visual:explain/references/onboarding-exploration-dimensions.md"
	grep -qF "Then run a **depth check** on that interface." "skills/code:api-design/SKILL.md"
}

@test "api design drafts Design It Twice designs in fresh contexts and verifies the final pick" {
	local skill="skills/code:api-design/SKILL.md"
	local mode="skills/code:api-design/references/design-it-twice.md"
	local sources="skills/code:api-design/references/sources.yaml"
	local description

	description="$(sed -n 's/^description: "\(.*\)"$/\1/p' "$skill")"
	[[ "$description" == *"in fresh-context sub-agents where the host allows"* ]] || false
	[[ "$description" == *"verifies the pick before recommending it"* ]] || false
	[ "${#description}" -le 1024 ]
	if grep -qF "sub-agents on Claude Code, sequentially elsewhere" "$skill"; then
		echo "the description must not tie the parallel form to one host" >&2
		return 1
	fi

	grep -qF "rather than a fork of the coordinating conversation; Claude Code's Agent tool is one example." "$skill"
	grep -qF "**Parallel form (any host that can launch independent sub-agents).**" "$mode"
	grep -qF "A sub-agent that forks the coordinating conversation does not count" "$mode"
	grep -qF "including when its only sub-agent mechanism forks the conversation" "$mode"
	grep -qF 'Form: parallel (<N> fresh-context sub-agents) | sequential (one context)' "$mode"
	grep -qF 'Drafted blind: yes | no — <reason>' "$mode"

	grep -qF 'Unknowns: <facts not yet established' "$mode"
	grep -qF "do not add criteria later or change them to favor a design" "$mode"
	grep -qF '### Design H: Hybrid (<what comes from which design>)' "$mode"
	grep -qF "using the same sections as the drafted designs" "$mode"
	grep -qF "### Step 4 — Verify the pick" "$mode"
	grep -qF "**Choose the hardest realistic scenario**" "$mode"
	grep -qF "For each invariant in the framing block, state whether it holds" "$mode"
	grep -qF 'as `confirmed` (cite the code, documentation, or framing inspected during this run) or `assumed`' "$mode"

	grep -qF "id: compound-ce-bakeoff" "$sources"
	grep -qF "id: compound-ce-bakeoff-verification" "$sources"
	[ "$(grep -A4 -E 'id: compound-ce-bakeoff(-verification)?$' "$sources" | grep -c 'usage: inspiration')" -eq 2 ]
}

@test "special cases deepen one requirement without duplicate findings or PR scan cost" {
	local skill="skills/code:refactor-opportunities/SKILL.md"
	local checklist="skills/code:refactor-opportunities/references/checklist.md"
	grep -qF '## 12. Special Cases' "$checklist"
	grep -qF '**Serves**' "$checklist"
	grep -qF 'add `Serves` to that record rather than recording a second item' "$checklist"
	grep -qF 'Agent 2 — Logic & Complexity' "$skill"
	grep -qF '12 (Special Cases) in full, path, and feature scopes, including `--for` runs. Skip category 12 in PR scope.' "$skill"
	local synthesis
	synthesis=$(sed -n '/^### Phase 3 — Synthesis/,/^### Phase 4 — Report/p' "$skill")
	[[ "$synthesis" == *'2. Deduplicate'*'A lone special case is a lead, not a finding'*'Group two or more special cases'*'carry the candidate through steps 3-5.'* ]] || false
	[[ "$synthesis" == *'do not group unknown requirements'*'Count removals only from surviving proposed fixes, once per distinct special case'* ]] || false
	grep -qF 'Special cases: N found; M removed by proposed fixes.' 'skills/code:refactor-opportunities/assets/report-template.md'
	grep -qF '**Special cases removed:**' 'skills/code:refactor-opportunities/assets/report-template.md'
	grep -qF '**Special cases serving one requirement.**' "$GLOSSARY"
	grep -qF 'special cases serving the same requirement' 'shared/codebase-audit/references/audit-workflow.md'
	local reader
	for reader in code:refactor-opportunities code:agent-readiness code:api-design pr:code-review; do
		grep -qF 'id: caldo-untangle-codebase' "skills/$reader/references/sources.yaml"
	done
	[ "$(printf '%s\n' "$synthesis" | grep -cE '^[0-9]+\. ')" -eq 10 ]
	[ "$(sed -n '/^### Phase 4 — Report/,/^## Guidelines/p' "$skill" | grep -cE '^[0-9]+\. ')" -eq 10 ]
}

@test "dependency direction carries history from orientation through scan and report" {
	local skill="skills/code:refactor-opportunities/SKILL.md"
	local checklist="skills/code:refactor-opportunities/references/checklist.md"
	grep -qF '8. **Depend toward what changes less.**' "$GLOSSARY"
	grep -qF 'adapter-count rule in principle 4' "$GLOSSARY"
	grep -qF 'as `CHANGE_COUNTS`' "$skill"
	grep -qF 'For path and feature scopes, including `--for`, collect `CHANGE_COUNTS`' "$skill"
	grep -qF 'plus `HOT_SPOTS`, `CHANGE_COUNTS`, and their history window, anchor, and counting convention' "$skill"
	grep -qF 'imports involving `CHANGE_TARGETS` come first' "$skill"
	grep -qF 'Do not require past edits to the stable interface or its callers' "$skill"
	grep -qF 'A useful stable module can pass the deletion test and still depend in the wrong direction.' "$skill"
	grep -qF 'Drop a dependency-direction finding without both commit counts and the importer count.' "$skill"
	grep -qF 'Exclude tests, fixtures, and test helpers as the stable side.' "$skill"
	grep -qF 'Missing either commit count or the importer count means drop the finding.' "$checklist"
	local consumer
	for consumer in code:refactor-opportunities code:agent-readiness code:api-design pr:code-review; do
		grep -qF 'history-backed dependency direction' "skills/$consumer/references/sources.yaml"
	done
}

@test "refactor scans run the outline helper outside PR scope and treat its output as leads" {
	local skill="skills/code:refactor-opportunities/SKILL.md"
	local ranked="skills/code:refactor-opportunities/references/ranked-mode.md"
	local outline
	outline="$(sed -n '/^\*\*Code outline\.\*\*/,/^### Phase 2/p' "$skill")"
	[ -f scripts/code-outline.py ]
	grep -qF 'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/code-outline.py" --files "$FILE_LIST" --out "$OUTLINE_DIR" --history-ref "${HISTORY_BASE_REF:-HEAD}"' <<<"$outline"
	grep -qF 'skip it in PR scope' <<<"$outline"
	grep -qF '`OUTLINE_DIR` to `<run directory>/outline/`, or to a new `mktemp -d` directory when the run keeps no run directory' <<<"$outline"
	grep -qF 'Everything it reports is a lead, and a finding still needs evidence from the code.' <<<"$outline"
	grep -qF 'read `outline.md` one folder at a time by its line range' <<<"$outline"
	grep -qF 'set `CODE_OUTLINE` to none, say so once, and continue without it' <<<"$outline"
	# The helper's ranked leads replace Agent 1's own importer search.
	grep -qF 'It investigates the dependency-direction leads in their ranked order' "$skill"
	! grep -qF 'For each hot-spot file, trace its direct importers' "$skill" || false
	grep -qF 'read `folders.tsv` for the folders where findings cluster' "$skill"
	grep -qF 'to the Architecture & boundaries reviewer as dependency signals' "$ranked"
	grep -qF 'scripted skeleton without function bodies and a scripted import map' "skills/code:refactor-opportunities/references/sources.yaml"
	grep -qF 'sourceFile: path.join(plugin.root, "scripts", "code-outline.py")' scripts/convert-plugin/codex-transformer.js
}
