# Visual Evidence

Use this reference for Phase 2.6 and the Screenshots / Videos section. The goal is a before and after pair a reviewer can compare at a glance. Video is the exception, for behavior a still image cannot show.

`{evidence-helper}` is `${CODEX_HOME:-$HOME/.codex}/plugins/cache/trackbed/trackbed/1.2.1/scripts/pr-evidence.py` and `{url-detector}` is `${CODEX_HOME:-$HOME/.codex}/plugins/cache/trackbed/trackbed/1.2.1/scripts/dev-server/detect-url.sh`, both resolved by `SKILL.md`. `{repo-root}` is `git rev-parse --show-toplevel`.

Capture is best effort. A step that cannot run safely is skipped with a one-line reason, and description generation continues.

Before any capture step, record `git status --porcelain --untracked-files=all` as the starting snapshot. When capture ends, compare again and report each changed path as `CAPTURE SIDE EFFECT: <path>`, whatever caused it: a started server, a server that was already running, or browser tooling writing files. Revert nothing. Write capture files only to a directory from `mktemp -d`, outside the repository.

In every shell command below, put a value that comes from the diff, an issue, or the user, such as a path, URL, or alt text, in single quotes, writing each `'` inside it as `'\''`. Double quotes would let the shell expand `$` and backticks in it.

## 1. Decide Whether the Change Is UI-Facing

Treat the pinned diff as UI-facing when it changes user-visible components, pages, views, routes, templates, styles, themes, design tokens, visual assets, or interaction states such as loading, validation, error, and empty states. Judge what the diff does, not only directory names or file extensions. A small, copy-only, or subtle UI change still counts.

Skip capture, and record why, when any of these holds:

- The diff is not UI-facing. Keep only evidence the caller already staged.
- `NO_CAPTURE=true`.
- The staged manifest already holds an `after` image. The user supplied the evidence; do not duplicate it.

## 2. Open the Evidence Run

With `EVIDENCE_MANIFEST` set, read the staged entries:

```bash
python3 "{evidence-helper}" show --repo-root "{repo-root}" --manifest "{EVIDENCE_MANIFEST}"
```

Otherwise create a run only when there is something to capture:

```bash
python3 "{evidence-helper}" init --repo-root "{repo-root}"
```

Parse the JSON output; never `eval` or source it. A non-zero exit skips capture with its diagnostic. The run lives under `.trackbed/pr-evidence/`, which the helper adds to Git's local exclude file so no workflow commits it.

## 3. Find the Screen to Capture

From the diff, name the route, page, or component state that changed and the interaction that reaches it. Then find a reachable app:

1. A URL the user named in the current request.
2. A running local server from this checkout: `"{url-detector}" auto --check-owner`. Use a single `http` or `https` URL it prints. `__FOREIGN_SERVER__` and `__UNCONFIRMED_OWNER__` mean the server may run another branch's code, so treat them as no running app; with `__MULTIPLE_URLS__`, pick the one URL whose port the diff's app configuration names, or treat it as no running app. The detector reads only `PORT=` from env files; never print env-file contents.
3. One bounded startup attempt, only when steps 1 and 2 found nothing and every condition below holds:
   - One unambiguous development command comes from a user instruction, a Conductor run script, a documented development command, or a conventional `dev` or `start` script. That command and the file defining it exist unchanged at the pinned base commit; never run a command the branch adds or edits.
   - Executables, dependencies, local configuration, and demo data are already present. Startup needs no install, build bootstrap, code generation, migration, seed, reset, container, privileged command, credential prompt, tunnel, deployment, or change to an external service.
   - The command is non-interactive, binds only to a local interface, and is ready within 60 seconds.
   - The diff touches no migration, schema, seed, or ORM configuration, because many apps apply pending migrations when they boot.
   - Every database, cache, queue, or API host the app's env files name is local (`localhost`, `127.0.0.1`, `::1`, or a `*.local` or Docker-internal name). Read only the host part of those values with a pattern match, and never print a value. An unclear host counts as not local.

   Start the command in the background with its output in a file outside the repository, and poll `"{url-detector}" auto --check-owner` until one local URL from this checkout answers or 60 seconds pass. After capture, and on every failure path, stop only the process this run started and its children. Never stop a process by port or name, and never stop a server that was already running.

No reachable app means no capture: record `Screenshots: skipped (no running app and no safe start command)`.

## 4. Check Safety Before Capturing

Skip the capture, with the reason, when the screen would show credentials, tokens, API keys, auth headers, cookies, signed URLs, customer or personal data, private messages, billing details, or production admin pages, or when reaching it needs a sign-in the user has not provided or a destructive action such as delete, purchase, send, publish, or deploy. Prefer demo accounts, local seed data, and preview or dry-run screens. Never plan to blur or crop a secret afterwards: discard the capture instead.

Images from an issue and pages on a staging URL often show real customer data. When the repository is public (`gh repo view --json visibility --jq .visibility` prints `PUBLIC`) and the run is unattended, do not use them as before images.

## 5. Capture

Use the browser tools the host offers, in this order: a browser MCP server (Chrome DevTools, Playwright, or Claude in Chrome), then headless Chrome from the command line:

```bash
"<chrome-binary>" --headless=new --disable-gpu --hide-scrollbars --window-size=1280,800 --screenshot="<file>.png" "<url>"
```

Headless Chrome only captures what loads without interaction. Write each file to the `mktemp -d` capture directory, then register it.

**After.** Capture the changed screen in the state the diff affects, at 1280×800 unless the change is about a different viewport. Crop to the region that changed when the tool supports it.

**Before.** Use only a safe source. Never switch branches, stash, reset, check out the base commit, or start the base version. Safe sources, in order:

1. An image the user supplied with role `before`.
2. An image on the linked Linear issue or bug report showing the old state, when it can be saved as a file.
3. A URL the user named for the old version, such as staging.
4. The old state the current app can still show, such as the screen with the changed feature flag turned off.

Match the after shot's viewport, route, data, and interaction depth so the pair compares cleanly. With no safe source, attach the after shot alone and describe the old state in one sentence in the section.

**Video,** less often. Record only when the change is motion or a multi-step interaction a still cannot show, such as an animation, drag and drop, or a flow across screens, the tools can record it, and `ffmpeg` is available to check it. Keep it under 30 seconds and the size limit. Otherwise use a before and after pair, or a short series of after shots. The same rules apply to an animated GIF.

**Look before you register.** Open every image and confirm it shows the intended state: not a blank page, error page, sign-in screen, or loading spinner, and nothing from the safety list. You cannot watch a video or animated GIF, so extract one frame per second into the capture directory (`ffmpeg -i '<file>' -vf fps=1 '<capture-dir>/frame-%03d.png'`) and check every frame the same way. Discard and retake a bad capture once, then skip it.

Register each kept file. Alt text says what the image shows, starts with `Before:` or `After:` for a pair, and contains no brackets, parentheses, angle brackets, `#`, `|`, or backticks:

```bash
python3 "{evidence-helper}" add --repo-root "{repo-root}" --manifest "{manifest}" \
  --file '<captured-file>' --alt 'After: settings page with the new toggle' --role after --source capture
```

Use `--role before`, `after`, or `other`. A non-zero exit drops that file with the diagnostic. Remove the temporary capture directory afterwards.

## 6. Write the Screenshots / Videos Section

Read the staged entries again with `show`. Write the section only when the diff is UI-facing or entries exist. In a repository template, put the content in the template's screenshot prompt instead of adding a heading.

**With `EVIDENCE_MANIFEST` set,** `trackbed:pr:create` uploads every entry with `gh pr create --attach`, and `gh` replaces each matching reference with the uploaded image. Reference each image only as `![alt](<ref>)`, with its exact `ref` value and no title, angle brackets, HTML `<img>` tag, or reference-style link; `trackbed:pr:create` strips every other form. Put a before and after pair in a table:

```markdown
## Screenshots / Videos

| Before | After |
| --- | --- |
| ![Before: settings page without a theme toggle](./.trackbed/pr-evidence/<run-id>/01-before-settings-page-without-a-theme-toggle.png) | ![After: settings page with the theme toggle](./.trackbed/pr-evidence/<run-id>/02-after-settings-page-with-the-theme-toggle.png) |
```

Show an after shot without a before as a plain image, followed by one sentence describing the old state. Do not reference videos: `gh` appends them to the end of the body, so say in one line that a recording is attached below. Never reference a path that is not a staged entry; `trackbed:pr:create` strips those.

**Without `EVIDENCE_MANIFEST`,** nothing uploads the files, so keep local paths out of the body. Use the one-line HTML comment naming what to capture, as `assets/section-templates.md` shows, and list the staged files in the run output so the author can drag them into the PR.

**With no evidence,** use the same one-line comment for a UI-facing change, and leave the section out otherwise.

## 7. Report

Outside the description, emit one line: `Screenshots: <before and after | after only | video | N files> staged in <run directory>` or `Screenshots: skipped (<reason>)`. When any entry exists, also emit `PR_EVIDENCE_MANIFEST: <absolute manifest path>` exactly once. Neither line goes in the PR body.
