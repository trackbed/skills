# hooks:toggle

Use it to switch one of this plugin's hooks off or back on, or to see which hooks are enabled. Reach for it when a hook fires where you do not want it. It changes only the hook state file. By default that file lives outside the installed plugin, so your choices survive plugin updates.

## Arguments

| Argument | Meaning |
| --- | --- |
| `status` | List every hook and whether it is enabled. |
| `reset` | Enable every hook again. |
| `<hook-name>` | The hook to change: `block-rm-rf`, `confirm-review-responses`, `skill-usage-stats`, `auto-format`, or `update-check`. With nothing after the name, the hook flips to the opposite state. |
| `[enable\|disable]` | After a hook name, turn that hook on or off instead of flipping it. |

## Examples

```text
# List every hook and whether it is enabled
/trackbed:hooks:toggle status

# Turn off automatic formatting after edits
/trackbed:hooks:toggle auto-format disable

# Flip a hook to the opposite state
/trackbed:hooks:toggle update-check

# Turn every hook back on
/trackbed:hooks:toggle reset
```

## What you get

- With `status`, a table of the hooks and their state.
- Otherwise, a confirmation of the change. It is saved in `~/.local/state/trackbed/hook-state.json` by default, under `$XDG_STATE_HOME` when that is set, or in the file `TRACKBED_HOOK_STATE_FILE` names.
- A warning and a confirmation question before the skill disables `block-rm-rf` or `confirm-review-responses`. These two are safety guardrails: the first blocks destructive file deletion, and the second asks before a commit includes review artifact files.

An unknown hook name stops the run with the list of valid names. The [hook reference](../hooks.md#toggling-hooks) describes what each hook does and where older installs keep their state.
