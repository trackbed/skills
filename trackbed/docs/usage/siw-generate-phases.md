# siw:generate-phases

Use it when the spec in `siw/` is ready to plan and you want the initial issue set. It reads the spec, breaks the work into phases and small issues with acceptance criteria, sizes, and dependencies, has the breakdown reviewed, and writes the issue files under `siw/` after you approve the plan; it changes no code. A spec that describes one coherent change gets a single issue and no phases. Once the work is in Linear, add issues with `trackbed:linear:issue-define` instead.

## Before you run it

- `siw/OPEN_ISSUES_OVERVIEW.md` exists. If it does not, run `trackbed:siw:init` first.
- The spec states its objective, scope, success criteria, and technical context, with no open question that blocks planning. Otherwise the run stops and points you to `trackbed:discovery:interview` with `--siw`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[spec-file-path]` | The main spec. Without it, the spec is found under `siw/`. If several files qualify, you are asked which one is the main spec. |

## Options

| Option | Effect |
| --- | --- |
| `--auto` | Create the issue files from the reviewed plan without asking for approval. When issues already exist, it appends and never replaces them. It stops instead of asking when work looks in progress, when the main spec is ambiguous, or when the review still has concerns. |

## Examples

```text
# Plan the issue set for the spec in siw/
/trackbed:siw:generate-phases

# Name the main spec when siw/ holds more than one candidate
/trackbed:siw:generate-phases siw/NOTIFICATIONS_SPEC.md

# Create the issue files without the approval prompt
/trackbed:siw:generate-phases --auto
```

## What you get

- A plan to approve or change: each phase with its goal and issues, and for every issue its size (XS to L) and whether an agent can do it alone (`AUTO`) or a person is needed (`HITL`, with the reason). Each group of issues says whether it can run in parallel.
- After approval, one file per issue in `siw/issues/`, named `ISSUE-P1-001-<title>.md` for phase issues and `ISSUE-G-001-<title>.md` for general ones.
- `siw/OPEN_ISSUES_OVERVIEW.md` and `siw/LOG.md` updated to match.
- A summary of the files created, what was left untouched, and any remaining concerns.

If issue files already exist, you choose Append, Replace, or Abort. Append keeps the existing issues and adds only work they do not cover; Replace moves them to the trash and writes a new set. Next, review the issues and run `trackbed:siw:transfer-to-linear`. The [SIW guide](../siw.md#issue-set) explains the issue set.
