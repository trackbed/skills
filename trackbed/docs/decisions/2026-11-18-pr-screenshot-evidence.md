# Attach Before and After Screenshots to Pull Requests

- Status: ACCEPTED
- Date: 2026-11-18
- Deciders: repository maintainers
- Supersedes: [2026-09-05-auto-pr-ui-evidence.md](2026-09-05-auto-pr-ui-evidence.md) (already deprecated)

## Context

Since 2026-10-08, `trackbed:pr:create` and `trackbed:pr:generate-description` have only added an empty `## Screenshots / Videos` heading for UI changes and reminded the author to fill it. Pull Requests reached review without images, and the plugin had no way to attach images the author had already taken. The earlier capture design delegated to `kramme:visual:demo-reel`, a separate skill with a manifest handoff and roughly 1,500 lines of skill text, scripts, and tests; it was removed with that skill.

GitHub CLI 2.102 supports `gh pr create --attach <file>#<alt>`. It uploads each file and replaces a matching `![alt](./path)` reference in the body with the uploaded image, or appends the file to the end of the body. If some uploads fail, it still creates the Pull Request and exits non-zero. `gh pr edit` and `gh pr comment` cannot attach files, so uploads happen only when the Pull Request is created.

Reviewers compare a before and after pair faster than a single image. Taking a "before" image at Pull Request time is hard: the branch already contains the change, and running the base version means a second checkout with its own dependencies, which Conductor's workspace rules also forbid.

## Decision

- `trackbed:pr:create` accepts `--attach <file[#alt]>`, repeatable, in the `gh` syntax. It validates and copies each file into an evidence run before anything is committed, and an invalid file stops the run. It also accepts `--no-capture`.
- `trackbed:pr:generate-description` tries to capture evidence for every UI-facing diff, in every mode except check mode. It captures the "after" state from an app served by the current checkout, never one the dev-server detector attributes to another checkout. When nothing is running, it makes one bounded attempt to start the app, only with an unchanged development command from the base commit, dependencies already installed, no install, migration, or credential step, no migration or ORM change in the diff, only local database and service hosts, a 60-second limit, and cleanup of only the process it started.
- "Before" images come only from safe sources: a file the user supplied, an image on the linked issue, a URL the user named for the old version, or an old state the current app can still show. The workflow never switches branches, stashes, or starts the base version. Without a safe source, it attaches the "after" image alone and describes the old state in one sentence.
- Video is the exception, for motion or multi-step interaction a still image cannot show. A video or animated GIF is uploaded only after the agent checks one extracted frame per second, so it needs `ffmpeg`.
- A pair is shown side by side in a table whose cells reference the staged files; `gh` swaps in the uploaded images. A standalone generator run, which cannot upload, keeps local paths out of the body and lists the files for the author to drag in.
- Automatic runs, including `trackbed:linear:issue-to-pr` and `trackbed:code:plan-to-pr`, attach without a preview. The agent checks each image for secrets, private data, and broken states before staging it, and skips when unsure.
- One plugin-level helper, `scripts/pr-evidence.py`, owns staging, validation, and body preparation for both skills. Evidence lives under `.trackbed/pr-evidence/`, which the helper adds to Git's local exclude file so no workflow commits it.
- A failed capture or upload never blocks a Pull Request. If uploads fail before creation, `trackbed:pr:create` retries once without attachments, using a body with the image references removed; it does not retry other failures. After any creation with attachments, it removes any local path `gh` left in the body.
- Only the canonical `![alt](./.trackbed/pr-evidence/...)` form survives into a published body; the helper strips every other form and drops any other line that names a file or run directory inside the evidence directory. A line that only mentions the directory, such as `.trackbed/pr-evidence/`, stays.

## Consequences

- Reviewers get screenshots for UI changes whenever a local app can show them safely, and authors can attach images they already took.
- Many UI Pull Requests get only an "after" image, because a safe "before" source often does not exist.
- Automatic runs spend time capturing, and capture can leave changes in the worktree, from a started or already running dev server or from browser tooling. The generator compares the worktree before and after capture, reports each change as `CAPTURE SIDE EFFECT:`, and reverts nothing. The clean-tree checks of the existing-remote modes then stop publication, and `trackbed:pr:create` names those paths as the likely cause.
- Attachment safety rests on the agent's check of each image; there is no human preview in auto mode.
- GitHub Enterprise Server and older `gh` versions cannot attach. Supplied files then stop the run with a clear message, and captures are left for manual upload with their directory named in the closing message.
- In a public repository, unattended runs do not use issue images or staging pages as "before" images, because they often show real customer data.

## Alternatives Considered

### Restore the capture child skill

Rejected because a separate model-invocable skill with its own manifest handoff carried most of the earlier complexity, and only the two Pull Request skills would use it.

### Run the base version for "before" images

Rejected by the maintainer because it needs a second checkout with installed dependencies, conflicts with Conductor's workspace rules, and makes automatic runs slower and less predictable.

### Capture "before" images during implementation

Deferred. `trackbed:linear:issue-implement` or `trackbed:code:work-from-plan` could save a "before" image before the first UI edit, which would make pairs common. It touches the implementation skills, so it needs its own change.

### Preview images before attaching in auto mode

Rejected because it would make automatic runs interactive, as the 2026-09-05 decision also concluded.
