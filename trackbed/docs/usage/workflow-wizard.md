# workflow:wizard

Use it when a task reaches steps only a person can do: clicking through a third-party dashboard, creating credentials or CI secrets, provisioning infrastructure, or running a one-off migration or cutover. It writes an interactive Bash script that walks you through those steps one at a time. It writes that one script, only after you confirm the plan, and never runs it. It is not for steps the agent can complete itself or for ordinary shell automation.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[procedure description or target script path]` | The procedure the wizard should guide you through, or the path to write the script to. Without a path, a one-off wizard goes to `.context/wizard-<slug>.sh`, and a setup script you want to keep in the repository goes to `scripts/<slug>-setup.sh`. |

## Examples

```text
# Generate a wizard for a third-party setup
/trackbed:workflow:wizard set up the payment provider's webhook and store its signing secret

# Generate a wizard for a one-off migration
/trackbed:workflow:wizard move the production database to the new region

# Write the wizard to a path you choose
/trackbed:workflow:wizard scripts/staging-setup.sh
```

## What you get

- The planned stages first, for you to confirm or adjust: where each one sends you, which value it captures, whether that value is secret, where it is stored, and which steps cannot be undone.
- One executable script at the target path, checked with `bash -n` and, when it is installed, `shellcheck`.
- The exact command to run it.

When you run the script, it opens the URLs, tells you what to click or copy, takes secrets with hidden input, writes values to your local environment file, sets GitHub Actions secrets and variables through `gh` where the plan calls for it, and asks before any step that cannot be undone. Delete a one-off wizard after you have used it.
