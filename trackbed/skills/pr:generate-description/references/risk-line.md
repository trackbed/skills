# Deterministic Risk Line

Use the committed range described by the Pull Request. For generation, use the pinned `DESCRIPTION_BASE` and `DESCRIPTION_HEAD` from the Phase 2 diff. In check mode, use `BASE_COMMIT` and `CURRENT_HEAD` from Phase C1 as those values. Local uncommitted work can inform the prose drift check, while the risk line uses the committed range.

Compute `MERGE_BASE` with `git merge-base "$DESCRIPTION_BASE" "$DESCRIPTION_HEAD"`, then run the helper with these OIDs:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/pr:generate-description/scripts/risk-line.py" \
  --merge-base "$MERGE_BASE" --head "$DESCRIPTION_HEAD"
```

It reads policy through `origin/HEAD`, falling back to `origin/main` or `origin/master` when the symbolic ref is absent. The Pull Request's base determines the diff range. The repository's default branch supplies the policy, including for stacked Pull Requests. Copy the floor and signal IDs verbatim, in the scanner's order. The line is `Risk: low (no signals)` when there are no signals, or for example `Risk: medium (signals: path:dependencies, shape:large)`. The review profile and model judgment play no part.

For check mode, save the captured Pull Request body as plain text in a temporary file and add `--check-body "$PR_BODY_FILE"` to the command. Pass the body as data, without interpolating it into shell code. Remove the file after the check. A zero exit with no output means either the existing line matches or the body has no risk line. A zero exit with a line means drift and gives the expected replacement.

If the merge base or assessment is unavailable, omit the generated line or skip the risk check. Surface the reason in the conversation output as `Risk assessment unavailable: <reason>` outside the body. This advisory never uses a `MISSING REQUIREMENT:` marker and never prevents publishing or checking the rest of the description.
