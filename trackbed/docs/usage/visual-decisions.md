# visual:decisions

Use it when you have findings, a proposal, or a set of tradeoffs and need to decide what to do about each, or when you want to see everything that is waiting on you. It builds one HTML file: an overview, an index of the items, and a page per item with its evidence, the options and what each gives and costs, a recommendation with its reasoning, and a place to record your own choice, a status, and notes. It works from a report or plan you already have, or finds the open decisions itself, and never reruns the review behind it. For a diagram or explainer use `trackbed:visual:explain`; for a snapshot of a report with accept and dismiss, add `--visual` to the skill that writes the report.

## Before you run it

Have the thing to decide on ready: a finished report such as `PRODUCT_AUDIT_OVERVIEW.md` or `REVIEW_OVERVIEW.md`, a plan, or a conversation that has reached the point of "which way do we go". To let the skill find the decisions, run it in the session where the work happened, from the project's folder: the conversation and the work's own files are all it looks at. Screenshots and other captures the report cites are embedded if their files are still where the report says. The builder needs `python3`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[report, plan, or topic]` | What to build the document from: one or more files. Leave it out, or give only a few words that name a subject, and the skill works out which decisions are waiting on you. It collects unanswered questions, choices the agent made on your behalf, and tradeoffs left open in the conversation, plus open findings, open questions, and proposed decisions in the reports, plans, and specifications of the same work. It reads what exists and does not review code or look for new problems. |

## Options

| Option | Effect |
| --- | --- |
| `--output <path>` | Write the page there instead of `~/.trackbed/decisions/<document-id>.html`. The content file it was built from goes beside it. |
| `--choices <file>` | Carry earlier choices into this build. The file is an export (`.json`) or a saved copy (`.html`) from a previous version of the same document. |

## Examples

```text
# Decide on the findings of a product review
/trackbed:visual:decisions PRODUCT_AUDIT_OVERVIEW.md

# Gather everything that is waiting on your decision
/trackbed:visual:decisions

# The same, kept to one subject
/trackbed:visual:decisions the caching approaches we compared

# Rebuild after the report changed, keeping what you already decided
/trackbed:visual:decisions REVIEW_OVERVIEW.md --choices ~/Downloads/checkout-review-choices.json

# Write the page into the project instead
/trackbed:visual:decisions PR_PLAN_INDEX.md --output .context/decisions/plan.html
```

You can also ask in your own words, such as "turn these findings into a decision document", "let me record my choices in this report", or "what do you still need me to decide?", including right after a review or planning skill finishes.

## What you get

- One HTML file that works offline and makes no network requests, opened in your browser, with its path in the reply. Screenshots, styles, and script are inside it; it uses the fonts already on your machine.
- **Overview**, **All items**, and a walkthrough per item that reads in the order summary, evidence, options, recommendation, your decision. A suggested order and an "Evidence and scope" page appear when the source has them.
- A decision per item: one of the options, a different approach you describe, or no change where that is a real choice, with a status of Not decided, Decided, Needs discussion, or Deferred, and your notes. Nothing is selected for you, the recommendation stays visible beside your choice, and you can change or clear a choice at any time.
- **Your choices**: progress, what you chose and whether it matches the recommendation, statuses, and notes, with links back to each item's evidence and options. Your decision status is separate from the item's status in its source.
- Four ways to keep what you decide. The browser saves as you go and says so, or tells you when it cannot. **Save a copy** downloads the whole document with your choices inside, and **Copy to clipboard** copies that same document so you can paste it straight to the agent instead of saving a file. **Export choices** downloads a small JSON file you can hand back to the agent, and **Import choices** restores one. An import is checked before anything changes, keeps what you already have unless you choose to replace it, and leaves everything alone when the file is invalid or belongs to another document.
- Visual aids where they help you decide: the source's own screenshots, bar charts drawn from the numbers it states, numbered steps for a sequence, and diagrams of a path or a structure. The skill looks for these on every item and adds none where prose is clearer. Anything it made itself, such as a diagram, a chart, or a capture taken now, is labelled "Made for this document" and shows only what the source states.
- A print view that holds every item, your decision on it, and your complete notes.
- When the skill found the decisions itself, the "Evidence and scope" page lists where it looked and what it considered and left out, so you can check the selection. It includes a decision only when it is open, yours to make, has a real choice in it, matters to the outcome, and can be traced to a file or to the conversation. If nothing is waiting on you, it says so and builds no page.

Recording a choice only records it: nothing is carried out, and nothing is written to Linear, GitHub, or the source report. To act on your decisions, give the agent the export and ask.

When a document is rebuilt, a choice stays attached to its item while the item and its options are unchanged. If they changed, your earlier choice comes back marked **Needs review** and is not counted as decided until you confirm or change it. Choices that exist only in a browser cannot be read by the agent; export them first.

The page and its content file are working artifacts under `~/.trackbed/decisions/`. `trackbed:workflow:cleanup-artifacts` leaves that folder alone, so delete old documents yourself.
