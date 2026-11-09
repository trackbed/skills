---
name: docs:update-agents-md
description: This skill should be used when the user asks to "update AGENTS.md", "add to AGENTS.md", "maintain agent docs", add the Hard-Cut Greenfield Policy or no-compatibility-code policy, or otherwise add guidelines to agent instructions. Verifies that every cited path, command, and skill exists, edits only AGENTS.md when CLAUDE.md just imports it, and enforces a structured, keyword-based style without listing installed skills.
disable-model-invocation: true
user-invocable: true
---

# Adding to AGENTS.md

AGENTS.md is the canonical agent-facing documentation. If a project uses `CLAUDE.md` or another equivalent instruction file instead, apply the same structure there. Many rules are OK.

## Context Pointer Model

Use `AGENTS.md` as a routing map, not a warehouse. A Context Pointer is a concise link from an agent-facing rule to deeper context: a skill, doc, script, module, test suite, schema, runbook, ADR, or example file.

A strong Context Pointer includes:

- **Target** — the exact file, command, module, or skill to open or run
- **Trigger** — when the agent should follow it
- **Purpose** — what the target answers or governs

Prefer Context Pointers when the detail would make `AGENTS.md` long, duplicate another source of truth, or apply only to a subset of tasks.

## Before Writing

Resolve the target file first:

- Detect existing instruction files: `AGENTS.md`, `CLAUDE.md`, or another equivalent.
- If several exist, prefer `AGENTS.md`.
- When `CLAUDE.md` or another instruction file only imports, links, or symlinks `AGENTS.md` (for example a lone `@AGENTS.md` line), edit `AGENTS.md` alone and leave the importing file untouched.
- When another instruction file keeps its own separate copy of the rules, do not write the new rules into both; edit `AGENTS.md` and report the separate copy so the user can merge it or point it at `AGENTS.md`.
- If none exists, create `AGENTS.md`.
- **ALWAYS** read the chosen file in full before proposing edits, so additions reconcile with what is already there.
- **ALWAYS** show the planned additions (or a diff) and apply them after confirmation — this file governs all future agent behavior. Run **Verify Pointers** below first, so the plan cites only pointers that exist.

Discover local skills so new rules do not repeat their content (skill directories vary by harness — adjust paths to the local layout):

```bash
find .claude/skills .agents -name "SKILL.md" 2> /dev/null
ls plugins/*/skills/*/SKILL.md 2> /dev/null
```

Read each skill's frontmatter to learn what it already covers. Do not add a list of installed skills: the host already shows them, and a list goes stale on every rename. Add a skill pointer only when the rule gives a trigger or requirement the skill's own description lacks.

Map existing context before editing:

```bash
find . -maxdepth 3 \
  \( -type d \( -name ".git" -o -name ".context" -o -name "node_modules" -o -name "dist" -o -name "build" -o -name ".next" -o -name ".nuxt" -o -name "coverage" -o -name ".venv" -o -name "venv" -o -name "target" \) -prune \) -o \
  -type f \( -name "*.md" \) -print 2> /dev/null
find . -maxdepth 3 \
  \( -type d \( -name ".git" -o -name ".context" -o -name "node_modules" -o -name "dist" -o -name "build" -o -name ".next" -o -name ".nuxt" -o -name "coverage" -o -name ".venv" -o -name "venv" -o -name "target" \) -prune \) -o \
  -type f \( -name "*schema*" -o -name "*registry*" -o -name "*routes*" -o -name "index.*" \) -print 2> /dev/null
```

Identify existing docs, scripts, modules, examples, and skills that should be pointed to instead of duplicated.

## Adding the Hard-Cut Greenfield Policy

When asked to add the Hard-Cut Greenfield Policy or no-compatibility-code policy, read `assets/greenfield-policy.md` and follow every insertion guard. Apply it only to projects with no released users; if the project has users, stop and report that the policy does not apply.

The policy block is an explicit verbatim-template exception to the **One rule per bullet**, **Start with keyword**, **Headers + bullets**, **Reference, don't duplicate**, and **Context Pointers over pasted detail** writing rules below. Do not rewrite the block or replace it with a pointer. All non-formatting safeguards still apply, including reading the target in full, showing the planned diff for confirmation, checking for an existing policy heading, and re-reading the inserted block.

## Guideline Keywords

Use these keywords to indicate requirement strength:

- **ALWAYS** — Mandatory requirement
- **NEVER** — Strong prohibition
- **PREFER** — Strong recommendation, exceptions allowed
- **CAN** — Optional, developer's discretion
- **NOTE** — Context or clarification
- **EXAMPLE** — Illustrative example

Strictness hierarchy: ALWAYS/NEVER > PREFER > CAN > NOTE/EXAMPLE

## Writing Rules

- **Existing sections first** - Only propose new sections if no appropriate existing section exists
- **Reconcile, don't append** - Before adding a rule or Context Pointer, check whether an equivalent already exists; update it in place instead of duplicating. Re-running this skill must not create duplicate rules or sections
- **One rule per bullet** - Keep each authored guideline minimal and atomic; explicitly marked verbatim templates are exempt
- **Start with keyword** - Every authored rule begins with ALWAYS/NEVER/PREFER/CAN/NOTE; explicitly marked verbatim templates are exempt
- **Headers + bullets** - Use no paragraphs in authored guidance; explicitly marked verbatim templates are exempt
- **Code blocks** - For commands and templates
- **Reference, don't duplicate** - Point to the doc, script, or skill that holds the detail instead of copying it; point to a skill only when the rule adds a trigger or requirement its description lacks
- **Context Pointers over pasted detail** - Point to deeper docs, scripts, modules, tests, schemas, or ADRs with a clear when/why cue
- **One hop** - Important pointers should be directly visible from the active agent instruction file; avoid chains of documents that only point to more documents
- **Enforce before instructing** - Before adding a rule that steers agents around the code's structure ("when you change X, also update Y", "never import from `foo/internal`"), check whether a lint rule, type, test, or script could enforce it, or whether the rule papers over scattered code that a refactor should fix; propose that alternative alongside the rule, and suggest `/trackbed:code:encode-constraint` to build and prove the check, or `/trackbed:code:refactor-opportunities` to assess the refactor
- **No filler** - No intros, conclusions, or pleasantries

## Verify Pointers

Before showing the planned additions, check every path, script, command, and skill name an authored rule cites:

- **Path or script** — confirm it exists, resolving repository paths from the root and Markdown links from the instruction file's directory. For a placeholder or glob such as `packages/<name>/src/`, confirm its fixed parent exists.
- **Command** — find the package script, make target, or task-runner entry that defines it, such as a `package.json` script, a `Makefile` target, or a `justfile` or `Taskfile` task. For a standalone tool, find where the project installs or configures it.
- **Skill** — find its `SKILL.md` among the discovered skills, or confirm the host lists it as available.

Fix a failing pointer when the correct target is clear; otherwise drop it. Never write a rule that cites a pointer that failed the check. List every fixed or dropped pointer in the plan and the final report.

## After Writing

- Re-read the edited region.
- **ALWAYS** confirm each authored bullet starts with a keyword and states exactly one rule; for an explicitly marked verbatim template, confirm the inserted block matches its source exactly instead.
- **ALWAYS** confirm no rule or section was duplicated.

## Common Sections

Add sections as needed for the project:

### Context Map

Use this authoring example when the repo has multiple important docs, skills, scripts, or subsystems:

```markdown
## Context Map

- **ALWAYS** read `docs/architecture.md` before changing module boundaries
- **ALWAYS** run `scripts/verify.sh` before claiming local verification; see `docs/testing.md` only for suite-specific details
- **PREFER** `packages/api/src/routes/index.ts` as the entry point for API route discovery
- **CAN** run `scripts/db-migrate.sh` to generate a migration after changing `db/schema.sql`
```

### Module Map

Use this authoring example when the top-level modules are not obvious from the directory tree. List each module once, with what it owns and its entry point, so an agent starts from the interface instead of searching implementation files:

```markdown
## Module Map

- **NOTE** `packages/billing/` owns invoices and payment state; enter through `packages/billing/src/index.ts`
- **NOTE** `packages/catalog/` owns products and pricing rules; enter through `packages/catalog/src/index.ts`
```

### When Stuck

```markdown
## When Stuck

- **ALWAYS** ask a clarifying question or propose alternatives
- **NEVER** initiate large speculative changes without confirmation
```

### Git Commits

```markdown
## Git Commits

- **ALWAYS** write succinct commit messages in imperative mood
- **ALWAYS** keep the first line short
- **NEVER** mention that you are an AI
```

### Issue Management

```markdown
## Linear Issues

- **NEVER** change issue status without explicit instruction
- **NEVER** create issues without explicit instruction
```

### Package Manager

```markdown
## Package Manager

- **ALWAYS** use **pnpm**: `pnpm install`, `pnpm dev`, `pnpm test`
```

### Skill Pointers

Point to a skill only when the rule adds a trigger or requirement the skill's own description lacks:

```markdown
## Database

- **ALWAYS** use `.claude/skills/db-migrate/SKILL.md` before editing `db/schema.sql`, because the migration files are generated from it
```

### Domain-Specific Sections

Add sections for each tech stack (Frontend, Backend, etc.) with domain-specific guidelines.

## Anti-Patterns

Omit these:

- "Welcome to..." or "This document explains..."
- Obvious instructions ("run tests", "write clean code")
- Long rationale paragraphs (keep a short reason clause when a rule's purpose or scope is not obvious, e.g. "because CI validates them")
- Long prose paragraphs
- Content duplicated from skills
- Lists of installed skills or plugins, which the host already shows
- Rules that configured lint, format, or type checks already enforce
- Link dumps without a trigger or purpose
- Deep pointer chains where the active agent instruction file points to a doc that only points elsewhere
