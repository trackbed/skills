# Finding the Decisions

For a run with no source to build from. Work out which decisions are waiting on the reader, then write them as items the way `content-format.md` describes.

You gather what already exists. You do not review code, rerun an audit, or go looking for new problems: a decision that nobody has raised and nothing has written down is not yours to add.

## Where to look

Look in this order, and stop at the edge of this piece of work.

1. **The conversation.** It decides what "this piece of work" is. Collect:
   - a question you asked that was never answered;
   - a choice you made on the reader's behalf: a default you took, an assumption you built on, a place where you departed from what was asked;
   - a tradeoff that was discussed and left open;
   - an offer you left hanging, such as "say if you want the other one".
2. **What the work has written down.** Reports, plans, specifications, and decision records in the working directory that belong to the same work as the conversation or, when there is no conversation to go by, to the current branch. Collect:
   - findings that are still open;
   - what sits under headings such as open questions, assumptions, risks, and alternatives considered;
   - a decision record still marked as proposed;
   - a plan step that says to decide, or that offers two ways to go.

   Find candidate files by name and place. When a name does not say which work a file belongs to, read enough of it to tell. A file left over from other work is not included, whatever it holds: name it in the closing message so the user can point you at it.

3. **Nowhere else.** Not the diff, not the rest of the codebase, not an issue tracker, not Pull Request threads. When the user wants one of those, they name it as the source. This limits where decisions are collected from. Checking a fact, as the next section allows, may read whatever the check needs.

When the user gave a few words naming a subject, keep to that subject in both places.

## What counts as a decision

Include a candidate only when every line holds:

- **It is open.** Nobody with the say has decided it. A choice you made for the reader is open until they confirm it.
- **It is theirs.** It turns on preference, priority, risk, cost, or something only they know. A question a check can settle is not a decision: settle it when that is quick and inside what you were asked to do, and otherwise report it as an open fact in the closing message.
- **There is a real choice.** Two or more ways to go that a careful person would weigh, or a real yes or no.
- **It matters.** What gets built, shipped, spent, or promised differs by the answer. Leave out matters of taste that nobody will notice.
- **You can point to it.** A file and the place in it, or the part of the conversation it came from.

Merge two candidates that are one decision seen from two places. Split a candidate that hides two choices the reader could make differently.

A choice you made without saying so is worth the reader's time only when they could reasonably have chosen otherwise and undoing it later costs something. Leave out the ones any reader would wave through. A question you asked, or an offer you left hanging, has already been put to the reader, so it is included when the other lines hold.

## How many

Aim for at most twelve. With more, keep the ones that block other work or cost the most to get wrong, and list the others in the document as described below.

With none, write no page. Say that nothing is waiting on a decision and list where you looked.

## Writing them as items

- **`title`:** what has to be decided, as a statement: `The page uses system fonts instead of embedding web fonts`.
- **`status`:** where it stands and where it came from: `Open question in PR_PLAN_INDEX.md`, or `Chosen without asking in this session · can be undone`.
- **`evidence`:** quote the lines of the file, or the exchange in the conversation, as an `excerpt` with its `source`. Then give the item the visual aid that fits it, as `content-format.md` describes under "Visual aids": a capture that exists, a chart of numbers that were stated, or a diagram of a path or a structure that was described.
- **A choice already made:** word `noChange` as keeping what was done, such as `Keep system fonts`, and give each real alternative as an option, saying in its `tradeoffs` what switching to it would cost now. Recommend as for any item: keeping what was done, switching, or `null` when you cannot say.
- **`id`:** the file's own id when it writes one as an id, such as `CR-001`; a numbered question or heading is not an id. Otherwise `D-01`, `D-02`, and so on, in the order the document presents them.
- **`startWith`:** the decisions that hold up other work, at most three.

Options, tradeoffs, and recommendations for a decision found in the conversation are mostly your own judgment. Label them as `content-format.md` requires.

## Showing the selection

The reader must be able to check what you chose to include. Put this in the document, because the closing message is not where they will be reading:

- **`document.sources`:** every file, and the conversation, that an item came from.
- **`document.sections`:** one titled `Where these decisions come from`, listing every place you looked, including the ones with nothing to decide; and one titled `Considered and left out`, with each candidate you dropped and the reason in a few words.

Give the same two lists, shortened, in the closing message, together with any open fact you could not settle and any file you set aside as belonging to other work.
