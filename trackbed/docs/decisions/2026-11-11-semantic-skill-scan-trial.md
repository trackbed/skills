# Trial a Report-Only LLM Skill Scan After Merge

- Status: PROPOSED
- Date: 2026-11-11
- Deciders: repository maintainer
- Decision review: two weeks after the scan is first enabled, and no later than 2026-12-16

## Context

Pull Requests run a static SkillSpector scan of changed skill directories, and high or critical findings block the merge. SkillSpector also has an LLM mode, which until now was a manual `make` target that nobody ran on a schedule. In that mode three analyzers read every file for intent the static rules cannot see (semantic prompt injection, a description that does not match the code, vague triggers), one call per skill that ships scripts compares the description with them, and a filter pass keeps a finding only when the model confirms it.

Measured on 2026-11-11 against the pinned SkillSpector commit, by building its real prompts without calling a model:

- A full-tree scan is about 1,650 model calls and 6 million input tokens across 103 directories and 526 files.
- From 2026-10-12 to 2026-11-10, 202 Pull Requests merged and 171 of them changed a skill or shared resource directory. Scanning once per merge is about 55 million input tokens and 14,700 calls a month.
- At GPT-6.1 Terra's list price of $1 per million input tokens and $5 per million output tokens, that is roughly $75 to $200 a month. The spread is the output per call, which was assumed (300 to 2,000 tokens, reasoning included) and not measured.

No model has published accuracy for this task, and no live run has happened yet.

## Decision

Run the LLM scan as a trial that reports and never blocks.

1. **Where it runs.** `.github/workflows/skill-security-semantic.yml` runs after a push to `main` that changes `trackbed/skills/` or `trackbed/shared/`, and scans the directories that push changed. A manual run scans the whole tree. Pull Request gates stay static and credential-free, as [sequential credit evals](2026-10-24-sequential-credit-evals.md) already requires for live model calls.
2. **Model and switch.** The repository variable `SKILLSPECTOR_SEMANTIC_MODEL` names the model, `gpt-6.1-terra` for the trial. The workflow does nothing while the variable is empty. The secret `SKILLSPECTOR_OPENAI_API_KEY` reaches the scan step only.
3. **What fails the run.** A scanner error, a report that did not use the model, or a failed model call. SkillSpector logs a failed call as a warning and still writes a clean-looking report, so the summary step reads the scan logs and fails the run. Findings never fail it.
4. **What the run reports.** The job summary pairs each LLM report with a static report of the same directory and lists the findings the model added and the static findings it dropped. JSON reports are kept for 90 days. Scan logs are not uploaded, because provider errors can name the account.
5. **What the model does not see.** `trackbed/config/skillspector-semantic-excludes.txt` lists files left out of the LLM scan only, starting with the vendored d3 bundle. The static scan still covers them.

Before the variable is set, scan about ten skills and three or four deliberately bad ones locally with GPT-6.1 Terra and GPT-6.1 Sol and compare the findings. Sol, at twice the price, is the fallback if Terra misses the planted issues. Watch the first enabled run by hand.

## Alternatives Considered

- **Scan every Pull Request push with the key.** Findings would arrive before merge. Rejected: the job would run the Pull Request's own scripts with the key in reach, it breaks the credential-free gate rule, and at 1.3 runs per Pull Request it scans about a third more.
- **Scan Pull Request content from trusted code** through `pull_request_target` or `workflow_run`. This keeps the key away from Pull Request code and still reports before merge. Deferred: that trigger is easy to get wrong, and the trial should first show the findings are worth having.
- **Block on LLM findings.** Rejected for now: in LLM mode a static finding survives only if the model confirms it, so the gate would stop being deterministic, and there is no accuracy evidence for any model.
- **A weekly full-tree scan.** About half the cost. Rejected for the trial because a finding would arrive up to a week late and would not point at the change that caused it.
- **SkillSpector's default models.** Claude Opus 4.6 and GPT-5.4 cost roughly five and three times as much as Terra on the same volume.

## Consequences

- Findings arrive after merge, in a run summary nobody is notified about. That is acceptable for a trial whose first question is whether the findings are worth reading.
- A failed run puts a red mark on a `main` commit. It is not a required check.
- The key is visible to SkillSpector and to its dependencies. SkillSpector is pinned by commit; its dependencies are not. Use a dedicated key with a budget.
- Tree-wide merges cost about $9 to $23 each on Terra. If credits run out, every run fails until the variable is cleared or credits return.
- The failure check matches SkillSpector's logger names. Rehearse it again when the pinned commit changes.
- The pinned release does not know GPT-6.1, so `trackbed/config/skillspector-model-registry.yaml` supplies the token limits. A model missing from that file fails the run with a clear problem line.

## Decision Review

After two weeks of enabled runs, download the reports and answer:

- How many findings did the model add, and how many were real?
- Which static findings did it drop, and were any of them real?
- How many runs failed, and why?
- What did the provider bill?

Then keep the scan as it is, change the model, surface findings where someone will see them, or remove it. Blocking merges on LLM findings needs its own decision record.
