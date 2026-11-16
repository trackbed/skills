---
name: visual:decisions
description: "Build a self-contained HTML decision document: evidence, options, a recommendation, and a place to record a choice, status, and notes per item. Use when asked for a decision document, a visual walkthrough with options and recommendations, a way to record choices in a report, or what still needs the user's decision, or when a review or planning skill hands off. Works from a report or plan, or finds the open decisions itself; never repeats the audit or acts on a choice."
argument-hint: "[report, plan, or topic] [--output <path>] [--choices <file>]"
disable-model-invocation: false
user-invocable: true
trackbed-platforms: [claude-code, codex]
permissions:
  - file_read
  - file_write
  - shell
---

# Decision Document

Turn what a person has to decide on into one HTML file they can read, decide in, and keep: an overview, an index of the items, and a walkthrough of each item with its evidence, the options, a recommendation, and a place to record their own choice, a status, and notes. Given a report or a plan, build from it. Given nothing, find the open decisions yourself.

**Arguments:** "$ARGUMENTS"

You write a content file. The builder at `${CLAUDE_PLUGIN_ROOT}/skills/visual:decisions/scripts/build-decisions.py` checks it and writes the page: it embeds the evidence images, the palette it shares with visual reports (`${CLAUDE_PLUGIN_ROOT}/shared/visual/assets/report-tokens.css`), the styles, and the script that keeps the reader's record. Never write the page's HTML, styles, or script yourself. Resolve this skill's own `references/...` and `assets/...` files relative to this `SKILL.md` file.

## Boundaries

- **The source stays the record.** Build from the report, plan, or conversation, and from what the work has already written down. Do not rerun the review or audit that produced it, do not go looking for new problems, and never edit it.
- **Nothing is invented.** No evidence or estimate that the source or the user did not supply, and no option added to fill out a list; `references/content-format.md` says what makes an option real, and what to do when there is only one approach or no basis for a recommendation.
- **The reader chooses.** The page recommends and never pre-selects. Do not put a choice in on the reader's behalf.
- **A recorded choice is a record.** It runs nothing and reaches no other service. Act on choices only when the user asks for that in a later message, as `references/choices-format.md` describes.
- **The page is a working artifact.** Do not commit the page or its content file.

## Step 1: Parse the Request

- **Source:** the remaining argument text names a report, a plan, or several of them. Build from those, starting at Step 2.
- **No source:** with no argument, or with only a few words that name a subject and no file, find the decisions yourself. Read `references/finding-decisions.md` and follow it in place of Step 2: it says where to look, what counts as a decision, and how to show the reader what you selected. Make the selection yourself: the document lists what you chose and what you left out, so the reader can correct it. If nothing is waiting on a decision, say so, list where you looked, and write no page.
- `--output <path>`: where to write the page. Default: `~/.trackbed/decisions/<document-id>.html`, a folder `trackbed:workflow:cleanup-artifacts` leaves alone.
- `--choices <file>`: a choices export (`.json`) or a saved copy (`.html`) of an earlier build, whose choices go into this one.
- Reject an unknown flag, and a flag whose value is missing, by naming it.

A skill that hands off to this one passes the path of its finished output as the source.

## Step 2: Read the Source

Read the source in full. Note, for each item a person must decide on: its own id, what it states, the evidence it cites (and where each capture or file is), any fix, alternative, or tradeoff it gives, and what it says is uncertain or untested. Leave out items with nothing to decide, such as strengths and filtered findings; mention them in the summary or a section when the reader needs them.

Options come from the source first: its suggested fix is an option, and each alternative it discusses is another. What an option gives and costs, and which one to recommend, are judgment: use the source's where it has one, and reason from its evidence where it has none, without adding a number it does not give. Say in the closing message which options, tradeoffs, and recommendations are yours and which are the source's, and say it in the document as `references/content-format.md` describes.

## Step 3: Write the Content File

Read `references/content-format.md` and `assets/example/content.json`, then write the content file beside the page, at the page's path with `.content.json` in place of `.html`. Keep `document.id`, every item id, and every option id stable: they are what a recorded choice is attached to. If a content file is already at that path, this is a rebuild: read it first, keep its `document.id` and the id of every item and option that is still the same thing, and never give a retired id to something new.

Make the effort to show, not only tell. For each item, look for the visual aid that makes it quicker to decide, as the "Visual aids" section of the content format describes: the source's captures first, a chart of the numbers it compares, the steps of a sequence, and a diagram, drawn from `assets/diagram-template.svg`, when a path or a structure is what has to be understood. A visual you make shows only what the source states and is marked as made for the document.

## Step 4: Build

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/visual:decisions/scripts/build-decisions.py" \
  --data <content.json> --output <page.html> --base-dir <where relative image paths start>
```

`--base-dir` is the folder that relative image paths in the content file start from, usually the project root; leave it out when the content has no images or gives every image by its absolute path. Add `--choices <file>` when the user gave one. On exit code `1` the builder prints one line per problem and writes nothing: fix each problem in the content file and rerun. Never weaken the content to get past a check you do not understand; report the problem instead. On success it prints the page's path, counts, and size.

With `--choices`, it also prints what happened to each recorded choice: `carried` (item unchanged), `needsReview` (the item or its options changed, so the page shows the earlier choice for the reader to confirm and does not count it as decided), and `dropped` (no such item any more). Tell the user all three lists. Without a file there is nothing to carry: choices that exist only in the reader's browser reappear when that browser opens the rebuilt page, and you cannot see or promise them.

## Step 5: Read It as the Reader

When a browser tool is available, open the page and look at the overview and at least one item, at desktop and phone width, before delivering. Check that the first screen says what to conclude, that each item can be decided from its own page, that numbers to compare and paths to follow are shown and not only described, that every chart and diagram is legible and says what its caption claims, and that nothing is clipped. Fix the content file and rebuild if not. When no browser tool is available, say that the page was built and checked by the builder but not looked at.

## Step 6: Deliver

Open the page in the default browser when the user asked for it (`open` on macOS, `xdg-open` on Linux, `start ""` on Windows); do not retry if that fails. End with:

- `Decision document: <absolute path>`, and the content file's path.
- How many items and options it holds, which visuals you made for the document, and anything from reading the source or from Step 4 the user must know. When you found the decisions yourself, also where you looked and what you considered and left out.
- One line on keeping choices: they save in the browser as the reader works; **Save a copy** downloads the page with the choices inside, and **Export choices** downloads a JSON file to hand back.

## When Choices Come Back

When the user gives you an export or a saved copy and asks what was decided, or asks you to act on it, read `references/choices-format.md` and follow it.

## Verification

- The page is one file that makes no network request: the builder embeds everything and writes a Content-Security-Policy that allows only its own script.
- The reader's record has four statuses, `Not decided`, `Decided`, `Needs discussion`, and `Deferred`, kept apart from the item's status in its source.
- An import in the page is checked whole before anything changes, keeps the reader's existing records unless they choose to replace them, and leaves everything as it was when the file is invalid or belongs to another document.
