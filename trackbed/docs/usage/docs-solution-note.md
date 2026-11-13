# docs:solution-note

Use it after a bug fix, migration, tricky refactor, or repeated manual workflow to record a reusable lesson in `docs/solutions/`: what failed, what worked, when to reuse it, and when not to. With `--refresh` it audits existing notes against the current code instead and rates each keep, update, consolidate, or delete. It writes nothing when the code, tests, or docs already make the lesson easy to recover. For a long-lived architecture decision, use `trackbed:docs:adr`; for domain terms, use `trackbed:docs:ubiquitous-language`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[problem, lesson, or context]` | The title or a short description of the solved problem. Without it, the skill takes the topic from the conversation. |
| `[solution-note-path]` | With `--refresh`, the one note to audit. It must be under `docs/solutions/`. |

## Options

| Option | Effect |
| --- | --- |
| `--refresh` | Audit existing notes instead of writing a new one. On its own it only reports. The other two options work only together with it. |
| `--all` | With `--refresh`, audit every Markdown file under `docs/solutions/`. This is the default when you give no path. |
| `--apply` | With `--refresh`, show a plan and then apply the report's changes to the notes. Deleting or merging notes still asks you first. |

## Examples

```text
# Record the lesson from a fix you finished
/trackbed:docs:solution-note Flaky login test caused by a shared session fixture

# Audit every note against the current code and report only
/trackbed:docs:solution-note --refresh

# Audit one note and apply the updates it needs
/trackbed:docs:solution-note --refresh docs/solutions/flaky-login-test.md --apply
```

## What you get

- A new note at `docs/solutions/<slug>.md`, or in the subfolder that fits when the notes are grouped. It has Problem, Context, When this applies, Failed approaches, Final approach, Code references, Tests / verification, and Reuse cautions.
- When an existing note covers the same lesson, a question: update that note, write a narrower one, or stop. An existing note is never overwritten without your confirmation.
- With `--refresh`, a `SOLUTION REFRESH REPORT` in the conversation: each note marked `KEEP`, `UPDATE`, `CONSOLIDATE`, or `DELETE`, with the reason and evidence for every change it proposes and the documents that link to the note. No report file is written.
- With `--refresh --apply`, edits to notes under `docs/solutions/` only. A refresh never edits other files or product code.
