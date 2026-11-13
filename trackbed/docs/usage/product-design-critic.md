# product:design-critic

Use it to get an opinionated product-design critique of a UI, flow, panel, chat experience, or design question (experimental). It inspects what you give it, works out the job the user is trying to do, and recommends a change with its tradeoff. It writes no files and changes nothing. For accessibility, visual-consistency, or copy-only checks, use `trackbed:pr:product-review` or `trackbed:code:copy-review`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[file-path, screenshot, URL, or product question]` | What to critique: one or more URLs, screenshots or image files, local files such as a spec, a question, or a mix. Artifacts are inspected first, and a question frames the critique. A URL is opened in a browser, in Claude Code through `trackbed:browse`. With a question alone, the critique is strategy-level and says so. |

## Examples

```text
# Critique a running page
/trackbed:product:design-critic http://localhost:3000/settings

# Critique a screenshot with a question that frames it
/trackbed:product:design-critic designs/approval-card.png Should approvals happen inline or in the side panel?

# Ask a design question with no artifact
/trackbed:product:design-critic Where should provenance appear in a chat-first product?
```

## What you get

- A critique in the conversation, in this order: job to be done, surface model, what is working, what is weak or risky, the recommended change, a plain-language reason for it, governance and trust implications, and competitor or pattern references when they are relevant.
- One recommendation that picks a side, not a list of equal options, unless you ask for exploration. Assumptions about the job and its priorities are stated.
- When a URL, screenshot, or file cannot be inspected, the reply says so and gives a concept-level critique instead.
