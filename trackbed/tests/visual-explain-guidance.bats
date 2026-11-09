#!/usr/bin/env bats

setup() {
	cd "$BATS_TEST_DIRNAME/.."
	SKILL="skills/visual:explain/SKILL.md"
	MODE="skills/visual:explain/references/onboarding-mode.md"
	SOURCES="skills/visual:explain/references/sources.yaml"
}

@test "visual explain replaces visual diagram and absorbs the onboarding guide as an opt-in mode" {
	test ! -e "skills/kramme:visual:onboarding"
	test ! -e "skills/kramme:visual:diagram"
	! grep -rqF "visual:onboarding" skills shared || false
	! grep -rqF "visual:diagram" skills shared || false
	grep -qxF "name: visual:explain" "$SKILL"
	grep -qF -- '--onboarding' <(sed -n '/^argument-hint:/p' "$SKILL")
	grep -qF -- '--onboarding' <(sed -n '/^description:/p' "$SKILL")
	grep -qF 'read `references/onboarding-mode.md` before Step 1' "$SKILL"
	grep -qF "Proactive table rendering never uses onboarding mode." "$SKILL"
	grep -qF 'references/onboarding-exploration-dimensions.md' "$MODE"
	grep -qF 'references/onboarding-explore-agent.md' "$MODE"
	test -f "skills/visual:explain/references/onboarding-exploration-dimensions.md"
	test -f "skills/visual:explain/references/onboarding-explore-agent.md"
	grep -qF '~/.trackbed/diagrams/onboarding-{project-name}.html' "$MODE"
	grep -qF 'Launch **2-3 Explore agents**' "$MODE"
	grep -qF 'cite `source: file:line`' "$MODE"
	grep -qF 'Escape repo-derived text' "$MODE"
	grep -qF 'id: aihero-codebases-ai-agents-love' "$SOURCES"
	grep -qF 'id: nicobailon-visual-explainer' "$SOURCES"
}

@test "visual explain points resource paths at the shared visual directory" {
	test ! -e "skills/visual:explain/assets"
	! grep -qF 'Resolve `assets/...`' "$SKILL" || false
	grep -qF '${CLAUDE_PLUGIN_ROOT}/shared/visual/' "$SKILL"
}

@test "shared visual references render without scripts, survive file pages, and follow the style rules" {
	LIBS="shared/visual/references/libraries.md"
	NAV="shared/visual/references/responsive-nav.md"
	FLOW="shared/visual/assets/mermaid-flowchart.html"

	# anime.js hides nodes only after a script has marked the document, on screens with motion allowed.
	grep -qF 'typeof anime === "function" &&' "$LIBS"
	grep -qF 'document.documentElement.classList.add("anime-ready");' "$LIBS"
	grep -qF '@media screen and (prefers-reduced-motion: no-preference) {' "$LIBS"
	grep -qF '  .anime-ready .node {' "$LIBS"
	! grep -qxF '.node {' "$LIBS" || false

	# The scroll-spy URL update cannot break navigation on file: pages.
	grep -B1 -F 'history.replaceState(null, "", "#" + id);' "$NAV" | grep -qF 'try {'

	# Mermaid stroke overrides beat Mermaid's ID-scoped rules.
	! grep -nE '^ *stroke-width: [0-9.]+px;$' "$LIBS" "$FLOW" || false

	# The removed violet and indigo values and any emoji stay out of the shared references and templates.
	! grep -rniE '#(7c3aed|8b5cf6|ede9fe|2d1b69|c4b5fd|1e1b4b|818cf8|4f46e5)\b|rgba\((124, 58, 237|129, 140, 248|79, 70, 229)' shared/visual || false
	python3 - shared/visual <<'PY'
import pathlib, sys
hits = [f"{p}:{n}" for p in sorted(pathlib.Path(sys.argv[1]).rglob("*")) if p.is_file()
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if any(0x1F000 <= ord(ch) <= 0x1FAFF or 0x2600 <= ord(ch) <= 0x27BF for ch in line)]
sys.exit("emoji found: " + ", ".join(hits) if hits else 0)
PY

	# ELK statements are labeled as Mermaid 11 behavior.
	grep -qF "**With ELK layout** (Mermaid 11: required for" "$LIBS"
	grep -qF "In Mermaid 11, without the ELK import and registration" "$LIBS"
	grep -qF "(with Mermaid 11, this requires the ELK import" "$LIBS"
	grep -qF "With Mermaid 11, which this template" "$FLOW"
	grep -qF "it, Mermaid 11 silently falls back to dagre." "$FLOW"
	grep -qF "with the pinned Mermaid 11, this requires the separate \`@mermaid-js/layout-elk\` package" "$SKILL"
}
