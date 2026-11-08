#!/usr/bin/env bats

setup() {
	cd "$BATS_TEST_DIRNAME/.."
	SKILL="skills/docs:adr/SKILL.md"
	INTERVIEW_REFS="skills/discovery:interview/references"
	OFFER="skills/docs:adr/references/inline-offer-pattern.md"
	SOURCES="skills/docs:adr/references/sources.yaml"
}

@test "adr skill is model-invocable with a least-side-effect model contract" {
	frontmatter="$(awk '/^---$/{n++; next} n==1' "$SKILL")"
	grep -qx 'disable-model-invocation: false' <<<"$frontmatter"
	grep -qx 'user-invocable: true' <<<"$frontmatter"
	grep -qF 'When the model started the skill and the user did not ask for this ADR in this session:' "$SKILL"
	grep -qF -- '- Write only when the decision passes the three-criterion test in step 1; otherwise write nothing.' "$SKILL"
	grep -qF -- '- Apply that test before pre-flight, so a decision that fails it stops there instead of asking about the ADR log.' "$SKILL"
	grep -qF -- '- Create only a new ADR file, with Status PROPOSED.' "$SKILL"
	grep -qF -- '- Emit `ASK FIRST` before editing, superseding, or deprecating an existing ADR, and before creating an ADR directory the project does not have.' "$SKILL"
	! grep -qF 'runs only after explicit user invocation' "$SKILL" || false
}

@test "every adr write ends with the ADR WRITTEN callout" {
	grep -qF 'Six steps. Do not skip steps.' "$SKILL"
	grep -qF '### 6. Announce the write' "$SKILL"
	grep -qF 'start the final message to the user with this block, before any other text, even when the ADR was a side step of a larger task' "$SKILL"
	grep -qF '> [!IMPORTANT]' "$SKILL"
	grep -qF '> **ADR WRITTEN — review before you commit**' "$SKILL"
	grep -qF '> - Started by: model, no user request' "$SKILL"
	grep -qF '> - Undo: delete #0007; in #0003 restore Status ACCEPTED and remove the successor reference added by this run' "$SKILL"
	grep -qF 'name the files this run created and the exact edits to reverse in existing ADRs' "$SKILL"
	grep -qF 'Preserve pre-existing and later edits. Never recommend whole-file `git restore` for an edited ADR.' "$SKILL"
	grep -qF 'Send the block as Markdown, not inside a code fence, so it renders as a callout.' "$SKILL"
	grep -qF 'Do not fold the block into prose, shorten it, or move it below a summary.' "$SKILL"
	grep -qF 'must repeat the block unchanged at the top of its own final message' "$SKILL"
}

@test "discovery interview invokes the adr skill and repeats its callout" {
	for ref in "$INTERVIEW_REFS/interview-operations.md" "$INTERVIEW_REFS/probing-techniques.md"; do
		grep -qF 'invoke `trackbed:docs:adr` with a decision title and short context summary as its arguments, and repeat its `ADR WRITTEN` callout at the top of your final message' "$ref"
		! grep -qF 'user-triggered only' "$ref" || false
	done
}

@test "adr pre-flight reads repository signals before falling back to defaults" {
	instructions=$(grep -nF '1. **Project instructions.**' "$SKILL" | cut -d: -f1)
	tooling=$(grep -nF '2. **ADR tool configuration.**' "$SKILL" | cut -d: -f1)
	folders=$(grep -nF '3. **ADR folders anywhere in the repository.**' "$SKILL" | cut -d: -f1)
	[ -n "$instructions" ]
	[ "$instructions" -lt "$tooling" ]
	[ "$tooling" -lt "$folders" ]
	grep -qF '`AGENTS.md`, `CLAUDE.md`, and `CONTRIBUTING.md`, and any decision index or guide they link to' "$SKILL"
	grep -qF '`.adr-dir` (adr-tools) or `.log4brains.yml` (log4brains)' "$SKILL"
	grep -qF 'Search below the repository root, not only at it' "$SKILL"
	grep -qF 'Keep a folder as a candidate only when it holds Markdown decision records.' "$SKILL"
	grep -qF 'Use `assets/adr-template.md` and the default `docs/decisions/` folder only when no signal above establishes a convention.' "$SKILL"
	grep -qF 'When no folder holds records yet, the log is the folder an instruction or tool setting names, or else the only ADR folder found that holds just an index or template.' "$SKILL"
}

@test "adr pre-flight stops on conflicting log signals" {
	grep -qF 'Stop with `CONFUSION` and ask the user before drafting when the signals conflict:' "$SKILL"
	grep -qF -- '- More than one candidate folder holds ADR records.' "$SKILL"
	grep -qF -- '- Instructions or tool configuration name a location or filename format that the records on disk do not follow. Records the next rule treats as legacy do not count.' "$SKILL"
	grep -qF 'One folder mixes numbering schemes, such as `0001-` records beside `2026-11-02-` records, and no project instruction names the scheme for new records.' "$SKILL"
	grep -qF 'treat records in the other scheme as legacy: keep them, and never number from them.' "$SKILL"
}

@test "adr numbering keeps dated records out of the number scan" {
	grep -qF -- '- **Dated scheme**: name the file with today'"'"'s date and a new slug' "$SKILL"
	grep -qF 'The highest-number scan is valid only when every record it reads follows one integer scheme.' "$SKILL"
	grep -qF 'In a dated log, cite records by filename wherever this skill shows `#NNNN` or `#MMMM`.' "$SKILL"
	grep -qF 'If `ADR_DIR` does not exist yet, create the folder pre-flight chose, or `docs/decisions/` when no signal names one' "$SKILL"
}

@test "unrequested adr runs pass all three criteria before writing" {
	grep -qF 'For a run nobody requested, the decision must also meet **all three** criteria before you write anything:' "$SKILL"
	grep -qF 'including by accepting another skill'"'"'s ADR offer' "$SKILL"
	grep -qF 'emit a `NOTICED BUT NOT TOUCHING` marker naming the decision and why it is not ADR-worthy, and stop' "$SKILL"
	grep -qF 'If any criterion fails, write nothing. Emit `NOTICED BUT NOT TOUCHING` naming the decision and each failed criterion, and stop.' "$SKILL"
	grep -qF 'For a run the user requested, a decision warrants an ADR if **any** of these are true.' "$SKILL"
	grep -qF 'A run nobody requested must also pass the stricter test in step 1.' "$SKILL"
}

@test "every copy of the three-criterion test names the same criteria" {
	for file in "$SKILL" "$OFFER"; do
		grep -qF -- '- **Hard to reverse** — undoing it later would be costly or destructive.' "$file"
		grep -qF -- '- **Surprising without context** — a future maintainer would reasonably ask "why this?" and not be able to infer the answer from the code alone.' "$file"
		grep -qF -- '- **Result of a real tradeoff** — a credible alternative was rejected for a stated reason.' "$file"
	done
	grep -qF 'offer `/trackbed:docs:adr` only when all three criteria are true:' "$INTERVIEW_REFS/interview-operations.md"
	grep -qF 'Offer once when all three are true:' "$INTERVIEW_REFS/probing-techniques.md"
	for ref in "$INTERVIEW_REFS/interview-operations.md" "$INTERVIEW_REFS/probing-techniques.md"; do
		grep -qF '1. The decision is hard to reverse.' "$ref"
		grep -qF '2. It would be surprising later without context.' "$ref"
		grep -qF '3. It came from a real tradeoff, not a default.' "$ref"
	done
}

@test "adr skill keeps original wording, source rationales, and step count accurate" {
	! grep -qiF "Don't delete old ADRs" "$SKILL" || false
	! grep -qF 'They capture historical context.' "$SKILL" || false
	grep -qF 'Keep every ADR in the directory once it is written, including SUPERSEDED and DEPRECATED ones.' "$SKILL"
	grep -qF 'which runs its own six-step authoring workflow' "$OFFER"
	! grep -qF '5-step' "$OFFER" || false
	! grep -qF 'drafting markers' "$SOURCES" || false
	! grep -qF '(discovery, refactor)' "$SOURCES" || false
}
