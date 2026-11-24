# Evidence Attachments

Use this reference for Step 4.6 and the evidence collection in Step 7.2 of `$trackbed:pr:create`. Screenshots and videos reach the Pull Request through `gh pr create --attach`, which uploads each file and replaces a matching `![alt](./path)` reference in the body with the uploaded image, or appends the file to the end of the body when nothing references it. Capture and upload failures never block Pull Request creation, with two exceptions: a file the user passed with `--attach` must be valid and attachable, and a capture side effect in the worktree can trip the clean-tree checks of the existing-remote modes.

`{evidence-helper}` is `${CODEX_HOME:-$HOME/.codex}/plugins/cache/trackbed/trackbed/1.2.1/scripts/pr-evidence.py`, resolved by `SKILL.md`. `{repo-root}` is the output of `git rev-parse --show-toplevel`. Parse every helper result as JSON; never `eval` or source it. Pass every user-supplied value to the shell in single quotes, writing each `'` inside it as `'\''`, so the shell expands nothing in it.

## Step 4.6: Stage Supplied Evidence

Run this after the preflight helper returns `ok` or a finished remote classification, and before Step 5 can commit anything.

1. Run `env GH_PROMPT_DISABLED=1 gh pr create --help` and look for the `--attach file` flag. Then run `env GH_PROMPT_DISABLED=1 gh repo view --json url --jq .url` and read the host. Set `ATTACHMENTS_SUPPORTED=true` only when both commands succeed, the flag is listed, and the host is `github.com`; GitHub Enterprise Server does not accept attachments.
2. When `ATTACHMENTS_SUPPORTED=false`: if `ATTACH_SPECS` is non-empty, stop with `This gh or GitHub host cannot attach files; upgrade gh, or rerun without --attach and add the files by hand.` Otherwise set `{evidence-status}` to `skipped (gh or the GitHub host cannot attach files)`, leave `EVIDENCE_MANIFEST` unset, and continue. The generator then captures without referencing files in the body, and the evidence collection below carries its run directory to the closing message for manual upload.
3. Otherwise open a run and keep its absolute `manifest` path as `EVIDENCE_MANIFEST`:

   ```bash
   python3 "{evidence-helper}" init --repo-root "{repo-root}"
   ```

   The helper adds `.trackbed/` to Git's local exclude file, so neither the run directory nor Step 5's include-all commit picks it up. A failure stops only when `ATTACH_SPECS` is non-empty; otherwise record the reason as `{evidence-status}` and continue without `EVIDENCE_MANIFEST`.

4. Stage each `ATTACH_SPECS` value, in order, as one single-quoted argument:

   ```bash
   python3 "{evidence-helper}" add --repo-root "{repo-root}" --manifest "{EVIDENCE_MANIFEST}" --spec '{attach-spec}' --source user
   ```

   The helper copies the file into the run, so later edits to the original do not change what is uploaded. It infers the role `before` or `after` from an alt text or file name that starts with that word. It rejects a missing file, a symlink, a type other than PNG, JPEG, GIF, WebP, MP4, MOV, or WebM, content that does not match the extension, an image over 10 MB or a video over 100 MB, more than 50 files, alt text with Markdown-breaking characters, and an untracked file inside the repository, which Step 5 would otherwise commit. The path ends at the first `#`, so a path containing `#` is rejected as missing. Any rejection is a hard blocker before Step 5: report the diagnostic and stop. Nothing has been mutated, so no rollback runs.

## Step 7.2 Evidence Collection

Collect the generator's `Screenshots:` line and any `CAPTURE SIDE EFFECT:` lines for the Step 8 preview and the closing message. Never put a marker or a manifest path in `{description}`.

When `EVIDENCE_MANIFEST` is unset, nothing will be uploaded. If the generator emitted a `PR_EVIDENCE_MANIFEST:` line, set `{evidence-status}` to `staged locally in <run directory>; drag the files into the Pull Request`, using the directory that holds that manifest, and set `EVIDENCE_COUNT=0`.

When `EVIDENCE_MANIFEST` is set, require the generator output to carry at most one `PR_EVIDENCE_MANIFEST:` line and, when present, require its path to equal `EVIDENCE_MANIFEST` exactly. Ignore a different or duplicated path: note it in `{evidence-status}`, keep using `EVIDENCE_MANIFEST`, whose entries the helper revalidates, and let Step 8.4 strip any body reference that is not a staged entry. Then read the final entries:

```bash
python3 "{evidence-helper}" show --repo-root "{repo-root}" --manifest "{EVIDENCE_MANIFEST}"
```

Set `EVIDENCE_COUNT` to the number of entries and `{evidence-status}` to `{N} files ({before and after | after only | other})`, or keep the skipped reason. A failing `show` with user-supplied files is a hard blocker under the Step 7 failure rules, because the user asked for those files; without them, record the diagnostic, set `EVIDENCE_COUNT=0`, and continue. Step 8.4 then strips any evidence reference from the body before creating the Pull Request without attachments.

When a clean-tree check in Step 8 later fails and the generator reported `CAPTURE SIDE EFFECT:` lines, name those paths as the likely cause in the blocker message.
