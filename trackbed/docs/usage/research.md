# research

Use it to get a cited answer to one bounded question before you plan or implement: an API fact, a check against source code or a spec, a standard, or how a first-party service behaves. It reads primary sources such as official documentation, source code, specifications, and release notes, uses blogs and other summaries only to find them, and saves one Markdown file in which each finding points to its source. It gathers facts only: it does not decide what to build and does not change code.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[research question or topic]` | The question to answer. Without it, the skill uses a clear question from the conversation, or asks for one. |

## Options

| Option | Effect |
| --- | --- |
| `--output <path>` | Write the file to this path. Without it, the skill follows the workspace's existing research-notes location, such as `docs/research/`, and otherwise writes `.context/research/<slug>.md`. |

## Examples

```text
# Answer a question and save it in the default location
/trackbed:research What does RFC 9110 say about retrying non-idempotent requests?

# Check the repository's own source and save the answer to a file you choose
/trackbed:research How does our webhook handler verify signatures? --output docs/research/webhook-signatures.md
```

## What you get

- One Markdown file titled `Research: <question>` with the sections Question, Scope, Sources, Findings, Conflicts And Gaps, and Non-Decisions. Each finding cites a URL or a repository path. A claim without a source is marked `UNVERIFIED` or left out.
- When the file already exists, the skill asks whether to overwrite it, refresh it, write to a numbered path such as `<slug>-2.md`, or stop. A path outside the working tree needs your confirmation.
- A closing report with the file path, whether it was created, refreshed, overwritten, or written to a numbered path, the number of primary sources used, and the conflicts or gaps that affect planning.
- When no primary source can be reached, no file is written. The skill asks for source material, or for permission to write a file that records only the gaps.

If you ask for a decision, you get the source-backed facts and a list of the decisions the research does not make.
