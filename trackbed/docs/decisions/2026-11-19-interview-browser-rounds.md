# The discovery interview can ask its rounds on a generated browser page

- Status: PROPOSED
- Date: 2026-11-19
- The maintainer selected a fresh tab and key per round on 2026-11-20. The broader browser-mode proposal awaits evaluation in real interviews.
- The mode ships as highly experimental: the skill says so when it starts, and its round format, controls, and helper may change or be removed without a migration.

## Context

`trackbed:discovery:interview` asks every question through AskUserQuestion: two to four text options per question and at most four questions per round. That fits a pick between labelled alternatives. It fits poorly the other things an interview asks for: an order of priorities, a point on a tradeoff, a split of effort, the same scope decision for eight features, or a choice between two layouts that is quicker to see than to read. The skill's references name those question types (forced tradeoff, negative space, restatement challenge), and the tool then flattens each into a short list of options.

The maintainer asked for a generative UI version: an interview whose interface is produced for the question in hand.

Two earlier pieces of work bound the design. The visual report record ([2026-11-10](2026-11-10-visual-report-style.md)) keeps pages free of script the model wrote and of network access, because page content quotes text other people wrote. `trackbed:visual:decisions` builds a page from a checked content file and takes the reader's choices back as a file they export. An interview differs from both in one respect: it is a loop. Each round depends on the last answers, so answers return to the agent many times in one sitting.

## Decision

Add `--ui` to `trackbed:discovery:interview`. With it each interview round is a page in the user's browser, and the rest of the skill is unchanged.

- **It is a mode, not a skill.** Intent, inputs, output, and safety gates are the interview's own; only the surface differs, which the catalog shape decision says to merge.
- **The model generates a round file, not a page.** For each question it picks one of seven controls (`choice`, `rank`, `scale`, `allocate`, `matrix`, `confirm`, `text`) and may attach an ordered set of figures to the question or its options. A chart draws sourced series from checked numbers. Screenshots embed local raster captures with optional numbered callouts. Sketches, steps, bars, code, and tables share the same slots. A helper checks the file and renders the page, and one tested script runs in it. The only free-form part is a sketch: an SVG the page shows through `<img>`, where it cannot run or load anything.
- **Answers return over a loopback listener.** `interview-ui.py ask` serves the round on `127.0.0.1`, opens it, and exits with the answers when the user sends them. A host that resumes the agent when a background command ends therefore continues without the user returning to the chat. Each invocation opens a fresh browser tab with an independent key and an ephemeral port, including retries. The helper checks the host, key, and round identity before accepting answers and exits after submission or timeout. A completed tab makes no further requests. This keeps later rounds’ credentials out of requests to a released port.
- **Copy and paste always works.** Every page can put its answers on the clipboard, and `interview-ui.py answers` checks a paste against its round. This is the path when a sandbox forbids listening.
- **Only the user turns it on**, as with `--visual` and `--apply`, because it opens a browser tab and a port.
- **The page asks interview questions only.** Overwrites, the ADR offer, and the SIW apply protocol stay in chat, and an answer from the page authorizes nothing.
- **The page recommends and never selects**, the rule decision documents already follow.

## Alternatives and consequences

Letting the model write each page, script included, is the most literal reading of generative UI. It would spend several thousand output tokens per round on untested script, and a round quotes repository text, which would then run in the user's browser. The visual report record rejected this for reports, and the same reasons hold here.

Copy and paste as the only way back would need no listener and would keep the other pages' no-network rule. It costs the user a copy, a window switch, and a paste on every round. Over four to eight rounds that is the difference between an interface and a form, so it stays as the fallback and not the main path.

One server for the whole interview would let the page change without reloading. It needs a detached process that a later command must find and stop, and it fails silently when a host kills it. Serving per round keeps every listener owned by the command that started it.

A host's own interface surface would tie the mode to that host. The plugin runs in Claude Code, in Codex, and inside Conductor, and a browser is the one surface all three share.

Consequences:

- This is the first shipped script that listens on a port. It is loopback-only and short-lived, and it is a new kind of surface for the security scan and for review.
- The mode assumes a computer with one user. The link carries the round key, and while the browser is being opened the link is visible in the process list, so another local user could read or answer the round that is open.
- The mode needs a browser on the computer the agent runs on. Cloud and SSH sessions fall back to chat.
- The visual report record's no-network rule gains one bounded exception: `connect-src 'self'` on a page the helper is serving. A page written to disk keeps the rule.
- A round file costs more output tokens than an AskUserQuestion call. The difference has not been measured.
- Whether these controls produce better plans than chat questions is not known. Accepting this record should wait for use on real interviews.
