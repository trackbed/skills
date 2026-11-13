# workflow:suggest-next

Use it when you do not know which trackbed command fits a task, or what to run next. It reads the descriptions of your installed skills and the names of trackbed files in the workspace, such as review reports, Pull Request plans, and SIW files, and replies with a short answer and at most three commands. It is read-only: it runs nothing and writes nothing. To choose which Linear issue to work on, use `trackbed:linear:next`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[question]` | The task or situation you want a command for. Without it, the suggestion is based on the trackbed files found in the workspace. |

## Examples

```text
# Ask what to run next, based on the files in the workspace
/trackbed:workflow:suggest-next

# Ask which skill fits a task
/trackbed:workflow:suggest-next which skill splits my branch into PRs?

# Ask how to continue from a report
/trackbed:workflow:suggest-next I have a review report, how do I fix its findings?
```

## What you get

- A reply of at most 15 lines in three parts: `Where you are` (the trackbed files it saw and what they suggest), `Answer`, and `Run` (up to three commands, best first, each with a reason).
- Commands written in the form your host uses, and only for skills that are installed.
- A question back to you when the files point to different stages of work, or when there are no files and you stated no goal.
- Nothing is run. You start the command you want yourself.

It only suggests trackbed commands. A general programming question gets no answer here.
