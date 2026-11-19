# Final Reports

Use this format for the success report of a workflow that loads this file. A stopped run shows a decision request instead. The format sets the order and how attention items are worded. It does not shorten the report: every fact the workflow reports keeps a place.

## Order

1. **Outcome:** one or two sentences saying what the run produced and where it stands. Include the Pull Request link when one exists; otherwise say that no Pull Request was created and why.
2. **Needs your attention:** everything the user must check or decide, as a list. It collects:
   - questions the issue or plan left open;
   - choices the workflow made on its own that the user may want to change;
   - things the workflow could not verify;
   - judgment calls, risk areas, and advisory notes that review surfaced;
   - limitations, such as degraded coverage, a skipped check, or a deferred optional finding the user may still want fixed.
3. **What was done:** the change as built, in a few sentences.
4. **What review uncovered:** what the review gates found and what happened to each finding.
5. **Status block:** the workflow's status template, last, with its field names unchanged, because later steps and tools read them.

Open with the outcome sentence, unlabeled, and give each later prose part its bold label as written above, as a heading line or inline before its text. An item listed under **Needs your attention** keeps its full detail there; a later part that mentions it refers back to it instead of repeating it.

## Attention Items

Start each item with what to check or decide, such as `Check that…` or `Decide whether…`. Follow it with the evidence that makes it worth the user's time, in a sentence or two. End with a suggested answer when the workflow has one, such as `Suggested: keep it; …`.

When nothing qualifies, say so in one line instead of leaving the part out: `**Needs your attention:** nothing. The issue settled every choice, every check ran, and review left nothing open.` Change the reason to fit the run, and never claim one that is not true.

## Example

```text
SKILLS-22 is implemented, reviewed, and open as https://github.com/org/repo/pull/123; CI is green.

**Needs your attention**

1. Decide whether a dropped region should also drop its closing tag. The
   issue does not say, and the run keeps the tag so existing documents
   still parse. Suggested: keep it.
2. Check the Windows path handling by hand. CI has no Windows runner, so
   no test ran it.

**What was done**

The parser now skips regions marked as dropped and reports them in its
summary. The change is in the parser module and its tests.

**What review uncovered**

Review fixed one missing test for nested regions and rejected a request
for a config flag, because the issue asks for fixed behavior. The
closing-tag question is item 1 above.

Linear issue: SKILLS-22
...
Pull Request: https://github.com/org/repo/pull/123
```
