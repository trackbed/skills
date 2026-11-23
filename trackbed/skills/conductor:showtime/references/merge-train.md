# The Merge Train

SKILL.md Step 6 sends you here. The helper's `board` decides what may merge; its `merge` command does the merging and refuses anything the newest saved board did not clear.

## The Merge Gate

A Pull Request is on the board's `train` only when all five checks hold:

1. It is your own Pull Request against the default branch, and it is not a draft.
2. Every required check is green on its head commit. The required checks are the ones branch rulesets and classic branch protection name, plus any `gh pr checks --required` reports; a required check that has not reported yet counts as pending. When the repository requires no check, every reported check counts, and a skipped one counts as green. A Pull Request with no reported checks at all does not pass.
3. It has no unresolved review thread, and GitHub reports no conflict, no missing required review, and no other branch-protection block. A Pull Request that branch protection requires to be up to date with the default branch and that is behind it gets `trackbed:pr:shape-up`, which rebases it.
4. Its workspace's chat is idle, its checkout is at the Pull Request's head, and it has no uncommitted change. A Pull Request with no live workspace skips this check.
5. Its checks are not stale. They are stale when a commit that reached the default branch after the Pull Request's head commit was made touches a file the Pull Request changes, CI configuration, a lockfile, or shared build tooling. Such a Pull Request gets `trackbed:pr:shape-up`, which rebases it, and must go green again.

## The Hold Rules

A Pull Request that passes the gate is on `held`, not `train`, when one of these matches:

- The deterministic risk signals of `trackbed:pr:triage-risk` report a high tier, or could not be computed.
- Its title has the Conventional Commits `!` marker, or its description has a `BREAKING CHANGE:` footer.
- A person's latest review requests changes, however the author answered it, or a person left a comment or a review with text that the author has not answered since. An author review with no text, such as the carrier of a reply to a bot's thread, answers no one.

A held Pull Request never merges under `--auto`. It stays open, and the report lists it with its `holds`.

## Ask Before Merging

Under `--auto`, skip this section: every entry of `train` is selected, and no entry of `held` is. Under `--dry-run`, skip it too, and ask nothing: the report lists `train` as "would merge" and `held` with its `holds`.

Otherwise, when `train` and `held` are both empty and no workspace has an `archive` move, there is nothing to ask. Else finish Steps 7 and 8 without archiving, end the report with this question, and end the turn:

```text
**Merge and archive?** Reply "all", the PR numbers to merge, or "none". Add "archive" to archive the merged workspaces.

Ready to merge, in this order: {number, title, and short head SHA of each `train` entry, with "shares files with #N" from `shared_with`}
Held, merged only if you name it: {number, title, short head SHA, and `holds` of each `held` entry}
Merged, ready to archive: {name and short merged head SHA of each workspace whose move is `archive`}

Each merge is a {merge method} merge pinned to the commit whose checks passed. Each one is rechecked right before it merges, and a Pull Request whose checks went stale through an earlier merge waits for a rebase.
```

Leave out a line that has nothing to list. Treat anything other than a clear selection as "none", and merge and archive nothing.

Before asking, retain the displayed board's repository and merge method, train PR numbers and head SHAs, held PR numbers, head SHAs and hold reasons, and archive workspace IDs and head SHAs. When the user answers, interpret "all", explicit numbers, and "archive" against that preview. Then run Steps 2 and 3 again. A saved board clears merges for fifteen minutes only. The fresh board may remove entries from the selection. A newly ready PR, a changed head, changed hold reasons, a new archive candidate, or a changed repository or merge method needs a new preview. Keep checking this same selection after every rebuild. Only an explicitly named entry from the preview's held list is eligible for `--allow-held`.

## Merge One at a Time

Under `--dry-run`, skip this section: nothing merges.

1. Take the first selected Pull Request in `train` order, then any selected `held` one.
2. Refresh the Conductor records in Step 2 without replacing the saved board. Run the helper with `PR_NUMBER` set to the selected entry's `number` and `HEAD_OID` to its selected `head_oid`:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/conductor:showtime/scripts/showtime.py" merge \
     --conductor .context/showtime/conductor.json --pr "$PR_NUMBER" --head "$HEAD_OID"
   ```

   Add `--allow-held` only for a held Pull Request the user named in this run's answer, and never under `--auto`. Keep every merge in the helper.

3. Read the result. `outcome: merged` confirms that GitHub completed the pinned merge. The helper uses GitHub's synchronous merge endpoint, which does not support merge queues. A `status` of `refused` skips this Pull Request for this pass: report its message and go on with the next selected one. When the message says the saved board is older than fifteen minutes, run Steps 2 and 3 again first and go on with the selected Pull Requests still on the new board's `train` or `held`. A `status` of `failed` or `error` stops the train for this pass. Report the message, including any requirement to use a merge queue.
4. After a merge, go back to step 1 with the next selected Pull Request. Do not rebuild the board between merges: `merge` rechecks each Pull Request against a freshly fetched default branch, so one whose checks went stale through an earlier merge is refused and skipped.

The train also stops for this pass when the board cannot be rebuilt.

When the train has ended and anything merged, run Steps 2 and 3 once to rebuild the board. Then apply Steps 4 and 5 once more to the newest board, for the workspaces that got no message in this pass. A Pull Request whose checks went stale through a merge gets its rebase started that way.
