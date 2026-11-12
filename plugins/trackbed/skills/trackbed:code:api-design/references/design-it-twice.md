# Design It Twice

The first interface that comes to mind is rarely the best one. Design It Twice escapes that trap by generating multiple radically different shapes, each under a constraint that pushes it away from the others, then comparing them in the open. The 8 rules in `SKILL.md` apply afterwards to whichever design is picked — Design It Twice is upstream of those rules, not a replacement for them.

## Parallel vs sequential form

The mode runs in one of two forms, chosen by what the host can do rather than by which host it is:

- **Parallel form (any host that can launch independent sub-agents).** Launch the constraint-pinned sub-agents in parallel, each starting from a fresh context. Claude Code's Agent tool with a general-purpose agent type is one example; other hosts have their own equivalents. A sub-agent that forks the coordinating conversation does not count: it inherits the coordinator's first idea and everything said so far, which defeats the point of separate drafts. Because a fresh sub-agent knows only what its prompt says, the prompt must carry the framing block, its constraint, and any file paths it needs to read. When the host can start fresh sub-agents but not concurrently, launch them one after another; each draft is still blind.
- **Sequential form (fallback).** Use it when the host cannot launch fresh-context sub-agents, including when its only sub-agent mechanism forks the conversation. Draft each design in turn against the same constraint slate, finishing one before starting the next. Do not re-read prior designs while drafting the next — consult only the shared framing block from Step 1. This reduces anchoring but cannot remove it, because one context has seen every earlier draft, so these designs are not drafted blind.

The comparison rubric (Step 3) is identical in both forms. Record which form ran and whether the designs were drafted blind; the output reports both (see "Output to user").

## When to enter this mode

Trigger on any of:

- The user passes `--design-twice` (or equivalent flag) to the skill invocation.
- The user says "design it twice", "show me alternatives", "what other shapes are there", or otherwise asks for a comparison rather than a single design.

Do not enter this mode by default. For high-leverage surfaces (SDK boundary, public API, cross-team contract) where the first shape feels obvious, ask the user whether to run this mode before producing designs. A single contract is right for most work; multiplying designs has overhead and is wasted on low-stakes interfaces.

## Process

### Step 1 — Frame the problem space

Write a short framing block before any design is produced. The framing names the _problem_, not the _interface_.

```
Problem: <what the caller is trying to accomplish, in one sentence>
Inputs and outputs: <data the interface moves, in domain terms>
Invariants: <what must hold across all designs>
Unknowns: <facts not yet established; leave them open rather than settling them for every design>
Out of scope: <variants we are not exploring>
```

Each design receives this framing verbatim. They diverge on shape, not on problem. List every correctness requirement under Invariants: the comparison and the final-pick trace in Step 4 judge designs only against this block, so do not add criteria later or change them to favor a design. An assumption that only one shape needs belongs in that design's output, not in the shared framing.

### Step 2 — Produce three or more designs

Produce at least three designs, each pinned to a different constraint — in parallel fresh-context sub-agents when the host can launch them, sequentially otherwise (see "Parallel vs sequential form" above). Concrete constraint slate:

| # | Constraint | Pushes the design toward |
| --- | --- | --- |
| 1 | **Minimize methods** (1–3 max). | Deep modules. One interface that hides everything. Risk: kitchen-sink "do" method. |
| 2 | **Maximize flexibility.** Composable primitives, no opinionated defaults. | Library-shape. Many small functions. Risk: shallow modules that push complexity to callers. |
| 3 | **Optimize the common case.** One ergonomic happy-path call; advanced cases via escape hatches. | Convenience-shape. Risk: hidden coupling between the happy path and the escape hatches. |
| 4 (optional) | **Ports & adapters** for cross-seam dependencies. | Interface plus N adapters. Only worth assigning when the dependency is **remote-but-owned** (a service we own across a network) or **true-external** (a third party we don't own) per the taxonomy below — for in-process and local-substitutable dependencies the constraint usually collapses. Drop if there's only one adapter — see the adapter-count rule. |

Each design must follow the same output structure (the prompt template below) so comparison is mechanical rather than subjective. In the parallel form, separate fresh-context sub-agents keep the designs blind to each other; in the sequential form, do not re-read prior designs while drafting the next.

#### Dependency categories (decide before constraint #4 fires)

Constraint #4 is only worth assigning when the _category_ of dependency justifies the cost of a port. Classify each thing the design depends on into exactly one of these four categories — including in-process collaborators that aren't external at all — and let the category decide the adapter strategy:

- **In-process** — pure logic or in-memory state with no I/O (math, parsing, in-memory transformation). No port, no adapter; the seam, if any, is internal to the module's own tests.
- **Local-substitutable** — a local resource with a substitutable in-process implementation (PGLite for Postgres, an in-memory FS for `node:fs`, a fake clock). The seam is internal to the module; no port at the module's external interface.
- **Remote-but-owned** — a service we own that happens to live across a network (an internal HTTP/gRPC/queue service). Define a port at the seam: an in-memory adapter for tests, the real network adapter for production. Logic stays in one deep module even though deployment splits across processes.
- **True-external** — a third party we don't own (Stripe, OpenAI, S3). Inject a port; mock at the seam. Mocking is acceptable here precisely because we can't substitute the real thing.

Use the category to decide whether constraint #4 is even a viable design — for in-process and local-substitutable dependencies, "Ports & adapters" usually collapses back into one of the other constraints because there is no real second adapter waiting. For remote-but-owned and true-external, constraint #4 is doing real work.

#### Prompt template per design

In the parallel form, send this prompt to each fresh-context sub-agent, filling in every placeholder, because the prompt is all the sub-agent sees. In the sequential form, use the same prompt as a self-brief at the start of each design pass.

```
You are designing one alternative for a comparative interface-design exercise.

Problem framing:
<paste the framing block from Step 1>

Your assigned constraint: <constraint from the slate above>

Code you may read: <file paths relevant to the problem, or "none">

Your design must push hard against the constraint — do not hedge by gesturing at other shapes. Pretend this constraint is the only thing that matters.

Output the following sections, in this order, with no preamble:

## Interface
- Types (input/output/error)
- Methods (signatures)
- Invariants
- Error modes

## Usage example
A 5–15 line snippet showing the most common call.

## What the implementation hides
What complexity lives behind the interface that callers do not see.

## Dependency strategy
What this interface depends on, and how it acquires those dependencies (constructor injection, factory, ambient, etc.). For each dependency, name which of the four categories it falls into (in-process / local-substitutable / remote-but-owned / true-external) and justify the adapter strategy with reference to that category — e.g. "remote-but-owned, so port + in-memory test adapter + real HTTP adapter" or "in-process, so no adapter and no port".

## Trade-offs
What this design gives up to satisfy its constraint. Be honest. The next step will compare you against the others, and unsurfaced trade-offs become hidden costs.

Do not compare yourself to other designs. Do not propose a hybrid. Do not break the constraint.
```

#### Handling missing or degenerate designs

Before moving to Step 3, check the produced designs:

- **Malformed output** (sections missing, constraint visibly broken): re-run that single design once with the same prompt. If it fails a second time, drop it and continue with the remainder.
- **Collapsed constraint** (two designs are substantively the same shape — typically constraint #4 collapsing into another when the dependency category is in-process or local-substitutable): drop the duplicate and note it in the comparison block so the reader sees the constraint did not buy a distinct design.
- **Fewer than two distinct designs survive**: stop and surface this to the user. The mode requires at least two real alternatives to be useful; below that, propose either re-framing the problem or proceeding without Design It Twice.

### Step 3 — Present and compare

Present the designs sequentially first — readers should be able to evaluate each on its own terms before seeing the comparison. Then write a comparison block in prose.

#### Comparison rubric

Score each design on three axes, using the definitions in the shared architecture glossary (`${CODEX_HOME:-$HOME/.codex}/plugins/cache/trackbed/trackbed/1.0.1/shared/architecture/references/architecture-language.md`, named in `SKILL.md`):

- **Depth.** What implementation complexity does the interface hide that the caller would otherwise carry? Cite an example call site.
- **Locality.** When the most likely change request arrives ("we now also need to <X>"), how many places does the design force a change in?
- **Seam placement.** Where does behavior vary across implementations? Are seams placed where variation actually exists, or where it might exist someday? Apply the adapter-count rule: one adapter is a hypothetical seam; two or more active adapters make the seam real.

The comparison should be a single block of 3–6 paragraphs, not a checklist. Show the reader the trade-off, do not just enumerate it.

Within that comparison, apply Rule 0's UX/DX/AX principle: explain relevant effects on user task completion, developer maintenance, and agent discovery, execution, recovery, and verification. Prefer improvements across all three without expanding scope; unchanged or inapplicable dimensions are acceptable. Name material tradeoffs, established contracts preserved outside the intended change, any intentional contract change and its compatibility or migration effects, and the checks needed to support compatibility claims.

#### Recommendation

End with one of:

- **Recommendation: pick Design N.** Single design wins outright. Brief justification grounded in the rubric.
- **Recommendation: hybrid.** Take the interface from Design A and the dependency strategy from Design B. Explicitly name what gets borrowed. Hybrids are permitted but cost honesty — call out what the original constraints were and why borrowing across them does not collapse back into "first idea was right after all". Write the hybrid out in full under a `### Design H: Hybrid (<what comes from which design>)` heading, using the same sections as the drafted designs: Interface, Usage example, What the implementation hides, Dependency strategy, and Trade-offs. A hybrid named only by its borrowings has not been designed, so it cannot be compared or verified.
- **Recommendation: none of the above; redesign with new constraint.** Sometimes the parallel exercise reveals the framing was wrong (the problem statement was hiding the actual question). Surface this; do not pick a least-bad design.

### Step 4 — Verify the pick

Before presenting a recommendation to pick a design or a hybrid, check that the pick holds up; the redesign outcome skips this step. Verify the design as written, including a hybrid's combined form, not the reputations of the designs it borrows from.

1. **Choose the hardest realistic scenario** — the concrete case most likely to break an invariant or overturn the choice, such as a failure halfway through an operation, concurrent callers, a retry, or the most likely change request. Name it in one or two sentences.
2. **Trace it through the pick** — walk the scenario call by call through the picked interface. For each invariant in the framing block, state whether it holds and show the step that shows it. Looking for a counterexample and not finding one is not enough; show the trace.
3. **Mark every assumption the trace relies on** as `confirmed` (cite the code, documentation, or framing inspected during this run) or `assumed` (state what would confirm it). Remembered behavior and claims from a design's own output do not count as confirmation.

If an invariant fails, revise the pick and trace it again, or switch to the redesign outcome. If an `assumed` premise could break an invariant or reverse the choice, present the recommendation as provisional and name that premise; do not present it as settled.

## Output to user

Present the result in this order:

1. A run note: `Form: parallel (<N> fresh-context sub-agents) | sequential (one context)` and `Drafted blind: yes | no — <reason>`. Answer yes only when every design came from a fresh context that saw only the framing, its constraint, and the code it was given.
2. The framing block (so the reader can challenge the problem statement).
3. Each design in full, sequential, with a clear `### Design 1: <constraint>` heading per design.
4. The prose comparison and the recommendation, followed by the full hybrid design when the recommendation is a hybrid.
5. The Step 4 verification: the scenario, the per-invariant trace, and each assumption marked `confirmed` or `assumed`.

Do not interleave designs with comparison commentary; let each stand first.

## When this mode does not help

- Interfaces with a single obvious shape (e.g., a getter for one field). Do not multiply variants for the sake of it.
- Internal helpers that are not on a stable surface — the contract-stability concern that motivates Design It Twice does not apply to private code.
- When you already have working code and are asking "should I refactor". That is a refactor question, not a design question; use `trackbed:code:refactor-opportunities` to survey the codebase or `trackbed:code:refactor-pass` for a narrow cleanup instead.
