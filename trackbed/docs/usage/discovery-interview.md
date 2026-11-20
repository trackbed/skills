# discovery:interview

Use it when requirements are vague, contested, or half-formed. It interviews you about a topic, proposal, or spec in rounds of questions with concrete options, then writes a plan file where you choose. With `--siw` it works on a tracked SIW initiative and writes `siw/DISCOVERY_BRIEF.md` or `siw/SPEC_STRENGTHENING_PLAN.md` instead, and it changes existing spec files only with `--apply`. For an initiative too large or uncertain to plan in one session, use `trackbed:discovery:wayfinder`.

## Before you run it

- For a `--siw` run on an existing spec or brief, no earlier `siw/SPEC_STRENGTHENING_PLAN.md` is waiting. If one is, the skill stops and asks you to apply, archive, or remove it.
- For `--ui`, a browser on the computer the agent runs on. In a cloud or SSH session the page cannot reach the agent, and the skill interviews in chat instead.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[topic]` | What to explore, as free text. With no argument, the skill asks. |
| `[file-path(s)]` | Files to read first, such as a proposal or spec. When every path is inside `siw/`, the run uses SIW mode. |
| `siw` | On its own, the same as `--siw`. |

## Options

| Option | Effect |
| --- | --- |
| `--siw` | Work on the SIW initiative in `siw/` and interview toward 90% confidence. Writes a discovery brief for new work, and a strengthening plan when a spec or brief already exists. See [SIW discovery](../siw.md#discovery). |
| `--apply` | In a `--siw` run on an existing spec or brief, edit those files as the plan says after you confirm the listed edits, then remove the plan file. It works only when you ask for it yourself. |
| `--visual` | Also write `siw/SPEC_STRENGTHENING_PLAN.html`, an interactive page of the same plan. Only a `--siw` run on an existing spec or brief accepts it. See [Visual Reports](../visual-reports.md). |
| `--ui` | Highly experimental. Ask each round on a page in your browser instead of in chat. The page is built for that round's questions, with a control that fits each one. It works only when you ask for it yourself. |
| `--ideate` | Start by proposing 5 to 8 variations of the idea, and interview on the framing you pick. Ignored when the run refines an existing SIW spec. |
| `--decision-tree` | Settle decisions that depend on each other in order, the root decision first, usually one question at a time. |
| `--research` | Research the codebase and documentation with parallel agents before the interview, then check in with you on what they found. |

## Examples

```text
# Interview about a topic and write a plan file
/trackbed:discovery:interview Add email-based 2FA to the login flow

# Explore other framings of a vague idea first
/trackbed:discovery:interview improve onboarding --ideate

# Answer each round on a page in your browser
/trackbed:discovery:interview Add email-based 2FA to the login flow --ui

# Start discovery for a new SIW initiative
/trackbed:discovery:interview --siw "build a notification system"

# Strengthen the existing SIW spec and apply the edits you approve
/trackbed:discovery:interview --siw --apply
```

## What you get

- Without `--siw`: a plan file at the name and location you confirm, in a layout that fits the topic: software feature, process, architecture decision, or document review. The run ends with `PLAN: Written to <path>. Ready for review.`
- With `--siw`: `siw/DISCOVERY_BRIEF.md` for new work, or `siw/SPEC_STRENGTHENING_PLAN.md` when a spec or brief already exists, reported with an `Artifact readiness:` line. See [Artifact Readiness](../siw.md#artifact-readiness).
- With `--apply`: the planned edits made in the SIW spec files or the discovery brief, a decision log entry in `siw/LOG.md` when the full SIW workflow exists, and the plan file removed.
- With `--ui` (highly experimental; it may change or be removed): each round opens in a fresh browser tab with its own key. Press **Send answers**, then close the tab. If the wait expires, use **Copy answers** in that tab to bring your draft back to chat. The questions, round sizes, and stopping rules are the same as in chat.
  - A pick between alternatives shows the options side by side, each with what it gives and costs and, where it helps, a sketch. Priorities are a list you reorder, a tradeoff is a scale, effort is a budget of points, and scope is a table. Something the agent found in your code is a statement you confirm or correct.
  - A round can put several pieces of evidence beside a decision. Inspect numbered details on an enlarged product screenshot, compare trends on a shared chart, or expand the chart for exact values. Sources identify real captures and distinguish measurements from modeled scenarios.
  - Each question explains why it matters. Choice, ranking, scale, allocation, and matrix questions show a recommendation or explain why the agent has no preference. Some choices offer a write-in. Every control starts empty, and every question accepts “Not sure” and a note. Tick "That is enough questions" to have the skill write up what it has.
  - The page is served from `127.0.0.1` by a helper that runs only while a round is waiting, and it reaches nothing else. **Copy answers** puts your answers on the clipboard to paste into the chat when the helper cannot listen.
  - File names, overwrites, and `--apply` edits are never asked or approved on the page.
  - Rounds and answers are kept in `~/.trackbed/interviews/<session>/`.
- Anything the interview did not settle is marked `MISSING REQUIREMENT:` in the output, not filled with a guess.

Next, turn a discovery brief into tracked work with `trackbed:siw:init`.
