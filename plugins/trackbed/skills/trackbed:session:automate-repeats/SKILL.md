---
name: trackbed:session:automate-repeats
description: Reviews recent agent sessions for repeated work, recurring friction, and evidence-backed skill effectiveness, then reports improvements to the existing owner before proposing or scaffolding new automation. Use when asked to inspect recent sessions, find automation opportunities, improve a skill from its runs, determine which skills are working, or turn repeated work into reusable workflows. Not for summarizing one session, general retrospectives, or codebase refactoring.
argument-hint: "[session-paths or --recent N] [--effectiveness] [--create|--auto]"
disable-model-invocation: true
user-invocable: true
---

# Automate Repeated Session Work

Find repeated work and recurring friction in recent agent sessions, optionally evaluate whether eligible skills were invoked effectively, propose improvements to the existing component that owns the work, and turn only the genuinely uncovered patterns into simple new skills or custom subagents.

## Boundaries

- Use this for session-history mining, repeated-ask detection, existing-component improvement proposals, and automation candidate creation.
- Use `--effectiveness` when the user wants evidence about which skills are working from real runs. Treat its counts as diagnostic sample evidence, never as an objective grade.
- Do not use this to summarize one session, write a personal retrospective, review code, or create broad "do everything" agents.
- Improvements to existing components are report-only. This skill never edits, rewrites, or scaffolds over an existing skill or subagent; applying a proposed improvement is a separate follow-up the user must request explicitly.
- Treat session logs as private. Use this skill's safe metadata and skeleton extractors before reading content. Paraphrase evidence unless a short exact phrase is necessary to justify a candidate. Do not copy secrets, customer data, tokens, raw tool payloads, or long user messages into generated files.

## Workflow

Before Step 1, parse `$ARGUMENTS` for `--auto` and `--effectiveness`. Treat `--auto` as an alias for `--create`: remove it from the remaining source arguments and scaffold the selected candidates after the usefulness gate. Remove `--effectiveness` from source arguments and enable the effectiveness evidence pass in Steps 4-5. Neither flag bypasses missing session-source handling or existing-destination protection, and neither grants authority to edit an existing skill or subagent.

1. Resolve the session extraction scripts.
   - Resolve `<skill-dir>` as the directory containing this `SKILL.md` and `<skills-root>` as its parent. Use the scripts at `<skill-dir>/scripts/` in both the source checkout and an installed plugin; call this path `<session-scripts>` below.
   - Required scripts: `discover-sessions.sh`, `extract-metadata.py`, `extract-skeleton.py`, and `extract-errors.py`. When `--effectiveness` is active, also require `extract-skill-usage.py`.
   - If the script set is unavailable, stop with `MISSING REQUIREMENT: session extraction scripts are not installed`.

2. Resolve the session source without reading raw transcripts into context.
   - If `$ARGUMENTS` includes files or directories, validate those exact paths. If an explicitly provided path is missing or unreadable, stop and report it instead of falling back to default stores. Expand directories to readable `*.jsonl` files and pass the file list to `extract-metadata.py`.
   - If `$ARGUMENTS` includes `--recent N`, discover sessions for the current repo, sort metadata by `last_ts`/`ts`/mtime, and keep the N most recent readable sessions.
   - Otherwise, discover sessions for the current repo over the last 30 days. First collect `SESSION_PREFIXES`: the repository root and every `worktree` path from `git worktree list --porcelain`. When the root matches `*/conductor/workspaces/<repo>/<workspace>`, use `*/conductor/workspaces/<repo>` instead, so sessions from the repository's other Conductor workspaces count. Pass every prefix to discovery and to the metadata pass, which keeps only sessions whose recorded working directory is at or below a prefix. A similarly named repository or a session started in a parent directory then does not count:
     ```bash
     REPO_NAME=$(basename "$(git rev-parse --show-toplevel)")
     PREFIX_ARGS=() FILTER_ARGS=()
     for prefix in "${SESSION_PREFIXES[@]}"; do
       PREFIX_ARGS+=(--cwd-prefix "$prefix")
       FILTER_ARGS+=(--cwd-filter "$prefix")
     done
     bash "<session-scripts>/discover-sessions.sh" "$REPO_NAME" 30 "${PREFIX_ARGS[@]}" \
       | tr '\n' '\0' \
       | xargs -0 python3 "<session-scripts>/extract-metadata.py" "${FILTER_ARGS[@]}"
     ```
   - Discovery reads Claude Code and Codex stores from `CLAUDE_CONFIG_DIR` and `CODEX_HOME` when they are set.
   - Prefer JSONL session files sorted by recency. Cap the metadata pass at about 30 sessions and the skeleton deep dive at 10 sessions. Skip parse failures and list them under `UNVERIFIED`. Report `files_without_metadata` separately: those files held no session the extractor recognizes, so they are not parse failures.
   - If no session source is readable, ask for an export path and stop.

3. Extract safe skeletons into scratch.
   - Create `.context/session-search/<timestamp>/automate-repeats/`.
   - For each selected session, run:
     ```bash
     python3 "<session-scripts>/extract-skeleton.py" --output "$SCRATCH/<session-id>.skeleton.txt" < "$SESSION_FILE"
     ```
   - Run `extract-errors.py` only for sessions where failed commands appear likely to explain a repeated workflow.
   - Read only the scratch skeleton/error files and metadata for pattern analysis. Never read raw transcript files directly.

4. Build an inventory of existing automation before proposing anything.
   - Always read sibling skill frontmatter from `<skills-root>/*/SKILL.md`, using the installed or source-checkout root resolved in Step 1. Also read workspace-local skill frontmatter from `skills/*/SKILL.md`, `.claude/skills/*/SKILL.md`, `.agents/skills/*/SKILL.md`, `trackbed/skills/*/SKILL.md`, or any explicit skill directory in the current workspace. Deduplicate the trusted inventory by frontmatter `name`.
   - Also read the frontmatter of user-level skills: the `skills/*/SKILL.md` entries in the Claude Code configuration directory (`CLAUDE_CONFIG_DIR`, by default `.claude` in the home directory), in the home directory's `.agents`, and in the Codex home (`CODEX_HOME`, by default `.codex` in the home directory), plus the workspace's `.codex/skills/*/SKILL.md`. Sessions invoke these skills too. Without them, an invocation of one counts as an unknown name, and a new candidate can duplicate one unnoticed. Read frontmatter only. A user-level skill with no local Git history gets per-pair `UNVERIFIED` availability under Step 5's historical-contract gate.
   - Treat this current inventory as the extractor allowlist and routing inventory only. Its presence does not prove that a skill or its current contract existed during a historical session.
   - Read existing subagent frontmatter from `agents/*.md`, `trackbed/agents/*.md`, `.claude/agents/*.md`, or any explicit agent directory in the current workspace.
   - Record likely overlaps by name, description, and trigger phrases.

5. When `--effectiveness` is active, build an eligibility-aware evidence table.
   - Establish a trustworthy session start time from transcript-derived metadata `ts`. Do not use `last_ts` or filesystem mtime as proof that a skill was available when the session began. If the start time is missing, malformed, or derived only from mtime, mark availability evidence for that session `UNVERIFIED`.
   - Before deciding eligibility, resolve the exact historical contract for each candidate skill as of the session start. Prefer complete local Git history: select the latest committed revision no later than the session timestamp, require that revision to contain the skill definition with the exact frontmatter `name`, and read that historical `SKILL.md` body. Follow recorded path renames only to find history; never project a later name or contract backward. Immutable local release or installation provenance may substitute only when it identifies the exact bundled contract and proves it was available by the session start.
   - If complete history proves that the exact skill name and contract were absent at the session start, classify the pair as **not available** and exclude it from eligibility, correct-invocation, missed-invocation, and suspected-false-invocation counts. If exact historical availability or contract contents cannot be established, classify the pair as **UNVERIFIED** and exclude it from those counts. Current contracts, current file timestamps, and observed invocation alone are not sufficient historical-contract evidence.
   - Decide eligibility from each safe skeleton's user ask and the verified historical contract before reading detected usage. Eligibility means that contract's documented trigger and boundaries fit the task; do not infer eligibility merely because a skill was invoked.
   - For every selected session, run:
     ```bash
     KNOWN_SKILL_ARGS=(--known-skill "<name>" ...) # one entry per Step 4 inventory name
     python3 "<session-scripts>/extract-skill-usage.py" "${KNOWN_SKILL_ARGS[@]}" --output "$SCRATCH/<session-id>.skill-usage.json" < "$SESSION_FILE"
     ```
   - Build `KNOWN_SKILL_ARGS` only from the trusted installed-skill inventory in Step 4. Pass `--known-skill "<name>"` once per inventory entry; never derive this allowlist from transcript content.
   - Read only the resulting skill names and diagnostics. The extractor must never emit transcript text, tool payloads, commands, transcript-derived paths, reasoning, or unrecognized candidate values. If it cannot write output, reports parse errors, or reports `near_miss_skill_events`, mark that session's invocation evidence `UNVERIFIED`; never fall back to reading raw transcripts or treat an unknown name as invoked. A near miss is an unknown name that resembles an inventory skill, such as a misspelling, which could otherwise turn into a false missed invocation. When it reports `unknown_skill_events` with no near misses, such as host commands like `/model` or another plugin's skills, keep the session's evidence and ignore those names. A missing required extractor already stops the workflow in Step 1.
   - Only after the historical-contract gate, classify each verified-available skill/session pair as **correct invocation** when eligible and invoked, **missed invocation** when eligible and not invoked, or **suspected false invocation** when invoked but not eligible. Count recurring friction separately when an eligible invocation still required repeated correction, failed assumptions, or avoidable rework.
   - Record artifact-quality evidence only when a session-linked diff or other reviewable artifact is available. Skeletons and successful tests alone are insufficient to judge code quality; otherwise record `insufficient evidence`.
   - Write `$SCRATCH/effectiveness.json` with session identifiers and per-skill arrays for `eligible`, `correct_invocations`, `missed_invocations`, `suspected_false_invocations`, `not_available`, `unverified_availability`, `friction`, and `artifact_quality_evidence`. Store no transcript excerpts or tool payloads.
   - Report one row per eligible or invoked skill: skill, eligible sessions, correct invocations, missed invocations, suspected false invocations, not-available sessions, unverified-availability sessions, friction sessions, artifact-quality evidence, and verified sample size. Do not calculate a coverage score, weighted overall score, or letter grade. Invocation frequency is not effectiveness, and zero use alone never justifies changing a skill.

6. Extract repeated patterns and recurring friction from the safe skeletons.
   - Group similar user asks, manual command sequences, review rituals, debugging loops, release steps, docs updates, CI-fix loops, test triage, changelog work, and PR-prep tasks.
   - Group friction signals that recur while an existing component is already in use: the user having to clarify or re-steer the same point, failed commands and wrong tool or path assumptions, steps the user repeatedly skips or undoes as unnecessary, stale paths, commands, or versions, and context the agent had to be handed every run.
   - Treat a prompt-footprint or contract warning from the destination repo's own skill linter, where one exists, as corroborating evidence for a friction signal, never as a candidate on its own.
   - Count independent evidence by session, not just repeated messages inside one session.
   - Preserve the user's phrasing as labels in private notes, but report paraphrased evidence.
   - Ignore one-off tasks, vague preferences, personal style notes, and work an existing skill or agent already handles without recurring friction.

7. Classify each candidate, asking whether an existing component already owns the work before considering a new one.
   - Recommend **IMPROVE EXISTING** when one existing skill or subagent clearly owns the behavior and the recurring friction points at a defect in that component's contract, or at a small variation of it, rather than at a missing entry point. Name the single owning component; if two or more components could own the work, or none does, do not use this classification.
   - Treat repeated missed invocations as a routing defect of the skill that should have run. When Step 5 records the same skill as a missed invocation in at least two independent sessions, and those sessions also show friction from doing its job by hand, consider **IMPROVE EXISTING** with that skill's `description` as the candidate contract defect. Step 6 counts friction only while a component is in use, so repeated misses otherwise fall through both routes.
   - Before recording `IMPROVE EXISTING`, read the owning component's file body, not just the frontmatter collected in Step 4, so the contract defect and proposed change name real steps, boundaries, or fields.
   - Recommend a **skill** when the repeated work is a reusable workflow with ordered steps, decision gates, side effects, or orchestration across tools, and no existing component owns it.
   - Recommend a **custom subagent** when the repeated work is a bounded role or investigation lens with a stable mission, clear inputs, and a repeatable output format, and no existing component owns it.
   - Reject candidates that need broad judgment across many domains, duplicate existing components, depend on unavailable tools, or cannot be explained in a short trigger description.

8. Apply the usefulness and counterfactual gates.
   - A candidate is useful only if it has evidence from at least 2 independent sessions or at least 3 clearly separate asks, a clear trigger, a narrow scope, low overlap with existing automation, and a simple implementation.
   - Hold `IMPROVE EXISTING` to the same evidence bar. Never propose an improvement from a single session or a single model failure, however severe that one run looked.
   - Test causality before changing a contract: identify the missing, incorrect, or underspecified instruction, then explain how the proposed rule closes that exact gap. If the current contract already specifies the correct behavior, classify the event as model variance or a failure outside instruction surfaces instead of duplicating guidance. For a missed-invocation route, eligibility already means the documented trigger fit the ask, so ask instead whether the `description` gave the model a distinctive cue for how those sessions phrased the ask, especially next to overlapping sibling descriptions; covering the ask on paper is not enough.
   - Edit the narrowest existing rule in place; add new prose only when no current rule owns the behavior. Name the one owning surface and the smallest reusable behavioral rule that closes the verified gap.
   - Cap and rank the two classes separately: keep the default to 1-3 new skill or subagent candidates and 1-3 `IMPROVE EXISTING` proposals, ranking within each class by time saved and frequency. Never drop a qualified improvement to make room for a new component.
   - Mark weaker ideas as `NOT CREATED` with a one-line reason instead of scaffolding or proposing them.

9. Report qualified existing-component improvements instead of applying them.
   - Report each one under `IMPROVE EXISTING` with six fields: affected component name and path, independent evidence count, paraphrased symptom, likely contract defect, proposed change, and how to verify the change worked.
   - State the proposed change as a concrete contract edit to that component, not as a wish. Name the step, boundary, or field to change and what it should say instead.
   - Paraphrase every symptom and name only components, files, and paths. Never quote private session content, secrets, customer data, tokens, or raw tool payloads in a proposal.
   - This report is the whole output for these candidates under every flag, including `--create` and `--auto`. Do not edit the affected component, and tell the user that applying the improvement is a separate follow-up they must request explicitly.

10. Present a compact plan before writing files unless the user explicitly requested hands-off creation.

- Include: candidate name, skill vs subagent, evidence count, destination path, and why it passes the usefulness gate.
- If the user asked only to "suggest", stop after the report.
- If the user said "create", passed `--create` or `--auto`, or confirms the plan, scaffold the selected new candidates. `IMPROVE EXISTING` candidates are never scaffolded or applied here.

11. Scaffold skills simply.
    - Use `skills/{skill-name}/SKILL.md` when the current workspace's skill root is `skills/`; use `trackbed/skills/{skill-name}/SKILL.md` when that plugin layout exists.
    - If the destination path already exists, do not overwrite it. Skip the candidate and report it under `NOT CREATED` with reason `already exists`.
    - Use names in the form `trackbed:{domain}:{action}` when adding to this plugin-style tree.
    - Include frontmatter fields: `name`, `description`, `disable-model-invocation`, and `user-invocable`; add `argument-hint` only when useful. Set `disable-model-invocation: true` for any generated skill with side effects (file writes, git, network, deletion); otherwise `false`.
    - Keep each generated `SKILL.md` focused on the workflow. Avoid placeholder docs, READMEs, and large reference files unless the candidate truly needs them.

12. Scaffold subagents simply.
    - Use `agents/{agent-name}.md` when the current workspace's agent root is `agents/`; use `trackbed/agents/{agent-name}.md` when that plugin layout exists.
    - If the destination path already exists, do not overwrite it. Skip the candidate and report it under `NOT CREATED` with reason `already exists`.
    - Include frontmatter fields: `name`, `description`, `model`, and `color`.
    - Keep the body to mission, scope boundaries, analysis process, and output format.
    - Make the agent read-only by default unless the role explicitly requires edits and the user's request authorizes side effects.

13. Update local indexes only when required by the destination repo's own instructions.
    - If a README or published skill index already lists all skills or agents, add concise rows for new components.
    - Update any visible skill or agent count in the same file when it is clearly maintained by hand.
    - Do not add extra documentation files inside the new skill or agent directories.

14. Close with an audit-style summary that keeps each outcome separate.
    - `REVIEWED`: session source count and date range if known.
    - `EFFECTIVENESS`: when requested, the eligibility-aware evidence table and the path to `effectiveness.json`.
    - `IMPROVE EXISTING`: proposed improvements to existing components, each with its owning component and evidence count, reported as proposals only.
    - `CREATED`: paths for any new skills or agents.
    - `NOT CREATED`: rejected repeated ideas and improvement proposals, with one-line reasons.
    - `UNVERIFIED`: any session stores, counts, or assumptions that could not be checked.

## Source Tracking

`references/sources.yaml` records the upstream `ce-compound` session-history scripts copied for discovery and extraction, the PostHog agent-skills post for the run-evidence improvement framing, and Warp's skill-doctor workflow, rubrics, collector, and improvement gate for eligibility-aware effectiveness evidence. Do not load it during normal use unless auditing or updating source attribution.

## Artifact Lifecycle

This skill writes safe extraction artifacts under `.context/session-search/<timestamp>/automate-repeats/`. The current run consumes skeletons, error summaries, skill-use evidence, and optional `effectiveness.json`; sibling agents may reuse them inside the same Conductor workspace. Refresh them by rerunning this skill. Retire them with `trackbed:workflow:cleanup-artifacts` or delete the matching run directory when the workspace no longer needs the evidence.
