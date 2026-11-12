# test:audit

Use it to find tests that cost more to maintain than they protect: low-value, brittle, obsolete, duplicated, or weak tests across a repository, a path, or the tests your branch changed. It is read-only: it changes no tests, code, snapshots, or configuration, and it writes no file. To check whether a Pull Request has enough tests, use `trackbed:pr:code-review`; to run the tests, use `trackbed:verify:run`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `full` | Audit the repository's whole test suite. This is the default. |
| `path <file-or-folder>` | Audit the tests at or below this path. When the path is production code, audit the tests that exercise it. |
| `changed` | Audit the tests your branch added or modified, including uncommitted ones. Finding the base branch contacts the Git remote and may refresh remote-tracking refs. |

## Options

| Option | Effect |
| --- | --- |
| `--base <ref>` | With `changed`, compare against `<ref>` instead of the detected base branch. |
| `--max-findings N` | Show at most N findings. The default is 20 and the usual ceiling is 50. Further findings are summarized as counts per verdict. |

## Examples

```text
# Audit the whole test suite
/trackbed:test:audit

# Audit the tests under one folder
/trackbed:test:audit path src/billing

# Audit the tests this branch changed, compared with develop
/trackbed:test:audit changed --base develop

# Audit everything and show the ten top-ranked findings
/trackbed:test:audit full --max-findings 10
```

## What you get

- A `Test Suite Audit` reply: the scope, the test frameworks, how many test files were reviewed, the number of findings per verdict, and the highest-value actions first.
- Findings numbered from `TA-001`. Each has a verdict (`REMOVE`, `REPAIR`, `CONSOLIDATE`, or `INVESTIGATE`), its location, the evidence, a recommendation, a command to verify the change later, and a confidence level.
- The leads it rejected after a closer look, and the areas it could not audit.
- No file and no changes. The reply ends by saying so.

The skill mostly reads. It runs an existing test command only when it can show that the command changes nothing. To act on a finding, ask for that change as a separate request.
