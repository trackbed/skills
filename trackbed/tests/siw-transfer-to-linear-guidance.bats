#!/usr/bin/env bats

setup() {
	cd "$BATS_TEST_DIRNAME/.."
	SKILL_DIR="skills/siw:transfer-to-linear"
	SKILL="$SKILL_DIR/SKILL.md"
	MAPPING="$SKILL_DIR/references/linear-mapping.md"
	EXTRACTION="$SKILL_DIR/references/artifact-extraction.md"
}

@test "transfer-to-linear discovers blocking and related-link support separately" {
	grep -qF 'Record blocking support (`blockedBy` or `blocks`) and related-link support (`relatedTo`) separately' "$SKILL"
	grep -qF 'Blocking edges need `blockedBy` or `blocks`; related links need `relatedTo`. Run each part only when its parameter exists' "$MAPPING"
}

@test "transfer-to-linear writes each resolvable Related value as one native related link" {
	grep -qF 'Related links from each issue'"'"'s `Related:` metadata value: the SIW issue IDs it names, with ranges expanded' "$SKILL"
	grep -qF 'Related links from the `Related:` metadata value: the SIW issue IDs it names, with ranges expanded.' "$EXTRACTION"
	grep -qF 'Take only the SIW issue IDs (`Pn-NNN`, `G-NNN`) the value names, expanding ranges the same way. Ignore every other value' "$MAPPING"
	grep -qF 'Write each resolvable pair once as `relatedTo`, from the issue whose `Related:` value names the other. A pair that both issues name is still one link.' "$MAPPING"
	grep -qF 'Skip a pair that a blocking edge already joins, in either direction' "$MAPPING"
	grep -qF 'Report edges and links that reference SIW IDs absent from the ledger' "$MAPPING"
	grep -qF 'resolve each planned `Blocked by:` / `Blocks:` edge and each planned `Related:` link from SIW IDs to Linear IDs' "$SKILL"
}

@test "transfer-to-linear plan counts blocking edges and related links separately" {
	grep -qF 'Count blocking edges and related links separately, and report any edge or link that references an unknown SIW ID.' "$SKILL"
	grep -qF 'Relations: {blocking_edge_count} blocking edges {planned as native relations | recorded as text only — no blocking support}; {related_edge_count} related links {planned as native relations | recorded as text only — no relatedTo support}' "$SKILL"
}

@test "transfer-to-linear fallback says mentions create no relation and read-back expects none" {
	grep -qF 'An identifier mentioned in a description creates no Linear relation, though Linear may show the mention as a backlink on the named issue.' "$MAPPING"
	grep -qF 'the Phase 7 read-back expects no relations from text alone' "$MAPPING"
	grep -qF 'Text alone creates none: an identifier mentioned in a description adds no Linear relation, though Linear may show the mention as a backlink.' "$SKILL"
	grep -qF 'With no relation support, expect no relations, and never count a backlink as a written relation.' "$SKILL"
	! grep -qF 'When no relation parameters exist, text is the only record.' "$MAPPING"
}
