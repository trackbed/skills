# code:migrate

Use it to move a project to a new major version of a framework, library, or runtime, such as Angular 19 or Node 22. It reads the official migration guide, finds the affected code, writes a phased plan, and, if you choose, carries the plan out on a new branch, running the project's checks after each phase. It is experimental. For routine dependency updates, use `trackbed:deps:audit` instead.

## Before you run it

- The working tree is clean. Otherwise you are asked whether to stop, stash the changes, or continue with them mixed in.
- No `migration-plan-*.md` file in the project root and no `migrate/*` branch from an earlier run, unless you want to resume that migration or restart it. Restarting deletes the earlier plan and, after you confirm, its branch.

## Arguments

| Argument | Meaning |
| --- | --- |
| `<target>` | The framework, library, or runtime and the version to move to, such as `Angular 19`, `React 19`, or `Node 22`. Without it, you are asked. The current version is read from your project files. |

## Options

| Option | Effect |
| --- | --- |
| `--auto` | Carry out the whole plan without the plan review, the confirmation of new network endpoints, or the pause after each phase. Every other question, such as what to do about uncommitted changes or an earlier migration, stops the run instead, and so does a phase that still fails its checks after three fix attempts. |

## Examples

```text
# Plan the upgrade to Angular 19, then choose how to carry it out
/trackbed:code:migrate "Angular 19"

# Upgrade to Node 22 and run every phase without pausing
/trackbed:code:migrate "Node 22" --auto

# Run it again later to resume or restart a migration you began earlier
/trackbed:code:migrate "Angular 19"
```

## What you get

- `migration-plan-<slug>.md` in the project root, where the slug is the target in lowercase, such as `migration-plan-angular-19.md`. It lists the breaking changes that affect your code, seven phases from preparation to cleanup, and the official source behind each change.
- A choice once the plan is ready: run all phases, run them with a pause after each, keep the plan only, or get the `trackbed:siw:init` command that turns the phases into tracked issues. First you confirm each network endpoint a step would add.
- When phases run, a `migrate/<slug>` branch created from your base branch, with the code and configuration changes made on it. `trackbed:verify:run` runs after each phase.
- A completion report: each phase as done, skipped, or failed, the build, lint, and test results, the steps left for you, and every claim no official source supports. A step that depends on such a claim is not carried out.

Next, run `trackbed:verify:run` for full verification and `trackbed:pr:create` to open the Pull Request.
