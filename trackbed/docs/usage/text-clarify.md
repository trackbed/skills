# text:clarify

Use it to make a report, guide, document, research note, or summary easier to read and act on. It puts the conclusion or required action first, tightens the structure and wording, and keeps the facts, caveats, citations, technical terms, and tone. It changes a file only after it has shown you the rewrite and you approve the write. It is not for marketing copy, code, configuration, quotations, or legal text.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[file-path or text]` | One file to rewrite, or one block of text. Without it, the skill uses a single clear passage from the conversation, or asks for one. |

## Options

| Option | Effect |
| --- | --- |
| `--humanize` | Remove AI-writing patterns, such as inflated claims, filler, and chatbot phrases, instead of restructuring the text. It keeps the author's voice and adds no facts. Put it first, before the file or text. |

## Examples

```text
# Rewrite a file for clarity, then choose whether to save the result
/trackbed:text:clarify docs/incident-report.md

# Clarify a sentence or passage typed after the command
/trackbed:text:clarify After a long investigation we now think the outage was probably caused by the cache change.

# Remove AI-writing patterns from a draft and keep its voice
/trackbed:text:clarify --humanize notes/announcement.md
```

## What you get

- The complete rewritten text in a block you can copy, with a short list of the main changes when that helps you review it.
- In the default mode, a list of the caveats the skill would drop and the claims it would narrow, each quoted with the reason. The rewrite keeps all of them, so the decision stays with you.
- With `--humanize`, a list of unfilled placeholders and questions for the author. The placeholders stay where they are.
- For a file, a question after the rewrite: overwrite the source, save to a new path, or leave the result in the conversation. Nothing is written before you answer.

Code, commands, paths, URLs, quotations, and citations in the text are left exactly as written. The skill never judges whether a text was written by AI.
