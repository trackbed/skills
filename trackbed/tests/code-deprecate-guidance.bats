#!/usr/bin/env bats

setup() {
	PLUGIN_ROOT="$BATS_TEST_DIRNAME/.."
	SKILL="$PLUGIN_ROOT/skills/code:deprecate/SKILL.md"
	DECISION_CHECKLIST="$PLUGIN_ROOT/skills/code:deprecate/references/decision-checklist.md"
	MIGRATION_PATTERNS="$PLUGIN_ROOT/skills/code:deprecate/references/migration-patterns.md"
}

@test "database migration pattern is routed before generic migration cost" {
	run python3 - "$SKILL" "$DECISION_CHECKLIST" <<'PY'
import pathlib
import sys

skill = pathlib.Path(sys.argv[1]).read_text()
checklist = pathlib.Path(sys.argv[2]).read_text()

skill_frontmatter = skill.split("---", 2)[1]
step_one = skill.split("## Step 1 —", 1)[1].split("## Step 2 —", 1)[0]
question_four = next(line for line in step_one.splitlines() if line.startswith("4. **"))
cost_section = checklist.split("## 4. What is the migration cost for dependents?", 1)[1].split("---", 1)[0]

required = {
    "public skill description": "Database Expand-Migrate-Contract patterns",
    "persistent-data routing": "persisted data/schema contract → Database Expand/Migrate/Contract at every cost tier",
    "decision-checklist routing": "use Database Expand/Migrate/Contract regardless of whether dependent work is Low, Medium, or High",
    "framework-only boundary": "framework/library-only `trackbed:code:migrate` workflow",
    "framework migration route": "Framework or library version migration",
}
texts = {
    "public skill description": skill_frontmatter,
    "persistent-data routing": question_four,
    "decision-checklist routing": cost_section,
    "framework-only boundary": cost_section,
    "framework migration route": cost_section,
}
missing = [name for name, phrase in required.items() if phrase not in texts[name]]
if question_four.find("persisted data/schema contract") > question_four.find("Then estimate"):
    missing.append("Step 1 chooses the persistence boundary before cost")
if cost_section.find("Persisted data or schema contract") > cost_section.find("Other boundaries, Low"):
    missing.append("decision checklist chooses the persistence boundary before cost tiers")
raise SystemExit("missing database routing contracts: " + ", ".join(missing) if missing else 0)
PY
	[ "$status" -eq 0 ] || { echo "$output"; false; }
}

@test "database phase status is authoritative for resume and completion" {
	run python3 - "$SKILL" "$MIGRATION_PATTERNS" <<'PY'
import pathlib
import re
import sys

skill = pathlib.Path(sys.argv[1]).read_text()
patterns = pathlib.Path(sys.argv[2]).read_text()

required_skill = {
    "authoritative plan section": "## Database Migration Phase Status (authoritative when Database Expand/Migrate/Contract is selected)",
    "resume traversal": "`## Database Migration Phase Status` to find the earliest incomplete exit criterion",
    "resume authority": "database phase-status checklist is the authoritative state",
    "operator gate": "Operator readiness — the named datastore owner reviewed the production phase plan",
    "pre-expand readiness": "complete the plan's `Operator readiness` gate before the first production schema operation",
    "step 4.1 exit": "before production Expand begins",
    "pre-contraction recovery gate": "every phase-status item through `Recovery` must be checked with evidence before contraction begins",
    "step 4.4 exit": "every item in `## Database Migration Phase Status` must also be checked with evidence",
    "overall completion": "additional completion gates. The generic four gates never override or replace them",
    "historical migration references retained": "retain required migration-history and audit artifacts",
    "application removal before contraction": "first deploy and verify removal or disablement of legacy application reads and writes while the expanded schema remains",
    "standalone contraction deployment": "Contract the old schema shape only in a separate later deployment",
}
missing = [name for name, phrase in required_skill.items() if phrase not in skill]
phase_section = skill.split("## Database Migration Phase Status", 1)[1].split("```", 1)[0]
expected_phases = [
    "Operator readiness",
    "Expand",
    "Transitional writes",
    "Backfill",
    "Read cutover",
    "Observation",
    "Recovery",
    "Contract",
]
phase_entries = re.findall(
    r"^- \[ \] ([^—\n]+?) —(.+)\n  - Evidence: (.+)$",
    phase_section,
    re.MULTILINE,
)
actual_phases = [name for name, _description, _evidence in phase_entries]
if actual_phases != expected_phases:
    missing.append("ordered database phases with paired evidence fields")
phase_descriptions = {name: description for name, description, _evidence in phase_entries}
phase_requirements = {
    "Operator readiness": ["datastore owner reviewed", "commands and recovery actions were rehearsed"],
    "Expand": ["additive schema supports every named old/new application combination"],
    "Transitional writes": ["partial-failure", "retry", "ordering", "repair", "observable"],
    "Backfill": [
        "every retained record and value required by the new contract is covered",
        "every exclusion has an explicit safe disposition",
        "reconciliation passes",
        "batching/throttling",
    ],
    "Read cutover": ["deployed independently", "rollback remains schema-compatible", "old writes remain supported"],
    "Observation": ["named window passed", "without an unresolved regression"],
    "Recovery": ["recovery was tested for each phase", "verified backup or restoration source", "rather than a schema-only down migration"],
    "Contract": ["no longer require the old shape before destructive removal"],
}
for phase, phrases in phase_requirements.items():
    description = phase_descriptions.get(phase, "")
    missing.extend(f"{phase} semantics: {phrase}" for phrase in phrases if phrase not in description)
required_patterns = {
    "reference-to-plan authority": "authoritative resumable state",
    "operator readiness before expand": "before the first production schema operation",
    "complete retained-data coverage": "Every retained record and value required by the new contract is covered",
    "new-only writes before contraction": "Verify new-only writes, then remove `name` in a later contraction",
    "standalone destructive contraction": "perform destructive removal as its own deployment",
}
missing.extend(name for name, phrase in required_patterns.items() if phrase not in patterns)
raise SystemExit("missing database phase-state contracts: " + ", ".join(missing) if missing else 0)
PY
	[ "$status" -eq 0 ] || { echo "$output"; false; }
}

@test "database expansion preserves mixed-version write compatibility" {
	run python3 - "$MIGRATION_PATTERNS" <<'PY'
import pathlib
import sys

text = pathlib.Path(sys.argv[1]).read_text()
database_pattern = text.split("## Database Expand/Migrate/Contract", 1)[1].split("## Pattern comparison", 1)[0]
expand_phase = database_pattern.split("**Step 4.1 —", 1)[1].split("**Step 4.2 —", 1)[0]
required = {
    "old application compatibility": "Prove the old application against the expanded schema",
    "pre-write compatibility state": "expanded schema before transitional writes or backfill",
    "partially migrated compatibility state": "partially migrated data while old and new shapes coexist",
    "supported mixed-version matrix": "Name every supported mixed-version combination",
    "constraint compatibility": "compatibility-preserving for old writers",
    "deferred enforcement": "defer incompatible enforcement or validation until those writers are absent",
}
missing = [name for name, phrase in required.items() if phrase not in expand_phase]
raise SystemExit("missing mixed-version compatibility contracts: " + ", ".join(missing) if missing else 0)
PY
	[ "$status" -eq 0 ] || { echo "$output"; false; }
}

@test "deprecation stop rules have authoritative workflow owners" {
	local remove_old
	local verification

	remove_old="$(sed -n '/^### 4.4 Remove old$/,/^---$/p' "$SKILL")"
	verification="$(sed -n '/^## Verification$/,$p' "$SKILL")"

	grep -qF "Execute in order. Do not compress or overlap" "$SKILL"
	grep -qF "Do not remove zombie code. Do not proceed past this step." "$SKILL"
	grep -qF 'Before executing this step, resolve every open `UNVERIFIED` from any step.' <<<"$remove_old"
	grep -qF 'ASK FIRST: removing with open UNVERIFIED markers' <<<"$remove_old"
	grep -qF "and do not proceed" <<<"$remove_old"
	grep -qF "no active consumer or obsolete application reference remains" "$SKILL"
	grep -qF 'Completion state is owned by `DEPRECATION_PLAN_<slug>.md`.' "$SKILL"
	grep -qF "Do not close the deprecation or replace a missing gate with a follow-up." <<<"$verification"
}

@test "code with unique value is kept and maintained in both the instructions and the decision tree" {
	run python3 - "$SKILL" "$DECISION_CHECKLIST" <<'PY'
import pathlib
import sys

skill = pathlib.Path(sys.argv[1]).read_text()
checklist = pathlib.Path(sys.argv[2]).read_text()

step_one = skill.split("## Step 1 —", 1)[1].split("## Step 2 —", 1)[0]
question_one = next(line for line in step_one.splitlines() if line.startswith("1. **"))
checklist_q1 = checklist.split("## 1. Does this code still provide unique value?", 1)[1].split("---", 1)[0]
tree = checklist.split("## Decision tree", 1)[1].split("```", 2)[1]
q1_branches = [
    line.strip()
    for line in tree.split("Q1:", 1)[1].split("Q3:", 1)[0].splitlines()
    if line.strip().startswith(("├─", "└─"))
]
checklist_q3 = checklist.split("## 3. Does a replacement exist?", 1)[1].split("---", 1)[0]

missing = []
if "If yes, do not deprecate: keep and maintain the code, record `Outcome: Keep and maintain` with a revisit trigger" not in question_one:
    missing.append("Step 1 question 1 keeps and maintains with a revisit trigger")
if "callers still need a capability that no existing or committed replacement is meant to provide" not in checklist_q1:
    missing.append("checklist question 1 uses the committed-replacement definition")
if "a clear YES means keep and maintain the code. Record `Outcome: Keep and maintain` with a revisit trigger and stop" not in checklist_q1:
    missing.append("checklist question 1 outcome")
if len(q1_branches) != 2 or "YES → Keep and maintain; record revisit trigger; stop" not in q1_branches[0] or not q1_branches[1].endswith("NO"):
    missing.append("decision tree question 1 has only the Keep and maintain and NO branches")
if "with a revisit trigger (a replacement is committed with an owner, scope, and plan" not in question_one:
    missing.append("Keep trigger waits for a committed replacement")
if "proposed but not committed" in checklist_q3:
    missing.append("checklist question 3 keeps the unreachable proposed-replacement signal")
if "**Committed, not built** — name it. Step 4.1 (Build the replacement) builds and verifies it _before_ any announcement" not in checklist_q3:
    missing.append("checklist question 3 continues a committed replacement")
raise SystemExit("unique-value outcome disagrees: " + ", ".join(missing) if missing else 0)
PY
	[ "$status" -eq 0 ] || { echo "$output"; false; }
}

@test "the decision step weighs migration against keeping and records a defer outcome" {
	run python3 - "$SKILL" "$DECISION_CHECKLIST" <<'PY'
import pathlib
import sys

skill = pathlib.Path(sys.argv[1]).read_text()
checklist = pathlib.Path(sys.argv[2]).read_text()

step_one = skill.split("## Step 1 —", 1)[1].split("## Step 2 —", 1)[0]
weigh = checklist.split("## Weigh migration against keeping", 1)[1].split("---", 1)[0]
tree = checklist.split("## Decision tree", 1)[1].split("```", 2)[1]
tree_lines = tree.splitlines()
keeping = next(i for i, line in enumerate(tree_lines) if "keeping cheaper?" in line)
verification = skill.split("## Verification", 1)[1]
required = {
    "Step 1 compares total effort with keeping cost": (step_one, "the total migration effort across every dependent from question 4"),
    "Step 1 keeping side": (step_one, "against the cost of keeping the old code from question 5"),
    "Step 1 defer outcome": (step_one, "When keeping the old code is cheaper, record `Outcome: Defer` with a revisit trigger"),
    "Step 1 stops before announcing": (step_one, "stop without announcing anything"),
    "Step 1 records the outcome": (step_one, "Record the answers and the outcome"),
    "checklist defer outcome": (weigh, "When keeping is cheaper, record `Outcome: Defer` with a revisit trigger"),
    "decision tree defers when keeping is cheaper": (tree_lines[keeping + 1], "YES → Defer; record revisit trigger; stop"),
    "plan template outcome field": (skill, "- Outcome: <Deprecate | Keep and maintain | Defer> Revisit trigger:"),
    "resume checks the archived revisit trigger": (skill, "durable project docs archive a Keep and maintain or Defer decision for the target, check its revisit trigger before anything else"),
    "resume stops on an unfired trigger": (skill, "otherwise report the archived decision and stop"),
    "verification closes archived decisions": (verification, "A Keep and maintain or Defer outcome closes the workflow once the outcome and its revisit trigger are archived in durable project docs and the plan is deleted"),
    "decision is archived, not kept in the disposable plan": (skill, "For a Keep and maintain or Defer outcome, archive the outcome and its revisit trigger in durable project docs"),
}
missing = [name for name, (text, phrase) in required.items() if phrase not in text]
raise SystemExit("missing defer-outcome contracts: " + ", ".join(missing) if missing else 0)
PY
	[ "$status" -eq 0 ] || { echo "$output"; false; }
}

@test "an announced deprecated surface is frozen to the fixes its consumers need" {
	local announce

	announce="$(sed -n '/^### 4.2 Announce \/ document$/,/^### 4.3 /p' "$SKILL")"

	grep -qF "Once the deprecation is announced, freeze the old surface: it gets only the security and correctness fixes its remaining consumers need" <<<"$announce"
	grep -qF 'Adding functionality to the old surface requires `ASK FIRST: adding functionality to a deprecated surface`' <<<"$announce"
	grep -qF "or adding functionality to an announced deprecated surface (see Step 4.2)" "$SKILL"
}

@test "advisory deprecations log callers on a cadence and escalate a stall or expired window" {
	run python3 - "$SKILL" <<'PY'
import pathlib
import sys

skill = pathlib.Path(sys.argv[1]).read_text()

migrate = skill.split("### 4.3 Migrate incrementally", 1)[1].split("### 4.4 Remove old", 1)[0]
check = next(line for line in migrate.splitlines() if line.startswith("**Advisory progress check.**"))
announce = skill.split("### 4.2 Announce / document", 1)[1].split("### 4.3 Migrate incrementally", 1)[0]
step_two = skill.split("## Step 2 —", 1)[1].split("## Zombie-code gate", 1)[0]
required = {
    "fixed cadence logging": (check, "log the remaining-caller count in `## Migration Log` at the plan's caller-count cadence"),
    "stall counts start at a dated boundary": (check, "Count only remaining-caller entries dated after the latest `announced` or `progress decision` entry."),
    "stall judged on the latest entries": (check, "Migration has stalled when the latest of those entries shows no fewer callers than the one before it"),
    "Step 4.2 logs the announced boundary": (announce, "Once the exit criterion is met, log a dated `announced` entry in `## Migration Log`."),
    "template has dated boundary entries": (skill, "- <date>: announced (Step 4.2 exit criterion met)"),
    "template has dated progress decisions": (skill, "- <date>: progress decision: <take over, new target removal date YYYY-MM-DD"),
    "stall with no take-over or reclassification re-runs Step 1": (check, "If you cannot migrate the remaining callers and the reclassification is declined, re-run Step 1 with current evidence and record its outcome as the progress decision"),
    "expired window definition": (check, "the window has expired when the target removal date passes with callers remaining"),
    "stall or expiry requires taking over or reclassifying": (check, "Either one requires a decision, logged as a dated `progress decision` entry and recorded in `## Decisions`: take over the remaining migrations yourself under the Churn Rule and set a new target removal date, or reclassify to Compulsory with a new date, subject to Step 2's `ASK FIRST` rules."),
    "Step 2 allows reclassifying a stall": (step_two, "or a Step 4.3 Advisory progress decision chooses to reclassify a stalled or expired window"),
    "Advisory needs a date and cadence": (step_two, "the window still needs a target removal date and a caller-count cadence"),
    "Step 2 gate requires the date and cadence": (skill, "- [ ] Step 2 classification recorded; an Advisory deprecation also has a target removal date and a caller-count cadence."),
    "plan template cadence field": (skill, "Caller-count cadence: <monthly | per release | n/a for Compulsory>"),
    "resume runs the progress check": (skill, "For an Advisory deprecation with an `announced` entry in `## Migration Log`, run the Step 4.3 Advisory progress check before resuming."),
}
missing = [name for name, (text, phrase) in required.items() if phrase not in text]
raise SystemExit("missing advisory progress contracts: " + ", ".join(missing) if missing else 0)
PY
	[ "$status" -eq 0 ] || { echo "$output"; false; }
}

@test "the deprecation source rationale names the adopted guardrail ideas" {
	run python3 - "$PLUGIN_ROOT/skills/code:deprecate/references/sources.yaml" <<'PY'
import pathlib
import sys

text = pathlib.Path(sys.argv[1]).read_text()
entry = text.split("id: addy-deprecation-and-migration", 1)[1].split("  - id:", 1)[0]
required = [
    "usage: inspiration",
    "Deprecation Decision section",
    "keeping and maintaining code that still provides unique value",
    "weighing total migration effort against the cost of keeping the old code",
    "Keep and maintain and Defer outcomes with revisit triggers",
    "Compulsory vs Advisory Deprecation section",
    "Red Flags",
    "freeze on new functionality once a deprecation is announced",
    "Advisory progress check",
]
missing = [phrase for phrase in required if phrase not in entry]
raise SystemExit("source rationale misses: " + ", ".join(missing) if missing else 0)
PY
	[ "$status" -eq 0 ] || { echo "$output"; false; }
}
