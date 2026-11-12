# docs:track-rejected-enhancements

Use it to remember enhancement ideas your team has turned down, and to check a new request against them. It keeps one short Markdown file per rejected concept in `.out-of-scope/` at the project root, with the reason, the decider, and the requests that asked for it. `record` and `append` write to that folder, and `reconsider` deletes a file after you confirm. The skill is experimental, and it is not for rejected bugs or deferrals; for an architecture decision with rejected alternatives, use `trackbed:docs:adr`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `record <concept>` | Record a settled rejection. The skill first asks whether it is settled, a deferral, or a feature that already exists, and writes only for a settled one. It takes the reason, earlier requests, and decider from the conversation and asks for what is missing. |
| `check <concept>` | Look for an earlier rejection of the same or a similar concept. On a match it shows the reason and asks whether to honor it or continue. It writes nothing. |
| `append <concept> <issue-ref>` | Add another request, such as `#123`, `ABC-123`, or a URL, to the record of an already rejected concept. |
| `reconsider <concept>` | Show the record of a rejection that no longer applies and delete it after you confirm. |

## Examples

```text
# Record that the team turned down dark mode
/trackbed:docs:track-rejected-enhancements record dark mode

# Check whether a new request was rejected before
/trackbed:docs:track-rejected-enhancements check night theme

# Add a new request to an already rejected concept
/trackbed:docs:track-rejected-enhancements append dark mode #482

# Remove a rejection that no longer applies
/trackbed:docs:track-rejected-enhancements reconsider dark mode
```

## What you get

- `record`: `.out-of-scope/<slug>.md` with the concept name, the decision date, the decider, the reason, and the earlier requests. It ends with `recorded .out-of-scope/<slug>.md`.
- `check`: the earlier rejection and its reason, or `no prior rejections found for <concept>`.
- `append`: one new line under the record's `Prior requests` heading. A reference that is already there is not added twice.
- `reconsider`: the file deleted. The skill does not reopen issues or touch Linear or Git history.

One concept keeps one record however it is worded: when a similar record exists, such as `night-theme` for `dark mode`, the skill offers it instead of creating a second file. If `.gitignore` hides `.out-of-scope/`, `record` asks whether to keep it ignored.
