# Stages

Every workspace is on exactly one stage. The helper picks it from the first row that matches, top to bottom, and names the move. The `group` decides the sidebar section and where the workspace appears in the report.

| Stage `label` | Signal | Move | Section |
| --- | --- | --- | --- |
| Setup failed | Conductor could not create the workspace | Report the reason | Needs me |
| Starting | Conductor is still setting it up | None | Working |
| Folder unreadable | Its folder or its Git state could not be read | Report | Needs me |
| Agent working | A chat is running | None | Working |
| Agent needs you | A chat waits on a dialog or a permission prompt | Report; never answered | Needs me |
| Chat stopped on an error | A chat ended in an error | Report | Needs me |
| Merged | Its repository, branch, and checked-out head match a merged Pull Request | Archive after a fresh clean and idle check | Merged |
| Pull Request closed | Its Pull Request was closed without merging | Report | Needs me |
| Branch behind a past PR | No open Pull Request, and a merged or closed Pull Request on its branch has a head the checkout does not contain | Report; no command, so the work is not opened twice | Needs me |
| Idle with uncommitted changes | No Pull Request, and files changed but not committed | Report; no command | Needs me |
| Nothing to ship | No Pull Request and no commit beyond the default branch | None; its chat's last message is still read, so a question asked before any commit is reported | Left where it is |
| Work done, no PR | Commits beyond the default branch, a clean checkout, and no Pull Request | Send `trackbed:pr:create` | Needs a nudge |
| Checkout differs from the PR | Its checkout is not at the Pull Request's head | Report; no command | Needs me |
| PR not in shape | A conflict, a branch behind its base that must be up to date, a failing required check, stale checks, or an open thread from an AI reviewer | Send `trackbed:pr:shape-up` | Needs a nudge |
| Human review open | An unresolved thread with feedback from a person | Report; never answered | Needs me |
| Checks running | Required checks are pending, or GitHub is still working out mergeability | None | Working |
| Draft PR, Stacked PR, No checks, Review threads unresolved, Review required, Blocked by branch protection | The Pull Request cannot pass the gate, and no command would change that | Report | Needs me |
| Uncommitted changes beside a ready PR | The Pull Request passes every other check, but the checkout has uncommitted changes | Report | Needs me |
| Held | It passes the gate and matches a hold rule | Report with its holds | Needs me |
| Merge-ready | It passes the gate and matches no hold rule | Join the merge train | Merge-ready |

A planned command does not go out in three cases:

- **The chat has not been idle long enough.** The stage stays, and the move is `wait` with the minutes left. This keeps a command from landing between two turns of a chat, or on a workspace the user is working in.
- **The same command was delivered twice for the same problem.** The stage becomes "Nudged twice, still stuck". The count is kept while the chat runs, waits on a prompt, stops on an error, or cannot be read, and while checks run. It starts over once the workspace reaches a stage that shows the problem changed.
- **The chat cannot run the command.** A workspace with no chat is "No chat", and one whose chat runs an agent other than Claude Code or Codex is "Agent cannot run trackbed skills".

"PR could not be read" comes before every row above. It means GitHub did not answer for the workspace's Pull Request or its branch's past Pull Requests, or the Pull Request's head is in another repository: nothing is sent and nothing merges for it in this pass.

An open Pull Request of yours with no live workspace is listed under `orphans`. It can pass the merge gate and join the train, but nothing can be sent for it, so one that is not ready is only reported as "PR with no workspace, not ready".
