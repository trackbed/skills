# Implementation Workflows

Three workflow options based on user's selected approach.

During Guided or Autonomous implementation, read `{forward-progress-reference}` before applying the convention when resuming prior work, retrying a failed step, after a context reset or compaction, when drift symptoms appear (repeated wrong file paths or API signatures, or lost decisions), or when stale workflow state would repeat proven work: continue from the latest proven work and rerun only the smallest dependency cone affected by a meaningful change or demonstrated defect. Branch identity, Linear requirements, user confirmations, resume proofs, acceptance criteria, and verification remain substantive controls and must never be bypassed under that convention. Context Setup Only performs no implementation, so it only reports the prepared starting point.

## Guided Implementation (Option 1)

**Goal:** Create detailed plan, implement with user verification at each step.

1. **Create Implementation Plan**
   - Break requirements into discrete tasks
   - Identify dependencies between tasks
   - Consider using Structured Implementation Workflow (SIW) for complex issues - use `$trackbed:siw:init` to set up

2. **Create Todo List**

   Use update_plan with tasks from the plan. Order each task's new or changed interface and the tests that pin it before the implementation behind it, following the technical plan's Interfaces table; an implementation-only task skips its interface item and keeps a test item after its implementation.

   ```
   - Analyze existing patterns for {feature area}
   - Define {interface for task 1} and add the tests that pin it
   - Implement {task 1 from requirements} behind that interface
   - Define {interface for task 2} and add the tests that pin it
   - Implement {task 2 from requirements} behind that interface
   - ...
   - Run fast verification (trackbed:verify:run --fast)
   ```

3. **Begin Implementation**
   - Work through tasks one at a time
   - **ALWAYS** ask user to review after completing each task
   - Update todo list as tasks complete

## Context Setup Only (Option 2)

**Goal:** Prepare everything, let user drive implementation.

1. **Create Minimal Context**
   - Branch is already created (Step 2)
   - Create todo list from extracted requirements

2. **Use update_plan for Requirements**

   Create tasks from acceptance criteria:

   ```
   - [ ] {Acceptance criterion 1}
   - [ ] {Acceptance criterion 2}
   - [ ] {Requirement from description}
   - [ ] Verify implementation meets requirements
   - [ ] Run fast verification checks (trackbed:verify:run --fast)
   ```

3. **Provide Starting Points**

   ```
   Context is set up. Here's where to start:

   Branch: {branchName}
   Linear Issue: {url}

   Likely affected areas based on requirements:
   - {file/module 1} - {why}
   - {file/module 2} - {why}

   Similar implementations to reference:
   - {existing feature 1} - {relevance}

   Ready when you want to begin. Just tell me what to work on.
   ```

## Autonomous Implementation (Option 3)

**Goal:** Complete implementation with minimal interaction, verify at end.

1. **Deep Codebase Analysis**
   - Search for related files using Glob and Grep
   - Read similar implementations for patterns
   - Identify all files that need modification
   - Understand testing patterns in the codebase

2. **Create Comprehensive Plan**
   - Use update_plan with detailed task breakdown
   - Include exploration, implementation, testing, and verification
   - Order each new or changed interface and the tests that pin it before the implementation behind it, following the technical plan's Interfaces table

3. **Implement Iteratively**
   - Work through all tasks
   - Make implementation decisions based on existing patterns
   - Run tests after each significant change
   - Document decisions in commit messages
   - **Stop after two failed fixes for the same check.** Do not try a third edit. Name the belief both attempts relied on, such as a file path, API signature, fixture, or reading of a requirement, and re-check it against the source. If it was wrong and correcting it stays within the issue's scope, correct it and note the change. Otherwise stop with a blocker that names the check, both attempts, and the belief that failed

4. **Verification Phase**
   - Invoke `trackbed:verify:run --fast` for the project's fast iteration tier; the full sweep runs once before publication, not here
   - Fix any issues found, then rerun `trackbed:verify:run --fast` so the fix receives the full fast-tier coverage; the two-failed-fixes stop in step 3 applies here too
   - Ensure every in-repository acceptance criterion is met, and mark each one met only from evidence for it
   - For a criterion that lives outside the repository, such as a feature flag, console setting, or content, repository state is not evidence. Mark it met only from what the live system shows through an available tool; otherwise list it as pending user action

5. **Present Results**

   ```
   Implementation Complete

   Linear Issue: {identifier}
   Branch: {branchName}

   Changes Made:
   - {summary of changes}

   Files Modified:
   - {list of key files}

   Verification Results (fast tier, tree {TREE_ID}):
   - Tests: {status}
   - Lint: {status}
   - Build: {status | not in fast tier}
   - Full sweep: not run; run `trackbed:verify:run --full` once before the first push or Pull Request

   Acceptance Criteria:
   - [x] {criterion met, with its evidence}

   Pending user action:
   - {criterion outside the repository - what to change, and where | None}

   Ready for your review. Run `$trackbed:pr:create` when ready to submit.
   ```
