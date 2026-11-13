# docs:feature-spec

Use it before you start a feature that needs written agreement on scope and success criteria, but not the full tracked SIW workflow. It lists its assumptions, waits for your corrections, writes a one-page spec, and stops for your approval. It writes only the spec file and never starts implementation, even when your request also asked for the build. For multi-phase work that needs tracked issues, use `trackbed:siw:init`; when the requirements are still unknown, run `trackbed:discovery:interview` first and pass its plan to this skill.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[feature name, brief description, or origin plan path]` | The feature to specify, as a name or a short description. Or the path of an existing plan, PRD, or brainstorm: the skill drafts the spec from it, cites it on the spec's `Origin:` line, and leaves that document unchanged. To revise an existing spec, name it and say so. |

## Options

| Option | Effect |
| --- | --- |
| `--synthesize` | Skip the assumptions step and draft from what the conversation or the origin document already establishes. This needs at least four of the six spec areas covered there, including Objective and Success Criteria. Otherwise the skill says so and lists its assumptions as usual. |
| `--auto` | Same as `--synthesize`. |

## Examples

```text
# List assumptions, wait for corrections, then draft the spec
/trackbed:docs:feature-spec CSV export for the invoices page

# Draft the spec from a discovery plan and leave the plan untouched
/trackbed:docs:feature-spec docs/plans/invoice-export-plan.md

# Skip the assumptions step for a feature already discussed in this conversation
/trackbed:docs:feature-spec --synthesize
```

## What you get

- `<slug>-spec.md` in the repository root, where the slug comes from the feature name, or the Markdown path you name inside the repository. It has six areas: Objective, Scope & Non-goals, Boundaries, Testing Strategy, Open Questions, and Success Criteria. Claims the skill inferred are marked `UNVERIFIED:`.
- A `PLAN:` summary of the spec. The run then stops so you can review the file.
- When you ask for changes, edits to the same file and a new request for approval. When you approve, the file path and the spec's [readiness state](../siw.md#artifact-readiness).

If the spec file already exists, the skill asks whether to overwrite it, revise it, or use another name. To turn an approved spec into tracked work, run `trackbed:siw:init` with the spec file.
