# Walkthrough Screenshots

Use this reference when `APPLY_MODE=true` and `VISUAL_REPORT=true`. It captures each change from the running app twice, before the edit and after it, so the walkthrough page can show the pair. `references/apply-findings.md` says when each pass runs.

`{url-detector}` is `${CLAUDE_PLUGIN_ROOT}/scripts/dev-server/detect-url.sh`, resolved by `SKILL.md`.

`{tree-fingerprint}` is `${CLAUDE_PLUGIN_ROOT}/scripts/review-tree-fingerprint.sh`, resolved by `SKILL.md`.

Capture is best effort and never blocks the fixes. A screen that cannot be captured safely is skipped with a one-line reason, and its change is shown as text.

## 1. Find the Running App

Use, in order:

1. `APP_URL`, when the user passed `--url`. It is used as given and its owner is not checked, so the after pass decides whether it shows this checkout: see **Reloading** below.
2. A local server from this checkout: `"{url-detector}" auto --check-owner`. Use it when it prints a single `http` or `https` URL. `__NO_RUNNING_SERVER__`, `__FOREIGN_SERVER__`, and `__UNCONFIRMED_OWNER__` all mean no app: a server from another checkout runs other code, so its after shots would not show this run's edits. With `__MULTIPLE_URLS__`, use the one URL that serves the files under review, or none.

Do not start, restart, build, or install anything, and never stop a process. With no app, record `Screenshots: skipped (no running app from this checkout)`, continue with the fixes, and show their before and after text. Tell the user to start the development server before applying any changes they want photographed.

## 2. Plan One Pair per Change

For each candidate finding, work out from the code:

- **Screen:** the route, page, or story that renders the flagged text, and the interaction that reaches it, such as opening a dialog or a menu.
- **Region:** the smallest part of the screen that shows the text together with what makes it redundant, such as the icon, the label, or the page title. A full page makes a one-word change invisible.
- **State:** the viewport (1280 by 800 unless the text only shows at another size), theme, locale, and data the shot depends on.

Findings that share a screen, region, and state share one pair. Choose one representative finding ID for both filenames before capture and use those paths for every finding in the group. Each caption names the other changes visible in the pair.

Skip a screen, with the reason, when:

- reaching it needs a sign-in the user has not provided, or a destructive or outward action such as delete, purchase, send, publish, or deploy;
- it would show credentials, tokens, customer or personal data, private messages, billing details, or a production admin page. Never plan to blur or crop these afterwards;
- nothing in the running app renders the text, as with a string behind a feature flag that is off.

Capture at most 20 pairs in one run, most severe first and then in report order. Show the remaining changes as text and say how many were not captured.

## 3. Prepare the Run Directory

Run from the repository root:

```bash
RUN_ID=$(date +%Y%m%d-%H%M%S)
SHOT_DIR=".trackbed/copy-review/$RUN_ID"
EXCLUDE_FILE=$(git rev-parse --git-path info/exclude) || exit 1
EXCLUDE_RULE='/.trackbed/copy-review/'
mkdir -p "$(dirname "$EXCLUDE_FILE")" || exit 1
grep -qxF "$EXCLUDE_RULE" "$EXCLUDE_FILE" 2> /dev/null \
  || printf '\n%s\n' "$EXCLUDE_RULE" >> "$EXCLUDE_FILE" || exit 1
git check-ignore -q -- "$SHOT_DIR/" || exit 1
mkdir -p "$SHOT_DIR" || exit 1
```

The directory sits under the project root so the page can load the images by relative path. If setup fails or Git reports the directory is eligible for staging, skip screenshots and record why. Directories from earlier runs stay until `/trackbed:workflow:cleanup-artifacts` removes them.

## 4. Capture

Use the browser tools the host offers, in this order: a browser MCP server (Chrome DevTools, Playwright, or Claude in Chrome), then headless Chrome from the command line for a screen that needs no interaction:

```bash
"<chrome-binary>" --headless=new --disable-gpu --hide-scrollbars --window-size=1280,800 --screenshot="<file>.png" "<url>"
```

- **Before pass,** before any file changes. Capture each planned comparison as `<SHOT_DIR>/<finding-id>-before.png`, such as `COPY-001-before.png`. Write down the URL, viewport, interaction steps, region, and findings for each pair.
- **After pass,** once verification is done. For each pair with a surviving change, repeat exactly the same URL, viewport, steps, and region as `<finding-id>-after.png`, using the original representative ID. Delete a before image when none of the findings that share it stayed.
- **Framing.** Crop to the region with an element screenshot when the tool supports it; otherwise keep the same full-viewport framing on both sides.
- **Reloading.** A development server reloads edited files itself. If a screen still shows the old text after one reload, record that side as not captured; do not wait, rebuild, or restart anything.

Look at every image before keeping it. Open it and confirm it shows the planned state: not a blank page, error page, sign-in screen, or loading spinner, and nothing from the skip list. A before shot shows the flagged text; an after shot shows it gone or shortened as recorded. Retake a bad shot once, then delete it and record that side as not captured.

A pair needs both sides. If an image fails the check for one finding, give that finding a text comparison. Keep both images if they form a valid pair for any surviving finding. Delete the remaining images when no surviving finding has a valid pair.

Run `"{tree-fingerprint}"` immediately before and after each capture pass, including its browser navigation. Compare the path and content records within that pass, before continuing to source edits or writing the report. Report each added, removed, or changed path as `CAPTURE SIDE EFFECT: <path>`, and revert nothing. If the helper fails or HEAD differs between snapshots, report that the side-effect check could not complete.

## 5. Record

For each change, fill the `Shown at` and `Screenshots` fields from `assets/applied-changes-format.md`: the relative paths of both images, or `none` followed by the reason. Fill the `Screenshots` line of `## Changes Applied` with the app URL, the viewport, and how many changes have a pair.

On the walkthrough page, a change with a pair shows both images in its comparison, and a change without one shows its `Before` and `After` text there instead, with the reason in the caption. Never draw, retouch, or mock up a side.
