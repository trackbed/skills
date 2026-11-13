# siw:init

Use it to start a Structured Implementation Workflow (SIW) for work that needs a written spec and a planned issue set before it moves to Linear. It creates the `siw/` folder with a spec, a progress log, and an empty issue tracker, built from spec files you already have, from a discovery interview, or from a few questions. It writes planning files only and changes no code. It defines no issues; that is the job of `trackbed:siw:generate-phases`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[spec-file(s)]` | Existing spec files. The new spec links to them and does not repeat their content. You choose whether the files stay in place or are moved or copied into `siw/`. Passing `siw/DISCOVERY_BRIEF.md` builds the spec from that brief. |
| `[folder]` | A folder to scan for `.md` and `.txt` files. You choose which ones to link. |
| `discover` | Run `trackbed:discovery:interview` first, on the topic you write after the keyword, and build the spec from its brief. |

## Options

| Option | Effect |
| --- | --- |
| `--auto` | Use defaults instead of asking: keep linked files in place, use every file in a folder, take the detected work context and spec filename, and create no supporting-specs folder. It stops instead of asking when you pass no source or when a workflow already exists in `siw/`. |

## Examples

```text
# Answer a few questions and create the workflow files
/trackbed:siw:init

# Link an existing spec instead of writing a new one
/trackbed:siw:init docs/notification-spec.md

# Run a discovery interview on a topic first
/trackbed:siw:init discover notification system

# Build the workflow from a discovery brief without further questions
/trackbed:siw:init siw/DISCOVERY_BRIEF.md --auto
```

## What you get

- `siw/<spec>.md`, the main spec. The filename follows the kind of work, such as `FEATURE_SPECIFICATION.md` or `PROJECT_PLAN.md`, and you confirm it.
- `siw/LOG.md` for progress and decisions, `siw/OPEN_ISSUES_OVERVIEW.md` for issue tracking, and an empty `siw/issues/` folder. `siw/supporting-specs/` is added when you ask for it.
- A closing summary that rates the spec as `product-only`, `requirements-only`, or `planning-ready` and names the next step.
- If `siw/` already holds a workflow, a choice to resume it, start fresh, or abort. Starting fresh deletes the log, the issue overview, the issue files, and earlier briefs and reports, and keeps the spec files.

Next, run `trackbed:siw:generate-phases` when the spec is `planning-ready`; otherwise strengthen it with `trackbed:discovery:interview` and `--siw`. The [SIW guide](../siw.md#quick-start) shows the whole sequence.
