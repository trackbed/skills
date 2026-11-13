# pr:stack

Use it when a change should land as a chain of small Pull Requests that build on each other instead of one large one. It builds and maintains the chain with the `gh stack` extension: it creates the branches, pushes them, opens chained draft Pull Requests, rebases the whole stack and pushes the rewritten branches when it syncs, and merges it. For a single independent change, use `trackbed:pr:create`. To decide how to split a large branch first, use `trackbed:code:breakdown-findings --split`.

## Before you run it

- `gh` has the `gh-stack` extension, version 0.3.0 or newer. The skill offers to install or upgrade it.
- Stacked Pull Requests are enabled for the repository. Without them, the skill offers a manual chain of ordinary Pull Requests instead.

## Arguments

| Argument | Meaning |
| --- | --- |
| `init <branches...>` | Start a new stack on the base branch with these branches, bottom to top. |
| `submit` | Push every branch and open the chained Pull Requests as drafts, then write each title and body. |
| `sync` | Bring the stack up to date after the base moved or a Pull Request merged: fetch, rebase each branch onto the one below, and push. |
| `merge <pr-number>` | Merge that Pull Request and every unmerged one below it. Name the top Pull Request to land the whole stack. |
| `adopt <branches...>` | Turn existing branches, bottom to top, into a stack and open their Pull Requests. Pull Requests that already exist on GitHub, or branches that another tool manages, are linked into a stack instead. |
| `status` | Report the base, the branch order with each Pull Request's state, which branches need a rebase, and the suggested next step. |

Without a subcommand, the skill checks whether the current branch is in a stack and chooses from that and from what you ask for.

## Options

| Option | Effect |
| --- | --- |
| `--base <trunk>` | Build the stack on `<trunk>` instead of the repository's detected base branch. Only valid with `init` and `adopt`. See [Base Branch](../shipping.md#base-branch). |

## Examples

```text
# Start a stack with its first branch on the develop branch
/trackbed:pr:stack init --base develop auth-layer

# Push every branch and open the chained draft Pull Requests
/trackbed:pr:stack submit

# Turn three existing branches, bottom to top, into a stack
/trackbed:pr:stack adopt auth-layer api-endpoints frontend

# Land Pull Request 42 and every unmerged Pull Request below it
/trackbed:pr:stack merge 42
```

## What you get

- Branches and Pull Requests on GitHub, each Pull Request based on the branch below it and naming its position in the chain.
- After `sync`, every stack branch rebased and pushed, all together or not at all. The skill stops first when a branch has diverged from its remote, and asks before it changes a branch that is checked out in another Conductor workspace.
- After `merge`, either all the selected Pull Requests landed or none did; with a merge queue they are queued. The skill asks for the merge method when the repository allows more than one and you named none. Once they are all merged, it syncs the stack and deletes the local branches of the merged Pull Requests.

Review skills handle a stack one layer at a time; see [Stacked Pull Requests](../review.md#stacked-pull-requests).
