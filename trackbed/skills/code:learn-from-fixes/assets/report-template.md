# Bug-Fix Retrospective

**Window:** {start} to {tip commit and date} on `{ref}`{, limited to `{path}`}

**Fixes:** {F fixes in N kept integrations, of M candidate integrations, with K set aside and U unread or partly read}

## Verdict

{Two to four sentences. Name the one or two decisions that would have removed the most fixes and how many of the window's fixes they cover. Say what the window does not explain. With one or two fixes, say the sample is too thin to rank decisions.}

## Bug Classes

{Repeat this section once per class. If no class formed, write `No bug class found in this window.`}

### {N}. {Class name: the enabling condition, stated as a property of the design}

**Fixes:** {count}{, `single fix` when there is one}

- `{hash}`{ and a short label when the commit holds several fixes} {subject} — {failure}; {mechanism in one line}; {cure | patch}

**From-scratch decision:** {link to the decision entry}

**Other lever:** {the strongest candidate from the lever not chosen, or why that lever offers nothing}

**Rating:** {Obviates | Reduces}

**Replay:**

- `{hash}`{ and the same short label used in Fixes} — {what stops the original mistake under this decision, or why it survives}

## Ranked Decisions

{Omit this section if no decisions were identified. Repeat once per decision, ordered by total distinct fixes prevented, then by lower cost. For one or two fixes, title this section Decisions and leave the entries unnumbered.}

### {N}. {Decision name}

**Change:** {the modules, data, or feature this from-scratch decision would change}

**Kind:** {Architecture decision | Feature adjustment}

**Classes:** {linked classes and total distinct fixes prevented out of all fixes in those classes}

**Overall rating:** {Obviates | Reduces}

**Cost:** {what the decision gives up or makes harder, the new kinds of bug it invites, and for a feature adjustment who loses what}

**Record:** {what decision records, instruction files, or rejected-proposal notes say about this decision and about why the current design was chosen, or `Nothing on record`}

**Today:** {Fixed in the window | Adopt now | Adopt for new code | Rewrite only | Already decided | Previously declined} — {where the condition still stands, the first step, the boundary, or the recorded reason}

## No Design Lesson

{Fixes that belong to no class, each with the reason. Omit this section when it is empty.}

- `{hash}`{ and a short label when the integration holds several fixes} {subject} — {why no structure would have prevented it}

## Next Steps

{One line per lesson worth acting on, most valuable first. Omit a lesson that needs no action.}

- {decision} → {one or more of: `/trackbed:docs:adr`, `/trackbed:code:encode-constraint`, `/trackbed:code:refactor-opportunities --for "<decision>"`, a decision from whoever owns the product}

## Coverage

- **History read:** `{ref}` at `{tip hash}`, {tip date}, {cached remote history or local history with no remote}{, with any shallow or missing history noted}
- **Candidates:** {how fixes were recognized: commit types, keywords, Pull Request labels}
- **Set aside:** {count, with the reason for each or for each group}
- **Unread or partly read:** {fixes not diagnosed, or diagnosed from part of their diff, and why, or `None`}
- **Limits:** {Pull Request or bug report text not read, areas outside `--path`, or `None material`}
