# pr:github-review-reply

Use it on your own Pull Request to work through what reviewers, bots, and apps wrote. It checks each comment against the code, decides what it needs, such as a code change, an explanation, or a question back, and drafts a reply. By default it only writes a plan. It edits code only with `--implement` or when you ask it to address the feedback, and it posts replies or resolves threads only with `--post` and `--resolve`. It never commits or pushes. To review someone else's Pull Request, use `trackbed:pr:github-review`; to fix failing checks, use `trackbed:pr:fix-ci`.

## Before you run it

- `gh` and `jq` are installed, and `gh` is authenticated.
- For `--implement`, you are on the Pull Request's branch.
- To post, you have no unsubmitted pending review of your own on the Pull Request. Submit or discard it in GitHub first.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[pr-url\|instructions]` | A Pull Request URL or number, or instructions such as "only reply to Sarah". Without a Pull Request, the current branch's is used. |

## Options

| Option | Effect |
| --- | --- |
| `--auto` | The same as `--implement`, `--post`, and `--resolve` together. It still asks before posting a reply to a person. |
| `--implement` | Make the code changes that valid comments ask for before drafting replies. This edits files and leaves them uncommitted. |
| `--no-implement` | Do not edit code; only plan and draft. This is the default. |
| `--post` | Post the drafted replies to GitHub. A reply to a person is shown to you for approval first. |
| `--resolve` | After posting, resolve inline threads that are fully addressed. It also offers to resolve threads you already answered but left open. |
| `--inline` | Reply with the plan in the conversation and write no file. Cannot be combined with `--visual`. |
| `--visual` | Also write `GITHUB_REVIEW_REPLY_PLAN.html`, an interactive page of the same plan. See [Visual Reports](../visual-reports.md). |
| `--humanize` | Run the drafted replies through `trackbed:text:clarify` to remove AI-sounding phrasing. Off by default, also with `--auto`. |
| `--human-only` | Leave out feedback that comes only from bots and apps. |
| `--bot-only` | Keep only feedback that comes entirely from bots and apps, so no reply to a person is drafted or posted. `trackbed:pr:shape-up` sets it for its reply pass. |
| `--include-bots` | Include bot and app comments. This is already the default. |
| `--all` | Also include resolved threads, comments the author already answered, and older summary and general comments. |
| `--only <login>` | Include only feedback whose latest reviewer comment is from this GitHub login. |

## Examples

```text
# Plan replies for the current branch's Pull Request, without changing anything
/trackbed:pr:github-review-reply

# Make the requested code changes, then draft replies that describe them
/trackbed:pr:github-review-reply --implement

# Answer only bot and app reviewers, post the replies, and resolve what they settle
/trackbed:pr:github-review-reply --bot-only --post --resolve

# Work on one reviewer's comments on a specific Pull Request
/trackbed:pr:github-review-reply --only sarah https://github.com/acme/app/pull/482
```

## What you get

- `GITHUB_REVIEW_REPLY_PLAN.md` in the project root: one entry per comment with its classification, the evidence checked, and the draft reply.
- With `--implement`, the code changes in your working tree, uncommitted. A reply that says a fix was made is held until you commit and push the fix; then run again with the same flags.
- With `--post` and `--resolve`, replies posted and threads resolved on GitHub, one at a time, after it shows you what it will do. The posted reply bodies are kept under `.context/github-review-replies/`.
- A closing summary: what was posted, resolved, and implemented, what still needs a code change or an answer, and what is held.
