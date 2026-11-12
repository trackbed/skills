# verify:run

Use it before you call work done, push, or open a Pull Request, to run the project's own checks on the code your changes affect: formatting, linting, type checking, the build, and tests. It finds the commands in the project's instruction files, its CI configuration, or its project type, and runs every check even when an earlier one fails. It only checks: it never fixes or reformats anything. To repair failing CI on an open Pull Request, use `trackbed:pr:fix-ci`.

## Before you run it

- The project names its checks in an instruction file such as `AGENTS.md` or `CLAUDE.md`, or in its CI configuration, or it is an Nx, .NET, Node.js, Python, Go, or Rust project. Otherwise the run stops with `No verification commands found`.
- `git`, `jq`, and the project's own toolchain are installed. A check whose tool is missing is reported as `SKIPPED`.

## Options

| Option | Effect |
| --- | --- |
| `--fast` | Run the quick tier for iterating: the project's documented fast loop, or else formatting, linting, type checking, and unit tests on the affected code. Cannot be combined with `--full`. |
| `--full` | Run the complete tier: the project's documented sweep for before a push or Pull Request, or else every check that applies. This is the default. |
| `--force` | Run the checks even when a passing run from this session already covers the same working tree, and look up the project's commands again instead of using the saved ones. |
| `--base <branch>` | Compare against `<branch>` instead of the detected base branch. |
| `--base-commit <oid>` | Pin the comparison to this exact commit, given as a full 40-character ID that already exists locally. Needs `--base`. |

## Examples

```text
# Run the full set of checks on the code your changes affect
/trackbed:verify:run

# Run the quick tier while you iterate
/trackbed:verify:run --fast

# Run the full tier and compare against the develop branch
/trackbed:verify:run --full --base develop

# Run the checks again although the same tree already passed in this session
/trackbed:verify:run --force
```

## What you get

- A result per check: `PASS`, `FAIL`, or `SKIPPED`. Failed checks quote their errors with file paths and line numbers.
- A `Verification Summary` with the tier, the ID of the working tree it covers, and the base it compared against.
- `REUSED` instead of a new run when a passing run from this session already covers the same working tree, base, and tier.
- A saved copy of the discovered commands under `.context/verify-run/`, when Git ignores that folder, so later runs start faster.

Integration and end-to-end suites can change databases or need running services, so the skill skips them when the environment is not prepared and asks you when in doubt. One optional check does touch your files: to prove that a regression test fails without its fix, the skill stashes the fix, restores it, and leaves the stash entry for you to remove. See [Verification](../shipping.md#verification).
